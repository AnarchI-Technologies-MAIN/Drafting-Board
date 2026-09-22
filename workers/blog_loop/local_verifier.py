"""Local Ollama execution adapter for Blog Atomic Reviewer.

This module adapts the existing local chat function to the verifier callable
expected by blog_loop.review_execution.

The local model remains proposal-only.

No publication, approval, adjudication, or factual authority originates here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from editorial_verifier_adapter import VerifierCase


ChatFunction = Callable[..., tuple[str, dict[str, Any]]]


@dataclass(frozen=True)
class LocalVerifierObservation:
    raw: str
    metrics: dict[str, Any]


def make_local_verifier(
    *,
    chat_function: ChatFunction,
    observations: list[LocalVerifierObservation] | None = None,
):
    def execute(
        case: VerifierCase,
        messages: list[dict[str, str]],
    ) -> str:
        raw, metrics = chat_function(
            messages,
            json_mode=True,
            num_predict=700,
            temperature=0.0,
        )

        if not isinstance(raw, str):
            raise TypeError(
                "local verifier returned non-string response"
            )

        if not isinstance(metrics, dict):
            raise TypeError(
                "local verifier returned invalid metrics"
            )

        if observations is not None:
            observations.append(
                LocalVerifierObservation(
                    raw=raw,
                    metrics=dict(metrics),
                )
            )

        return raw

    return execute
