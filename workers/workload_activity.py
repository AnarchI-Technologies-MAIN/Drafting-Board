"""Read-only workload activity observation.

This module translates live container metadata into bounded workload
families.

It grants no:
- container authority,
- worker authority,
- recovery authority,
- admission authority,
- database authority,
- publication authority.

Explicit ANARCHI_WORKLOAD_ROLE metadata wins over conservative
Compose-service fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import subprocess
from typing import Iterable


WORKLOAD_ACTIVITY_VERSION = "anarchi.workload-activity.v1"

ROLE_ENV = "ANARCHI_WORKLOAD_ROLE"


class WorkloadFamily(str, Enum):
    CRAWLER = "CRAWLER"
    GENERATOR = "GENERATOR"
    REVIEWER = "REVIEWER"
    ILLUSTRATOR = "ILLUSTRATOR"
    UNKNOWN = "UNKNOWN"


EXPLICIT_ROLE_MAP = {
    "crawler": WorkloadFamily.CRAWLER,
    "generator": WorkloadFamily.GENERATOR,
    "atomic-reviewer": WorkloadFamily.REVIEWER,
    "reviewer": WorkloadFamily.REVIEWER,
    "illustrator": WorkloadFamily.ILLUSTRATOR,
}


SERVICE_FALLBACK_MAP = {
    "crawler-bot": WorkloadFamily.CRAWLER,
    "llm-blogger": WorkloadFamily.GENERATOR,
}


@dataclass(frozen=True)
class RuntimeObservation:
    container_id: str
    container_name: str
    compose_service: str
    explicit_role: str | None
    workload_family: WorkloadFamily


@dataclass(frozen=True)
class WorkloadActivitySnapshot:
    runtimes: tuple[RuntimeObservation, ...]

    def active_count(
        self,
        family: WorkloadFamily,
    ) -> int:
        return sum(
            1
            for item in self.runtimes
            if item.workload_family is family
        )

    @property
    def crawler_active(self) -> bool:
        return self.active_count(
            WorkloadFamily.CRAWLER
        ) > 0

    @property
    def generator_active(self) -> bool:
        return self.active_count(
            WorkloadFamily.GENERATOR
        ) > 0

    @property
    def reviewer_active(self) -> bool:
        return self.active_count(
            WorkloadFamily.REVIEWER
        ) > 0

    @property
    def illustrator_active(self) -> bool:
        return self.active_count(
            WorkloadFamily.ILLUSTRATOR
        ) > 0

    @property
    def precision_compute_active(self) -> bool:
        return (
            self.generator_active
            or self.reviewer_active
            or self.illustrator_active
        )

    @property
    def grants_admission(self) -> bool:
        return False

    @property
    def grants_execution(self) -> bool:
        return False

    @property
    def grants_recovery(self) -> bool:
        return False

    @property
    def grants_publication(self) -> bool:
        return False


def normalize_role(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()

    if not normalized:
        return None

    return normalized


def classify_runtime(
    *,
    compose_service: str,
    explicit_role: str | None,
) -> WorkloadFamily:
    role = normalize_role(
        explicit_role
    )

    if role is not None:
        return EXPLICIT_ROLE_MAP.get(
            role,
            WorkloadFamily.UNKNOWN,
        )

    return SERVICE_FALLBACK_MAP.get(
        compose_service,
        WorkloadFamily.UNKNOWN,
    )


def env_value(
    env_items: Iterable[str],
    key: str,
) -> str | None:
    prefix = key + "="

    for item in env_items:
        if item.startswith(prefix):
            return item[len(prefix):]

    return None


def observation_from_inspect(
    payload: dict,
) -> RuntimeObservation:
    config = payload.get("Config") or {}
    labels = config.get("Labels") or {}
    env_items = config.get("Env") or []

    compose_service = labels.get(
        "com.docker.compose.service",
        "",
    )

    explicit_role = env_value(
        env_items,
        ROLE_ENV,
    )

    return RuntimeObservation(
        container_id=str(
            payload.get("Id", "")
        ),
        container_name=str(
            payload.get("Name", "")
        ).lstrip("/"),
        compose_service=compose_service,
        explicit_role=normalize_role(
            explicit_role
        ),
        workload_family=classify_runtime(
            compose_service=compose_service,
            explicit_role=explicit_role,
        ),
    )


def snapshot_from_inspect(
    payloads: Iterable[dict],
) -> WorkloadActivitySnapshot:
    return WorkloadActivitySnapshot(
        runtimes=tuple(
            observation_from_inspect(item)
            for item in payloads
        )
    )


def live_snapshot() -> WorkloadActivitySnapshot:
    ids_raw = subprocess.check_output(
        [
            "docker",
            "ps",
            "-q",
        ],
        text=True,
    )

    ids = [
        item.strip()
        for item in ids_raw.splitlines()
        if item.strip()
    ]

    if not ids:
        return WorkloadActivitySnapshot(
            runtimes=(),
        )

    inspect_raw = subprocess.check_output(
        [
            "docker",
            "inspect",
            *ids,
        ],
        text=True,
    )

    payloads = json.loads(
        inspect_raw
    )

    return snapshot_from_inspect(
        payloads
    )


def as_dict(
    snapshot: WorkloadActivitySnapshot,
) -> dict:
    return {
        "version": WORKLOAD_ACTIVITY_VERSION,
        "authority": {
            "admission": False,
            "execution": False,
            "recovery": False,
            "publication": False,
        },
        "active": {
            "crawler": snapshot.crawler_active,
            "generator": snapshot.generator_active,
            "reviewer": snapshot.reviewer_active,
            "illustrator": snapshot.illustrator_active,
            "precision_compute": (
                snapshot.precision_compute_active
            ),
        },
        "counts": {
            family.value: snapshot.active_count(
                family
            )
            for family in WorkloadFamily
        },
        "runtimes": [
            {
                "container_id": item.container_id,
                "container_name": item.container_name,
                "compose_service": item.compose_service,
                "explicit_role": item.explicit_role,
                "workload_family": (
                    item.workload_family.value
                ),
            }
            for item in snapshot.runtimes
        ],
    }


def main() -> None:
    print(
        json.dumps(
            as_dict(
                live_snapshot()
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
