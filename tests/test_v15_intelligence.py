import unittest
from indo_brain.intelligence import plan_intelligence, intelligence_guidance, evaluate_response

class AdaptiveIntelligenceTests(unittest.TestCase):
    def test_fast_general_chat(self):
        p = plan_intelligence("hey bro")
        self.assertEqual(p["lane"], "fast")
        self.assertEqual(p["intent"], "general")

    def test_complex_coding_is_deep(self):
        p = plan_intelligence("Build a complete FastAPI app with OAuth, database, tests and deployment", "Coding")
        self.assertEqual(p["lane"], "deep")
        self.assertIn("preserve existing interfaces and data", p["acceptance_criteria"])

    def test_research_requires_retrieval_when_available(self):
        p = plan_intelligence("Research the latest AI releases with sources", "Research")
        self.assertIn("live_retrieval_if_available", p["tool_requirements"])

    def test_math_requires_check(self):
        p = plan_intelligence("Calculate 19 * 27")
        self.assertIn("recheck arithmetic", p["acceptance_criteria"])

    def test_education_is_not_overrouted(self):
        p = plan_intelligence("Explain photosynthesis for class 7", "Study")
        self.assertEqual(p["lane"], "standard")

    def test_short_creative_is_fast(self):
        p = plan_intelligence("Write a short poem about rain", "Creative")
        self.assertEqual(p["lane"], "fast")

    def test_attachments_add_complexity(self):
        no_file = plan_intelligence("Summarize this", attachment_count=0)
        with_file = plan_intelligence("Summarize this", attachment_count=2)
        self.assertGreater(with_file["complexity"], no_file["complexity"])
        self.assertIn("inspect_supported_attachment_content", with_file["tool_requirements"])

    def test_guidance_disallows_simulated_tools(self):
        guidance = intelligence_guidance(plan_intelligence("latest AI news", "Research"))
        self.assertIn("never simulate tool use", guidance)

    def test_evaluator_is_explicitly_not_truth_score(self):
        result = evaluate_response("Explain photosynthesis", "Photosynthesis converts light energy into chemical energy.")
        self.assertTrue(result["checks"]["nonempty"])
        self.assertIn("not factual accuracy", result["score_type"])

    def test_unclosed_code_fence_is_flagged(self):
        result = evaluate_response("Write code", "```python\nprint('hello')")
        self.assertFalse(result["checks"]["no_obvious_unclosed_code_fence"])

    def test_empty_answer_is_flagged(self):
        result = evaluate_response("Explain gravity", "")
        self.assertFalse(result["checks"]["nonempty"])

    def test_planner_does_not_mutate_input(self):
        msg = "Design a secure project"
        plan_intelligence(msg)
        self.assertEqual(msg, "Design a secure project")

if __name__ == "__main__":
    unittest.main()
