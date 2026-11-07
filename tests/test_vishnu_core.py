import tempfile
import unittest
from pathlib import Path

from indo_brain.vishnu_core import (
    build_vishnu_plan, vishnu_guidance, evaluate_vishnu_answer,
    select_provider, EvidenceLedger, MemoryVault, run_vishnu_smoke_benchmarks,
)


class VishnuCoreTests(unittest.TestCase):
    def test_research_pipeline_contains_evidence(self):
        p = build_vishnu_plan("Research the latest AI models with citations", "Research")
        self.assertIn("record_evidence", p["pipeline"])
        self.assertEqual(p["provider_calls_made"], 0)

    def test_coding_pipeline_contains_testing_stage(self):
        p = build_vishnu_plan("Debug this Python project", "Coding")
        self.assertIn("run_tests_if_available", p["pipeline"])

    def test_guidance_disallows_automatic_memory_writes(self):
        g = vishnu_guidance("Plan a project")
        self.assertIn("explicit user intent/consent", g)

    def test_evaluation_is_not_truth_claim(self):
        result = evaluate_vishnu_answer("Explain gravity", "Gravity is an attraction between masses.")
        self.assertIn("no factual verification", result["evaluation_boundary"])

    def test_provider_selection_respects_capability(self):
        result = select_provider([
            {"name": "fast-text", "available": True, "capabilities": ["text"], "latency_ms": 100, "cost_per_1k": 0.01},
            {"name": "vision-model", "available": True, "capabilities": ["text", "vision"], "latency_ms": 500, "cost_per_1k": 0.02},
        ], ["vision"])
        self.assertEqual(result["selected"], "vision-model")
        self.assertFalse(result["provider_call_made"])

    def test_provider_selection_returns_none_when_no_match(self):
        result = select_provider([{"name": "text", "available": True, "capabilities": ["text"]}], ["audio"])
        self.assertIsNone(result["selected"])

    def test_evidence_ledger_validates_urls(self):
        ledger = EvidenceLedger()
        ledger.add("Claim A", "Source A", "https://example.com/article", "supports")
        ledger.add("Claim A", "Source B", "https://example.org/article", "contradicts")
        self.assertTrue(ledger.summary()["has_conflict"])
        with self.assertRaises(ValueError):
            ledger.add("bad", "bad", "javascript:alert(1)")

    def test_memory_requires_explicit_consent_and_isolated_by_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = MemoryVault(Path(tmp) / "memory.sqlite3")
            with self.assertRaises(PermissionError):
                vault.remember("account-a", "Project fact")
            saved = vault.remember("account-a", "Project fact", consent=True, tags=["project"])
            self.assertEqual(len(vault.search("account-a", "project")), 1)
            self.assertEqual(vault.search("account-b", "project"), [])
            self.assertTrue(vault.forget("account-a", saved["memory_id"]))
            self.assertEqual(vault.search("account-a"), [])

    def test_memory_scope_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = MemoryVault(Path(tmp) / "memory.sqlite3")
            vault.remember("scope", "One", consent=True)
            vault.remember("scope", "Two", consent=True)
            self.assertEqual(vault.clear_scope("scope"), 2)

    def test_smoke_benchmark_cases(self):
        result = run_vishnu_smoke_benchmarks()
        self.assertEqual(result["passed"], result["total"])


if __name__ == "__main__":
    unittest.main()
