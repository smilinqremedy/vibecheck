"""Local hash-based caching and persistence for VibeCheck AI.

Caches verified AI classifications keyed by review ID, source text hash (SHA256),
model identifier, and prompt/schema version. Automatically invalidates results
if the source review text is modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.models import ClassificationResult, Review


def make_cache_key(review_id: str, source_hash: str, model_id: str, prompt_version: str) -> str:
    """Construct composite cache key."""
    return f"{review_id}:{source_hash}:{model_id}:{prompt_version}"


class ClassificationCache:
    """Local cache manager for classification outputs."""

    def __init__(self, cache_file_path: Path | str) -> None:
        self.cache_path = Path(cache_file_path)
        # Internal storage: key -> serialized dict
        self._entries: Dict[str, dict] = {}
        # Index: review_id -> latest key
        self._review_index: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        """Load cache from disk. Fails gracefully if file is missing or corrupted."""
        if not self.cache_path.is_file():
            self._entries = {}
            self._review_index = {}
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._entries = data.get("entries", {})
                    self._review_index = data.get("review_index", {})
        except Exception:
            # If cache file is corrupted, reset safely
            self._entries = {}
            self._review_index = {}

    def save(self) -> None:
        """Persist cache to disk atomically."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": self._entries,
            "review_index": self._review_index,
        }
        temp_path = self.cache_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            temp_path.replace(self.cache_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def get_valid(
        self,
        review_id: str,
        source_hash: str,
        model_id: str,
        prompt_version: str,
    ) -> Optional[ClassificationResult]:
        """Retrieve cached result ONLY if source hash, model, and prompt version match and status is verified."""
        key = make_cache_key(review_id, source_hash, model_id, prompt_version)
        entry = self._entries.get(key)
        if not entry:
            return None

        # Verify status is verified
        if entry.get("status") != "verified":
            return None

        # Verify source hash strictly matches
        if entry.get("source_hash") != source_hash:
            return None

        return ClassificationResult.from_dict(entry)

    def put(self, result: ClassificationResult) -> None:
        """Store classification result."""
        key = make_cache_key(
            result.review_id,
            result.source_hash,
            result.model_id,
            result.prompt_schema_version,
        )
        self._entries[key] = result.to_dict()
        self._review_index[result.review_id] = key
        self.save()

    def get_latest_for_review(self, review: Review) -> Optional[ClassificationResult]:
        """Get the latest result for a review, checking if it is still valid or stale."""
        key = self._review_index.get(review.id)
        if not key or key not in self._entries:
            return None
        entry = self._entries[key]
        # If source hash has changed, it is stale!
        if entry.get("source_hash") != review.source_hash:
            return None
        return ClassificationResult.from_dict(entry)

    def is_stale_or_missing(
        self,
        review: Review,
        model_id: str,
        prompt_version: str,
    ) -> bool:
        """Return True if review has no verified cached entry matching current text hash and config."""
        res = self.get_valid(review.id, review.source_hash, model_id, prompt_version)
        return res is None

    def all_cached_results(self) -> List[ClassificationResult]:
        """Return all stored classification results."""
        results: List[ClassificationResult] = []
        for raw in self._entries.values():
            results.append(ClassificationResult.from_dict(raw))
        return results

    def clear(self) -> None:
        """Purge all cached entries."""
        self._entries.clear()
        self._review_index.clear()
        self.save()
