"""Deterministic machine adjudication for reviewed blog artifacts.

This stage consumes an already-sealed ReviewedArticleArtifact.

It does not:
- call an LLM,
- create factual claims,
- alter the reviewed artifact,
- grant human approval,
- grant publication authority,
- transition a database job to staged.

Its job is to create a deterministic machine adjudication receipt and
a local adjudicated-bucket record for downstream human adjudication.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


MACHINE_ADJUDICATION_VERSION = "anarchi.blog-machine-adjudication.v1"

MACHINE_PASS = "ADJUDICATED_PASS"
MACHINE_HOLD = "ADJUDICATED_HOLD"

LOCAL_BUCKET_STATE = "MACHINE_ADJUDICATED_HUMAN_PENDING"

NO_AUTHORITY = "NONE"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(payload: dict[str, Any]) -> str:
    encoded = _canonical_json(payload).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_artifact(artifact: Any) -> None:
    required = (
        "artifact_digest",
        "text_review_passed",
        "human_adjudication_permitted",
        "publication_permitted",
    )

    missing = [name for name in required if not hasattr(artifact, name)]

    if missing:
        raise TypeError(
            "reviewed artifact missing required fields: "
            + ", ".join(missing)
        )


def _fracture_ids(artifact: Any) -> tuple[str, ...]:
    verification = getattr(artifact, "article_verification", None)
    fractures = getattr(verification, "fractures", ())

    result: list[str] = []

    for fracture in fractures:
        claim_id = getattr(fracture, "claim_id", None)

        if claim_id is not None:
            result.append(str(claim_id))

    return tuple(result)


def _receipt_payload(
    *,
    artifact_digest: str,
    disposition: str,
    fracture_claim_ids: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": MACHINE_ADJUDICATION_VERSION,
        "artifact_digest": artifact_digest,
        "disposition": disposition,
        "fracture_claim_ids": list(fracture_claim_ids),
        "human_adjudication_authority": NO_AUTHORITY,
        "publication_authority": NO_AUTHORITY,
    }


def _seal_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt["receipt_digest"] = _digest(payload)
    return receipt


def validate_machine_receipt(receipt: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []

    required = (
        "schema_version",
        "artifact_digest",
        "disposition",
        "fracture_claim_ids",
        "human_adjudication_authority",
        "publication_authority",
        "receipt_digest",
    )

    for field in required:
        if field not in receipt:
            errors.append("missing field: " + field)

    if errors:
        return tuple(errors)

    if receipt["schema_version"] != MACHINE_ADJUDICATION_VERSION:
        errors.append("invalid schema_version")

    if receipt["disposition"] not in {
        MACHINE_PASS,
        MACHINE_HOLD,
    }:
        errors.append("invalid disposition")

    if not isinstance(receipt["artifact_digest"], str):
        errors.append("artifact_digest must be a string")

    if not isinstance(receipt["fracture_claim_ids"], list):
        errors.append("fracture_claim_ids must be a list")

    if receipt["human_adjudication_authority"] != NO_AUTHORITY:
        errors.append("human_adjudication_authority must be NONE")

    if receipt["publication_authority"] != NO_AUTHORITY:
        errors.append("publication_authority must be NONE")

    expected_digest = _digest(
        {
            "schema_version": receipt["schema_version"],
            "artifact_digest": receipt["artifact_digest"],
            "disposition": receipt["disposition"],
            "fracture_claim_ids": receipt["fracture_claim_ids"],
            "human_adjudication_authority": (
                receipt["human_adjudication_authority"]
            ),
            "publication_authority": receipt["publication_authority"],
        }
    )

    if receipt["receipt_digest"] != expected_digest:
        errors.append("receipt_digest mismatch")

    return tuple(errors)


@dataclass(frozen=True)
class MachineAdjudication:
    schema_version: str
    artifact_digest: str
    disposition: str
    fracture_claim_ids: tuple[str, ...]
    receipt: dict[str, Any]
    bucket: dict[str, Any]

    @property
    def human_adjudication_permitted(self) -> bool:
        return True

    @property
    def publication_permitted(self) -> bool:
        return False


def adjudicate_reviewed_artifact(
    artifact: Any,
) -> MachineAdjudication:
    """Create a deterministic machine adjudication for a reviewed artifact."""

    _require_artifact(artifact)

    if artifact.human_adjudication_permitted:
        raise ValueError(
            "reviewed artifact unexpectedly grants human adjudication authority"
        )

    if artifact.publication_permitted:
        raise ValueError(
            "reviewed artifact unexpectedly grants publication authority"
        )

    artifact_digest = str(artifact.artifact_digest)
    fracture_claim_ids = _fracture_ids(artifact)

    disposition = (
        MACHINE_PASS
        if bool(artifact.text_review_passed)
        else MACHINE_HOLD
    )

    receipt = _seal_receipt(
        _receipt_payload(
            artifact_digest=artifact_digest,
            disposition=disposition,
            fracture_claim_ids=fracture_claim_ids,
        )
    )

    receipt_errors = validate_machine_receipt(receipt)

    if receipt_errors:
        raise ValueError(
            "machine receipt validation failed: "
            + "; ".join(receipt_errors)
        )

    bucket = {
        "schema_version": MACHINE_ADJUDICATION_VERSION,
        "bucket_state": LOCAL_BUCKET_STATE,
        "artifact_digest": artifact_digest,
        "machine_disposition": disposition,
        "machine_receipt_digest": receipt["receipt_digest"],
        "human_adjudication_authority": NO_AUTHORITY,
        "publication_authority": NO_AUTHORITY,
    }

    return MachineAdjudication(
        schema_version=MACHINE_ADJUDICATION_VERSION,
        artifact_digest=artifact_digest,
        disposition=disposition,
        fracture_claim_ids=fracture_claim_ids,
        receipt=receipt,
        bucket=bucket,
    )
