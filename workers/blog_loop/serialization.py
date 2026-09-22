"""Pure generation serialization admission contracts.

This module prepares a legacy editorial source bundle for durable generation.

It does not:
- connect to PostgreSQL,
- mutate pipeline state,
- execute publication,
- call network providers,
- create factual authority,
- create approval authority,
- create publication authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import canonical_json
from .legacy_bridge import (
    LegacyNormalizationError,
    normalize_legacy_bundle,
)


def load_editorial_intake_policy(
    policy_path: Path | None = None,
) -> dict[str, Any]:
    if policy_path is None:
        policy_path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "config"
            / "intake_policy.json"
        )

    return json.loads(
        policy_path.read_text(encoding="utf-8")
    )


def prepare_serializable_source_bundle(
    intake: dict[str, Any],
    packets: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Earn deterministic generation admission from materialized packets."""

    if not packets:
        raise LegacyNormalizationError(
            "ready intake had no active packets"
        )

    bundle = {
        "schema": "anarchi.editorial-source-bundle.v1",
        "intake": {
            key: value
            for key, value in intake.items()
            if key not in {"claimed_at", "last_error"}
        },
        "packets": packets,
    }

    bundle = json.loads(canonical_json(bundle))

    normalization = normalize_legacy_bundle(
        bundle,
        policy,
    )

    result = {
        **bundle,
        "normalization": normalization,
        "generation_admission": {
            "schema": "anarchi.generation-admission.v1",
            "state": "NORMALIZATION_PASSED",
            "bridge_digest": normalization["bridge_digest"],
            "article_input_digest": normalization[
                "article_input"
            ]["article_input_digest"],
            "factual_authority": "NONE",
            "publication_authority": "NONE",
            "approval": "NONE",
        },
    }

    return json.loads(canonical_json(result))
