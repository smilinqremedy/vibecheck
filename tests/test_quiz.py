"""Unit tests for Engineering Self-Check quiz engine and assessment scoring."""

import tempfile
import unittest
from pathlib import Path

from app.quiz import QuizQuestion, QuizSession


class TestQuizEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_quiz_initialization(self) -> None:
        session = QuizSession()
        self.assertGreaterEqual(len(session.questions), 8)
        # Verify at least 4 multiple choice and at least 4 written questions
        mc_questions = [q for q in session.questions if q.question_type == "multiple_choice"]
        written_questions = [q for q in session.questions if q.question_type == "written_explanation"]
        self.assertGreaterEqual(len(mc_questions), 4)
        self.assertGreaterEqual(len(written_questions), 4)

    def test_record_multiple_choice_correct_and_incorrect(self) -> None:
        custom_q = [
            QuizQuestion(
                id="Q01",
                prompt="Test prompt",
                question_type="multiple_choice",
                options={"A": "opt A", "B": "opt B"},
                correct_option="A",
                explanation="Explanation A",
            )
        ]
        session = QuizSession(questions=custom_q)

        # Invalid option rejected
        success, err = session.record_multiple_choice("Q01", "Z")
        self.assertFalse(success)
        self.assertIn("Invalid option", err)

        # Correct option scored
        success, explanation = session.record_multiple_choice("Q01", "A")
        self.assertTrue(success)
        self.assertEqual(session.mc_correct_count, 1)
        self.assertEqual(session.mc_total_count, 1)

    def test_record_written_explanation(self) -> None:
        custom_q = [
            QuizQuestion(
                id="Q06",
                prompt="Explain quote check",
                question_type="written_explanation",
                rubric="Rubric details",
            )
        ]
        session = QuizSession(questions=custom_q)

        # Too short explanation rejected
        success, msg = session.record_written_explanation("Q06", "too short")
        self.assertFalse(success)
        self.assertIn("too brief", msg)

        # Valid explanation accepted
        success, msg = session.record_written_explanation(
            "Q06", "Verifying the verbatim substring ensures the claim is strictly grounded."
        )
        self.assertTrue(success)
        summary = session.get_summary()
        self.assertEqual(summary["written_explanations_submitted"], 1)

    def test_save_results(self) -> None:
        session = QuizSession()
        session.record_multiple_choice("Q01", "B")
        out_file = self.tmp_path / "quiz_results.json"
        saved = session.save_results(out_file)
        self.assertTrue(saved.is_file())
        content = saved.read_text(encoding="utf-8")
        self.assertIn("multiple_choice_score", content)


if __name__ == "__main__":
    unittest.main()
