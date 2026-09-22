import os
import sys
import unittest
from pathlib import Path


WORKERS = Path(__file__).resolve().parents[1]
if str(WORKERS) not in sys.path:
    sys.path.insert(0, str(WORKERS))

from pipeline_core import hashtags_from_keywords, slugify, term_density_score, topic_relevance  # noqa: E402
from llm_blogger import code_fence_quality, quality_check  # noqa: E402


class PipelineCoreTests(unittest.TestCase):
    def test_slug_is_bounded_and_stable(self):
        value = slugify("PostgreSQL: Deadlocks, Pool Saturation & Production Recovery")
        self.assertEqual(value, "postgresql-deadlocks-pool-saturation-production-recovery")
        self.assertLessEqual(len(value), 78)

    def test_hashtags_are_deduplicated_and_safe(self):
        tags = hashtags_from_keywords(["node.js", "Node JS", "eBPF observability", "x" * 50])
        self.assertEqual(tags[0], "#NodeJs")
        self.assertIn("#EbpfObservability", tags)
        self.assertEqual(len(tags), len(set(tags)))
        self.assertTrue(all(len(tag) <= 29 for tag in tags))

    def test_problem_intent_increases_score(self):
        calm = term_density_score("general software overview", {"incident", "debug"})
        urgent = term_density_score("production incident debug workflow", {"incident", "debug"})
        self.assertGreater(urgent, calm)

    def test_smart_goals_cannot_pass_smart_contract_gate(self):
        result = topic_relevance(
            "How to write SMART goals for project management and personal development",
            "smart contract security audit for reentrancy and signature attacks",
            ["solidity", "smart contract", "wallet", "reentrancy", "signature"],
        )
        self.assertFalse(result["passed"])

    def test_relevant_smart_contract_source_passes(self):
        result = topic_relevance(
            "Solidity smart contract reentrancy defense and signature validation audit",
            "smart contract security audit for reentrancy and signature attacks",
            ["solidity", "smart contract", "wallet", "reentrancy", "signature"],
        )
        self.assertTrue(result["passed"])


class EditorialQualityTests(unittest.TestCase):
    def setUp(self):
        self.old_min = os.environ.get("MIN_POST_WORDS")

    def tearDown(self):
        if self.old_min is None:
            os.environ.pop("MIN_POST_WORDS", None)
        else:
            os.environ["MIN_POST_WORDS"] = self.old_min

    def test_quality_rejects_unsupported_links_and_thin_copy(self):
        context = {
            "sources": [
                {"url": "https://docs.example.test/a", "evidence_excerpt": "bounded source excerpt"},
                {"url": "https://docs.example.test/b", "evidence_excerpt": "second source excerpt"},
                {"url": "https://docs.example.test/c", "evidence_excerpt": "third source excerpt"},
            ]
        }
        body = """# Thin\n\n## A\nText [bad](https://invented.example/x).\n\n```sh\necho ok\n```"""
        result = quality_check(body, context, "Thin")
        self.assertFalse(result["passed"])
        self.assertTrue(any("not present" in failure for failure in result["failures"]))
        self.assertTrue(any("word count" in failure for failure in result["failures"]))

    def test_code_fence_rejects_language_on_closing_fence(self):
        result = code_fence_quality("```python\nprint('ok')\n```python")
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
