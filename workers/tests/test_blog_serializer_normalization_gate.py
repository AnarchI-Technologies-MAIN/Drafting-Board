from __future__ import annotations

import copy
import unittest

from blog_loop.legacy_bridge import LegacyNormalizationError
from blog_loop.serialization import prepare_serializable_source_bundle


NOW = "2026-08-28T12:00:00Z"


def policy() -> dict:
    return {
        "schema": "anarchi.editorial-intake-policy.v1",
        "minimum_total_score": 72,
        "minimum_value_score": 55,
        "minimum_problem_score": 55,
        "max_new_queries_per_cycle": 12,
        "max_signal_queries_per_cluster": 4,
        "scoring_note": "fixture",
        "clusters": [
            {
                "id": "node-platform-failures",
                "label": "Node.js platform failures",
                "keywords": [
                    "node.js",
                    "memory leak",
                    "event loop",
                ],
                "queries": [
                    "Node.js production memory leak and event loop latency debugging",
                ],
                "commercial_base": 78,
                "problem_base": 96,
                "intent": "developer-problem-solution",
            }
        ],
    }


def intake() -> dict:
    query = "Node.js production memory leak and event loop latency debugging"

    return {
        "id": 10,
        "query": query,
        "topic_cluster": "node-platform-failures",
        "search_intent": "developer-problem-solution",
        "total_score": 84,
        "claimed_at": None,
        "last_error": None,
        "seo_plan": {
            "primary_query": query,
            "secondary_keywords": [
                "node.js",
                "memory leak",
                "event loop",
            ],
            "intent": "developer-problem-solution",
            "title_pattern": f"{query}: evidence and verification",
            "required_sections": [
                "symptoms and impact",
                "root-cause model",
                "verification and observability",
            ],
            "measurement_disclaimer": "not measured search volume or CPC",
        },
    }


def packets() -> list[dict]:
    query = "Node.js production memory leak and event loop latency debugging"

    return [
        {
            "id": 1,
            "packet_type": "search_intake",
            "producer": "research-bot",
            "packet_hash": "legacy-search",
            "created_at": NOW,
            "payload": {
                "schema": "anarchi.search-intake.v1",
                "query": query,
                "scores": {
                    "traffic_score": 80,
                    "value_score": 78,
                    "problem_score": 96,
                    "trend_score": 75,
                    "total_score": 84,
                    "tier": 4,
                },
                "evidence": [
                    {
                        "source": "hacker-news-algolia",
                        "title": query,
                        "url": "https://news.ycombinator.com/item?id=123",
                        "engagement": 250,
                        "points": 150,
                        "comments": 50,
                        "observed_at": NOW,
                        "matched_keywords": ["node.js"],
                    }
                ],
                "seo_plan": {
                    "primary_query": query,
                    "secondary_keywords": [
                        "node.js",
                        "memory leak",
                        "event loop",
                    ],
                    "intent": "developer-problem-solution",
                    "title_pattern": f"{query}: evidence and verification",
                    "required_sections": [
                        "symptoms and impact",
                        "root-cause model",
                        "verification and observability",
                    ],
                    "measurement_disclaimer": "not measured search volume or CPC",
                },
                "captured_at": NOW,
            },
        },
        {
            "id": 2,
            "packet_type": "source_document",
            "producer": "crawler-bot",
            "packet_hash": "legacy-doc",
            "created_at": NOW,
            "payload": {
                "schema": "anarchi.source-document.v1",
                "query": query,
                "provider": "nodejs-docs",
                "title": "Node.js diagnostics documentation",
                "url": "https://nodejs.org/docs/example",
                "search_snippet": "Node.js diagnostics guidance.",
                "metrics": {},
                "page": {
                    "excerpt": (
                        "Bounded evidence about Node.js diagnostics, "
                        "memory behavior, and event-loop operation."
                    ),
                    "canonical_url": "https://nodejs.org/docs/example",
                    "retrieved_at": NOW,
                },
                "keywords": [
                    "node.js",
                    "memory leak",
                    "event loop",
                ],
                "relevance": {
                    "score": 91,
                    "passed": True,
                    "surface": {"passed": True},
                    "authoritative_domain": True,
                    "policy_version": 2,
                },
                "captured_at": NOW,
            },
        },
    ]


class SerializerNormalizationGateTests(unittest.TestCase):
    def test_valid_legacy_material_earns_generation_admission(self):
        result = prepare_serializable_source_bundle(
            intake(),
            packets(),
            policy=policy(),
        )

        self.assertEqual(
            result["generation_admission"]["state"],
            "NORMALIZATION_PASSED",
        )

        self.assertEqual(
            result["generation_admission"]["bridge_digest"],
            result["normalization"]["bridge_digest"],
        )

        self.assertEqual(
            result["generation_admission"]["article_input_digest"],
            result["normalization"]["article_input"]["article_input_digest"],
        )

    def test_generation_admission_has_no_authority(self):
        result = prepare_serializable_source_bundle(
            intake(),
            packets(),
            policy=policy(),
        )

        admission = result["generation_admission"]

        self.assertEqual(admission["factual_authority"], "NONE")
        self.assertEqual(admission["publication_authority"], "NONE")
        self.assertEqual(admission["approval"], "NONE")

    def test_normalization_receipt_is_physically_embedded(self):
        result = prepare_serializable_source_bundle(
            intake(),
            packets(),
            policy=policy(),
        )

        self.assertEqual(
            result["normalization"]["schema"],
            "anarchi.legacy-blog-normalization.v1",
        )

        self.assertIn(
            "keyword_receipt",
            result["normalization"],
        )

        self.assertIn(
            "topic_packet",
            result["normalization"],
        )

        self.assertIn(
            "article_input",
            result["normalization"],
        )

    def test_missing_search_packet_cannot_serialize(self):
        fixture = [
            item
            for item in packets()
            if item["packet_type"] != "search_intake"
        ]

        with self.assertRaises(LegacyNormalizationError):
            prepare_serializable_source_bundle(
                intake(),
                fixture,
                policy=policy(),
            )

    def test_missing_evidence_cannot_serialize(self):
        fixture = [
            item
            for item in packets()
            if item["packet_type"] != "source_document"
        ]

        with self.assertRaises(LegacyNormalizationError):
            prepare_serializable_source_bundle(
                intake(),
                fixture,
                policy=policy(),
            )

    def test_unknown_niche_cannot_serialize(self):
        fixture = intake()
        fixture["topic_cluster"] = "unknown-cluster"
        fixture["query"] = "Unknown unrelated subject"

        with self.assertRaises(LegacyNormalizationError):
            prepare_serializable_source_bundle(
                fixture,
                packets(),
                policy=policy(),
            )

    def test_replay_is_deterministic(self):
        first = prepare_serializable_source_bundle(
            copy.deepcopy(intake()),
            copy.deepcopy(packets()),
            policy=copy.deepcopy(policy()),
        )

        second = prepare_serializable_source_bundle(
            copy.deepcopy(intake()),
            copy.deepcopy(packets()),
            policy=copy.deepcopy(policy()),
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
