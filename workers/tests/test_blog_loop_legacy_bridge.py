from __future__ import annotations

import copy
import unittest

from blog_loop.legacy_bridge import (
    LegacyNormalizationError,
    normalize_legacy_bundle,
)


NOW = "2026-08-28T12:00:00Z"
EARLIER = "2026-08-28T11:55:00Z"


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
                    "typescript",
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


def source_document() -> dict:
    return {
        "schema": "anarchi.source-document.v1",
        "query": "Node.js production memory leak and event loop latency debugging",
        "provider": "nodejs-docs",
        "title": "Node.js diagnostics documentation",
        "url": "https://nodejs.org/docs/example",
        "search_snippet": "Node.js diagnostics guidance for memory and event-loop behavior.",
        "metrics": {},
        "page": {
            "excerpt": (
                "This fixture contains bounded documentation evidence about "
                "Node.js diagnostics, memory behavior, and the event loop."
            ),
            "excerpt_hash": "sha256:fixture-not-authoritative",
            "canonical_url": "https://nodejs.org/docs/example",
            "retrieved_at": NOW,
        },
        "keywords": ["node.js", "memory leak", "event loop"],
        "relevance": {
            "score": 91,
            "passed": True,
            "surface": {"passed": True},
            "authoritative_domain": True,
            "policy_version": 2,
        },
        "captured_at": NOW,
    }


def bundle(
    *,
    query: str,
    signal_title: str,
    cluster_id: str = "node-platform-failures",
) -> dict:
    return {
        "schema": "anarchi.editorial-source-bundle.v1",
        "intake": {
            "id": 10,
            "query": query,
            "topic_cluster": cluster_id,
            "search_intent": "developer-problem-solution",
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
                "measurement_disclaimer": (
                    "not measured search volume or CPC"
                ),
            },
        },
        "packets": [
            {
                "id": 1,
                "packet_type": "search_intake",
                "producer": "research-bot",
                "packet_hash": "legacy-search",
                "created_at": EARLIER,
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
                            "title": signal_title,
                            "url": "https://news.ycombinator.com/item?id=123",
                            "engagement": 250,
                            "points": 150,
                            "comments": 50,
                            "observed_at": EARLIER,
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
                        "measurement_disclaimer": (
                            "not measured search volume or CPC"
                        ),
                    },
                    "captured_at": EARLIER,
                },
            },
            {
                "id": 2,
                "packet_type": "source_document",
                "producer": "crawler-bot",
                "packet_hash": "legacy-doc",
                "created_at": NOW,
                "payload": source_document(),
            },
            {
                "id": 3,
                "packet_type": "affiliate_opportunity",
                "producer": "outreach-bot",
                "packet_hash": "legacy-affiliate",
                "created_at": NOW,
                "payload": {
                    "schema": "anarchi.affiliate-opportunity.v1",
                    "name": "Example Monitoring Tool",
                    "category": "observability",
                    "verification_status": "verified",
                    "destination_url": "https://example.com/tool",
                    "observed_at": NOW,
                },
            },
        ],
    }


class LegacyBridgeTests(unittest.TestCase):
    def test_exact_public_signal_title_earns_live_keyword(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(query=query, signal_title=query),
            policy(),
        )

        keyword = result["keyword_receipt"]

        self.assertEqual(
            keyword["keyword_state"],
            "LIVE_ACQUIRED_KEYWORD",
        )
        self.assertEqual(
            keyword["provider"],
            "hacker-news-algolia",
        )
        self.assertEqual(
            keyword["raw_source_reference"],
            "https://news.ycombinator.com/item?id=123",
        )

    def test_curated_policy_query_is_not_promoted_to_live(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(
                query=query,
                signal_title="A different Node.js discussion",
            ),
            policy(),
        )

        keyword = result["keyword_receipt"]

        self.assertEqual(
            keyword["keyword_state"],
            "DERIVED_KEYWORD",
        )
        self.assertEqual(
            keyword["acquisition_method"],
            "CURATED_POLICY_QUERY",
        )
        self.assertIsNone(keyword["raw_source_reference"])

    def test_niche_is_reearned_from_policy_not_cluster_label_alone(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(
                query=query,
                signal_title="A different Node.js discussion",
            ),
            policy(),
        )

        self.assertEqual(
            result["niche_assessment"]["disposition"],
            "IN_NICHE",
        )

    def test_unknown_cluster_fails_closed_before_topic_qualification(self):
        query = "Completely unrelated unknown subject"

        fixture = bundle(
            query=query,
            signal_title=query,
            cluster_id="unknown-cluster",
        )

        with self.assertRaises(LegacyNormalizationError):
            normalize_legacy_bundle(fixture, policy())

    def test_source_without_canonical_age_policy_remains_unknown(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(query=query, signal_title=query),
            policy(),
        )

        self.assertEqual(
            result["evidence_receipts"][0]["freshness_state"],
            "UNKNOWN",
        )
        self.assertEqual(
            result["freshness_policy_state"],
            "NOT_DEFINED",
        )

    def test_legacy_affiliate_is_hint_not_candidate(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(query=query, signal_title=query),
            policy(),
        )

        self.assertIn(
            "Example Monitoring Tool",
            result["legacy_affiliate_hints"],
        )
        self.assertEqual(
            result["affiliate_candidate_digests"],
            [],
        )
        self.assertEqual(
            result["article_input"]["affiliate_candidate_digests"],
            [],
        )

    def test_missing_source_document_fails_closed(self):
        query = "Node.js production memory leak and event loop latency debugging"

        fixture = bundle(query=query, signal_title=query)
        fixture["packets"] = [
            item
            for item in fixture["packets"]
            if item["packet_type"] != "source_document"
        ]

        with self.assertRaises(LegacyNormalizationError):
            normalize_legacy_bundle(fixture, policy())

    def test_replay_is_byte_semantically_deterministic(self):
        query = "Node.js production memory leak and event loop latency debugging"
        fixture = bundle(query=query, signal_title=query)

        first = normalize_legacy_bundle(
            copy.deepcopy(fixture),
            copy.deepcopy(policy()),
        )
        second = normalize_legacy_bundle(
            copy.deepcopy(fixture),
            copy.deepcopy(policy()),
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first["bridge_digest"],
            second["bridge_digest"],
        )

    def test_bridge_grants_no_authority(self):
        query = "Node.js production memory leak and event loop latency debugging"

        result = normalize_legacy_bundle(
            bundle(query=query, signal_title=query),
            policy(),
        )

        self.assertEqual(result["factual_authority"], "NONE")
        self.assertEqual(result["publication_authority"], "NONE")
        self.assertEqual(result["approval"], "NONE")

        for receipt_name in (
            "keyword_receipt",
            "niche_assessment",
            "topic_packet",
            "seo_plan",
            "article_input",
        ):
            receipt = result[receipt_name]
            self.assertEqual(receipt["factual_authority"], "NONE")
            self.assertEqual(receipt["publication_authority"], "NONE")
            self.assertEqual(receipt["approval"], "NONE")

        for receipt in result["evidence_receipts"]:
            self.assertEqual(receipt["factual_authority"], "NONE")
            self.assertEqual(receipt["publication_authority"], "NONE")
            self.assertEqual(receipt["approval"], "NONE")


if __name__ == "__main__":
    unittest.main()
