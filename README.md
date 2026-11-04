# VibeCheck AI — Festival Feedback Detective
> **An evidence-grounded AI review intelligence CLI built using the Python standard library.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Standard Library Only](https://img.shields.io/badge/dependencies-none%20(stdlib%20only)-success.svg)]()
[![Tests Passing](https://img.shields.io/badge/tests-31%2F31%20passing-brightgreen.svg)]()

---

## The Mission — Turning Chaotic Reviews into Trustworthy Insights
Music and food festival attendees submit hundreds of short, chaotic comments: *"Sensational DJ, but the bar queue was a nightmare"*, *"Sound bleed ruined stage B"*, *"Water was nine dollars!"*.

**VibeCheck AI** is a production-grade terminal application that:
1. **Safely imports & normalizes** synthetic attendee feedback from CSV and JSON datasets.
2. **Classifies reviews using AI** according to strict contracts (`sentiment`, `topics`, `evidence_quote`, `short_reason`).
3. **Defensively parses model responses** in Python, verifying that quoted text appears verbatim in source reviews.
4. **Calculates reproducible statistics** strictly in Python (the AI is never asked to hallucinate counts or percentages).
5. **Answers grounded user questions** by passing only retrieved reviews into context and rejecting hallucinated citations.
6. **Prevents prompt injection** and isolates untrusted user text inside prompt fences.
7. **Includes an Engineering Self-Check** audit mode evaluating data boundaries and AI trust limitations.

---

## Engineering Highlights
- **Zero External Dependencies**: Built 100% on Python standard library (`json`, `csv`, `pathlib`, `os`, `re`, `collections`, `datetime`, `urllib.request`, `unittest`, `hashlib`).
- **Cryptographic Cache Invalidation**: Caches verified classifications keyed by review ID, source text hash (SHA256), model ID, and schema version. Stale results are automatically invalidated when review text changes.
- **Defensive Error Handling**: Network timeouts (20s) and bounded exponential backoff retries (max 2) on HTTP 429/5xx errors. The CLI never crashes on provider outages.
- **Secret Redaction**: Bearer tokens are masked (`sk-...1234`) in logs and CLI output.

---

## Directory Layout
```
vibecheck/
├── main.py                     # Main CLI entry point
├── app/
│   ├── __init__.py
│   ├── config.py               # Pure stdlib .env parser & secret redaction
│   ├── models.py               # Immutable dataclasses & schema definitions
│   ├── ingest.py               # CSV/JSON import, normalization & duplicate rejection
│   ├── provider.py             # urllib.request HTTPS client with 429/5xx backoff retries
│   ├── classify.py             # Prompt builder, JSON parser & verbatim quote validator
│   ├── cache.py                # SHA-256 content-hash keyed local persistence
│   ├── retrieve.py             # Deterministic token-overlap retrieval engine
│   ├── report.py               # Deterministic Python statistics & report exporter
│   ├── qa.py                   # Evidence-grounded Q&A & citation grounding validator
│   ├── quiz.py                 # Engineering Self-Check quiz engine (Part 7)
│   └── cli.py                  # 8-option interactive terminal menu
├── data/
│   ├── synthetic_reviews.csv   # 36 realistic synthetic festival comments
│   └── synthetic_reviews.json  # JSON equivalent dataset
├── docs/
│   ├── requirements.md         # Full product & engineering requirements
│   ├── architecture.md         # System design, data flow diagrams & sequence charts
│   ├── ai-learning-log.md      # Readiness gate, Lessons 1-10 & verified study cycles
│   ├── gold-set-evaluation.md  # 14-sample hand-labelled benchmark & error analysis
│   ├── security-notes.md       # Threat model, prompt injection defense & secret hygiene
│   └── pr_reviews.md           # 4 Git PR reviews with review comments & resolutions
├── tests/
│   ├── __init__.py
│   ├── test_all_milestones.py  # All 22 mandatory unit tests from Part 4
│   ├── test_gold_set.py        # Benchmark runner for hand-labelled gold set
│   ├── test_quiz.py            # Unit tests for self-check quiz scoring
│   ├── test_retrieve.py        # Unit tests for token retrieval engine
│   └── test_live_ai.py         # Live AI acceptance demonstration (Live 1, 2, 3)
├── .env.example                # Example configuration with placeholders
└── .gitignore                  # Ignores .env and runtime storage
```

---

## Quick Start & Usage

### 1. Run the Interactive CLI
```bash
cd /home/student/vibecheck
python3 main.py
```

### 2. CLI Menu Navigation
```
[MAIN MENU]
  1) Import Reviews (CSV or JSON)
  2) List Reviews
  3) Analyze Pending Reviews with AI
  4) View Classification Details
  5) Generate Insights & Deterministic Stats
  6) Ask AI Grounded in Review Evidence
  7) Export Traceable Report
  8) Run Engineering Self-Check Quiz
  0) Quit
```
- **Option 1**: Enter `data/synthetic_reviews.csv` to load the 36 festival comments.
- **Option 2**: View tabular listing with date, event name, snippet, and status.
- **Option 3**: Run batch analysis (utilizes offline demo mode or live API if configured).
- **Option 4**: Inspect single review details (SHA-256 hash, verified quote, topics, reason).
- **Option 5**: View beautiful ASCII report computed purely in Python.
- **Option 6**: Ask queries like *"How was the headline DJ and stage sound?"* or *"What was the feedback on queues?"*.
- **Option 7**: Exports `storage/export_report.json` and `storage/export_report.txt`.
- **Option 8**: Complete the 10-question engineering self-check quiz.

---

## Configuring a Live AI Provider (Optional)
VibeCheck AI connects to any standard OpenAI-compatible HTTPS endpoint (OpenAI, Groq, OpenRouter, Mistral, or Gemini OpenAI-compatible).

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` with your provider details:
   ```ini
   AI_BASE_URL=https://api.openai.com/v1
   AI_MODEL=gpt-4o-mini
   AI_API_KEY=your_actual_api_key_here
   ```
3. Run the live acceptance demonstration:
   ```bash
   PYTHONPATH=. python3 tests/test_live_ai.py
   ```
*Note: If no API key is provided, the application runs in offline demo mode using the deterministic `MockProviderClient`, and documents the blocker honestly without falsely claiming live integration.*

---

## Running the Automated Test Suite
To run all 31 unit and milestone tests:
```bash
cd /home/student/vibecheck
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

### Mandatory Tests Verified (Tests 01–22):
- `test_01_duplicate_review_id`: Rejects duplicate review IDs in file/state.
- `test_02_invalid_date`: Rejects malformed dates not matching `YYYY-MM-DD`.
- `test_03_empty_text`: Rejects empty or `< 5` character strings.
- `test_04_csv_utf8_handling`: UTF-8 decoding & non-UTF8 corruption safety.
- `test_05_valid_classifier_json`: Validates compliant AI JSON schema.
- `test_06_malformed_ai_json`: Marks status `analysis_failed` on bad JSON.
- `test_07_wrong_review_id`: Rejects mismatched `review_id`.
- `test_08_invented_evidence_quote`: Rejects quotes not in source text.
- `test_09_invalid_label`: Rejects unsupported sentiment enums.
- `test_10_duplicated_or_unallowed_topic`: Rejects unallowed or duplicate topics.
- `test_11_provider_timeout_handling`: Catches network timeouts cleanly.
- `test_12_429_5xx_finite_retry`: Bounded exponential backoff on transient errors.
- `test_13_no_secret_printed_logged`: Verifies secrets are never printed or logged.
- `test_14_unchanged_cache_avoids_repeat_calls`: Reuses cached verified results.
- `test_15_changed_source_invalidates_cache`: SHA256 invalidation when text changes.
- `test_16_denominator_and_missing_analysis_reporting`: Zero-denominator safety & coverage.
- `test_17_mixed_sentiment_recognized`: Multi-topic mixed feedback recognition.
- `test_18_grounded_qa_unknown_cited_id_rejected`: Flags hallucinated citation IDs.
- `test_19_insufficient_evidence_triggers_abstention`: Abstains when evidence is absent.
- `test_20_malicious_review_text_treated_as_untrusted`: Prompt injection defense.
- `test_21_bad_cli_choice_reprompts`: Re-prompts gracefully on invalid menu choice.
- `test_22_export_counts_agree_with_validated_records`: Verifies export stats match Python metrics.

---

## Team Ownership & Git Collaboration
- **Engineer A (Maya Lin — Data Integrity & AI Provider Engineer)**:
  - Owned ingestion (`ingest.py`), provider adapter (`provider.py`), response validation (`classify.py`), and cryptographic caching (`cache.py`).
  - Authored PR #1 (`feat/11-review-import`) and PR #2 (`feat/12-provider-client`).
- **Engineer B (Devon Brooks — Insight & Conversational Evidence Engineer)**:
  - Owned deterministic reporting (`report.py`), token retrieval (`retrieve.py`), grounded Q&A (`qa.py`), self-check quiz (`quiz.py`), and CLI (`cli.py`).
  - Authored PR #3 (`feat/13-insight-reports`) and PR #4 (`feat/14-grounded-qa`).
- **Peer Review Discipline**: All four feature branches were reviewed with specific observations and resolved before merging into `main`. Direct commits to `main` were prohibited.
