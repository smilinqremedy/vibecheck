# VibeCheck AI — Pull Request Reviews & Git Collaboration Log

This document records the four core engineering Pull Requests developed collaboratively by **Engineer A (Maya Lin)** and **Engineer B (Devon Brooks)**.

---

## PR #1: Review Ingestion & Schema Sanitization
- **Branch**: `feat/11-review-import` -> `main`
- **Author**: Engineer A (Maya Lin — Data Integrity & AI Provider Engineer)
- **Reviewer**: Engineer B (Devon Brooks — Insight & Conversational Evidence Engineer)
- **Status**: APPROVED & MERGED

### 1. Requirements & Scope
- Implement `import_reviews(path)` supporting CSV and JSON formats.
- Enforce review contract: unique alphanumeric ID, non-empty event, text length between 5 and 500 characters, valid `YYYY-MM-DD` date.
- Protect existing application state: if a file cannot be read or is corrupted, raise `ImportValidationError` without mutating previously loaded records.
- Support CLI listing of reviews with status indicators.

### 2. Risk Assessment
- **Corrupted Encoded Files**: Non-UTF8 files could crash the CLI.
- **State Pollution**: Partial file imports could inject dirty records if validation fails midway.

### 3. Automated Tests & Verification
- `test_01_duplicate_review_id`: Verified rejection of duplicate IDs.
- `test_02_invalid_date`: Verified rejection of malformed dates (`2026/06/12`, `invalid-date`, `2026-02-31`).
- `test_03_empty_text`: Verified rejection of strings `< 5` characters.
- `test_04_csv_utf8_handling`: Verified UTF-8 symbols and rejection of corrupt non-UTF8 bytes.

### 4. Review Comments & Resolutions
- **Reviewer Comment 1 (Devon Brooks)**:
  > *"Maya, in `validate_review_record`, `strptime` parses `2026-02-28` fine, but if someone inputs `2026-2-28` it parses even though the contract says strict `YYYY-MM-DD`. Can we verify that `parsed.strftime('%Y-%m-%d') == created_at`?"*
  - **Resolution (Maya Lin)**: Implemented bidirectional date format verification `parsed_date.strftime("%Y-%m-%d") == created_at` to enforce 4-digit year and 2-digit month/day.
- **Reviewer Comment 2 (Devon Brooks)**:
  > *"If a CSV contains 10 records and record 5 fails decoding, let's make sure the whole file is rejected and existing reviews in memory are untouched."*
  - **Resolution (Maya Lin)**: Added raw byte pre-decoding step `path.read_bytes().decode('utf-8')` before parsing, raising `ImportValidationError` cleanly if decoding fails.

---

## PR #2: Provider Client, Bounded Retries & Cryptographic Cache
- **Branch**: `feat/12-provider-client` -> `main`
- **Author**: Engineer A (Maya Lin)
- **Reviewer**: Engineer B (Devon Brooks)
- **Status**: APPROVED & MERGED

### 1. Requirements & Scope
- Pure Python `urllib.request` HTTPS POST client for OpenAI-compatible `/chat/completions`.
- Bounded retries (max 2) with exponential backoff on HTTP 429 and 5xx errors.
- Strict secret redaction: bearer tokens must never appear in logs or error messages.
- SHA-256 content-hash keyed local caching to prevent stale results when reviews change.

### 2. Risk Assessment
- **Thundering Herd / Rate Limit Lockups**: Indefinite retries could drain rate limits and freeze the CLI.
- **Secret Exfiltration**: Exception stack traces could print raw `Authorization` headers.

### 3. Automated Tests & Verification
- `test_11_provider_timeout_handling`: Verified clean timeout exception.
- `test_12_429_5xx_finite_retry`: Verified backoff (0.5s, 1.0s) and termination after max retries.
- `test_13_no_secret_printed_logged`: Verified API key masking (`sk-...2345`).
- `test_14_unchanged_cache_avoids_repeat_calls`: Verified cache hit skips network.
- `test_15_changed_source_invalidates_cache`: Verified SHA256 invalidation when text is edited.

### 4. Review Comments & Resolutions
- **Reviewer Comment 1 (Devon Brooks)**:
  > *"Maya, what happens if an unhandled `HTTPError` occurs? In Python, printing `http_err` could output request headers if not carefully controlled."*
  - **Resolution (Maya Lin)**: Added explicit secret redaction inside `HTTPProviderClient.call_model()`. The auth token is never printed; errors display masked keys (`sk-...1234`).
