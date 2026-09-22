"""Deterministic identity and fail-closed validation primitives."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urlparse


HEX64 = re.compile(r"^[0-9a-f]{64}$")
NO_AUTHORITY = {
    "factual_authority": "NONE",
    "publication_authority": "NONE",
    "approval": "NONE",
}


class ContractError(ValueError):
    """Raised when a contract cannot be materialized without ambiguity."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def receipt_payload(receipt: dict[str, Any], digest_field: str = "receipt_digest") -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != digest_field}


def seal_receipt(payload: dict[str, Any], digest_field: str = "receipt_digest") -> dict[str, Any]:
    result = dict(payload)
    result[digest_field] = canonical_digest(result)
    return result


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.endswith("Z") is False:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def valid_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def exact_fields(value: dict[str, Any], required: Iterable[str], optional: Iterable[str] = ()) -> list[str]:
    required_set, optional_set = set(required), set(optional)
    errors: list[str] = []
    missing = sorted(required_set - set(value))
    extra = sorted(set(value) - required_set - optional_set)
    if missing:
        errors.append("missing fields: " + ",".join(missing))
    if extra:
        errors.append("unexpected fields: " + ",".join(extra))
    return errors


def validate_authority_none(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected in NO_AUTHORITY.items():
        require(value.get(field) == expected, f"{field} must remain {expected}", errors)
    return errors


def validate_receipt(receipt: dict[str, Any], *, digest_field: str = "receipt_digest") -> tuple[str, ...]:
    errors: list[str] = []
    require(isinstance(receipt, dict), "receipt must be an object", errors)
    if not isinstance(receipt, dict):
        return tuple(errors)
    digest = receipt.get(digest_field)
    require(valid_digest(digest), f"{digest_field} must be a lowercase SHA-256", errors)
    if valid_digest(digest):
        require(
            digest == canonical_digest(receipt_payload(receipt, digest_field)),
            f"{digest_field} does not match canonical payload",
            errors,
        )
    return tuple(errors)


def assert_valid(errors: Iterable[str]) -> None:
    values = tuple(errors)
    if values:
        raise ContractError("; ".join(values))
