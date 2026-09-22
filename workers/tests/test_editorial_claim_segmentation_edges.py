from __future__ import annotations

import unittest

from editorial_claims import (
    extract_claims,
    split_candidate_sentences,
)


class TechnicalSentenceSegmentationEdgeContract(
    unittest.TestCase
):
    def assert_segments(
        self,
        body: str,
        expected: tuple[str, ...],
    ) -> None:
        actual = tuple(
            text
            for text, _, _
            in split_candidate_sentences(body)
        )

        self.assertEqual(
            expected,
            actual,
        )

    def test_initialism_remains_internal_before_lowercase_continuation(self):
        cases = (
            (
                "U.S. policy changed.",
                (
                    "U.S. policy changed.",
                ),
            ),
            (
                "The U.S.A. policy changed.",
                (
                    "The U.S.A. policy changed.",
                ),
            ),
        )

        for body, expected in cases:
            with self.subTest(body=body):
                self.assert_segments(
                    body,
                    expected,
                )

    def test_initialism_terminal_period_remains_real_boundary(self):
        cases = (
            (
                "The region is the U.S. "
                "The policy changed.",
                (
                    "The region is the U.S.",
                    "The policy changed.",
                ),
            ),
            (
                "The region is the U.S.A. "
                "The policy changed.",
                (
                    "The region is the U.S.A.",
                    "The policy changed.",
                ),
            ),
        )

        for body, expected in cases:
            with self.subTest(body=body):
                self.assert_segments(
                    body,
                    expected,
                )

    def test_ellipsis_is_one_terminal_punctuation_cluster(self):
        body = (
            "The worker waited... "
            "Then it resumed."
        )

        self.assert_segments(
            body,
            (
                "The worker waited...",
                "Then it resumed.",
            ),
        )

    def test_mixed_question_exclamation_is_one_terminal_cluster(self):
        body = (
            "Did it fail?! "
            "The worker stopped."
        )

        self.assert_segments(
            body,
            (
                "Did it fail?!",
                "The worker stopped.",
            ),
        )

    def test_repeated_exclamation_is_one_terminal_cluster(self):
        body = (
            "Stop!! "
            "The worker halted."
        )

        self.assert_segments(
            body,
            (
                "Stop!!",
                "The worker halted.",
            ),
        )

    def test_repeated_question_is_one_terminal_cluster(self):
        body = (
            "Really?? "
            "The audit continued."
        )

        self.assert_segments(
            body,
            (
                "Really??",
                "The audit continued.",
            ),
        )

    def test_terminal_technical_tokens_stay_correct(self):
        cases = (
            (
                "api.example.com. "
                "The worker continued.",
                (
                    "api.example.com.",
                    "The worker continued.",
                ),
            ),
            (
                "Version v1.2.3. "
                "The deployment completed.",
                (
                    "Version v1.2.3.",
                    "The deployment completed.",
                ),
            ),
            (
                "The value was 3.14. "
                "The measurement ended.",
                (
                    "The value was 3.14.",
                    "The measurement ended.",
                ),
            ),
            (
                "The address is 127.0.0.1. "
                "The service started.",
                (
                    "The address is 127.0.0.1.",
                    "The service started.",
                ),
            ),
            (
                "Call foo.bar(). "
                "The process continued.",
                (
                    "Call foo.bar().",
                    "The process continued.",
                ),
            ),
        )

        for body, expected in cases:
            with self.subTest(body=body):
                self.assert_segments(
                    body,
                    expected,
                )

    def test_punctuation_clusters_do_not_create_punctuation_only_claims(self):
        cases = (
            "The worker waited... Then it resumed.",
            "Did it fail?! The worker stopped.",
            "Stop!! The worker halted.",
            "Really?? The audit continued.",
        )

        punctuation_only = {
            ".",
            "..",
            "...",
            "!",
            "!!",
            "?",
            "??",
            "?!",
            "!?",
        }

        for body in cases:
            with self.subTest(body=body):
                ledger = extract_claims(body)

                for claim in ledger.claims:
                    self.assertNotIn(
                        claim.text,
                        punctuation_only,
                    )

    def test_edge_source_spans_reconstruct_exact_text(self):
        cases = (
            "U.S. policy changed.",
            "The U.S.A. policy changed.",
            "The region is the U.S. The policy changed.",
            "The worker waited... Then it resumed.",
            "Did it fail?! The worker stopped.",
            "api.example.com. The worker continued.",
            "Version v1.2.3. The deployment completed.",
        )

        for body in cases:
            with self.subTest(body=body):
                for (
                    text,
                    start,
                    end,
                ) in split_candidate_sentences(body):
                    exact = body[start:end]

                    normalized = " ".join(
                        exact.split()
                    )

                    self.assertEqual(
                        text,
                        normalized,
                    )

    def test_edge_replay_is_deterministic(self):
        body = (
            "U.S. policy changed. "
            "The worker waited... "
            "Did it fail?! "
            "The region is the U.S.A. "
            "The audit continued."
        )

        first = extract_claims(body)
        second = extract_claims(body)

        first_shape = tuple(
            (
                claim.claim_id,
                claim.text,
                claim.claim_type.value,
                claim.material,
                claim.source_span_start,
                claim.source_span_end,
            )
            for claim in first.claims
        )

        second_shape = tuple(
            (
                claim.claim_id,
                claim.text,
                claim.claim_type.value,
                claim.material,
                claim.source_span_start,
                claim.source_span_end,
            )
            for claim in second.claims
        )

        self.assertEqual(
            first_shape,
            second_shape,
        )

    def test_edge_segmentation_creates_no_authority(self):
        ledger = extract_claims(
            "U.S. policy changed. "
            "The worker waited..."
        )

        self.assertFalse(
            ledger.verification_authority
        )

        self.assertFalse(
            ledger.adjudication_authority
        )


if __name__ == "__main__":
    unittest.main()
