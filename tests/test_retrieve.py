"""Unit tests for deterministic text retrieval engine."""

import unittest

from app.models import Review
from app.retrieve import retrieve_relevant_reviews, score_review_relevance, tokenize


class TestRetrievalEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = [
            Review(id="R001", event="Sound Fest", text="Headline DJ set was sensational with great bass.", created_at="2026-06-12"),
            Review(id="R002", event="Sound Fest", text="Waited 50 minutes in the taco queue.", created_at="2026-06-12"),
            Review(id="R003", event="Echo Bass", text="Loud sound and amazing lasers.", created_at="2026-07-04"),
            Review(id="R004", event="Echo Bass", text="Security guard was helpful at the gate.", created_at="2026-07-04"),
        ]

    def test_tokenize_and_stop_words(self) -> None:
        tokens = tokenize("What did attendees say about the long queues?")
        self.assertNotIn("what", tokens)
        self.assertNotIn("the", tokens)
        self.assertIn("attendees", tokens)
        self.assertIn("queues", tokens)

    def test_retrieve_relevant_reviews_matching(self) -> None:
        results = retrieve_relevant_reviews("taco queue", self.reviews, top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].id, "R002")

    def test_retrieve_empty_when_no_match(self) -> None:
        results = retrieve_relevant_reviews("unrelated elephant circus", self.reviews)
        self.assertEqual(len(results), 0)

    def test_top_k_limits(self) -> None:
        results = retrieve_relevant_reviews("sound fest", self.reviews, top_k=1)
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
