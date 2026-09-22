"""Deterministic filesystem store for Blogger educational topics."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from blog_loop.corpus_contract import EducationalTopic, validate_topic


class CorpusStoreError(ValueError):
    """Raised when a corpus operation violates the store contract."""


class CorpusStore:
    """Persist validated educational topics as canonical JSON files."""

    def __init__(self, root: str | Path = "data/corpus") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, topic_id: str) -> Path:
        if not isinstance(topic_id, str) or not topic_id.strip():
            raise CorpusStoreError("topic_id must be a non-empty string")
        if Path(topic_id).name != topic_id or topic_id in {".", ".."}:
            raise CorpusStoreError(
                "topic_id must be a simple filename-safe identifier"
            )
        return self.root / f"{topic_id}.json"

    def save_topic(self, topic: EducationalTopic) -> Path:
        payload = topic.to_dict()
        errors = validate_topic(payload)
        if errors:
            raise CorpusStoreError("invalid topic: " + "; ".join(errors))

        target = self._path(topic.topic_id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target

    def load_topic(self, topic_id: str) -> dict[str, Any]:
        path = self._path(topic_id)
        if not path.is_file():
            raise FileNotFoundError(path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_topic(payload)
        if errors:
            raise CorpusStoreError(
                "stored topic is invalid: " + "; ".join(errors)
            )
        return payload

    def list_topic_ids(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.json"))

    def delete_topic(self, topic_id: str) -> None:
        self._path(topic_id).unlink()

