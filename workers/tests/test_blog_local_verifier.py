from __future__ import annotations

import json
import unittest

from blog_loop.local_verifier import (
    LocalVerifierObservation,
    make_local_verifier,
)
from editorial_claims import extract_claims
from editorial_evidence import (
    EvidenceSource,
    bind_evidence_candidates,
)
from editorial_verifier_adapter import VerifierCase


ARTICLE = (
    "Node.js can expose runtime diagnostic information."
)


def case() -> VerifierCase:
    claim = extract_claims(
        ARTICLE
    ).claims[0]

    source = EvidenceSource(
        packet_id=2,
        title="Node.js docs",
        url="https://nodejs.org/docs/example",
        excerpt=(
            "Node.js runtime diagnostics can expose "
            "diagnostic information."
        ),
        provider="fixture",
        relevance_passed=True,
    )

    evidence = bind_evidence_candidates(
        claim,
        [source],
    )

    return VerifierCase(
        claim=claim,
        evidence_set=evidence,
    )


class LocalVerifierAdapterTests(unittest.TestCase):
    def test_adapter_forces_json_zero_temperature(self):
        captured = {}

        def chat(messages, *, json_mode, num_predict, temperature):
            captured["messages"] = messages
            captured["json_mode"] = json_mode
            captured["num_predict"] = num_predict
            captured["temperature"] = temperature

            return (
                json.dumps(
                    {
                        "claim_id": case().claim.claim_id,
                        "verdict": "SUPPORTED",
                        "calibration": "PRECISE",
                        "relied_on_packet_ids": [2],
                        "rationale": "fixture",
                    }
                ),
                {"provider": "fixture"},
            )

        verifier = make_local_verifier(
            chat_function=chat
        )

        verifier(
            case(),
            [{"role": "user", "content": "fixture"}],
        )

        self.assertTrue(
            captured["json_mode"]
        )

        self.assertEqual(
            captured["temperature"],
            0.0,
        )

        self.assertEqual(
            captured["num_predict"],
            700,
        )

    def test_adapter_records_metrics_without_authority(self):
        observations: list[
            LocalVerifierObservation
        ] = []

        def chat(messages, *, json_mode, num_predict, temperature):
            return (
                "{}",
                {
                    "provider": "fixture",
                    "duration_ms": 10,
                },
            )

        verifier = make_local_verifier(
            chat_function=chat,
            observations=observations,
        )

        verifier(
            case(),
            [{"role": "user", "content": "fixture"}],
        )

        self.assertEqual(
            len(observations),
            1,
        )

        self.assertEqual(
            observations[0].metrics["provider"],
            "fixture",
        )

    def test_non_string_model_response_fails_closed(self):
        def chat(messages, *, json_mode, num_predict, temperature):
            return (
                {"not": "a string"},
                {},
            )

        verifier = make_local_verifier(
            chat_function=chat
        )

        with self.assertRaises(TypeError):
            verifier(
                case(),
                [{"role": "user", "content": "fixture"}],
            )

    def test_invalid_metrics_fail_closed(self):
        def chat(messages, *, json_mode, num_predict, temperature):
            return (
                "{}",
                "not-a-dict",
            )

        verifier = make_local_verifier(
            chat_function=chat
        )

        with self.assertRaises(TypeError):
            verifier(
                case(),
                [{"role": "user", "content": "fixture"}],
            )


if __name__ == "__main__":
    unittest.main()
