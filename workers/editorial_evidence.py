"""Evidence candidate contracts for AnarchI Editorial Foundry.

This module retrieves and binds evidence candidates to atomic claims.

A binding means only that evidence is eligible for verification.
It does NOT mean the evidence supports, contradicts, or proves the claim.

No factual, adjudication, image, or publication authority is granted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable

from editorial_claims import ExtractedClaim


EVIDENCE_BINDER_VERSION = "anarchi.editorial-evidence.v1"


STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "you",
        "your",
    }
)


@dataclass(frozen=True)
class EvidenceSource:
    packet_id: int
    title: str
    url: str
    excerpt: str
    provider: str = ""
    relevance_passed: bool = False


@dataclass(frozen=True)
class EvidenceCandidate:
    claim_id: str
    packet_id: int
    source_url: str
    source_title: str
    provider: str
    excerpt: str
    excerpt_digest: str
    shared_terms: tuple[str, ...]
    retrieval_score: float
    eligible: bool

    @property
    def proves_claim(self) -> bool:
        return False

    @property
    def verification_authority(self) -> bool:
        return False


@dataclass(frozen=True)
class ClaimEvidenceSet:
    claim_id: str
    candidates: tuple[EvidenceCandidate, ...]

    @property
    def eligible_candidates(self) -> tuple[EvidenceCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.eligible
        )

    @property
    def supported(self) -> bool:
        # Retrieval cannot establish factual support.
        return False

    @property
    def adjudication_authority(self) -> bool:
        return False

    @property
    def publication_authority(self) -> bool:
        return False


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def evidence_digest(excerpt: str) -> str:
    return hashlib.sha256(
        normalize_text(excerpt).encode("utf-8")
    ).hexdigest()


def meaningful_terms(text: str) -> frozenset[str]:
    tokens = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9_.:/+-]*",
        text.lower(),
    )

    return frozenset(
        token
        for token in tokens
        if len(token) >= 3 and token not in STOPWORDS
    )


def retrieval_score(
    claim_text: str,
    evidence_text: str,
) -> tuple[float, tuple[str, ...]]:
    claim_terms = meaningful_terms(claim_text)
    evidence_terms = meaningful_terms(evidence_text)

    if not claim_terms:
        return 0.0, ()

    shared = tuple(
        sorted(claim_terms.intersection(evidence_terms))
    )

    score = len(shared) / len(claim_terms)

    return round(score, 4), shared


def source_from_context(
    source: dict[str, Any],
) -> EvidenceSource:
    relevance = source.get("relevance") or {}

    return EvidenceSource(
        packet_id=int(source["packet_id"]),
        title=str(source.get("title") or ""),
        url=str(source.get("url") or ""),
        excerpt=normalize_text(
            str(source.get("evidence_excerpt") or "")
        ),
        provider=str(source.get("provider") or ""),
        relevance_passed=bool(relevance.get("passed")),
    )


def candidate_for(
    claim: ExtractedClaim,
    source: EvidenceSource,
) -> EvidenceCandidate:
    score, shared = retrieval_score(
        claim.text,
        source.excerpt,
    )

    eligible = bool(
        claim.material
        and source.relevance_passed
        and source.packet_id > 0
        and source.url
        and source.excerpt
        and shared
    )

    return EvidenceCandidate(
        claim_id=claim.claim_id,
        packet_id=source.packet_id,
        source_url=source.url,
        source_title=source.title,
        provider=source.provider,
        excerpt=source.excerpt,
        excerpt_digest=evidence_digest(source.excerpt),
        shared_terms=shared,
        retrieval_score=score,
        eligible=eligible,
    )


def bind_evidence_candidates(
    claim: ExtractedClaim,
    sources: Iterable[EvidenceSource],
    limit: int = 8,
) -> ClaimEvidenceSet:
    candidates = [
        candidate_for(claim, source)
        for source in sources
    ]

    candidates.sort(
        key=lambda item: (
            item.eligible,
            item.retrieval_score,
            -item.packet_id,
        ),
        reverse=True,
    )

    return ClaimEvidenceSet(
        claim_id=claim.claim_id,
        candidates=tuple(candidates[: max(0, limit)]),
    )
