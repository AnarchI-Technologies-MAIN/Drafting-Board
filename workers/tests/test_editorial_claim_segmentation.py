from __future__ import annotations

import unittest

from editorial_claims import (
    extract_claims,
    split_candidate_sentences,
)


class TechnicalSentenceSegmentationContract(unittest.TestCase):
    TECHNICAL_SINGLE_SENTENCE_CASES = (
        (
            "node_js",
            "Node.js is a JavaScript runtime.",
        ),
        (
            "version_triple",
            "Version v1.2.3 remains supported.",
        ),
        (
            "domain_name",
            "api.example.com exposes an endpoint.",
        ),
        (
            "decimal",
            "The request completed in 3.14 seconds.",
        ),
        (
            "abbreviation_eg",
            "Use cached results, e.g. local copies.",
        ),
        (
            "abbreviation_ie",
            "The state is immutable, i.e. it cannot be changed.",
        ),
        (
            "title_abbreviation",
            "Dr. Smith published the report.",
        ),
        (
            "method_dotted",
            "Call foo.bar() before shutdown.",
        ),
        (
            "rfc_section",
            "See RFC 9110 section 7.1 for details.",
        ),
    )

    TECHNICAL_TWO_SENTENCE_CASES = (
        (
            "node_js_two",
            "Node.js is installed. The worker uses it.",
            (
                "Node.js is installed.",
                "The worker uses it.",
            ),
        ),
        (
            "domain_two",
            "api.example.com responded. "
            "The worker persisted the receipt.",
            (
                "api.example.com responded.",
                "The worker persisted the receipt.",
            ),
        ),
        (
            "version_two",
            "Version v1.2.3 shipped. "
            "The deployment completed.",
            (
                "Version v1.2.3 shipped.",
                "The deployment completed.",
            ),
        ),
        (
            "decimal_two",
            "Latency was 3.14 seconds. "
            "The retry succeeded.",
            (
                "Latency was 3.14 seconds.",
                "The retry succeeded.",
            ),
        ),
    )

    ORDINARY_BOUNDARY_CASES = (
        (
            "period",
            "The API failed. The worker retried.",
            (
                "The API failed.",
                "The worker retried.",
            ),
        ),
        (
            "three_periods",
            "The worker started. "
            "The API responded. "
            "The job completed.",
            (
                "The worker started.",
                "The API responded.",
                "The job completed.",
            ),
        ),
        (
            "question",
            "Did the worker retry? The audit says yes.",
            (
                "Did the worker retry?",
                "The audit says yes.",
            ),
        ),
        (
            "exclamation",
            "The request failed! The worker stopped.",
            (
                "The request failed!",
                "The worker stopped.",
            ),
        ),
    )

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

    def test_technical_periods_do_not_split_single_sentences(self):
        for name, body in self.TECHNICAL_SINGLE_SENTENCE_CASES:
            with self.subTest(name=name):
                self.assert_segments(
                    body,
                    (body,),
                )

    def test_technical_periods_preserve_real_following_boundary(self):
        for (
            name,
            body,
            expected,
        ) in self.TECHNICAL_TWO_SENTENCE_CASES:
            with self.subTest(name=name):
                self.assert_segments(
                    body,
                    expected,
                )

    def test_ordinary_sentence_boundaries_remain_boundaries(self):
        for (
            name,
            body,
            expected,
        ) in self.ORDINARY_BOUNDARY_CASES:
            with self.subTest(name=name):
                self.assert_segments(
                    body,
                    expected,
                )

    def test_returned_source_spans_reconstruct_exact_original_text(self):
        cases = (
            "Node.js is installed. The worker uses it.",
            "api.example.com responded. "
            "The worker persisted the receipt.",
            "Version v1.2.3 shipped. "
            "The deployment completed.",
            "Latency was 3.14 seconds. "
            "The retry succeeded.",
        )

        for body in cases:
            with self.subTest(body=body):
                for (
                    text,
                    start,
                    end,
                ) in split_candidate_sentences(body):
                    self.assertEqual(
                        text,
                        body[start:end],
                    )

    def test_multiline_whitespace_remains_inside_sentence(self):
        body = (
            "Node.js is a JavaScript\n"
            "runtime used by the worker."
        )

        segments = split_candidate_sentences(body)

        self.assertEqual(
            1,
            len(segments),
        )

        self.assertEqual(
            "Node.js is a JavaScript runtime used by the worker.",
            segments[0][0],
        )

    def test_markdown_heading_does_not_become_claim(self):
        body = (
            "# Runtime Notes\n"
            "Node.js is installed. "
            "The worker uses it."
        )

        ledger = extract_claims(body)

        self.assertEqual(
            (
                "Node.js is installed.",
                "The worker uses it.",
            ),
            tuple(
                claim.text
                for claim in ledger.claims
            ),
        )

    def test_claim_identity_is_deterministic_after_segmentation(self):
        body = (
            "Node.js is installed. "
            "Version v1.2.3 is available. "
            "Latency was 3.14 seconds."
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

    def test_segmentation_does_not_create_authority(self):
        ledger = extract_claims(
            "Node.js is installed."
        )

        self.assertFalse(
            ledger.verification_authority
        )

        self.assertFalse(
            ledger.adjudication_authority
        )


if __name__ == "__main__":
    unittest.main()
