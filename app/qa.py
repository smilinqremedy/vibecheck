"""Evidence-grounded Question Answering for VibeCheck AI.

Passes only deterministically retrieved reviews to the AI model and strictly
validates citations and claims against the supplied evidence context.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Set

from app.classify import clean_json_text
from app.models import QAResponse, Review
from app.provider import BaseProviderClient, ProviderError
from app.retrieve import retrieve_relevant_reviews

QA_SYSTEM_PROMPT = """You are VibeCheck AI's Evidence-Grounded Festival Q&A Assistant.
Your task is to answer the user's question relying EXCLUSIVELY on the review excerpts provided in CONTEXT.

STRICT RULES:
1. Rely ONLY on the facts directly stated in the CONTEXT reviews below.
2. Do NOT extrapolate, speculate, or introduce external knowledge (e.g. ticket sales, festival causes, overall satisfaction).
3. If the CONTEXT does not contain sufficient direct evidence to answer the question, you MUST return:
   "Insufficient evidence in the supplied reviews."
4. Every factual statement in your answer must cite the supporting review ID in bracket format, e.g. [R001].
5. You MUST return ONLY a valid JSON object matching the schema below. No Markdown code fences, no extra text.

JSON OUTPUT SCHEMA:
{
  "answer": "<grounded answer with [Rxxx] citations, or 'Insufficient evidence in the supplied reviews.'>",
  "cited_review_ids": ["<list of review IDs cited in your answer>"]
}
"""


def build_qa_prompt(question: str, retrieved_reviews: List[Review]) -> List[Dict[str, str]]:
    """Construct grounded Q&A prompt with explicit review evidence context."""
    context_lines = []
    for r in retrieved_reviews:
        context_lines.append(f"[{r.id}] (Event: {r.event}): \"{r.text}\"")

    context_str = "\n".join(context_lines)

    user_content = f"""QUESTION:
{question}

CONTEXT REVIEWS (ONLY EVIDENCE ALLOWED):
{context_str}

Respond with the required JSON object now:"""

    return [
        {"role": "system", "content": QA_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def answer_grounded_question(
    question: str,
    all_reviews: List[Review],
    provider: BaseProviderClient,
    top_k: int = 5,
) -> QAResponse:
    """Execute evidence retrieval, prompt generation, model invocation, and grounding verification."""
    clean_question = question.strip()
    if not clean_question:
        return QAResponse(
            question=question,
            answer="Question cannot be empty.",
            cited_review_ids=[],
            status="error",
            retrieved_review_ids=[],
            error_message="Empty question provided.",
        )

    # 1. Deterministic retrieval
    retrieved = retrieve_relevant_reviews(clean_question, all_reviews, top_k=top_k)
    retrieved_ids: List[str] = [r.id for r in retrieved]
    retrieved_id_set: Set[str] = set(retrieved_ids)

    # If no evidence was retrieved, abstain immediately without calling LLM
    if not retrieved:
        return QAResponse(
            question=clean_question,
            answer="Insufficient evidence in the supplied reviews.",
            cited_review_ids=[],
            status="insufficient_evidence",
            retrieved_review_ids=[],
            error_message=None,
        )

    # 2. Invoke provider
    messages = build_qa_prompt(clean_question, retrieved)
    try:
        raw_output = provider.call_model(messages, temperature=0.0)
    except ProviderError as exc:
        return QAResponse(
            question=clean_question,
            answer="Unable to answer due to provider error.",
            cited_review_ids=[],
            status="error",
            retrieved_review_ids=retrieved_ids,
            error_message=f"Provider error: {exc}",
        )

    # 3. Parse JSON defensively
    cleaned = clean_json_text(raw_output)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return QAResponse(
            question=clean_question,
            answer="Model returned invalid JSON format.",
            cited_review_ids=[],
            status="error",
            retrieved_review_ids=retrieved_ids,
            error_message=f"JSON decode error: {exc}. Raw: {raw_output[:100]}",
        )

    if not isinstance(data, dict):
        return QAResponse(
            question=clean_question,
            answer="Model output is not a JSON object.",
            cited_review_ids=[],
            status="error",
            retrieved_review_ids=retrieved_ids,
            error_message="Root JSON structure is not an object",
        )

    answer = str(data.get("answer", "")).strip()
    cited_ids_raw = data.get("cited_review_ids", [])

    if not isinstance(cited_ids_raw, list):
        return QAResponse(
            question=clean_question,
            answer="Model returned invalid 'cited_review_ids' field type.",
            cited_review_ids=[],
            status="error",
            retrieved_review_ids=retrieved_ids,
            error_message="'cited_review_ids' must be a JSON array",
        )

    cited_ids = [str(cid).strip() for cid in cited_ids_raw]

    # 4. Strict Citation Grounding Check
    # Every cited ID must be present in retrieved_ids!
    hallucinated_ids = [cid for cid in cited_ids if cid not in retrieved_id_set]
    if hallucinated_ids:
        return QAResponse(
            question=clean_question,
            answer="Model cited review IDs that were not provided in the evidence context.",
            cited_review_ids=cited_ids,
            status="error",
            retrieved_review_ids=retrieved_ids,
            error_message=f"Citation grounding violation: cited unknown or unprovided IDs: {hallucinated_ids}",
        )

    # 5. Check for abstention
    if "insufficient evidence" in answer.casefold() or not cited_ids:
        return QAResponse(
            question=clean_question,
            answer="Insufficient evidence in the supplied reviews.",
            cited_review_ids=[],
            status="insufficient_evidence",
            retrieved_review_ids=retrieved_ids,
            error_message=None,
        )

    return QAResponse(
        question=clean_question,
        answer=answer,
        cited_review_ids=cited_ids,
        status="grounded",
        retrieved_review_ids=retrieved_ids,
        error_message=None,
    )
