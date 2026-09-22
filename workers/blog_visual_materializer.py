"""Blogger-owned deterministic visual materializer.

This module consumes an already validated EditorialVisualPackage and
materializes a local image artifact.

It does not:
- adjudicate factual truth,
- grant human approval,
- grant publication authority,
- mutate the reviewed article,
- mutate the visual package,
- call external services.

The materializer is deliberately deterministic. The resulting image
artifact carries provenance binding it to the exact visual package that
authorized its representation.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from editorial_visual_package import (
    EDITORIAL_VISUAL_PACKAGE_VERSION,
    validate_package,
)


BLOG_VISUAL_MATERIALIZER_VERSION = "anarchi.blogger-visual-materializer.v1"
BLOG_VISUAL_MIME_TYPE = "image/svg+xml"
BLOG_VISUAL_FORMAT = "svg"
BLOG_VISUAL_RENDERER_ID = "blogger-deterministic-visual-v1"
BLOG_VISUAL_RUNTIME_ID = "python-stdlib-local"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest_payload(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _escape(value: Any) -> str:
    return html.escape(
        str(value or ""),
        quote=True,
    )


def _svg_for_package(package: dict[str, Any]) -> bytes:
    reviewed = package["reviewed_context"]
    instruction = package["handoff"]["visual_instruction"]

    title = ""
    bound_claims = reviewed.get("bound_claims", [])

    if bound_claims:
        title = str(
            bound_claims[0].get("claim_text")
            or ""
        )

    if not title:
        title = "Editorial Visual"

    instruction_text = str(instruction or "").strip()

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="1600" height="900" viewBox="0 0 1600 900">
<rect width="1600" height="900" fill="#111827"/>
<rect x="70" y="70" width="1460" height="760"
rx="28" fill="#1f2937" stroke="#6366f1" stroke-width="3"/>
<text x="120" y="155"
font-family="Arial, sans-serif"
font-size="28"
fill="#a5b4fc">BLOGGER EDITORIAL VISUAL</text>
<text x="120" y="245"
font-family="Arial, sans-serif"
font-size="46"
font-weight="700"
fill="#f9fafb">{_escape(title[:180])}</text>
<foreignObject x="120" y="310" width="1360" height="260">
<div xmlns="http://www.w3.org/1999/xhtml"
style="font-family:Arial,sans-serif;font-size:30px;line-height:1.45;color:#d1d5db;">
{_escape(instruction_text[:1000])}
</div>
</foreignObject>
<text x="120" y="735"
font-family="Arial, sans-serif"
font-size="22"
fill="#9ca3af">DETERMINISTIC LOCAL MATERIALIZATION</text>
<text x="120" y="775"
font-family="Arial, sans-serif"
font-size="20"
fill="#9ca3af">Representation only · machine adjudication required</text>
</svg>
"""

    return svg.encode("utf-8")


