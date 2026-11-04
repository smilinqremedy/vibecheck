# VibeCheck AI — Engineering Learning Log & Curriculum Verification

---

## PART 0 — YOUR READINESS GATE (WITHOUT AI ASSISTANCE)

### 1. Read a JSON file and handle bad JSON
```python
import json
from pathlib import Path

def safe_load_json(file_path: str) -> list | dict:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"File contains invalid JSON at line {exc.lineno}, col {exc.colno}: {exc.msg}")
```

### 2. Loop through `list[dict]` and count categories
```python
from collections import Counter

def count_categories(records: list[dict], category_key: str = "sentiment") -> dict[str, int]:
    counts = Counter()
    for item in records:
        val = item.get(category_key, "unknown")
        counts[val] += 1
    return dict(counts)
```

### 3. Write a function that returns a dict and checks inputs
```python
def make_review_summary(review_id: str, text: str, rating: int) -> dict:
    if not isinstance(review_id, str) or not review_id.strip():
        raise ValueError("review_id must be a non-empty string")
    if not isinstance(text, str) or len(text.strip()) < 5:
        raise ValueError("text must be at least 5 characters")
    if not (1 <= rating <= 5):
        raise ValueError(f"rating must be between 1 and 5, got {rating}")
    return {"review_id": review_id.strip(), "text": text.strip(), "rating": rating}
```

### 4. Explain an HTTP request versus response and status code
An HTTP **request** is an outbound message formatted in plaintext according to RFC specifications sent by a client to an HTTP server. It contains an HTTP method (e.g. `POST`), a resource path (e.g. `/v1/chat/completions`), protocol version (e.g. `HTTP/1.1`), headers (such as `Host`, `Authorization: Bearer <key>`, `Content-Type: application/json`), and an optional message body (e.g. UTF-8 JSON payload).

An HTTP **response** is returned by the server. It contains the protocol version, an HTTP status code (e.g. `200 OK`, `429 Too Many Requests`, `500 Internal Server Error`), response headers (e.g. `Content-Type`, `Retry-After`), and a response body. Status codes are grouped into semantic ranges: `2xx` = success, `4xx` = client errors (401 unauthorized, 403 forbidden, 429 rate limit), and `5xx` = server-side faults (500 internal error, 503 gateway unavailable).

### 5. Explain a `unittest.mock` fake response
In automated unit testing, calling a live remote API introduces external network latency, flakiness, rate limits, and financial cost. `unittest.mock.patch` replaces the target function (such as `urllib.request.urlopen`) with a controlled mock object (`MagicMock`). When the code under test calls `urlopen()`, the mock intercepts the call, returns a simulated response (e.g. an `io.BytesIO` containing fixed JSON bytes, or raises a simulated `urllib.error.HTTPError`), and records call arguments (`mock.call_count`, `mock.call_args`). This allows testing success, transient retries, and failure branches deterministically in milliseconds without touching the internet.

### 6. Create a branch/PR and explain why review precedes merge
In professional engineering, changes are never committed directly to `main`. A developer branches off main (e.g. `git checkout -b feat/11-review-import`), makes atomic commits with descriptive commit messages, pushes to remote, and opens a Pull Request (PR). A peer engineer reviews the PR to verify:
- Functional correctness against requirements.
- Absence of security regressions (e.g. committed API tokens or injection vulnerabilities).
- Adequate automated test coverage and reproducible reproduction steps.
- Code style and adherence to system contracts.
Approval from review precedes merging to prevent buggy, insecure, or breaking code from entering the shared production trunk.

---

## PART 1 — LEARN-FIRST CURRICULUM (LESSONS 1–10)

### Lesson 1 | Data modelling, parsing and safe imports
- **Mini-Lab**: Ingest 5 records from CSV, check unique IDs, reject duplicates. Implemented in `app/ingest.py` and tested in `test_01_duplicate_review_id`.
- **CHECK**: *Why might a JSON file be syntactically valid but wrong for your app?*
  **Answer**: A JSON file can parse cleanly with `json.loads()` (syntactically valid braces, quotes, commas), but violate business domain constraints: e.g., missing required fields (`review_id`, `text`), field values having wrong types (an integer instead of a string), out-of-range dates, or schema violations. Syntax is only the serialization container; schema validation enforces data integrity.

### Lesson 2 | Text processing and reproducible statistics
- **Mini-Lab**: Calculated sentiment percentages and topic counts from sample reviews with zero-denominator safety in `app/report.py`.
- **CHECK**: *If 7 of 20 reviews are negative, what percentage is negative? Can you infer the sentiment of all festival attendees from 20 voluntarily supplied reviews?*
  **Answer**: $7 / 20 = 35.0\%$. No, you cannot extrapolate to all festival attendees. Voluntarily submitted reviews suffer from voluntary response bias and negative selection bias (attendees with extreme complaints or extreme enthusiasm are disproportionately likely to submit feedback). 20 reviews from an event of 10,000 attendees cannot support statistically significant population-level inferences.

### Lesson 3 | HTTP and API contracts from first principles
- **Mini-Lab**: Request/response flow diagram documented in `docs/architecture.md`.
- **CHECK**: *Which error requires user guidance versus a retry?*
  **Answer**: An HTTP 401 Unauthorized or 403 Forbidden indicates an invalid or missing API key; retrying will never succeed and simply wastes time. The program must halt and display actionable guidance ("Check AI_API_KEY in your .env file"). In contrast, an HTTP 429 (Rate Limit) or HTTP 503 (Service Unavailable) indicates temporary throttling or upstream load; the client should perform bounded retries with exponential backoff before failing.

