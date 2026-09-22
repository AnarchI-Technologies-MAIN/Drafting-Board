"""Pure Atomic Reviewer case preparation for Blog candidates.

This module converts an exact materialized article plus an admitted source
bundle into the deterministic inputs required by the existing Atomic Reviewer.

It does not:
- execute a verifier model,
- create ClaimVerification verdicts,
- decide factual truth,
- create human approval,
- create publication authority,
- connect to PostgreSQL,
- mutate generation state,
- call network providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from editorial_claims import (
    ClaimLedger,
    ExtractedClaim,
    article_digest,
    extract_claims,
)
from editorial_evidence import (
    ClaimEvidenceSet,
    EvidenceSource,
    bind_evidence_candidates,
    source_from_context,
)
from editorial_verifier_adapter import VerifierCase

from .core import canonical_digest


ATOMIC_REVIEW_CASE_VERSION = "anarchi.blog-atomic-review-case.v1"


class AtomicReviewPreparationError(ValueError):
    pass


@dataclass(frozen=True)
class BlogAtomicReviewCase:
    schema_version: str
    article_text: str
    article_digest: str
    source_bundle_digest: str
    generation_admission_bridge_digest: str
    article_input_digest: str
    claim_ledger: ClaimLedger
    evidence_sources: tuple[EvidenceSource, ...]
    evidence_sets: tuple[ClaimEvidenceSet, ...]
    verifier_cases: tuple[VerifierCase, ...]

    @property
    def material_claim_ids(self) -> tuple[str, ...]:
        return tuple(
            claim.claim_id
            for claim in self.claim_ledger.claims
            if claim.material
        )

    @property
    def factual_authority(self) -> bool:
        return False

    @property
    def adjudication_authority(self) -> bool:
        return False

    @property
    def publication_authority(self) -> bool:
        return False


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AtomicReviewPreparationError(message)


def _bridge_digest_is_valid(
    normalization: dict[str, Any],
) -> bool:
    claimed = normalization.get("bridge_digest")

    if not isinstance(claimed, str) or not claimed:
        return False

    payload = {
        key: value
        for key, value in normalization.items()
        if key != "bridge_digest"
    }

    return canonical_digest(payload) == claimed


def _admission(
    source_bundle: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalization = source_bundle.get("normalization")
    admission = source_bundle.get("generation_admission")

    _require(
        isinstance(normalization, dict),
        "normalized source bundle is required",
    )

    _require(
        isinstance(admission, dict),
        "generation admission is required",
    )

    _require(
        normalization.get("schema")
        == "anarchi.legacy-blog-normalization.v1",
        "normalization schema mismatch",
    )

    _require(
        _bridge_digest_is_valid(normalization),
        "normalization bridge digest invalid",
    )

    _require(
        admission.get("schema")
        == "anarchi.generation-admission.v1",
        "generation admission schema mismatch",
    )

    _require(
        admission.get("state")
        == "NORMALIZATION_PASSED",
        "generation admission state invalid",
    )

    _require(
        admission.get("bridge_digest")
        == normalization.get("bridge_digest"),
        "generation admission bridge binding mismatch",
    )

    article_input = normalization.get("article_input")

    _require(
        isinstance(article_input, dict),
        "normalized article input is required",
    )

    article_input_digest = article_input.get(
        "article_input_digest"
    )

    _require(
        isinstance(article_input_digest, str)
        and bool(article_input_digest),
        "article input digest is required",
    )

    _require(
        admission.get("article_input_digest")
        == article_input_digest,
        "generation admission article-input binding mismatch",
    )

    for object_name, value in (
        ("normalization", normalization),
        ("generation admission", admission),
        ("article input", article_input),
    ):
        _require(
            value.get("factual_authority") == "NONE",
            f"{object_name} factual authority must remain NONE",
        )

        _require(
            value.get("publication_authority") == "NONE",
            f"{object_name} publication authority must remain NONE",
        )

        _require(
            value.get("approval") == "NONE",
            f"{object_name} approval must remain NONE",
        )

    return normalization, admission


def _evidence_excerpt(
    payload: dict[str, Any],
) -> str:
    page = payload.get("page")

    if isinstance(page, dict):
        excerpt = str(page.get("excerpt") or "").strip()

        if excerpt:
            return excerpt

    return str(payload.get("search_snippet") or "").strip()


def _source_documents(
    source_bundle: dict[str, Any],
) -> tuple[EvidenceSource, ...]:
    packets = source_bundle.get("packets")

    _require(
        isinstance(packets, list),
        "source bundle packets must be a list",
    )

    sources: list[EvidenceSource] = []

    for packet in packets:
        if not isinstance(packet, dict):
            continue

        if packet.get("packet_type") != "source_document":
            continue

        payload = packet.get("payload")

        if not isinstance(payload, dict):
            continue

        relevance = payload.get("relevance")

        if not isinstance(relevance, dict):
            relevance = {}

        context = {
            "packet_id": packet.get("id"),
            "title": payload.get("title"),
            "url": payload.get("url"),
            "evidence_excerpt": _evidence_excerpt(payload),
            "provider": payload.get("provider"),
            "relevance": relevance,
        }

        try:
            source = source_from_context(context)
        except Exception as exc:
            raise AtomicReviewPreparationError(
                "source document could not become EvidenceSource: "
                + type(exc).__name__
                + ": "
                + str(exc)
            ) from exc

        if (
            source.packet_id > 0
            and source.url
            and source.excerpt
            and source.relevance_passed
        ):
            sources.append(source)

    sources.sort(
        key=lambda item: (
            item.packet_id,
            item.url,
        )
    )

    _require(
        bool(sources),
        "no review-eligible source documents were available",
    )

    _require(
        len({source.packet_id for source in sources})
        == len(sources),
        "duplicate source packet IDs",
    )

    return tuple(sources)


def _evidence_sets(
    ledger: ClaimLedger,
    sources: tuple[EvidenceSource, ...],
) -> tuple[ClaimEvidenceSet, ...]:
    return tuple(
        bind_evidence_candidates(
            claim,
            sources,
        )
        for claim in ledger.claims
    )


def _verifier_cases(
    ledger: ClaimLedger,
    evidence_sets: tuple[ClaimEvidenceSet, ...],
) -> tuple[VerifierCase, ...]:
    evidence_by_claim = {
        evidence_set.claim_id: evidence_set
        for evidence_set in evidence_sets
    }

    cases: list[VerifierCase] = []

    for claim in ledger.claims:
        evidence_set = evidence_by_claim.get(
            claim.claim_id
        )

        _require(
            evidence_set is not None,
            "claim evidence set missing",
        )

        cases.append(
            VerifierCase(
                claim=claim,
                evidence_set=evidence_set,
            )
        )

    return tuple(cases)


def validate_atomic_review_case(
    case: BlogAtomicReviewCase,
) -> BlogAtomicReviewCase:
    _require(
        isinstance(case, BlogAtomicReviewCase),
        "atomic review case type invalid",
    )

    _require(
        case.schema_version
        == ATOMIC_REVIEW_CASE_VERSION,
        "atomic review case schema invalid",
    )

    _require(
        case.article_digest
        == article_digest(case.article_text),
        "article digest does not match exact article text",
    )

    rebuilt = extract_claims(case.article_text)

    _require(
        rebuilt == case.claim_ledger,
        "claim ledger is not canonical for article text",
    )

    _require(
        case.claim_ledger.article_digest
        == case.article_digest,
        "claim ledger article identity mismatch",
    )

    _require(
        bool(case.claim_ledger.claims),
        "article produced no atomic claims",
    )

    _require(
        bool(case.material_claim_ids),
        "article produced no material claims",
    )

    _require(
        len(case.evidence_sets)
        == len(case.claim_ledger.claims),
        "evidence-set coverage is structurally incomplete",
    )

    _require(
        len(case.verifier_cases)
        == len(case.claim_ledger.claims),
        "verifier-case coverage is structurally incomplete",
    )

    by_claim = {
        claim.claim_id: claim
        for claim in case.claim_ledger.claims
    }

    for evidence_set in case.evidence_sets:
        _require(
            evidence_set.claim_id in by_claim,
            "evidence set references unknown claim",
        )

    for verifier_case in case.verifier_cases:
        expected = by_claim.get(
            verifier_case.claim.claim_id
        )

        _require(
            expected == verifier_case.claim,
            "verifier case claim identity mismatch",
        )

        _require(
            verifier_case.evidence_set.claim_id
            == verifier_case.claim.claim_id,
            "verifier case evidence binding mismatch",
        )

    return case


def build_atomic_review_case(
    *,
    article_text: str,
    source_bundle: dict[str, Any],
) -> BlogAtomicReviewCase:
    _require(
        isinstance(article_text, str)
        and bool(article_text.strip()),
        "exact article text is required",
    )

    _require(
        source_bundle.get("schema")
        == "anarchi.editorial-source-bundle.v1",
        "source bundle schema mismatch",
    )

    normalization, admission = _admission(
        source_bundle
    )

    ledger = extract_claims(article_text)

    sources = _source_documents(
        source_bundle
    )

    evidence_sets = _evidence_sets(
        ledger,
        sources,
    )

    cases = _verifier_cases(
        ledger,
        evidence_sets,
    )

    case = BlogAtomicReviewCase(
        schema_version=ATOMIC_REVIEW_CASE_VERSION,
        article_text=article_text,
        article_digest=ledger.article_digest,
        source_bundle_digest=canonical_digest(
            source_bundle
        ),
        generation_admission_bridge_digest=str(
            admission["bridge_digest"]
        ),
        article_input_digest=str(
            normalization[
                "article_input"
            ][
                "article_input_digest"
            ]
        ),
        claim_ledger=ledger,
        evidence_sources=sources,
        evidence_sets=evidence_sets,
        verifier_cases=cases,
    )

    return validate_atomic_review_case(case)
