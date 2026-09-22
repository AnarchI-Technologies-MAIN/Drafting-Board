from __future__ import annotations

import copy
import json
import unittest

from blog_loop.atomic_review import (
    build_atomic_review_case,
)
from blog_loop.review_execution import (
    AtomicReviewExecutionError,
    execute_atomic_review,
)
from blog_loop.serialization import (
    prepare_serializable_source_bundle,
)
from editorial_verifier import (
    CalibrationVerdict,
    VerificationVerdict,
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


def review_case():
    return build_atomic_review_case(
        article_text=ARTICLE,
        source_bundle=admitted_bundle(),
    )


def supported_verifier(case, prompt) -> str:
    eligible = sorted(
        case.eligible_packet_ids
    )

    if not eligible:
        verdict = (
            VerificationVerdict.INSUFFICIENT_EVIDENCE.value
        )
        relied = []
    else:
        verdict = VerificationVerdict.SUPPORTED.value
        relied = [eligible[0]]

    return json.dumps(
        {
            "claim_id": case.claim.claim_id,
            "verdict": verdict,
            "calibration": CalibrationVerdict.PRECISE.value,
            "relied_on_packet_ids": relied,
            "rationale": (
                "fixture verdict grounded only in supplied evidence"
            ),
        },
        sort_keys=True,
    )


class ReviewExecutionTests(unittest.TestCase):
    def test_supported_fixture_builds_reviewed_artifact(self):
        result = execute_atomic_review(
            case=review_case(),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        self.assertEqual(
            result.reviewed_artifact.article_digest,
            result.case.article_digest,
        )

        self.assertEqual(
            len(result.claim_verifications),
            len(result.case.claim_ledger.claims),
        )

    def test_all_fixture_claims_pass_text_review(self):
        result = execute_atomic_review(
            case=review_case(),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        self.assertTrue(
            result.text_review_passed
        )

        self.assertTrue(
            result.article_verification.passed
        )

    def test_passed_text_review_still_cannot_publish(self):
        result = execute_atomic_review(
            case=review_case(),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        self.assertTrue(
            result.text_review_passed
        )

        self.assertFalse(
            result.human_adjudication_permitted
        )

        self.assertFalse(
            result.publication_permitted
        )

        self.assertFalse(
            result.reviewed_artifact.human_adjudication_permitted
        )

        self.assertFalse(
            result.reviewed_artifact.publication_permitted
        )

    def test_verifier_is_called_once_per_atomic_claim(self):
        calls = []

        def recorder(case, prompt):
            calls.append(
                (
                    case.claim.claim_id,
                    prompt,
                )
            )

            return supported_verifier(
                case,
                prompt,
            )

        case = review_case()

        execute_atomic_review(
            case=case,
            verifier=recorder,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        self.assertEqual(
            len(calls),
            len(case.claim_ledger.claims),
        )

        self.assertEqual(
            [item[0] for item in calls],
            [
                claim.claim_id
                for claim in case.claim_ledger.claims
            ],
        )

    def test_unknown_evidence_packet_is_rejected(self):
        def bad_verifier(case, prompt):
            return json.dumps(
                {
                    "claim_id": case.claim.claim_id,
                    "verdict": VerificationVerdict.SUPPORTED.value,
                    "calibration": CalibrationVerdict.PRECISE.value,
                    "relied_on_packet_ids": [999999],
                    "rationale": "invalid fixture",
                }
            )

        with self.assertRaises(
            AtomicReviewExecutionError
        ):
            execute_atomic_review(
                case=review_case(),
                verifier=bad_verifier,
                verifier_model="fixture-verifier",
                verifier_run_id="run-bad",
            )

    def test_wrong_claim_identity_is_rejected(self):
        def bad_verifier(case, prompt):
            return json.dumps(
                {
                    "claim_id": "claim-not-the-case",
                    "verdict": VerificationVerdict.SUPPORTED.value,
                    "calibration": CalibrationVerdict.PRECISE.value,
                    "relied_on_packet_ids": list(
                        sorted(case.eligible_packet_ids)
                    )[:1],
                    "rationale": "invalid fixture",
                }
            )

        with self.assertRaises(
            AtomicReviewExecutionError
        ):
            execute_atomic_review(
                case=review_case(),
                verifier=bad_verifier,
                verifier_model="fixture-verifier",
                verifier_run_id="run-bad",
            )

    def test_supported_without_evidence_is_rejected(self):
        def bad_verifier(case, prompt):
            return json.dumps(
                {
                    "claim_id": case.claim.claim_id,
                    "verdict": VerificationVerdict.SUPPORTED.value,
                    "calibration": CalibrationVerdict.PRECISE.value,
                    "relied_on_packet_ids": [],
                    "rationale": "invalid fixture",
                }
            )

        with self.assertRaises(
            AtomicReviewExecutionError
        ):
            execute_atomic_review(
                case=review_case(),
                verifier=bad_verifier,
                verifier_model="fixture-verifier",
                verifier_run_id="run-bad",
            )

    def test_unparseable_model_output_is_rejected(self):
        def bad_verifier(case, prompt):
            return "this is not json"

        with self.assertRaises(
            AtomicReviewExecutionError
        ):
            execute_atomic_review(
                case=review_case(),
                verifier=bad_verifier,
                verifier_model="fixture-verifier",
                verifier_run_id="run-bad",
            )

    def test_insufficient_evidence_creates_failed_case_file(self):
        def insufficient(case, prompt):
            return json.dumps(
                {
                    "claim_id": case.claim.claim_id,
                    "verdict": (
                        VerificationVerdict
                        .INSUFFICIENT_EVIDENCE
                        .value
                    ),
                    "calibration": CalibrationVerdict.PRECISE.value,
                    "relied_on_packet_ids": [],
                    "rationale": (
                        "fixture intentionally withholds support"
                    ),
                }
            )

        result = execute_atomic_review(
            case=review_case(),
            verifier=insufficient,
            verifier_model="fixture-verifier",
            verifier_run_id="run-insufficient",
        )

        self.assertFalse(
            result.article_verification.passed
        )

        self.assertFalse(
            result.text_review_passed
        )

        self.assertFalse(
            result.publication_permitted
        )

    def test_replay_is_deterministic_for_same_run_identity(self):
        first = execute_atomic_review(
            case=copy.deepcopy(
                review_case()
            ),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        second = execute_atomic_review(
            case=copy.deepcopy(
                review_case()
            ),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            first.reviewed_artifact.artifact_digest,
            second.reviewed_artifact.artifact_digest,
        )

    def test_verifier_run_identity_changes_artifact_identity(self):
        first = execute_atomic_review(
            case=review_case(),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-001",
        )

        second = execute_atomic_review(
            case=review_case(),
            verifier=supported_verifier,
            verifier_model="fixture-verifier",
            verifier_run_id="run-002",
        )

        self.assertNotEqual(
            first.reviewed_artifact.artifact_digest,
            second.reviewed_artifact.artifact_digest,
        )


if __name__ == "__main__":
    unittest.main()
