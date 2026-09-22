import unittest

from editorial_claims import (
    CLAIM_EXTRACTOR_VERSION,
    ExtractedClaimType,
    article_digest,
    extract_claims,
)


class EditorialClaimExtractionTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            CLAIM_EXTRACTOR_VERSION,
            "anarchi.editorial-claims.v2",
        )

    def test_fact_is_extracted(self):
        ledger = extract_claims(
            "Docker contexts select a target endpoint."
        )
        self.assertEqual(ledger.claim_count, 1)
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.FACT,
        )

    def test_capability_is_classified(self):
        ledger = extract_claims(
            "Docker contexts can select different daemon endpoints."
        )
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.CAPABILITY,
        )

    def test_causal_claim_is_classified(self):
        ledger = extract_claims(
            "The request fails because the client targets the wrong daemon."
        )
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.CAUSAL,
        )

    def test_recommendation_is_classified(self):
        ledger = extract_claims(
            "You should inspect the active context before reinstalling Docker."
        )
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.RECOMMENDATION,
        )

    def test_inference_is_classified(self):
        ledger = extract_claims(
            "The logs suggest the daemon may be unreachable."
        )
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.INFERENCE,
        )

    def test_temporal_claim_is_classified(self):
        ledger = extract_claims(
            "Docker Desktop currently exposes this setting."
        )
        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.TEMPORAL,
        )

    def test_multiple_claims_get_unique_stable_ids(self):
        body = (
            "Docker contexts select a target endpoint. "
            "The active context can point at another daemon."
        )
        first = extract_claims(body)
        second = extract_claims(body)

        self.assertEqual(
            [claim.claim_id for claim in first.claims],
            [claim.claim_id for claim in second.claims],
        )
        self.assertEqual(
            len(set(claim.claim_id for claim in first.claims)),
            2,
        )

    def test_article_digest_is_stable(self):
        body = "A deterministic specimen."
        self.assertEqual(
            article_digest(body),
            article_digest(body),
        )

    def test_source_spans_reconstruct_claim_text(self):
        body = (
            "The client targets one daemon. "
            "The context can select another."
        )
        ledger = extract_claims(body)

        for claim in ledger.claims:
            raw = body[
                claim.source_span_start:
                claim.source_span_end
            ]
            self.assertEqual(
                " ".join(raw.split()),
                claim.text,
            )

    def test_wrapped_sentence_is_preserved(self):
        body = (
            "Docker trouble becomes expensive when diagnosis starts with ritual instead\n"
            "of topology."
        )

        ledger = extract_claims(body)

        self.assertEqual(ledger.claim_count, 1)
        self.assertEqual(
            ledger.claims[0].text,
            "Docker trouble becomes expensive when diagnosis starts with ritual instead of topology.",
        )
        self.assertTrue(ledger.claims[0].material)

    def test_wrapped_multi_sentence_specimen_is_preserved(self):
        body = (
            "Docker trouble becomes expensive when diagnosis starts with ritual instead\n"
            "of topology. The Docker CLI can target different daemon endpoints through\n"
            "contexts. You should inspect the active context before reinstalling the\n"
            "stack. The logs may suggest that the daemon is unreachable."
        )

        ledger = extract_claims(body)

        self.assertEqual(ledger.claim_count, 4)
        self.assertEqual(ledger.material_count, 4)

        self.assertEqual(
            [claim.claim_type for claim in ledger.claims],
            [
                ExtractedClaimType.FACT,
                ExtractedClaimType.CAPABILITY,
                ExtractedClaimType.RECOMMENDATION,
                ExtractedClaimType.INFERENCE,
            ],
        )

    def test_markdown_heading_does_not_consume_first_sentence(self):
        body = (
            "# Docker Context Diagnosis\n\n"
            "The Docker CLI can target different daemon endpoints."
        )

        ledger = extract_claims(body)

        self.assertEqual(ledger.claim_count, 1)
        self.assertEqual(
            ledger.claims[0].text,
            "The Docker CLI can target different daemon endpoints.",
        )

    def test_temporal_precedence_over_configuration_shape(self):
        ledger = extract_claims(
            "Docker Desktop currently exposes this setting."
        )

        self.assertEqual(
            ledger.claims[0].claim_type,
            ExtractedClaimType.TEMPORAL,
        )

    def test_extractor_grants_no_verification_authority(self):
        ledger = extract_claims(
            "Docker contexts select a target endpoint."
        )
        self.assertFalse(ledger.verification_authority)

    def test_extractor_grants_no_adjudication_authority(self):
        ledger = extract_claims(
            "Docker contexts select a target endpoint."
        )
        self.assertFalse(ledger.adjudication_authority)

    def test_extractor_grants_no_publication_authority(self):
        ledger = extract_claims(
            "Docker contexts select a target endpoint."
        )
        self.assertFalse(ledger.publication_authority)


if __name__ == "__main__":
    unittest.main()
