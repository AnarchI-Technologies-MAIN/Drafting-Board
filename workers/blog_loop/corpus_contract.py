"""Blogger educational corpus topic contract.

This contract defines the bounded semantic unit used by the Blogger
educational corpus. A topic is knowledge, not an article.

Schema authority:
    anarchi.blogger.educational-topic.v1

Design principles:
    - Human-readable semantics.
    - Explicit uncertainty and provenance.
    - Destructive-construction learning path.
    - Demonstrations are first-class evidence-bearing objects.
    - Topic boundaries are explicit.
    - Articles are downstream artifacts, never the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CORPUS_TOPIC_SCHEMA = "anarchi.blogger.educational-topic.v1"


REQUIRED_FIELDS = (
    "topic_id",
    "title",
    "domain",
    "starting_question",
    "barrier",
    "evidence_required",
    "historical_context",
    "transformation",
    "current_truth",
    "lesson",
    "related_topics",
    "status",
    "provenance",
    "completion_boundary",
)


ALLOWED_STATUS = (
    "PLANNED",
    "RESEARCHING",
    "DRAFTED",
    "VALIDATING",
    "VERIFIED",
    "REJECTED",
    "DEPRECATED",
)


@dataclass(frozen=True)
class EducationalTopic:
    """Bounded educational knowledge unit."""

    topic_id: str
    title: str
    domain: str
    starting_question: str
    barrier: str
    evidence_required: list[dict[str, Any]]
    historical_context: str
    transformation: str
    current_truth: str
    lesson: str
    related_topics: list[str]
    status: str
    provenance: list[dict[str, Any]]
    completion_boundary: str
    prerequisites: list[str]
    demonstrations: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    diagrams: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical semantic representation."""

        return {
            "schema": CORPUS_TOPIC_SCHEMA,
            "topic_id": self.topic_id,
            "title": self.title,
            "domain": self.domain,
            "starting_question": self.starting_question,
            "barrier": self.barrier,
            "evidence_required": self.evidence_required,
            "historical_context": self.historical_context,
            "transformation": self.transformation,
            "current_truth": self.current_truth,
            "lesson": self.lesson,
            "related_topics": self.related_topics,
            "status": self.status,
            "provenance": self.provenance,
            "completion_boundary": self.completion_boundary,
            "prerequisites": self.prerequisites,
            "demonstrations": self.demonstrations,
            "examples": self.examples,
            "diagrams": self.diagrams,
        }


def validate_topic(payload: dict[str, Any]) -> list[str]:
    """Validate a topic semantically and structurally.

    Returns an empty list when valid.
    """

    errors: list[str] = []

    if payload.get("schema") != CORPUS_TOPIC_SCHEMA:
        errors.append("schema must equal the canonical Blogger educational topic schema")

    for field in REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"missing required field: {field}")

    topic_id = payload.get("topic_id")
    if not isinstance(topic_id, str) or not topic_id.strip():
        errors.append("topic_id must be a non-empty string")

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")

    domain = payload.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        errors.append("domain must be a non-empty string")

    if not isinstance(payload.get("evidence_required"), list):
        errors.append("evidence_required must be a list")

    if not isinstance(payload.get("related_topics"), list):
        errors.append("related_topics must be a list")

    if not isinstance(payload.get("provenance"), list):
        errors.append("provenance must be a list")

    status = payload.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"status must be one of: {', '.join(ALLOWED_STATUS)}")

    for field in (
        "starting_question",
        "barrier",
        "historical_context",
        "transformation",
        "current_truth",
        "lesson",
        "completion_boundary",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    return errors