"""Fail-closed adapter between a probabilistic verifier and deterministic law.

The model may propose a claim verdict.

This adapter validates that proposal against:
- the exact atomic claim,
- the exact eligible evidence set,
- known verdict vocabulary,
- known calibration vocabulary,
- immutable packet IDs,
- immutable excerpt digests.

Only then can the proposal become a ClaimVerification.

No adjudication or publication authority exists here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from editorial_claims import ExtractedClaim
from editorial_evidence import ClaimEvidenceSet
from editorial_verifier import (
    CalibrationVerdict,
    ClaimVerification,
    TemporalSensitivity,
    VerificationVerdict,
    VerifiedEvidence,
)


VERIFIER_ADAPTER_VERSION = "anarchi.editorial-verifier-adapter.v5"


@dataclass(frozen=True)
class VerifierCase:
    claim: ExtractedClaim
    evidence_set: ClaimEvidenceSet

    @property
    def eligible_packet_ids(self) -> frozenset[int]:
        return frozenset(
            item.packet_id
            for item in self.evidence_set.eligible_candidates
        )

    @property
    def evidence_by_packet(self):
        return {
            item.packet_id: item
            for item in self.evidence_set.eligible_candidates
        }


class VerifierAdapterError(ValueError):
    pass


def canonicalize_packet_ids(
    values: Any,
) -> list[int]:
    """Normalize only unambiguous JSON integer representations.

    Accepted:
    - JSON integer 11001
    - canonical decimal string "11001"

    Rejected:
    - leading zeros
    - signs
    - whitespace
    - labels
    - floats
    - booleans
    """
    if not isinstance(values, list):
        raise VerifierAdapterError(
            "relied_on_packet_ids must be an array"
        )

    normalized: list[int] = []

    for value in values:
        if isinstance(value, bool):
            raise VerifierAdapterError(
                "packet IDs cannot be booleans"
            )

        if isinstance(value, int):
            normalized.append(value)
            continue

        if isinstance(value, str):
            if not value.isascii():
                raise VerifierAdapterError(
                    "packet ID string must be ASCII decimal"
                )

            if not value.isdigit():
                raise VerifierAdapterError(
                    "packet ID string must be canonical decimal"
                )

            if value == "0":
                normalized.append(0)
                continue

            if value.startswith("0"):
                raise VerifierAdapterError(
                    "packet ID string cannot contain leading zeros"
                )

            converted = int(value)

            if str(converted) != value:
                raise VerifierAdapterError(
                    "packet ID string is not canonical"
                )

            normalized.append(converted)
            continue

        raise VerifierAdapterError(
            "packet IDs must be integers or canonical decimal strings"
        )

    return normalized


def build_verifier_prompt(case: VerifierCase) -> list[dict[str, str]]:
    evidence = [
        {
            "packet_id": item.packet_id,
            "url": item.source_url,
            "excerpt_digest": item.excerpt_digest,
            "excerpt": item.excerpt,
        }
        for item in case.evidence_set.eligible_candidates
    ]

    evidence_instruction = (
        "eligible_evidence is empty. "
        "SUPPORTED is forbidden. "
        "For a factual claim that cannot be assessed from supplied "
        "evidence, use the INSUFFICIENT_EVIDENCE verdict. "
        "NON_FACTUAL remains available only for a genuinely "
        "non-factual claim."
        if not evidence
        else (
            "eligible_evidence is not empty. "
            "Any relied_on_packet_ids must reference only supplied "
            "eligible evidence."
        )
    )

    system = (
        "You are an atomic technical fact verifier. "
        "Review exactly one claim against only the supplied evidence. "
        "Do not use outside knowledge. Do not reward fluency. "
        "Do not infer support from topical similarity. "
        "Contradictory evidence must remain visible. "
        "Field semantics are strict. ""Claim identity is owned by the deterministic case. ""Do not return claim_id in verifier output. "
        "verdict is the evidentiary disposition of the claim. "
        "calibration describes wording precision only. "
        "Verdict values and calibration values must not be copied "
        "between fields. "
        "INSUFFICIENT_EVIDENCE is a verdict and is never a calibration "
        "value. "
        "The rationale must not introduce outside facts, source "
        "properties, or conclusions that are absent from the supplied "
        "eligible evidence. "
        + evidence_instruction
        + " Return JSON only."
    )

    user = {
        "claim_id": case.claim.claim_id,
        "claim_text": case.claim.text,
        "claim_type": case.claim.claim_type.value,
        "material": case.claim.material,
        "eligible_evidence": evidence,
        "required_output": {
            "verdict": {
                "type": "string",
                "enum": [
                    item.value
                    for item in VerificationVerdict
                ],
            },
            "calibration": {
                "type": "string",
                "enum": [
                    item.value
                    for item in CalibrationVerdict
                    if item
                    != CalibrationVerdict.UNASSESSED
                ],
            },
            "temporal_sensitivity": {
                "type": "string",
                "enum": [
                    item.value
                    for item in TemporalSensitivity
                ],
            },
            "relied_on_packet_ids": (
                "array of eligible JSON integer packet IDs only; "
                "example: [11001], never quoted identifiers"
            ),
            "rationale": ("short explanation grounded only in supplied evidence; ""must not introduce outside facts"),
        },
    }

    return [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": json.dumps(
                user,
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


MODEL_AUTHORABLE_CALIBRATIONS = frozenset(
    {
        CalibrationVerdict.PRECISE.value,
        CalibrationVerdict.OVERSTATED.value,
        CalibrationVerdict.UNDERSTATED.value,
        CalibrationVerdict.MISLEADING.value,
    }
)


def parse_verifier_response(
    case: VerifierCase,
    raw: str,
) -> ClaimVerification:
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise VerifierAdapterError(
            f"unparseable verifier JSON: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise VerifierAdapterError(
            "verifier response is not an object"
        )

    declared_claim_id = payload.get(
        "claim_id"
    )

    if (
        declared_claim_id is not None
        and declared_claim_id
        != case.claim.claim_id
    ):
        raise VerifierAdapterError(
            "claim_id mismatch"
        )

    try:
        verdict = VerificationVerdict(
            payload.get("verdict")
        )
    except Exception as exc:
        raise VerifierAdapterError(
            "invalid verification verdict"
        ) from exc

    proposed_calibration = payload.get(
        "calibration"
    )

    if not isinstance(
        proposed_calibration,
        str,
    ):
        raise VerifierAdapterError(
            "calibration must be a model-authorable string verdict"
        )

    if (
        proposed_calibration
        not in MODEL_AUTHORABLE_CALIBRATIONS
    ):
        raise VerifierAdapterError(
            "calibration is not model-authorable"
        )

    calibration = CalibrationVerdict(
        proposed_calibration
    )

    try:
        temporal = TemporalSensitivity(
            payload.get(
                "temporal_sensitivity",
                TemporalSensitivity.NONE.value,
            )
        )
    except Exception as exc:
        raise VerifierAdapterError(
            "invalid temporal sensitivity"
        ) from exc

    relied = canonicalize_packet_ids(
        payload.get(
            "relied_on_packet_ids",
            [],
        )
    )

    if len(relied) != len(set(relied)):
        raise VerifierAdapterError(
            "duplicate relied_on_packet_ids"
        )

    unknown = sorted(
        set(relied).difference(
            case.eligible_packet_ids
        )
    )

    if unknown:
        raise VerifierAdapterError(
            "verifier relied on ineligible packet IDs: "
            + ",".join(str(item) for item in unknown)
        )

    evidence_by_packet = case.evidence_by_packet

    verified_evidence = tuple(
        VerifiedEvidence(
            packet_id=packet_id,
            source_url=evidence_by_packet[
                packet_id
            ].source_url,
            excerpt_digest=evidence_by_packet[
                packet_id
            ].excerpt_digest,
        )
        for packet_id in relied
    )

    rationale = payload.get(
        "rationale",
        "",
    )

    if not isinstance(rationale, str):
        raise VerifierAdapterError(
            "rationale must be a string"
        )

    if verdict == VerificationVerdict.SUPPORTED and not verified_evidence:
        raise VerifierAdapterError(
            "SUPPORTED verdict requires relied-on evidence"
        )

    return ClaimVerification(
        claim_id=case.claim.claim_id,
        claim_text=case.claim.text,
        claim_type=case.claim.claim_type,
        material=case.claim.material,
        verdict=verdict,
        calibration=calibration,
        temporal_sensitivity=temporal,
        evidence=verified_evidence,
        rationale=rationale.strip(),
    )
