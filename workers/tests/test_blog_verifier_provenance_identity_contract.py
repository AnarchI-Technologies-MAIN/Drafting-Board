from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from blog_loop.atomic_review import (
    build_atomic_review_case,
)
from blog_loop.review_execution import (
    REVIEW_EXECUTION_VERSION,
    VERIFIER_CONTRACT_ID,
    execute_atomic_review,
)
from editorial_verifier import (
    VERIFIER_CONTRACT_VERSION,
)
from editorial_verifier_adapter import (
    VERIFIER_ADAPTER_VERSION,
)
from workers.tests.test_blog_atomic_review_preparation import (
    ARTICLE,
    admitted_bundle,
)


ROOT = Path(__file__).resolve().parents[2]

VERIFIER_FILE = (
    ROOT
    / "workers"
    / "editorial_verifier.py"
)

OLD_VERIFIER_SHA = (
    "77042e528def76428bb52dbfe93f66bf"
    "972f9cbb61fae28b01b100eea654af67"
)


def current_verifier_sha() -> str:
    return hashlib.sha256(
        VERIFIER_FILE.read_bytes()
    ).hexdigest()


def current_contract_id() -> str:
    return (
        "editorial_verifier.py@sha256:"
        + current_verifier_sha()
    )


class VerifierProvenanceIdentityContractTests(
    unittest.TestCase
):
    def test_semantic_contract_version_is_v2(self):
        self.assertEqual(
            "anarchi.editorial-verifier.v2",
            VERIFIER_CONTRACT_VERSION,
        )

    def test_adapter_identity_remains_v5(self):
        self.assertEqual(
            "anarchi.editorial-verifier-adapter.v5",
            VERIFIER_ADAPTER_VERSION,
        )

    def test_review_execution_is_post_repair_v3(self):
        self.assertEqual(
            "anarchi.blog-review-execution.v3",
            REVIEW_EXECUTION_VERSION,
        )

    def test_digest_qualified_contract_identity_is_derived_from_current_bytes(self):
        expected = (
            "editorial_verifier.py@sha256:"
            + current_verifier_sha()
        )

        self.assertEqual(
            expected,
            current_contract_id(),
        )

    def test_runtime_contract_id_matches_current_verifier_bytes(self):
        self.assertEqual(
            current_contract_id(),
            VERIFIER_CONTRACT_ID,
        )

    def test_runtime_contract_id_does_not_name_superseded_v1_bytes(self):
        self.assertNotIn(
            OLD_VERIFIER_SHA,
            VERIFIER_CONTRACT_ID,
        )

    def test_semantic_version_and_digest_identity_are_distinct(self):
        self.assertNotEqual(
            VERIFIER_CONTRACT_VERSION,
            current_contract_id(),
        )

        self.assertTrue(
            VERIFIER_CONTRACT_VERSION.startswith(
                "anarchi.editorial-verifier."
            )
        )

        self.assertTrue(
            current_contract_id().startswith(
                "editorial_verifier.py@sha256:"
            )
        )

    def test_materialized_artifact_records_current_digest_qualified_identity(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        def verifier(
            verifier_case,
            prompt,
        ):
            eligible = (
                verifier_case
                .evidence_set
                .eligible_candidates
            )

            if not eligible:
                raise AssertionError(
                    "fixture unexpectedly reached "
                    "zero-evidence model path"
                )

            return json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "calibration": "PRECISE",
                    "temporal_sensitivity": "NONE",
                    "relied_on_packet_ids": [
                        item.packet_id
                        for item in eligible
                    ],
                    "rationale": (
                        "Fixture verification response."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "provenance-identity-contract"
            ),
        )

        self.assertEqual(
            current_contract_id(),
            execution
            .reviewed_artifact
            .provenance
            .verifier_contract_version,
        )

    def test_artifact_provenance_does_not_record_semantic_version_in_digest_identity_field_convention(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        def verifier(
            verifier_case,
            prompt,
        ):
            eligible = (
                verifier_case
                .evidence_set
                .eligible_candidates
            )

            return json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "calibration": "PRECISE",
                    "temporal_sensitivity": "NONE",
                    "relied_on_packet_ids": [
                        item.packet_id
                        for item in eligible
                    ],
                    "rationale": (
                        "Fixture verification response."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "provenance-representation-contract"
            ),
        )

        observed = (
            execution
            .reviewed_artifact
            .provenance
            .verifier_contract_version
        )

        self.assertNotEqual(
            VERIFIER_CONTRACT_VERSION,
            observed,
        )

        self.assertTrue(
            observed.startswith(
                "editorial_verifier.py@sha256:"
            )
        )


if __name__ == "__main__":
    unittest.main()
