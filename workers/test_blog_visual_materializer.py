"""Initial isolated tests for Blogger visual materialization."""

from __future__ import annotations

import base64
import hashlib
import json

from blog_visual_materializer import (
    BLOG_VISUAL_MATERIALIZER_VERSION,
    materialize_package,
    validate_materialized_artifact,
)


def digest_payload(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def make_package() -> dict:
    package = {
        "schema": "anarchi.editorial-visual-package.v1",
        "handoff": {
            "schema": "anarchi.editorial-visual-handoff.v1",
            "request_id": "editorial_visual_test",
            "package_id": "test-package",
            "visual_purpose": "EXPLANATORY",
            "visual_instruction": (
                "Create a clear explanatory visual representing the reviewed "
                "technical concept without introducing new factual claims."
            ),
        },
        "reviewed_context": {
            "reviewed_article_schema": "anarchi.editorial-reviewed-article.v1",
            "artifact_digest": "a" * 64,
            "article_digest": "b" * 64,
            "article_text": (
                "PostgreSQL connection pools can exhaust under sustained load."
            ),
            "bound_claims": [
                {
                    "claim_id": "claim-1",
                    "claim_text": (
                        "PostgreSQL connection pools can exhaust under sustained load."
                    ),
                    "claim_type": "TECHNICAL",
                    "material": True,
                }
            ],
        },
        "authority_state": "TRANSPORT_ONLY",
        "evidentiary_authority": "NONE",
        "human_approval": "NONE",
        "publication_authority": "NONE",
    }

    package["package_digest"] = digest_payload(package)

    return package


def test_materializer_produces_artifact() -> None:
    package = make_package()

    artifact = materialize_package(package)

    assert artifact["schema"] == BLOG_VISUAL_MATERIALIZER_VERSION
    assert artifact["authority_state"] == "MATERIALIZED_UNADJUDICATED"
    assert artifact["evidentiary_authority"] == "NONE"
    assert artifact["human_approval"] == "NONE"
    assert artifact["publication_authority"] == "NONE"
    assert (
        artifact["provenance"]["source_package_digest"]
        == package["package_digest"]
    )

    decoded = base64.b64decode(
        artifact["asset"]["bytes_base64"],
        validate=True,
    )

    assert decoded.startswith(b"<svg")
    assert (
        hashlib.sha256(decoded).hexdigest()
        == artifact["asset"]["sha256"]
    )


def test_materializer_validation_passes() -> None:
    package = make_package()
    artifact = materialize_package(package)

    assert validate_materialized_artifact(
        artifact,
        package,
    ) == ()


def test_package_tampering_is_rejected() -> None:
    package = make_package()

    package["reviewed_context"]["bound_claims"][0]["claim_text"] = (
        "TAMPERED CLAIM"
    )

    try:
        materialize_package(package)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError(
            "tampered package was accepted"
        )


def test_asset_tampering_is_rejected() -> None:
    package = make_package()
    artifact = materialize_package(package)

    artifact["asset"]["bytes_base64"] = base64.b64encode(
        b"tampered"
    ).decode("ascii")

    errors = validate_materialized_artifact(
        artifact,
        package,
    )

    assert (
        "materialized visual asset digest mismatch"
        in errors
    )


if __name__ == "__main__":
    test_materializer_produces_artifact()
    test_materializer_validation_passes()
    test_package_tampering_is_rejected()
    test_asset_tampering_is_rejected()
    print("BLOG VISUAL MATERIALIZER TESTS = PASS")
