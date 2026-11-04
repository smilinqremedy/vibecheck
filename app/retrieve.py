"""Deterministic text retrieval for VibeCheck AI.

Selects top-k relevant reviews using token overlap and keyword relevance.
Operates entirely in Python with zero external vector database dependencies.
"""

from __future__ import annotations

import re
from typing import List, Set

from app.models import Review

# Standard small stop words list to emphasize substantive query keywords
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "did", "do", "does", "doing", "down", "during", "each", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


def tokenize(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens from text."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.casefold())
    return [t for t in tokens if len(t) >= 2 and t not in STOP_WORDS]


def score_review_relevance(query_tokens: List[str], review: Review) -> float:
    """Calculate deterministic token overlap score between query and review text/event."""
    if not query_tokens:
        return 0.0

    review_text_tokens = tokenize(review.text)
    event_tokens = tokenize(review.event)
    combined_tokens = review_text_tokens + event_tokens
    token_set = set(combined_tokens)

    # Count matching query terms
    matches = sum(1 for q in query_tokens if q in token_set)
    if matches == 0:
        return 0.0

    # Score: token matches with slight bonus for phrase frequency
    term_frequency = sum(combined_tokens.count(q) for q in query_tokens)
    return matches * 10.0 + term_frequency


def retrieve_relevant_reviews(
    query: str,
    reviews: List[Review],
    top_k: int = 5,
) -> List[Review]:
    """Retrieve up to top_k reviews ranked deterministically by query token overlap."""
    query_tokens = tokenize(query)
    if not query_tokens or not reviews:
        return []

    scored_reviews = []
    for rev in reviews:
        score = score_review_relevance(query_tokens, rev)
        if score > 0.0:
            scored_reviews.append((score, rev))

    # Sort descending by score, tie-breaking by review ID for reproducibility
    scored_reviews.sort(key=lambda item: (item[0], item[1].id), reverse=True)

    return [rev for _, rev in scored_reviews[:top_k]]
