import unittest

from editorial_claims import extract_claims
from editorial_evidence import (
    EVIDENCE_BINDER_VERSION,
    EvidenceSource,
    bind_evidence_candidates,
    evidence_digest,
    retrieval_score,
)


def claim(text: str):
    ledger = extract_claims(text)
    return ledger.claims[0]


class EditorialEvidenceTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            EVIDENCE_BINDER_VERSION,
            "anarchi.editorial-evidence.v1",
        )

    def test_digest_is_stable(self):
        excerpt = "Docker contexts select daemon endpoints."
        self.assertEqual(
            evidence_digest(excerpt),
            evidence_digest(excerpt),
        )

    def test_whitespace_normalization_preserves_digest_identity(self):
        self.assertEqual(
            evidence_digest(
                "Docker contexts select daemon endpoints."
            ),
            evidence_digest(
                "Docker   contexts\nselect daemon endpoints."
            ),
        )

    def test_changed_evidence_changes_digest(self):
        self.assertNotEqual(
            evidence_digest(
                "Docker contexts select daemon endpoints."
            ),
            evidence_digest(
                "Docker contexts do not select daemon endpoints."
            ),
        )

    def test_topical_overlap_creates_candidate(self):
        subject = claim(
            "Docker contexts can select different daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=11,
            title="Docker contexts",
            url="https://example.invalid/docker-contexts",
            excerpt=(
                "A Docker context determines which daemon endpoint "
                "the Docker CLI communicates with."
            ),
            relevance_passed=True,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        self.assertEqual(len(bound.eligible_candidates), 1)

    def test_failed_upstream_relevance_is_not_eligible(self):
        subject = claim(
            "Docker contexts can select different daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=12,
            title="Irrelevant specimen",
            url="https://example.invalid/specimen",
            excerpt=(
                "Docker contexts select different daemon endpoints."
            ),
            relevance_passed=False,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        self.assertEqual(len(bound.eligible_candidates), 0)

    def test_zero_lexical_overlap_is_not_eligible(self):
        subject = claim(
            "Docker contexts can select different daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=13,
            title="Unrelated",
            url="https://example.invalid/unrelated",
            excerpt="PostgreSQL vacuum reclaims dead tuples.",
            relevance_passed=True,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        self.assertEqual(len(bound.eligible_candidates), 0)

    def test_candidate_binding_does_not_mean_support(self):
        subject = claim(
            "Docker contexts can select different daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=14,
            title="Contradictory specimen",
            url="https://example.invalid/contradiction",
            excerpt=(
                "Docker contexts cannot select different "
                "daemon endpoints."
            ),
            relevance_passed=True,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        self.assertEqual(len(bound.eligible_candidates), 1)
        self.assertFalse(bound.supported)
        self.assertFalse(
            bound.eligible_candidates[0].proves_claim
        )

    def test_retrieval_score_is_not_truth_score(self):
        score, shared = retrieval_score(
            "Docker contexts select daemon endpoints.",
            "Docker contexts do not select daemon endpoints.",
        )

        self.assertGreater(score, 0)
        self.assertGreater(len(shared), 0)

    def test_candidate_preserves_packet_identity(self):
        subject = claim(
            "Docker contexts can select daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=992,
            title="Packet identity",
            url="https://example.invalid/packet",
            excerpt=(
                "Docker contexts can select daemon endpoints."
            ),
            relevance_passed=True,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        candidate = bound.eligible_candidates[0]

        self.assertEqual(candidate.packet_id, 992)
        self.assertEqual(
            candidate.source_url,
            "https://example.invalid/packet",
        )

    def test_binding_grants_no_verification_authority(self):
        subject = claim(
            "Docker contexts can select daemon endpoints."
        )

        source = EvidenceSource(
            packet_id=15,
            title="Authority specimen",
            url="https://example.invalid/authority",
            excerpt=(
                "Docker contexts can select daemon endpoints."
            ),
            relevance_passed=True,
        )

        bound = bind_evidence_candidates(
            subject,
            [source],
        )

        self.assertFalse(
            bound.eligible_candidates[0].verification_authority
        )

    def test_binding_grants_no_adjudication_authority(self):
        subject = claim(
            "Docker contexts select daemon endpoints."
        )

        bound = bind_evidence_candidates(
            subject,
            [],
        )

        self.assertFalse(bound.adjudication_authority)

    def test_binding_grants_no_publication_authority(self):
        subject = claim(
            "Docker contexts select daemon endpoints."
        )

        bound = bind_evidence_candidates(
            subject,
            [],
        )

        self.assertFalse(bound.publication_authority)


if __name__ == "__main__":
    unittest.main()