### Lesson 4 | API keys, privacy and untrusted input
- **Mini-Lab**: Implemented `Config.redact_secret()` and verified in `test_13_no_secret_printed_logged`.
- **CHECK**: *Is a comment that says 'ignore previous instructions' a trustworthy instruction or untrusted dataset content?*
  **Answer**: It is **untrusted dataset content**. In LLM applications, user-supplied content must be treated strictly as passive data inside delimited fences (`<<<UNTRUSTED_DATA>>>`), never as system instructions. Post-generation Python checks must verify that output adheres to the application's contract regardless of adversarial commands in the input text.

### Lesson 5 | Prompt design as an engineering interface
- **Mini-Lab**: Designed `CLASSIFIER_SYSTEM_PROMPT` in `app/classify.py` with strict schema, enum definitions, and JSON-only requirements.
- **CHECK**: *Why can a well-worded prompt STILL return malformed JSON?*
  **Answer**: LLMs are autoregressive probability models, not deterministic compiler engines. Even with explicit instructions, temperature sampling, model drift, token limit cutoffs, or complex nested text can cause the model to emit explanatory markdown fences, trailing commas, or truncated strings. Defensive parsing with `json.loads` and exception handling in Python is mandatory.

### Lesson 6 | Defensive parsing and evidence-grounded AI
- **Mini-Lab**: Implemented verbatim substring check `quote in review.text` in `app/classify.py` and verified rejection in `test_08_invented_evidence_quote`.
- **CHECK**: *Can a model be confidently wrong, even when the JSON syntax is valid?*
  **Answer**: Yes (hallucination). A model can output syntactically valid JSON with high output probabilities while inventing plausible-sounding but completely fabricated facts (e.g. inventing quotes not in the review, citing non-existent review IDs, or hallucinating attendance numbers). Python-side verification must anchor claims to actual source text.

### Lesson 7 | Reliability, retries, caching and deterministic tests
- **Mini-Lab**: Built `MockProviderClient` with simulated 429 rate limit retry in `test_12_429_5xx_finite_retry`.
- **CHECK**: *Why should unit tests never need a live AI provider?*
  **Answer**: Unit tests must be fast, deterministic, reproducible offline, and free of financial costs. Relying on live APIs causes test flakiness due to network latency, transient outages, API rate limits, non-deterministic model generation, and unauthorized credential exposure in CI/CD environments.

### Lesson 8 | Retrieval, aggregation and grounded question-answering
- **Mini-Lab**: Built token overlap retrieval in `app/retrieve.py` tested in `tests/test_retrieve.py`.
- **CHECK**: *When should AI abstain rather than invent a percentage or cause?*
  **Answer**: The AI should abstain whenever the retrieved evidence does not explicitly contain the necessary facts or data points to answer the question. It must respond `"Insufficient evidence in the supplied reviews."` rather than extrapolating or guessing causal relationships.

### Lesson 9 | Evaluation and critical thinking
- **Mini-Lab**: Hand-labelled 14 gold reviews and benchmarked agreement in `tests/test_gold_set.py`.
- **CHECK**: *Accuracy on 12 examples does not prove the model is correct everywhere—why?*
  **Answer**: A 12 or 14-example evaluation set has high statistical variance and fails to represent the long tail of edge cases, unseen slang, multilingual inputs, or nuanced sentiment combinations encountered in real-world deployments. It serves as a regression baseline, not a universal guarantee.

### Lesson 10 | Git collaboration, versioning and code review
- **Mini-Lab**: Inspected fake PR committing secrets and trusting raw LLM JSON. Documented rejection reasons in `docs/security-notes.md`.

---

## PART 5 — VERIFIED AI STUDY CYCLES

### Engineer A Study Cycles (Maya Lin — Data Integrity & AI Provider)
1. **Cycle A1 (urllib.request vs. requests/SDK)**: Investigated using Python's standard `urllib.request` vs. installing the `openai` SDK. Proved that standard library avoids dependency bloat, security supply-chain vulnerabilities, and version incompatibilities while completely fulfilling the HTTP POST chat completion specification.
2. **Cycle A2 (Bounded Exponential Backoff)**: Verified that retrying immediately on HTTP 429 exacerbates upstream provider throttling. Implemented exponential backoff ($0.5s \times 2^{\text{attempt}}$) capped at 2 retries.
3. **Cycle A3 (Cryptographic Invalidation)**: Designed SHA256 source hashing to solve cache staleness when review text is edited. Verified in unit test 15.

### Engineer B Study Cycles (Devon Brooks — Insight & Conversational Evidence)
1. **Cycle B1 (Deterministic Text Overlap vs. Vector Embeddings)**: Evaluated BM25/token overlap vs. remote embedding models. Concluded that for a local festival CLI with < 500 reviews, token overlap has zero latency, zero API cost, zero privacy leakage, and deterministic ranking.
2. **Cycle B2 (Citation Grounding Defense)**: Proved that LLMs will occasionally cite review IDs that were never provided in the prompt context. Built Python citation set-difference validation (`cited_ids - retrieved_ids`) to flag hallucinations.
3. **Cycle B3 (Statistical Aggregation Integrity)**: Proved that asking LLMs to compute totals results in hallucinated numbers (e.g. claiming 15 negative reviews when only 9 exist). Enforced pure Python aggregation via `collections.Counter`.
