"""Interactive Command Line Interface for VibeCheck AI.

Provides the complete 8-option terminal workflow for festival feedback detective:
ingestion, review listing, AI classification, insight reports, grounded Q&A,
traceable exports, and engineering self-audit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from app.cache import ClassificationCache
from app.classify import classify_review
from app.config import Config
from app.ingest import ImportValidationError, import_reviews
from app.models import ClassificationResult, Review
from app.provider import (
    BaseProviderClient,
    HTTPProviderClient,
    MockProviderClient,
    ProviderError,
)
from app.qa import answer_grounded_question
from app.quiz import QuizSession
from app.report import (
    export_report_json,
    export_report_txt,
    format_ascii_report,
    generate_report_summary,
)


class VibeCheckCLI:
    """Manages state and user interaction for the terminal application."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.reviews: List[Review] = []
        self.classifications: Dict[str, ClassificationResult] = {}
        self.cache = ClassificationCache(self.config.storage_dir / "classifications_cache.json")
        self.provider: BaseProviderClient = self._initialize_provider()

    def _initialize_provider(self) -> BaseProviderClient:
        """Initialize provider client from config. If API key is missing or blank, warn user."""
        if self.config.ai_api_key:
            return HTTPProviderClient(
                base_url=self.config.ai_base_url,
                model=self.config.ai_model,
                api_key=self.config.ai_api_key,
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )
        # Default to HTTP client (will fail cleanly on live call if unconfigured, or can use mock for demos)
        return HTTPProviderClient(
            base_url=self.config.ai_base_url,
            model=self.config.ai_model,
            api_key="",
            timeout_seconds=self.config.timeout_seconds,
            max_retries=self.config.max_retries,
        )

    def print_header(self) -> None:
        print("\n" + "=" * 68)
        print("    VIBECHECK AI: FESTIVAL FEEDBACK DETECTIVE (CLI)")
        print("    Evidence-Grounded Intelligence & Audit Framework")
        print("=" * 68)
        summary = self.config.get_sanitized_summary()
        print(f" Model: {summary['AI_MODEL']} | Provider: {summary['AI_BASE_URL']}")
        print(f" Key Status: {summary['AI_API_KEY']} | Schema Version: {summary['PROMPT_SCHEMA_VERSION']}")
        print(f" Reviews Loaded: {len(self.reviews)} | Verified Cached: {len(self.classifications)}")
        print("=" * 68)

    def print_menu(self) -> None:
        print("\n[MAIN MENU]")
        print("  1) Import Reviews (CSV or JSON)")
        print("  2) List Reviews")
        print("  3) Analyze Pending Reviews with AI")
        print("  4) View Classification Details")
        print("  5) Generate Insights & Deterministic Stats")
        print("  6) Ask AI Grounded in Review Evidence")
        print("  7) Export Traceable Report")
        print("  8) Run Engineering Self-Check Quiz")
        print("  0) Quit")

    def run(self) -> None:
        """Main event loop."""
        self.print_header()
        while True:
            self.print_menu()
            choice = input("\nEnter choice [0-8]: ").strip()

            if choice == "0":
                print("\nGoodbye! Exiting VibeCheck AI.")
                sys.exit(0)
            elif choice == "1":
                self.handle_import_reviews()
            elif choice == "2":
                self.handle_list_reviews()
            elif choice == "3":
                self.handle_analyze_pending()
            elif choice == "4":
                self.handle_classification_details()
            elif choice == "5":
                self.handle_insights()
            elif choice == "6":
                self.handle_grounded_qa()
            elif choice == "7":
                self.handle_export()
            elif choice == "8":
                self.handle_self_check()
            else:
                print(f"\n[!] Invalid option '{choice}'. Please select a number between 0 and 8.")

    # -------------------------------------------------------------
    # 1. Import Reviews
    # -------------------------------------------------------------
    def handle_import_reviews(self) -> None:
        print("\n--- 1. Import Reviews ---")
        default_path = "data/synthetic_reviews.csv"
        user_input = input(f"Enter path to CSV/JSON file (default: {default_path}): ").strip()
        path_str = user_input if user_input else default_path

        try:
            result = import_reviews(path_str, existing_reviews=self.reviews)
            self.reviews.extend(result.accepted)
            print(f"\n[+] Successfully imported {result.num_accepted} reviews.")
            if result.num_rejected > 0:
                print(f"[!] Rejected {result.num_rejected} invalid/duplicate records:")
                for item, reason in result.rejected[:5]:
                    print(f"    - {reason}")
                if result.num_rejected > 5:
                    print(f"    ... and {result.num_rejected - 5} more.")

            # Sync any pre-existing verified cache entries
            for rev in self.reviews:
                cached = self.cache.get_valid(
                    review_id=rev.id,
                    source_hash=rev.source_hash,
                    model_id=self.config.ai_model,
                    prompt_version=self.config.prompt_schema_version,
                )
                if cached:
                    self.classifications[rev.id] = cached

        except ImportValidationError as exc:
            print(f"\n[ERROR] Import failed: {exc}")
        except Exception as exc:
            print(f"\n[ERROR] Unexpected error during import: {exc}")

    # -------------------------------------------------------------
    # 2. List Reviews
    # -------------------------------------------------------------
    def handle_list_reviews(self) -> None:
        print(f"\n--- 2. Loaded Reviews ({len(self.reviews)} total) ---")
        if not self.reviews:
            print("[!] No reviews loaded yet. Please import a dataset first (Option 1).")
            return

        print(f"{'ID':<6} | {'DATE':<10} | {'EVENT':<24} | {'STATUS':<10} | {'TEXT SNIPPET'}")
        print("-" * 80)
        for r in self.reviews:
            res = self.classifications.get(r.id)
            status_str = "PENDING"
            if res:
                status_str = "VERIFIED" if res.status == "verified" else "FAILED"
            snippet = (r.text[:34] + "...") if len(r.text) > 34 else r.text
            event_trunc = (r.event[:22] + "..") if len(r.event) > 22 else r.event
            print(f"{r.id:<6} | {r.created_at:<10} | {event_trunc:<24} | {status_str:<10} | {snippet}")

    # -------------------------------------------------------------
    # 3. Analyze Pending Reviews
    # -------------------------------------------------------------
    def handle_analyze_pending(self) -> None:
        print("\n--- 3. Analyze Pending Reviews with AI ---")
        if not self.reviews:
            print("[!] No reviews loaded. Please import reviews first.")
            return

        if not self.config.ai_api_key and isinstance(self.provider, HTTPProviderClient):
            print("\n[WARNING] AI_API_KEY is not configured in .env or environment variables.")
            print("To run live AI analysis, set AI_API_KEY in your .env file.")
            use_mock = input("Would you like to run in offline demonstration mode with mock AI? (y/n): ").strip().lower()
            if use_mock == "y":
                # Create a smart mock provider that generates compliant output for reviews
                canned = {}
                for r in self.reviews:
                    # Deterministic mock based on content
                    words = r.text.casefold()
                    if "loved" in words or "sensational" in words or "crystal clear" in words or "fantastic" in words:
                        sentiment = "mixed" if ("queue" in words or "terrible" in words or "deafening" in words or "crowd" in words) else "positive"
                    elif "rude" in words or "ripoff" in words or "nightmare" in words or "broken" in words or "gasp" in words or "mud" in words or "price" in words:
                        sentiment = "negative"
                    else:
                        sentiment = "neutral"

                    topics = []
                    for t in ("sound", "food", "queue", "staff", "pricing", "safety", "venue"):
                        if t in words:
                            topics.append(t)
                    if not topics:
                        topics = ["other"]

                    # Quote first 5 words
                    words_list = r.text.split()
                    quote = " ".join(words_list[:min(5, len(words_list))])

                    canned[r.id] = (
                        f'{{"review_id": "{r.id}", "sentiment": "{sentiment}", '
                        f'"topics": {str(topics[:2]).replace(chr(39), chr(34))}, '
                        f'"evidence_quote": "{quote}", '
                        f'"short_reason": "Offline demo classification for {r.id}"}}'
                    )
                self.provider = MockProviderClient(canned_responses=canned)
                print("[+] Loaded offline demonstration provider.")
            else:
                print("[!] Analysis cancelled. Configure AI_API_KEY to proceed with live provider.")
                return

        succeeded = 0
        failed = 0
        skipped = 0

        print("\nStarting batch analysis...\n")
        for i, review in enumerate(self.reviews, start=1):
            # Check cache
            cached = self.cache.get_valid(
                review_id=review.id,
                source_hash=review.source_hash,
                model_id=self.config.ai_model,
                prompt_version=self.config.prompt_schema_version,
            )
            if cached:
                self.classifications[review.id] = cached
                skipped += 1
                continue

            print(f"[{i}/{len(self.reviews)}] Analyzing {review.id}...", end="", flush=True)
            result = classify_review(
                review=review,
                provider=self.provider,
                model_id=self.config.ai_model,
                provider_name="Configured-Provider",
                prompt_schema_version=self.config.prompt_schema_version,
            )

            if result.status == "verified":
                self.cache.put(result)
                self.classifications[review.id] = result
                succeeded += 1
                print(f" OK ({result.sentiment}, topics: {result.topics})")
            else:
                self.classifications[review.id] = result
                failed += 1
                print(f" FAILED: {result.error_message}")

        print("\n" + "=" * 50)
        print("BATCH ANALYSIS COMPLETE")
        print(f"  Succeeded : {succeeded}")
        print(f"  Skipped   : {skipped} (valid results in cache)")
        print(f"  Failed    : {failed}")
        print("=" * 50)

    # -------------------------------------------------------------
    # 4. View Classification Details
    # -------------------------------------------------------------
    def handle_classification_details(self) -> None:
        print("\n--- 4. Classification Details ---")
        if not self.reviews:
            print("[!] No reviews loaded.")
            return

        rev_id = input("Enter Review ID to inspect (e.g. R001): ").strip().upper()
        review = next((r for r in self.reviews if r.id == rev_id), None)
        if not review:
            print(f"[!] Review with ID '{rev_id}' not found.")
            return

        res = self.classifications.get(rev_id)
        print("\n" + "-" * 60)
        print(f"Review ID:     {review.id}")
        print(f"Event:         {review.event}")
        print(f"Date:          {review.created_at}")
        print(f"Source Hash:   {review.source_hash}")
        print(f"Source Text:   \"{review.text}\"")
        print("-" * 60)

        if not res:
            print("Status:        NOT ANALYZED (Pending)")
        elif res.status == "analysis_failed":
            print("Status:        ANALYSIS FAILED [!]")
            print(f"Error Message: {res.error_message}")
            print(f"Attempted At:  {res.analyzed_at}")
        else:
            print("Status:        VERIFIED [PASS]")
            print(f"Sentiment:     {res.sentiment}")
            print(f"Topics:        {', '.join(res.topics) if res.topics else '(none)'}")
            print(f"Evidence Quote:\"{res.evidence_quote}\"")
            print(f"Short Reason:  {res.short_reason}")
            print(f"Model ID:      {res.model_id}")
            print(f"Schema Version:{res.prompt_schema_version}")
            print(f"Analyzed At:   {res.analyzed_at}")
        print("-" * 60)

    # -------------------------------------------------------------
    # 5. Insights & Deterministic Stats
    # -------------------------------------------------------------
    def handle_insights(self) -> None:
        print("\n--- 5. Deterministic Insights ---")
        if not self.reviews:
            print("[!] No reviews loaded. Please import reviews first.")
            return

        summary = generate_report_summary(self.reviews, self.classifications)
        ascii_table = format_ascii_report(summary)
        print("\n" + ascii_table)

    # -------------------------------------------------------------
    # 6. Ask AI Grounded in Review Evidence
    # -------------------------------------------------------------
    def handle_grounded_qa(self) -> None:
        print("\n--- 6. Evidence-Grounded Q&A ---")
        if not self.reviews:
            print("[!] No reviews loaded.")
            return

        question = input("\nEnter your question about festival feedback:\n> ").strip()
        if not question:
            print("[!] Question cannot be empty.")
            return

        print("\nSearching review database for evidence...")
        response = answer_grounded_question(
            question=question,
            all_reviews=self.reviews,
            provider=self.provider,
            top_k=5,
        )

        print("\n" + "=" * 60)
        print("GROUNDED Q&A RESULT")
        print("=" * 60)
        print(f"Status:            {response.status.upper()}")
        print(f"Retrieved Reviews: {response.retrieved_review_ids or '(none)'}")
        print(f"Cited Evidence IDs:{response.cited_review_ids or '(none)'}")
        print("-" * 60)
        print(f"Answer:\n{response.answer}")
        if response.error_message:
            print(f"\n[!] Note: {response.error_message}")
        print("=" * 60)

    # -------------------------------------------------------------
    # 7. Export Traceable Report
    # -------------------------------------------------------------
    def handle_export(self) -> None:
        print("\n--- 7. Export Traceable Report ---")
        if not self.reviews:
            print("[!] No reviews loaded.")
            return

        summary = generate_report_summary(self.reviews, self.classifications)
        json_path = self.config.storage_dir / "export_report.json"
        txt_path = self.config.storage_dir / "export_report.txt"

        export_report_json(
            summary=summary,
            reviews=self.reviews,
            classifications=self.classifications,
            output_path=json_path,
            model_metadata=self.config.get_sanitized_summary(),
        )
        export_report_txt(summary=summary, output_path=txt_path)

        print("\n[+] Reports exported successfully:")
        print(f"    - JSON: {json_path}")
        print(f"    - TXT:  {txt_path}")

    # -------------------------------------------------------------
    # 8. Run Engineering Self-Check Quiz
    # -------------------------------------------------------------
    def handle_self_check(self) -> None:
        print("\n" + "=" * 68)
        print("          ENGINEERING SELF-CHECK & CONCEPTUAL AUDIT")
        print("=" * 68)
        print("This audit tests your understanding of data trust boundaries,")
        print("schema contracts, LLM hallucination prevention, and evaluation.\n")

        session = QuizSession()

        for i, q in enumerate(session.questions, start=1):
            print(f"\n[Question {i}/{len(session.questions)}] ({q.id})")
            print(q.prompt)

            if q.question_type == "multiple_choice":
                assert q.options is not None
                for opt_key in sorted(q.options.keys()):
                    print(f"  {opt_key}) {q.options[opt_key]}")

                while True:
                    user_opt = input("\nYour answer (A/B/C/D): ").strip().upper()
                    if user_opt in ("A", "B", "C", "D"):
                        break
                    print("[!] Please enter A, B, C, or D.")

                is_correct, explanation = session.record_multiple_choice(q.id, user_opt)
                if is_correct:
                    print(f"[+] Correct! {explanation}")
                else:
                    print(f"[-] Incorrect. Correct option was ({q.correct_option}).")
                    print(f"    Explanation: {explanation}")

            elif q.question_type == "written_explanation":
                print("\n[Mentor Review Question - Minimum 10 characters]")
                while True:
                    response_text = input("Your explanation: ").strip()
                    success, msg = session.record_written_explanation(q.id, response_text)
                    if success:
                        print(f"[+] {msg}")
                        print(f"    Rubric Reference: {q.rubric}")
                        break
                    print(f"[!] {msg}")

        summary = session.get_summary()
        result_path = self.config.storage_dir / "self_check_results.json"
        session.save_results(result_path)

        print("\n" + "=" * 68)
        print("SELF-CHECK COMPLETE")
        print(f"Multiple Choice Score: {summary['multiple_choice_score']} ({summary['multiple_choice_percentage']}%)")
        print(f"Written Explanations Submitted: {summary['written_explanations_submitted']}")
        print(f"Submission saved to: {result_path}")
        print("=" * 68)
