import json
import unittest

from editorial_claims import extract_claims
from editorial_evidence import (
    EvidenceSource,
    bind_evidence_candidates,
)
from editorial_verifier import (
    CalibrationVerdict,
    VerificationVerdict,
)
from editorial_verifier_adapter import (
    VERIFIER_ADAPTER_VERSION,
    VerifierAdapterError,
    VerifierCase,
    build_verifier_prompt,
    parse_verifier_response,
)


def specimen_case():
    claim = extract_claims(
        "Docker contexts can select different daemon endpoints."
    ).claims[0]

    evidence = bind_evidence_candidates(
        claim,
        [
            EvidenceSource(
                packet_id=101,
                title="Primary documentation",
                url="https://example.invalid/101",
                excerpt=(
                    "Docker contexts allow a client to select "
                    "different daemon endpoints."
                ),
                relevance_passed=True,
            ),
            EvidenceSource(
                packet_id=102,
                title="Contradictory candidate",
                url="https://example.invalid/102",
                excerpt=(
                    "Docker contexts cannot select "
                    "different daemon endpoints."
                ),
                relevance_passed=True,
            ),
        ],
    )

    return VerifierCase(
        claim=claim,
        evidence_set=evidence,
    )


def response(**changes):
    payload = {
        "claim_id": specimen_case().claim.claim_id,
        "verdict": "SUPPORTED",
        "calibration": "PRECISE",
        "temporal_sensitivity": "NONE",
        "relied_on_packet_ids": [101],
        "rationale": "Packet 101 directly supports the capability.",
    }

    payload.update(changes)

    return json.dumps(payload)


class EditorialVerifierAdapterTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            VERIFIER_ADAPTER_VERSION,
            "anarchi.editorial-verifier-adapter.v5",
        )

    def test_prompt_contains_exact_claim_id(self):
        case = specimen_case()
        messages = build_verifier_prompt(case)

        self.assertIn(
            case.claim.claim_id,
            messages[1]["content"],
        )

    def test_prompt_contains_both_conflicting_candidates(self):
        messages = build_verifier_prompt(
            specimen_case()
        )

        payload = json.loads(
            messages[1]["content"]
        )

        ids = {
            item["packet_id"]
            for item in payload["eligible_evidence"]
        }

        self.assertEqual(ids, {101, 102})

    def test_valid_response_materializes_verification(self):
        case = specimen_case()

        result = parse_verifier_response(
            case,
            response(),
        )

        self.assertEqual(
            result.verdict,
            VerificationVerdict.SUPPORTED,
        )
        self.assertEqual(
            result.calibration,
            CalibrationVerdict.PRECISE,
        )
        self.assertEqual(
            [item.packet_id for item in result.evidence],
            [101],
        )

    def test_malformed_json_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                "{broken",
            )

    def test_wrong_claim_id_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    claim_id="claim-invented"
                ),
            )

    def test_unknown_verdict_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    verdict="MOSTLY_TRUE"
                ),
            )

    def test_unknown_calibration_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    calibration="CONFIDENT"
                ),
            )

    def test_ineligible_packet_id_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=[999]
                ),
            )

    def test_canonical_decimal_string_packet_id_is_normalized(self):
        result = parse_verifier_response(
            specimen_case(),
            response(
                relied_on_packet_ids=["101"]
            ),
        )

        self.assertEqual(
            [item.packet_id for item in result.evidence],
            [101],
        )

    def test_leading_zero_packet_string_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=["0101"]
                ),
            )

    def test_signed_packet_string_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=["+101"]
                ),
            )

    def test_whitespace_packet_string_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=[" 101 "]
                ),
            )

    def test_string_ineligible_packet_still_fails_whitelist(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=["999"]
                ),
            )

    def test_duplicate_packet_id_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=[
                        101,
                        101,
                    ]
                ),
            )

    def test_supported_without_evidence_fails_closed(self):
        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                specimen_case(),
                response(
                    relied_on_packet_ids=[]
                ),
            )

    def test_contradicted_can_rely_on_conflicting_evidence(self):
        result = parse_verifier_response(
            specimen_case(),
            response(
                verdict="CONTRADICTED",
                relied_on_packet_ids=[102],
                rationale=(
                    "Packet 102 contradicts the claim."
                ),
            ),
        )

        self.assertEqual(
            result.verdict,
            VerificationVerdict.CONTRADICTED,
        )
        self.assertEqual(
            result.evidence[0].packet_id,
            102,
        )

    def test_insufficient_evidence_can_use_zero_packets(self):
        result = parse_verifier_response(
            specimen_case(),
            response(
                verdict="INSUFFICIENT_EVIDENCE",
                relied_on_packet_ids=[],
                rationale=(
                    "No eligible evidence establishes the claim."
                ),
            ),
        )

        self.assertEqual(
            result.verdict,
            VerificationVerdict.INSUFFICIENT_EVIDENCE,
        )

    def test_adapter_cannot_change_claim_text(self):
        case = specimen_case()

        result = parse_verifier_response(
            case,
            response(),
        )

        self.assertEqual(
            result.claim_text,
            case.claim.text,
        )


if __name__ == "__main__":
    unittest.main()
