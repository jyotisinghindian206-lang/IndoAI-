import unittest
from unittest.mock import patch

from indo_brain.evaluation import CASES, CATEGORY_TARGETS, validate_suite, score_answer, run_local_benchmark


class IntelligenceBenchmarkTests(unittest.TestCase):
    def test_suite_has_expected_140_cases_and_unique_ids(self):
        status = validate_suite()
        self.assertTrue(status["valid"])
        self.assertEqual(status["total"], 140)
        self.assertEqual(status["unique_ids"], 140)
        self.assertEqual(status["category_counts"], CATEGORY_TARGETS)

    def test_general_knowledge_alias_scoring(self):
        case = next(x for x in CASES if x["id"] == "GK-001")
        self.assertEqual(score_answer(case, "The chemical symbol is Au." )["status"], "passed")
        self.assertEqual(score_answer(case, "The chemical symbol is Ag." )["status"], "failed")

    def test_numeric_scoring_uses_boundaries_and_normalizes_percent_and_commas(self):
        case = {"scoring": "all_terms", "expected": ["2450", "70%"]}
        self.assertEqual(score_answer(case, "Subtotal INR 2,450; target is 70 percent.")["status"], "passed")
        self.assertEqual(score_answer({"scoring": "contains_any", "expected": ["7"]}, "The result is 70.")["status"], "failed")

    def test_long_context_requires_every_expected_value(self):
        case = next(x for x in CASES if x["id"] == "LC-001")
        good = "PROJECT-01 Team A Pune Monday 12000 70%"
        bad = "PROJECT-01 Team A Pune Monday 12000"
        self.assertEqual(score_answer(case, good)["status"], "passed")
        self.assertEqual(score_answer(case, bad)["status"], "failed")

    def test_coding_is_never_auto_scored_or_executed(self):
        case = next(x for x in CASES if x["category"] == "coding")
        scored = score_answer(case, "print('hello')")
        self.assertEqual(scored["status"], "needs_human_review")
        self.assertIsNone(scored["score"])

    def test_image_cases_are_not_claimed_as_run(self):
        case = next(x for x in CASES if x["category"] == "multimodal_image")
        self.assertEqual(score_answer(case, "looks like a chart")["status"], "not_run_missing_vision_fixture")

    def test_runner_uses_mocked_local_inference_and_reports_metrics(self):
        with patch("indo_brain.evaluation.runner._ollama_generate", return_value=("Au", 125.0)):
            report = run_local_benchmark(base_url="http://127.0.0.1:11434", model="test-model", limit=1)
        self.assertTrue(report["suite_valid"])
        self.assertEqual(report["selected"], 1)
        self.assertEqual(report["objective_accuracy"], 1.0)
        self.assertEqual(report["mean_latency_ms"], 125.0)
        self.assertEqual(report["provider"], "ollama_local")

    def test_full_suite_report_separates_objective_manual_and_image_cases(self):
        expected_by_prompt = {case["prompt"]: case.get("expected") for case in CASES}
        def fake_generate(base_url, model, prompt, timeout):
            expected = expected_by_prompt[prompt]
            return (", ".join(expected) if expected else "candidate solution for review", 10.0)
        with patch("indo_brain.evaluation.runner._ollama_generate", side_effect=fake_generate):
            report = run_local_benchmark(base_url="http://127.0.0.1:11434", model="test-model", limit=140)
        self.assertEqual(report["selected"], 140)
        self.assertEqual(report["objective_scored"], 110)
        self.assertEqual(report["category_summary"]["coding"]["human_review"], 20)
        self.assertEqual(report["category_summary"]["multimodal_image"]["not_run"], 10)
        self.assertEqual(report["objective_accuracy"], 1.0)

    def test_runner_offset_selects_next_batch_without_repeating_first_case(self):
        with patch("indo_brain.evaluation.runner._ollama_generate", return_value=("Mars", 15.0)):
            report = run_local_benchmark(base_url="http://127.0.0.1:11434", model="test-model", limit=1, offset=1)
        self.assertEqual(report["offset"], 1)
        self.assertEqual(report["results"][0]["id"], "GK-002")

    def test_runner_rejects_unknown_category(self):
        with self.assertRaises(ValueError):
            run_local_benchmark(base_url="http://127.0.0.1:11434", model="test", categories=["made_up"])


if __name__ == "__main__":
    unittest.main()
