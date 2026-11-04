"""Deterministic statistics and report generation for VibeCheck AI.

Computes exact frequency distributions, percentages, coverage metrics, and
theme summaries strictly in Python. The LLM is never asked to calculate totals.
"""

from __future__ import annotations

import collections
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.models import (
    ALLOWED_SENTIMENTS,
    ALLOWED_TOPICS,
    ClassificationResult,
    ReportSummary,
    Review,
)


def generate_report_summary(
    reviews: List[Review],
    classifications: Dict[str, ClassificationResult],
) -> ReportSummary:
    """Compute aggregate insights purely in Python from verified classifications."""
    total_reviews = len(reviews)

    verified_results: List[ClassificationResult] = []
    failed_count = 0

    for review in reviews:
        res = classifications.get(review.id)
        if res is None:
            continue
        if res.status == "verified":
            verified_results.append(res)
        elif res.status == "analysis_failed":
            failed_count += 1

    analyzed_count = len(verified_results)
    unanalyzed_count = total_reviews - analyzed_count - failed_count

    # Zero-denominator protection for coverage
    coverage_pct = (analyzed_count / total_reviews * 100.0) if total_reviews > 0 else 0.0

    # 1. Sentiment distribution & percentages
    sentiment_counts: Dict[str, int] = {s: 0 for s in ALLOWED_SENTIMENTS}
    for res in verified_results:
        if res.sentiment in sentiment_counts:
            sentiment_counts[res.sentiment] += 1

    sentiment_percentages: Dict[str, float] = {}
    for s, count in sentiment_counts.items():
        pct = (count / analyzed_count * 100.0) if analyzed_count > 0 else 0.0
        sentiment_percentages[s] = pct

    # 2. Topic frequencies
    topic_counts: Dict[str, int] = {t: 0 for t in ALLOWED_TOPICS}
    for res in verified_results:
        for t in res.topics:
            if t in topic_counts:
                topic_counts[t] += 1

    # 3. Mixed review count
    mixed_count = sentiment_counts.get("mixed", 0)

    # 4. Top complaint themes (topics present on negative or mixed reviews)
    complaint_topics_counter: collections.Counter = collections.Counter()
    for res in verified_results:
        if res.sentiment in ("negative", "mixed"):
            for t in res.topics:
                complaint_topics_counter[t] += 1

    top_complaint_themes: List[Tuple[str, int]] = complaint_topics_counter.most_common()

    # 5. Cited example IDs per topic
    cited_examples: Dict[str, List[str]] = collections.defaultdict(list)
    for res in verified_results:
        for t in res.topics:
            if len(cited_examples[t]) < 4:
                cited_examples[t].append(res.review_id)

    return ReportSummary(
        total_reviews=total_reviews,
        analyzed_reviews=analyzed_count,
        failed_reviews=failed_count,
        unanalyzed_reviews=unanalyzed_count,
        coverage_percentage=coverage_pct,
        sentiment_distribution=sentiment_counts,
        sentiment_percentages=sentiment_percentages,
        topic_frequencies=topic_counts,
        mixed_count=mixed_count,
        top_complaint_themes=top_complaint_themes,
        cited_examples=dict(cited_examples),
    )


def format_ascii_report(summary: ReportSummary) -> str:
    """Format report summary as a structured, human-readable terminal table."""
    lines: List[str] = []
    lines.append("=" * 64)
    lines.append("            VIBECHECK AI - FESTIVAL INTELLIGENCE REPORT")
    lines.append("=" * 64)
    lines.append(f"Coverage: {summary.analyzed_reviews} analyzed / {summary.total_reviews} total reviews ({summary.coverage_percentage:.1f}%)")
    lines.append(f"Status:   {summary.analyzed_reviews} verified, {summary.failed_reviews} failed, {summary.unanalyzed_reviews} unanalyzed")
    lines.append("-" * 64)

    if summary.analyzed_reviews == 0:
        lines.append("[!] No verified review analyses available yet. Run batch analysis first.")
        lines.append("=" * 64)
        return "\n".join(lines)

    lines.append("SENTIMENT DISTRIBUTION (Computed in Python from verified labels):")
    for s in ("positive", "negative", "mixed", "neutral"):
        count = summary.sentiment_distribution.get(s, 0)
        pct = summary.sentiment_percentages.get(s, 0.0)
        bar = "#" * int(pct / 4)
        lines.append(f"  {s.upper():<9} : {count:>3} ({pct:>5.1f}%)  | {bar}")

    lines.append("-" * 64)
    lines.append("TOPIC FREQUENCIES (Observed across verified reviews):")
    sorted_topics = sorted(summary.topic_frequencies.items(), key=lambda x: x[1], reverse=True)
    for topic, count in sorted_topics:
        pct = (count / summary.analyzed_reviews * 100.0) if summary.analyzed_reviews > 0 else 0.0
        lines.append(f"  {topic:<10} : {count:>3} occurrences ({pct:>5.1f}% of reviews)")

    lines.append("-" * 64)
    lines.append(f"MIXED FEEDBACK: {summary.mixed_count} reviews express simultaneous praise and criticism.")

    lines.append("-" * 64)
    lines.append("TOP COMPLAINT THEMES (Negative / Mixed reviews):")
    if not summary.top_complaint_themes:
        lines.append("  None identified.")
    else:
        for theme, count in summary.top_complaint_themes:
            examples = summary.cited_examples.get(theme, [])
            ex_str = f" [e.g. {', '.join(examples[:3])}]" if examples else ""
            lines.append(f"  - {theme.capitalize()}: {count} complaints{ex_str}")

    lines.append("=" * 64)
    lines.append("NOTE: Counts and percentages are computed purely by Python standard")
    lines.append("library. Festival management causes are not inferred without evidence.")
    lines.append("=" * 64)
    return "\n".join(lines)


def export_report_json(
    summary: ReportSummary,
    reviews: List[Review],
    classifications: Dict[str, ClassificationResult],
    output_path: Path | str,
    model_metadata: Dict[str, str],
) -> Path:
    """Export comprehensive traceable report to a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    verified_records = []
    failed_records = []

    for r in reviews:
        res = classifications.get(r.id)
        if res and res.status == "verified":
            verified_records.append({
                "review_id": r.id,
                "event": r.event,
                "text": r.text,
                "created_at": r.created_at,
                "sentiment_ai": res.sentiment,
                "topics_ai": res.topics,
                "evidence_quote_ai": res.evidence_quote,
                "short_reason_ai": res.short_reason,
                "source_hash": res.source_hash,
                "analyzed_at": res.analyzed_at,
            })
        elif res and res.status == "analysis_failed":
            failed_records.append({
                "review_id": r.id,
                "event": r.event,
                "text": r.text,
                "error_message": res.error_message,
                "analyzed_at": res.analyzed_at,
            })

    payload: Dict[str, Any] = {
        "export_metadata": {
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "generator": "VibeCheck AI CLI",
            "model_metadata": model_metadata,
            "provenance_disclosure": {
                "statistics": "COMPUTED_BY_PYTHON (deterministic)",
                "sentiment_and_topics": "INFERRED_BY_AI_MODEL (unverified inference, validated by schema)",
                "evidence_quotes": "EXTRACTED_SUBSTRING_VERIFIED_BY_PYTHON",
            },
        },
        "python_computed_summary": summary.to_dict(),
        "verified_classifications": verified_records,
        "failed_classifications": failed_records,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return path


def export_report_txt(summary: ReportSummary, output_path: Path | str) -> Path:
    """Export human-readable text report."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = format_ascii_report(summary)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

