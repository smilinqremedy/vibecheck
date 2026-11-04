# VibeCheck AI — Product & Engineering Requirements

## 1. Executive Summary
**VibeCheck AI (Festival Feedback Detective)** is an evidence-grounded AI review intelligence terminal CLI built using the Python standard library. It imports chaotic synthetic attendee reviews, classifies them using a language model adhering to strict schema contracts, validates model outputs defensively in Python, computes reproducible statistical summaries, and answers questions using strictly retrieved evidence without hallucinations or speculation.

---

## 2. System Scope & Boundaries
- **Runtime Environment**: Python 3.10+ (Built and verified on Python 3.12).
- **Library Constraints**: Python Standard Library only (`json`, `csv`, `pathlib`, `os`, `re`, `collections`, `datetime`, `urllib.request`, `unittest`, `unittest.mock`, `hashlib`).
- **No External Heavy Frameworks**: Zero dependencies on FastAPI, Django, LangChain, LlamaIndex, ChromaDB, or Pinecone.
- **Network Boundaries**: Outbound HTTPS POST requests to configured AI providers via `urllib.request` with bounded exponential backoff retries and timeout controls.
- **Privacy & Security**: Zero transmission or storage of Personally Identifiable Information (PII). No credentials or secrets logged or committed.

---

## 3. Data Contracts

### 3.1 Input Review Dataset Contract
Synthetic festival feedback records in CSV or JSON format.
- `id`: Unique alphanumeric identifier (e.g. `R001`). Rejects duplicate records.
- `event`: Non-empty string representing festival name (e.g. `Pulse Music & Food Fest`).
- `text`: Feedback text string, minimum 5 characters, maximum 500 characters.
- `created_at`: Valid date string strictly matching format `YYYY-MM-DD`.

### 3.2 AI Classification Output Schema (Strict JSON Contract)
```json
{
  "review_id": "R001",
  "sentiment": "positive",
  "topics": ["sound"],
  "evidence_quote": "The headline DJ set was absolutely sensational",
  "short_reason": "Praises the headline musical performance."
}
```
Validation Rules:
1. `review_id`: String matching input review ID exactly.
2. `sentiment`: Must be one of `["positive", "negative", "neutral", "mixed"]`. No binary forcing; mixed feedback must be labeled `"mixed"`.
3. `topics`: List of 0 to 3 unique items from allowed enum: `["sound", "food", "queue", "staff", "pricing", "safety", "venue", "other"]`.
4. `evidence_quote`: Non-empty string present verbatim as a substring inside the source review text.
5. `short_reason`: String with length `<= 160` characters.

If any validation check fails, the result is marked `status: "analysis_failed"`; the system never guesses or assigns a false sentiment.

### 3.3 Evidence-Grounded Q&A Contract
```json
{
  "answer": "Attendees noted sound bleed between Stages A and B [R004].",
  "cited_review_ids": ["R004"]
}
```
Validation Rules:
1. The AI model receives ONLY the deterministically retrieved top-k reviews (up to 5).
2. Every ID in `cited_review_ids` MUST exist in the retrieved subset.
3. If evidence does not support the question, the system abstains with: `"Insufficient evidence in the supplied reviews."`
4. Citing unprovided IDs is flagged as a citation grounding violation.

---

## 4. Functional Capabilities
- **F-01: Safe Ingestion**: Loads CSV/JSON, handles UTF-8, rejects duplicates, invalid dates, and out-of-bound text without modifying existing application state on error.
- **F-02: Review Listing**: Interactive tabular display of loaded reviews with date, event, text snippet, and current analysis status (`PENDING`, `VERIFIED`, `FAILED`).
- **F-03: Provider Adapter**: Pure Python HTTPS POST client connecting to OpenAI-compatible endpoints with configurable timeouts (20s) and bounded retries (max 2) on HTTP 429/5xx.
- **F-04: Batch Analysis & Cache**: Classifies pending reviews, saves verified outputs to a SHA256 content-hash keyed local cache, skips unchanged records, and invalidates entries when review text changes.
- **F-05: Deterministic Insights**: Python-calculated sentiment distribution, percentages, topic frequencies, complaint themes, and coverage metrics.
- **F-06: Grounded Q&A**: Token-overlap retrieval engine and citation validator ensuring queries are answered solely from festival evidence.
- **F-07: Traceable Export**: Exports comprehensive reports in both structured JSON and formatted ASCII TXT with explicit AI vs. Python provenance disclosure.
- **F-08: Engineering Self-Check**: Interactive 10-question audit evaluating data boundaries, schema enforcement, rate limits, and evaluation rigor.

---

## 5. Non-Functional & Reliability Requirements
- **Deterministic Statistics**: All totals, counts, and percentages are computed strictly in Python standard library.
- **Fault Tolerance**: Network outages, rate limits, or malformed LLM responses never crash the CLI.
- **Zero-Secret Leakage**: Bearer tokens are redacted (`sk-...1234`) in logs and UI.
