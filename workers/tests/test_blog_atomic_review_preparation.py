from __future__ import annotations

import copy
import unittest

from blog_loop.atomic_review import (
    AtomicReviewPreparationError,
    build_atomic_review_case,
    validate_atomic_review_case,
)
from blog_loop.serialization import (
    prepare_serializable_source_bundle,
)


NOW = "2026-08-28T12:00:00Z"

QUERY = (
    "Node.js production memory leak and event loop latency debugging"
)

ARTICLE = """# Diagnosing Node.js memory pressure

Node.js applications can expose memory behavior through runtime diagnostics.

A growing heap may indicate retained objects or other memory pressure.

Engineers should compare repeated observations before attributing a production failure to one cause.
"""


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
                    "heap",
                ],
                "queries": [QUERY],
                "commercial_base": 78,
                "problem_base": 96,
                "intent": "developer-problem-solution",
            }
        ],
    }


def intake() -> dict:
    return {
        "id": 10,
        "query": QUERY,
        "topic_cluster": "node-platform-failures",
        "search_intent": "developer-problem-solution",
        "total_score": 84,
        "claimed_at": None,
        "last_error": None,
        "seo_plan": {
            "primary_query": QUERY,
            "secondary_keywords": [
                "node.js",
                "memory leak",
                "event loop",
                "heap",
            ],
            "intent": "developer-problem-solution",
            "title_pattern": (
                f"{QUERY}: evidence and verification"
            ),
            "required_sections": [
                "symptoms and impact",
                "root-cause model",
                "verification and observability",
            ],
            "measurement_disclaimer": (
                "not measured search volume or CPC"
            ),
        },
    }


def packets() -> list[dict]:
    return [
        {
            "id": 1,
            "packet_type": "search_intake",
            "producer": "research-bot",
            "packet_hash": "legacy-search",
            "created_at": NOW,
            "payload": {
                "schema": "anarchi.search-intake.v1",
                "query": QUERY,
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
                        "title": QUERY,
                        "url": (
                            "https://news.ycombinator.com/"
                            "item?id=123"
                        ),
                        "engagement": 250,
                        "points": 150,
                        "comments": 50,
                        "observed_at": NOW,
                        "matched_keywords": [
                            "node.js",
                            "memory leak",
                        ],
                    }
                ],
                "seo_plan": {
                    "primary_query": QUERY,
                    "secondary_keywords": [
                        "node.js",
                        "memory leak",
                        "event loop",
                        "heap",
                    ],
                    "intent": "developer-problem-solution",
                    "title_pattern": (
                        f"{QUERY}: evidence and verification"
                    ),
                    "required_sections": [
                        "symptoms and impact",
                        "root-cause model",
                        "verification and observability",
                    ],
                    "measurement_disclaimer": (
                        "not measured search volume or CPC"
                    ),
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
                "query": QUERY,
                "provider": "nodejs-docs",
                "title": "Node.js diagnostics documentation",
                "url": "https://nodejs.org/docs/example",
                "search_snippet": (
                    "Node.js runtime diagnostics expose "
                    "information about heap and memory behavior."
                ),
                "metrics": {},
                "page": {
                    "excerpt": (
                        "Node.js runtime diagnostics can expose "
                        "memory and heap behavior. Repeated "
                        "observations can help engineers investigate "
                        "retained objects and event-loop behavior."
                    ),
                    "canonical_url": (
                        "https://nodejs.org/docs/example"
                    ),
                    "retrieved_at": NOW,
                },
                "keywords": [
                    "node.js",
                    "memory leak",
                    "event loop",
                    "heap",
                ],
                "relevance": {
                    "score": 91,
                    "passed": True,
                    "surface": {
                        "passed": True,
                    },
                    "authoritative_domain": True,
                    "policy_version": 2,
                },
                "captured_at": NOW,
            },
        },
    ]


def admitted_bundle() -> dict:
    return prepare_serializable_source_bundle(
        intake(),
        packets(),
        policy=policy(),
    )


class AtomicReviewPreparationTests(unittest.TestCase):
    def test_exact_article_becomes_canonical_claim_ledger(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertEqual(
            case.article_digest,
            case.claim_ledger.article_digest,
        )

        self.assertGreater(
            case.claim_ledger.claim_count,
            0,
        )

        self.assertGreater(
            case.claim_ledger.material_count,
            0,
        )

    def test_every_claim_gets_evidence_set_and_verifier_case(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertEqual(
            len(case.claim_ledger.claims),
            len(case.evidence_sets),
        )

        self.assertEqual(
            len(case.claim_ledger.claims),
            len(case.verifier_cases),
        )

    def test_relevant_source_packet_becomes_evidence_source(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertEqual(
            len(case.evidence_sources),
            1,
        )

        self.assertEqual(
            case.evidence_sources[0].packet_id,
            2,
        )

        self.assertEqual(
            case.evidence_sources[0].url,
            "https://nodejs.org/docs/example",
        )

    def test_case_does_not_grant_authority(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertFalse(case.factual_authority)
        self.assertFalse(case.adjudication_authority)
        self.assertFalse(case.publication_authority)

    def test_raw_legacy_bundle_without_admission_is_rejected(self):
        raw = {
            "schema": "anarchi.editorial-source-bundle.v1",
            "intake": intake(),
            "packets": packets(),
        }

        with self.assertRaises(
            AtomicReviewPreparationError
        ):
            build_atomic_review_case(
                article_text=ARTICLE,
                source_bundle=raw,
            )

    def test_tampered_bridge_digest_is_rejected(self):
        fixture = admitted_bundle()

        fixture["normalization"][
            "legacy_bundle_digest"
        ] = "tampered"

        with self.assertRaises(
            AtomicReviewPreparationError
        ):
            build_atomic_review_case(
                article_text=ARTICLE,
                source_bundle=fixture,
            )

    def test_tampered_generation_binding_is_rejected(self):
        fixture = admitted_bundle()

        fixture["generation_admission"][
            "article_input_digest"
        ] = "tampered"

        with self.assertRaises(
            AtomicReviewPreparationError
        ):
            build_atomic_review_case(
                article_text=ARTICLE,
                source_bundle=fixture,
            )

    def test_no_review_eligible_source_fails_closed(self):
        fixture = admitted_bundle()

        for packet in fixture["packets"]:
            if packet.get("packet_type") == "source_document":
                packet["payload"]["relevance"]["passed"] = False

        with self.assertRaises(
            AtomicReviewPreparationError
        ):
            build_atomic_review_case(
                article_text=ARTICLE,
                source_bundle=fixture,
            )

    def test_article_with_no_material_claims_fails_closed(self):
        with self.assertRaises(
            AtomicReviewPreparationError
        ):
            build_atomic_review_case(
                article_text="# Heading only\n",
                source_bundle=admitted_bundle(),
            )

    def test_replay_is_deterministic(self):
        first = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=copy.deepcopy(
                admitted_bundle()
            ),
        )

        second = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=copy.deepcopy(
                admitted_bundle()
            ),
        )

        self.assertEqual(first, second)

    def test_case_revalidation_succeeds(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertEqual(
            validate_atomic_review_case(case),
            case,
        )


if __name__ == "__main__":
    unittest.main()
