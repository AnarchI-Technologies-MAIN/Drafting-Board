from __future__ import annotations

import json
import unittest

from editorial_verifier import CalibrationVerdict
from editorial_verifier_adapter import (
    MODEL_AUTHORABLE_CALIBRATIONS,
    VERIFIER_ADAPTER_VERSION,
    VerifierAdapterError,
    parse_verifier_response,
)
from test_editorial_verifier_adapter import specimen_case


class VerifierProposalVocabularyContractTests(
    unittest.TestCase
):
    def test_adapter_identity_is_v5(self):
        self.assertEqual(
            VERIFIER_ADAPTER_VERSION,
            "anarchi.editorial-verifier-adapter.v5",
        )

    def test_internal_contract_retains_unassessed(self):
        self.assertEqual(
            CalibrationVerdict.UNASSESSED.value,
            "UNASSESSED",
        )

    def test_model_authorable_calibration_set_is_exact(self):
        self.assertEqual(
            MODEL_AUTHORABLE_CALIBRATIONS,
            frozenset(
                {
                    "PRECISE",
                    "OVERSTATED",
                    "UNDERSTATED",
                    "MISLEADING",
                }
            ),
        )

    def test_unassessed_is_not_model_authorable(self):
        self.assertNotIn(
            "UNASSESSED",
            MODEL_AUTHORABLE_CALIBRATIONS,
        )

    def test_model_returned_unassessed_is_rejected(
        self,
    ):
        case = specimen_case()

        packet_id = tuple(
            case.eligible_packet_ids
        )[0]

        raw = json.dumps(
            {
                "verdict": "SUPPORTED",
                "calibration": "UNASSESSED",
                "temporal_sensitivity": "NONE",
                "relied_on_packet_ids": [
                    packet_id
                ],
                "rationale": (
                    "Adversarial model-authored "
                    "deterministic-only calibration."
                ),
            }
        )

        with self.assertRaisesRegex(
            VerifierAdapterError,
            "model-authorable",
        ):
            parse_verifier_response(
                case,
                raw,
            )

    def test_all_model_authorable_calibrations_parse(
        self,
    ):
        case = specimen_case()

        packet_id = tuple(
            case.eligible_packet_ids
        )[0]

        for calibration in sorted(
            MODEL_AUTHORABLE_CALIBRATIONS
        ):
            with self.subTest(
                calibration=calibration
            ):
                raw = json.dumps(
                    {
                        "verdict": "SUPPORTED",
                        "calibration": calibration,
                        "temporal_sensitivity": "NONE",
                        "relied_on_packet_ids": [
                            packet_id
                        ],
                        "rationale": (
                            "Legal model-authored "
                            "calibration fixture."
                        ),
                    }
                )

                result = parse_verifier_response(
                    case,
                    raw,
                )

                self.assertEqual(
                    result.calibration.value,
                    calibration,
                )

    def test_non_string_calibration_is_rejected(
        self,
    ):
        case = specimen_case()

        packet_id = tuple(
            case.eligible_packet_ids
        )[0]

        raw = json.dumps(
            {
                "verdict": "SUPPORTED",
                "calibration": [
                    "PRECISE"
                ],
                "temporal_sensitivity": "NONE",
                "relied_on_packet_ids": [
                    packet_id
                ],
                "rationale": "Invalid shape.",
            }
        )

        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                case,
                raw,
            )


if __name__ == "__main__":
    unittest.main()