def materialize_package(
    package: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(package, dict):
        raise ValueError("visual package must be an object")

    if package.get("schema") != EDITORIAL_VISUAL_PACKAGE_VERSION:
        raise ValueError("unsupported editorial visual package schema")

    supplied_digest = package.get("package_digest")

    unsigned = dict(package)
    unsigned.pop("package_digest", None)

    expected_digest = digest_payload(unsigned)

    if supplied_digest != expected_digest:
        raise ValueError(
            "editorial visual package digest mismatch"
        )

    asset = _svg_for_package(package)
    asset_digest = hashlib.sha256(asset).hexdigest()

    provenance = {
        "schema": BLOG_VISUAL_MATERIALIZER_VERSION,
        "renderer_id": BLOG_VISUAL_RENDERER_ID,
        "runtime_id": BLOG_VISUAL_RUNTIME_ID,
        "source_package_digest": supplied_digest,
        "source_package_schema": package["schema"],
        "asset_digest": asset_digest,
        "mime_type": BLOG_VISUAL_MIME_TYPE,
        "format": BLOG_VISUAL_FORMAT,
    }

    result = {
        "schema": BLOG_VISUAL_MATERIALIZER_VERSION,
        "asset": {
            "mime_type": BLOG_VISUAL_MIME_TYPE,
            "format": BLOG_VISUAL_FORMAT,
            "bytes_base64": base64.b64encode(asset).decode("ascii"),
            "sha256": asset_digest,
        },
        "provenance": provenance,
        "authority_state": "MATERIALIZED_UNADJUDICATED",
        "evidentiary_authority": "NONE",
        "human_approval": "NONE",
        "publication_authority": "NONE",
    }

    result["artifact_digest"] = digest_payload(result)

    return result


def validate_materialized_artifact(
    artifact: Any,
    package: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []

    if not isinstance(artifact, dict):
        return ("materialized visual artifact must be an object",)

    expected_fields = {
        "schema",
        "asset",
        "provenance",
        "authority_state",
        "evidentiary_authority",
        "human_approval",
        "publication_authority",
        "artifact_digest",
    }

    if set(artifact) != expected_fields:
        errors.append(
            "materialized visual artifact fields invalid"
        )
        return tuple(errors)

    if artifact["schema"] != BLOG_VISUAL_MATERIALIZER_VERSION:
        errors.append(
            "materialized visual artifact schema mismatch"
        )

    if artifact["authority_state"] != "MATERIALIZED_UNADJUDICATED":
        errors.append(
            "materialized visual authority state invalid"
        )

    if artifact["evidentiary_authority"] != "NONE":
        errors.append(
            "materialized visual artifact may not carry evidentiary authority"
        )

    if artifact["human_approval"] != "NONE":
        errors.append(
            "materialized visual artifact may not carry human approval"
        )

    if artifact["publication_authority"] != "NONE":
        errors.append(
            "materialized visual artifact may not carry publication authority"
        )

    package_digest = package.get("package_digest")

    if artifact["provenance"].get("source_package_digest") != package_digest:
        errors.append(
            "materialized visual provenance package identity changed"
        )

    asset = artifact["asset"]

    if not isinstance(asset, dict):
        errors.append("materialized visual asset invalid")
    if isinstance(asset, dict):
        encoded = asset.get("bytes_base64")
        supplied_asset_digest = asset.get("sha256")

        if not isinstance(encoded, str):
            errors.append(
                "materialized visual asset encoding invalid"
            )
        else:
            try:
                decoded = base64.b64decode(
                    encoded,
                    validate=True,
                )
            except Exception:
                errors.append(
                    "materialized visual asset encoding malformed"
                )
            else:
                actual_asset_digest = hashlib.sha256(
                    decoded
                ).hexdigest()

                if actual_asset_digest != supplied_asset_digest:
                    errors.append(
                        "materialized visual asset digest mismatch"
                    )

    unsigned = dict(artifact)
    supplied_digest = unsigned.pop("artifact_digest", None)

    if supplied_digest != digest_payload(unsigned):
        errors.append(
            "materialized visual artifact digest mismatch"
        )

    return tuple(errors)


def materialize_and_validate(
    package: dict[str, Any],
) -> dict[str, Any]:
    package_errors = validate_package(
        package,
        artifact=_reviewed_artifact_from_package(package),
        request=_visual_request_from_package(package),
    )

    if package_errors:
        raise ValueError(
            "invalid editorial visual package: "
            + "; ".join(package_errors)
        )

    artifact = materialize_package(package)

    errors = validate_materialized_artifact(
        artifact,
        package,
    )

    if errors:
        raise ValueError(
            "invalid materialized visual artifact: "
            + "; ".join(errors)
        )

    return artifact


def _reviewed_artifact_from_package(
    package: dict[str, Any],
) -> Any:
    raise NotImplementedError(
        "package-to-reviewed-artifact reconstruction is intentionally "
        "not implemented in the first materializer seam"
    )


def _visual_request_from_package(
    package: dict[str, Any],
) -> Any:
    raise NotImplementedError(
        "package-to-visual-request reconstruction is intentionally "
        "not implemented in the first materializer seam"
    )
