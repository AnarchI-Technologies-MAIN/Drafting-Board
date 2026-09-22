from __future__ import annotations

import json
import unittest

from blog_loop.atomic_review import (
    build_atomic_review_case,
)
from editorial_verifier import (
    CalibrationVerdict,
    TemporalSensitivity,
    VerificationVerdict,
)
from editorial_verifier_adapter import (
    VERIFIER_ADAPTER_VERSION,
    VerifierAdapterError,
    build_verifier_prompt,
    parse_verifier_response,
)
from workers.tests.test_blog_atomic_review_preparation import (
    ARTICLE,
    admitted_bundle,
)


class VerifierIdentityOwnershipV3Contract(
    unittest.TestCase
):
    def case(self):
        review = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertTrue(
            review.verifier_cases
        )

        return review.verifier_cases[0]

    def response(
        self,
        *,
        claim_id_marker="ABSENT",
        calibration="PRECISE",
    ):
        case = self.case()

        payload = {
            "verdict": "SUPPORTED",
            "calibration": calibration,
            "temporal_sensitivity": "NONE",
            "relied_on_packet_ids": [
                item.packet_id
                for item
                in case.evidence_set.eligible_candidates
            ],
            "rationale": (
                "The supplied evidence supports "
                "the bounded claim."
            ),
        }

        if claim_id_marker != "ABSENT":
            payload["claim_id"] = (
                claim_id_marker
            )

        return (
            case,
            json.dumps(payload),
        )

    def prompt_payload(self):
        case = self.case()

        messages = build_verifier_prompt(
            case
        )

        self.assertEqual(
            2,
            len(messages),
        )

        payload = json.loads(
            messages[1]["content"]
        )

        return (
            case,
            messages[0]["content"],
            payload,
        )

    def test_claim_identity_is_not_required_model_output(self):
        _, _, payload = (
            self.prompt_payload()
        )

        required_output = payload[
            "required_output"
        ]

        self.assertNotIn(
            "claim_id",
            required_output,
        )

    def test_prompt_explicitly_states_deterministic_identity_ownership(self):
        _, system, payload = (
            self.prompt_payload()
        )

        combined = (
            system
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        ).lower()

        self.assertIn(
            "claim identity",
            combined,
        )

        self.assertIn(
            "deterministic",
            combined,
        )

        self.assertIn(
            "do not return claim_id",
            combined,
        )

    def test_missing_model_claim_id_is_accepted_and_bound_from_case(self):
        case, raw = self.response()

        result = parse_verifier_response(
            case,
            raw,
        )

        self.assertEqual(
            case.claim.claim_id,
            result.claim_id,
        )

        self.assertEqual(
            case.claim.text,
            result.claim_text,
        )

        self.assertEqual(
            case.claim.claim_type,
            result.claim_type,
        )

        self.assertEqual(
            case.claim.material,
            result.material,
        )

    def test_wrong_optional_claim_id_still_fails_closed(self):
        case, raw = self.response(
            claim_id_marker="claim-wrong",
        )

        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                case,
                raw,
            )

    def test_exact_optional_claim_id_may_not_change_identity(self):
        case = self.case()

        _, raw = self.response(
            claim_id_marker=(
                case.claim.claim_id
            ),
        )

        result = parse_verifier_response(
            case,
            raw,
        )

        self.assertEqual(
            case.claim.claim_id,
            result.claim_id,
        )

    def test_prompt_declares_calibration_as_scalar_string_enum(self):
        _, _, payload = (
            self.prompt_payload()
        )

        calibration = payload[
            "required_output"
        ][
            "calibration"
        ]

        self.assertIsInstance(
            calibration,
            dict,
        )

        self.assertEqual(
            "string",
            calibration["type"],
        )

        self.assertEqual(
            [
                item.value
                for item
                in CalibrationVerdict
                if item
                != CalibrationVerdict.UNASSESSED
            ],
            calibration["enum"],
        )

        self.assertNotIn(
            CalibrationVerdict.UNASSESSED.value,
            calibration["enum"],
        )

    def test_prompt_declares_verdict_as_scalar_string_enum(self):
        _, _, payload = (
            self.prompt_payload()
        )

        verdict = payload[
            "required_output"
        ][
            "verdict"
        ]

        self.assertIsInstance(
            verdict,
            dict,
        )

        self.assertEqual(
            "string",
            verdict["type"],
        )

        self.assertEqual(
            [
                item.value
                for item
                in VerificationVerdict
            ],
            verdict["enum"],
        )

    def test_prompt_declares_temporal_sensitivity_as_scalar_string_enum(self):
        _, _, payload = (
            self.prompt_payload()
        )

        temporal = payload[
            "required_output"
        ][
            "temporal_sensitivity"
        ]

        self.assertIsInstance(
            temporal,
            dict,
        )

        self.assertEqual(
            "string",
            temporal["type"],
        )

        self.assertEqual(
            [
                item.value
                for item
                in TemporalSensitivity
            ],
            temporal["enum"],
        )

    def test_live_array_calibration_shape_remains_rejected(self):
        case, raw = self.response(
            claim_id_marker=(
                self.case().claim.claim_id
            ),
            calibration=[
                "PRECISE"
            ],
        )

        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                case,
                raw,
            )

    def test_scalar_calibration_remains_accepted(self):
        case, raw = self.response(
            claim_id_marker=(
                self.case().claim.claim_id
            ),
            calibration="PRECISE",
        )

        result = parse_verifier_response(
            case,
            raw,
        )

        self.assertEqual(
            CalibrationVerdict.PRECISE,
            result.calibration,
        )

    def test_adapter_v5_is_post_repair_identity(self):
        self.assertEqual(
            "anarchi.editorial-verifier-adapter.v5",
            VERIFIER_ADAPTER_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
