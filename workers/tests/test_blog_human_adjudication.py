from __future__ import annotations

import json

import pytest

from blog_loop.human_adjudication import (
    ADJUDICATION_SCHEMA,
    canonical_json,
    receipt_digest,
)


def test_receipt_digest_is_deterministic():
    payload = {
        "schema": ADJUDICATION_SCHEMA,
        "generation_job_id": 7,
        "artifact_digest": "abc",
        "decision": "APPROVED",
        "reviewer": "Alex",
        "reason": "",
        "created_at": "2026-09-21T00:00:00+00:00",
    }

    assert receipt_digest(payload) == receipt_digest(dict(payload))
    assert canonical_json(payload) == canonical_json(dict(payload))


def test_receipt_digest_changes_when_artifact_changes():
    base = {
        "schema": ADJUDICATION_SCHEMA,
        "generation_job_id": 7,
        "artifact_digest": "abc",
        "decision": "APPROVED",
        "reviewer": "Alex",
        "reason": "",
        "created_at": "2026-09-21T00:00:00+00:00",
    }

    changed = dict(base)
    changed["artifact_digest"] = "different"

    assert receipt_digest(base) != receipt_digest(changed)


def test_reviewer_is_part_of_receipt_identity():
    base = {
        "schema": ADJUDICATION_SCHEMA,
        "generation_job_id": 7,
        "artifact_digest": "abc",
        "decision": "APPROVED",
        "reviewer": "Alex",
        "reason": "",
        "created_at": "2026-09-21T00:00:00+00:00",
    }

    changed = dict(base)
    changed["reviewer"] = "Other Reviewer"

    assert receipt_digest(base) != receipt_digest(changed)