- **Reviewer Comment 2 (Devon Brooks)**:
  > *"If an attendee review text is edited to correct a typo, we must not return the old cached analysis. How does the cache handle this?"*
  - **Resolution (Maya Lin)**: Added `source_hash` (SHA256 hex digest of the review text) into the composite cache key: `f"{review_id}:{source_hash}:{model_id}:{prompt_version}"`. Modifying text immediately causes a cache miss.

---

## PR #3: Deterministic Reporting & Traceable Export
- **Branch**: `feat/13-insight-reports` -> `main`
- **Author**: Engineer B (Devon Brooks — Insight & Conversational Evidence Engineer)
- **Reviewer**: Engineer A (Maya Lin — Data Integrity & AI Provider Engineer)
- **Status**: APPROVED & MERGED

### 1. Requirements & Scope
- Compute sentiment distribution, topic frequencies, complaint themes, and coverage strictly in Python.
- Zero-denominator protection on all percentages.
- Recognize `mixed` sentiment explicitly; do not force reviews into binary positive/negative.
- Export structured JSON and ASCII reports with explicit provenance disclosures.

### 2. Risk Assessment
- **Arithmetic Hallucination**: Asking LLMs to count totals leads to confabulation.
- **ZeroDivisionError**: Empty datasets causing runtime crashes.

### 3. Automated Tests & Verification
- `test_16_denominator_and_missing_analysis_reporting`: Verified coverage and percentage calculations.
- `test_17_mixed_sentiment_recognized`: Verified multi-topic mixed feedback preservation.
- `test_22_export_counts_agree_with_validated_records`: Verified export metrics agree with Python statistics.

### 4. Review Comments & Resolutions
- **Reviewer Comment 1 (Maya Lin)**:
  > *"Devon, what happens if the user runs Option 5 before any reviews have been analyzed? Will `coverage_percentage` raise a `ZeroDivisionError`?"*
  - **Resolution (Devon Brooks)**: Added ternary zero checks: `(analyzed_count / total_reviews * 100.0) if total_reviews > 0 else 0.0`.
- **Reviewer Comment 2 (Maya Lin)**:
  > *"In `export_report.json`, external auditors need to know which fields were computed by deterministic Python code versus inferred by AI models. Please add an explicit provenance disclosure block."*
  - **Resolution (Devon Brooks)**: Added `provenance_disclosure` block separating Python deterministic statistics from AI-derived inferences.

---

## PR #4: Evidence-Grounded Q&A & Citation Auditing
- **Branch**: `feat/14-grounded-qa` -> `main`
- **Author**: Engineer B (Devon Brooks)
- **Reviewer**: Engineer A (Maya Lin)
- **Status**: APPROVED & MERGED

### 1. Requirements & Scope
- Deterministic token overlap retrieval selecting top-k (up to 5) relevant reviews.
- Strict grounding prompt: pass ONLY retrieved reviews into model context.
- Citation validation: check that every cited ID in `cited_review_ids` exists in the retrieved subset.
- Verified abstention: respond `"Insufficient evidence in the supplied reviews."` when unsupported.

### 2. Risk Assessment
- **Citation Hallucination**: Model inventing review IDs or citing reviews from outside the prompt context.
- **Extrapolation**: Model inventing festival attendance figures or operational causes.

### 3. Automated Tests & Verification
- `test_18_grounded_qa_unknown_cited_id_rejected`: Verified rejection of hallucinated review IDs.
- `test_19_insufficient_evidence_triggers_abstention`: Verified abstention when evidence is absent.
- `test_20_malicious_review_text_treated_as_untrusted`: Verified prompt injection text is safely isolated.

### 4. Review Comments & Resolutions
- **Reviewer Comment 1 (Maya Lin)**:
  > *"Devon, if the user asks a completely unrelated question like 'What is the capital of France?', our retrieval engine will find 0 matching reviews. Let's abstain immediately in Python without making an expensive API call."*
  - **Resolution (Devon Brooks)**: Added early abstention guard: `if not retrieved: return QAResponse(..., status='insufficient_evidence')`.
- **Reviewer Comment 2 (Maya Lin)**:
  > *"If the model answers but cites `[R999]` (which doesn't exist), what status is returned?"*
  - **Resolution (Devon Brooks)**: Added set difference check `[cid for cid in cited_ids if cid not in retrieved_id_set]`. If any unknown ID is cited, status is set to `'error'` and flagged as a citation grounding violation.
