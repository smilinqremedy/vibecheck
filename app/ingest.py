"""Data ingestion, validation, and sanitization for VibeCheck AI.

Safely parses reviews from CSV and JSON files, validates schemas, enforces
field constraints, rejects duplicates, and protects against malformed inputs.
"""

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models import Review


class ImportValidationError(Exception):
    """Raised when an import file cannot be read or parsed safely."""


class IngestResult:
    """Represents the outcome of importing review records."""

    def __init__(self) -> None:
        self.accepted: List[Review] = []
        self.rejected: List[Tuple[Dict[str, Any], str]] = []

    @property
    def total_read(self) -> int:
        return len(self.accepted) + len(self.rejected)

    @property
    def num_accepted(self) -> int:
        return len(self.accepted)

    @property
    def num_rejected(self) -> int:
        return len(self.rejected)


def validate_review_record(
    raw: Dict[str, Any],
    seen_ids: Set[str],
) -> Tuple[Optional[Review], Optional[str]]:
    """Validate a single raw record dict against the review contract.

    Returns:
        (Review, None) if valid.
        (None, reason_for_rejection) if invalid.
    """
    # 1. Check required fields
    for field in ("id", "event", "text", "created_at"):
        if field not in raw or raw[field] is None:
            return None, f"Missing required field: '{field}'"

    review_id = str(raw["id"]).strip()
    event = str(raw["event"]).strip()
    text = str(raw["text"]).strip()
    created_at = str(raw["created_at"]).strip()

    # 2. Check review ID
    if not review_id:
        return None, "Review ID cannot be empty"
    if review_id in seen_ids:
        return None, f"Duplicate review ID: '{review_id}'"

    # 3. Check event name
    if not event:
        return None, "Event name cannot be empty"

    # 4. Check text length constraint (5 to 500 characters)
    if len(text) < 5:
        return None, f"Review text too short ({len(text)} chars; minimum is 5 chars)"
    if len(text) > 500:
        return None, f"Review text too long ({len(text)} chars; maximum is 500 chars)"

    # 5. Check created_at date format YYYY-MM-DD
    try:
        parsed_date = datetime.datetime.strptime(created_at, "%Y-%m-%d")
        # Ensure year is 4 digits and matches parsed value
        if parsed_date.strftime("%Y-%m-%d") != created_at:
            return None, f"Invalid date format: '{created_at}', expected YYYY-MM-DD"
    except ValueError:
        return None, f"Invalid date format: '{created_at}', expected YYYY-MM-DD"

    review = Review(
        id=review_id,
        event=event,
        text=text,
        created_at=created_at,
    )
    return review, None


def import_reviews(
    file_path: Path | str,
    existing_reviews: Optional[List[Review]] = None,
) -> IngestResult:
    """Import and validate reviews from CSV or JSON file.

    Guarantees state protection: If file reading fails or file is corrupted,
    raises ImportValidationError without modifying existing_reviews.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ImportValidationError(f"File not found: {path}")

    # Read raw bytes to test UTF-8 decoding defensively
    try:
        raw_bytes = path.read_bytes()
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportValidationError(f"File encoding error: {exc}. Reviews must be valid UTF-8.") from exc
    except Exception as exc:
        raise ImportValidationError(f"Could not read file: {exc}") from exc

    raw_records: List[Dict[str, Any]] = []
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ImportValidationError("JSON root must be a list of review objects.")
            raw_records = parsed
        except json.JSONDecodeError as exc:
            raise ImportValidationError(f"Malformed JSON file: {exc}") from exc
    elif suffix == ".csv":
        try:
            reader = csv.DictReader(content.splitlines())
            raw_records = list(reader)
        except Exception as exc:
            raise ImportValidationError(f"Malformed CSV file: {exc}") from exc
    else:
        raise ImportValidationError(f"Unsupported file format '{suffix}'. Supported formats: .csv, .json")

    result = IngestResult()
    seen_ids: Set[str] = set()

    # If existing reviews were passed, register their IDs to reject duplicates
    if existing_reviews:
        for rev in existing_reviews:
            seen_ids.add(rev.id)

    for item in raw_records:
        if not isinstance(item, dict):
            result.rejected.append(({"raw": item}, "Record is not a JSON/CSV object"))
            continue

        review, error = validate_review_record(item, seen_ids)
        if review is not None:
            seen_ids.add(review.id)
            result.accepted.append(review)
        else:
            result.rejected.append((item, error or "Unknown validation error"))

    return result
