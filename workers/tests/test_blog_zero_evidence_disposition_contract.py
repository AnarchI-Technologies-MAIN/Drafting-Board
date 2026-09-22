from __future__ import annotations

import json
import unittest

from blog_loop.atomic_review import (
    build_atomic_review_case,
)
from blog_loop.review_execution import (
    execute_atomic_review,
)
from editorial_verifier import (
    CalibrationVerdict,
    VerificationVerdict,
)
from editorial_verifier_adapter import (
    build_verifier_prompt,
)
from workers.tests.test_blog_atomic_review_preparation import (
    admitted_bundle,
)


ARTICLE = (
    "Node.js runtime diagnostics expose memory and heap behavior, "
    "enabling engineers to analyze resource allocation and garbage "
    "collection patterns. "
    "Repeated observations of retained objects and event-loop behavior "
    "help identify performance bottlenecks and memory leaks. "
    "Diagnostic tools provide performance counters and memory profilers, "
    "offering actionable insights for optimization. "
    "These analyses support troubleshooting and refining application "
    "stability and efficiency."
)


class ZeroEvidenceDispositionContractTests(
    unittest.TestCase
):
    def case(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertEqual(
            4,
            len(case.verifier_cases),
        )

        return case

    def zero_case(self):
        matches = [
            item
            for item in self.case().verifier_cases
            if not item.evidence_set.eligible_candidates
        ]

        self.assertEqual(
            1,
            len(matches),
        )

        return matches[0]

    def test_calibration_contract_has_unassessed_state(self):
        self.assertEqual(
            "UNASSESSED",
            CalibrationVerdict.UNASSESSED.value,
        )

    def test_zero_evidence_case_is_material_factual_claim(self):
        verifier_case = self.zero_case()

        self.assertTrue(
            verifier_case.claim.material,
        )

        self.assertEqual(
            "CAPABILITY",
            verifier_case.claim.claim_type.value,
        )

        self.assertEqual(
            (),
            verifier_case.evidence_set.eligible_candidates,
        )

    def test_zero_evidence_factual_claim_does_not_invoke_model(self):
        case = self.case()

        calls = []

        def verifier(
            verifier_case,
            prompt,
        ):
            calls.append(
                verifier_case.claim.claim_id
            )

            eligible = (
                verifier_case
                .evidence_set
                .eligible_candidates
            )

            if not eligible:
                raise AssertionError(
                    "zero-evidence factual claim "
                    "must not invoke verifier model"
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
                        "The supplied eligible evidence "
                        "supports the bounded claim."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "zero-evidence-contract"
            ),
        )

        self.assertEqual(
            3,
            len(calls),
        )

        self.assertEqual(
            4,
            len(
                execution.claim_verifications
            ),
        )

    def test_zero_evidence_case_materializes_deterministic_insufficient_verification(self):
        case = self.case()

        zero = [
            item
            for item in case.verifier_cases
            if not item.evidence_set.eligible_candidates
        ][0]

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
                    "zero-evidence case reached model"
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
                        "The supplied eligible evidence "
                        "supports the bounded claim."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "zero-evidence-materialization"
            ),
        )

        matches = [
            item
            for item
            in execution.claim_verifications
            if item.claim_id
            == zero.claim.claim_id
        ]

        self.assertEqual(
            1,
            len(matches),
        )

        verification = matches[0]

        self.assertEqual(
            VerificationVerdict
            .INSUFFICIENT_EVIDENCE,
            verification.verdict,
        )

        self.assertEqual(
            CalibrationVerdict.UNASSESSED,
            verification.calibration,
        )

        self.assertEqual(
            (),
            verification.evidence,
        )

        self.assertFalse(
            verification.acceptable,
        )

        self.assertIn(
            "no eligible evidence",
            verification.rationale.lower(),
        )

    def test_complete_review_materializes_but_fails_text_review(self):
        case = self.case()

        calls = []

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
                    "deterministic disposition "
                    "must bypass verifier"
                )

            calls.append(
                verifier_case.claim.claim_id
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
                        "The supplied eligible evidence "
                        "supports the bounded claim."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "zero-evidence-complete-review"
            ),
        )

        self.assertEqual(
            3,
            len(calls),
        )

        self.assertEqual(
            4,
            len(
                execution.claim_verifications
            ),
        )

        self.assertFalse(
            execution.text_review_passed,
        )

        self.assertFalse(
            execution.article_verification.passed,
        )

        self.assertIsNotNone(
            execution.reviewed_artifact,
        )

        self.assertFalse(
            execution.publication_permitted,
        )

    def test_model_prompt_does_not_offer_unassessed_calibration(self):
        case = self.case()

        nonzero = [
            item
            for item in case.verifier_cases
            if item.evidence_set.eligible_candidates
        ][0]

        messages = build_verifier_prompt(
            nonzero
        )

        payload = json.loads(
            messages[1]["content"]
        )

        calibration = payload[
            "required_output"
        ][
            "calibration"
        ]

        self.assertEqual(
            "string",
            calibration["type"],
        )

        self.assertNotIn(
            "UNASSESSED",
            calibration["enum"],
        )

    def test_zero_evidence_disposition_grants_no_authority(self):
        case = self.case()

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
                    "zero-evidence case reached model"
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
                        "The supplied eligible evidence "
                        "supports the bounded claim."
                    ),
                }
            )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model="fixture-verifier",
            verifier_run_id=(
                "zero-evidence-authority"
            ),
        )

        self.assertFalse(
            execution.publication_permitted,
        )

        self.assertFalse(
            execution.text_review_passed,
        )


if __name__ == "__main__":
    unittest.main()
