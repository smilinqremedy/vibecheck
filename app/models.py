"""Data models for VibeCheck AI.

Defines schemas and immutable data structures for reviews, classifications,
reports, and grounded Q&A responses using Python standard library.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Dict, List, Optional


ALLOWED_SENTIMENTS = {"positive", "negative", "neutral", "mixed"}
ALLOWED_TOPICS = {
    "sound",
    "food",
    "queue",
    "staff",
    "pricing",
    "safety",
    "venue",
    "other",
}
MAX_TOPICS = 3
MAX_SHORT_REASON_LEN = 160


def compute_source_hash(text: str) -> str:
    """Compute deterministic SHA256 hex digest of review text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class Review:
    """Represents a validated festival review record."""

    id: str
    event: str
    text: str
    created_at: str  # YYYY-MM-DD format

    @property
    def source_hash(self) -> str:
        return compute_source_hash(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "text": self.text,
            "created_at": self.created_at,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Review:
        return cls(
            id=str(data["id"]).strip(),
            event=str(data["event"]).strip(),
            text=str(data["text"]).strip(),
            created_at=str(data["created_at"]).strip(),
        )


@dataclasses.dataclass(frozen=True)
class ClassificationResult:
    """Represents an AI classification result, either verified or marked failed."""

    review_id: str
    sentiment: Optional[str]
    topics: List[str]
    evidence_quote: str
    short_reason: str
    status: str  # 'verified' or 'analysis_failed'
    error_message: Optional[str] = None
    model_id: str = "unknown"
    provider: str = "unknown"
    prompt_schema_version: str = "v1.0.0"
    analyzed_at: str = ""
    source_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "sentiment": self.sentiment,
            "topics": list(self.topics),
            "evidence_quote": self.evidence_quote,
            "short_reason": self.short_reason,
            "status": self.status,
            "error_message": self.error_message,
            "model_id": self.model_id,
            "provider": self.provider,
            "prompt_schema_version": self.prompt_schema_version,
            "analyzed_at": self.analyzed_at,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClassificationResult:
        return cls(
            review_id=str(data.get("review_id", "")),
            sentiment=data.get("sentiment"),
            topics=list(data.get("topics", [])),
            evidence_quote=str(data.get("evidence_quote", "")),
            short_reason=str(data.get("short_reason", "")),
            status=str(data.get("status", "analysis_failed")),
            error_message=data.get("error_message"),
            model_id=str(data.get("model_id", "unknown")),
            provider=str(data.get("provider", "unknown")),
            prompt_schema_version=str(data.get("prompt_schema_version", "v1.0.0")),
            analyzed_at=str(data.get("analyzed_at", "")),
            source_hash=str(data.get("source_hash", "")),
        )


@dataclasses.dataclass
class ReportSummary:
    """Summary statistics computed purely in Python from verified classifications."""

    total_reviews: int
    analyzed_reviews: int
    failed_reviews: int
    unanalyzed_reviews: int
    coverage_percentage: float
    sentiment_distribution: Dict[str, int]
    sentiment_percentages: Dict[str, float]
    topic_frequencies: Dict[str, int]
    mixed_count: int
    top_complaint_themes: List[tuple[str, int]]
    cited_examples: Dict[str, List[str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_reviews": self.total_reviews,
            "analyzed_reviews": self.analyzed_reviews,
            "failed_reviews": self.failed_reviews,
            "unanalyzed_reviews": self.unanalyzed_reviews,
            "coverage_percentage": round(self.coverage_percentage, 2),
            "sentiment_distribution": self.sentiment_distribution,
            "sentiment_percentages": {k: round(v, 2) for k, v in self.sentiment_percentages.items()},
            "topic_frequencies": self.topic_frequencies,
            "mixed_count": self.mixed_count,
            "top_complaint_themes": [list(item) for item in self.top_complaint_themes],
            "cited_examples": self.cited_examples,
        }


@dataclasses.dataclass(frozen=True)
class QAResponse:
    """Structured response for grounded question answering."""

    question: str
    answer: str
    cited_review_ids: List[str]
    status: str  # 'grounded', 'insufficient_evidence', 'error'
    retrieved_review_ids: List[str]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "cited_review_ids": list(self.cited_review_ids),
            "status": self.status,
            "retrieved_review_ids": list(self.retrieved_review_ids),
            "error_message": self.error_message,
        }
