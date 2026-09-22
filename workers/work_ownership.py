"""Deterministic work ownership classification.

Durable workflow state and live ownership are separate facts.

This module does not:
- start workers,
- mutate queues,
- recover claims,
- grant admission,
- grant publication authority.

It only classifies observed ownership state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


WORK_OWNERSHIP_VERSION = "anarchi.work-ownership.v1"


class OwnershipState(str, Enum):
    AVAILABLE = "AVAILABLE"
    OWNED = "OWNED"
    ORPHANED = "ORPHANED"
    STALE_BUT_OWNED = "STALE_BUT_OWNED"
    UNOWNED_ACTIVE = "UNOWNED_ACTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class WorkClaim:
    work_id: str
    durable_state: str
    claimed_at: datetime | None
    owner_present: bool | None


@dataclass(frozen=True)
class OwnershipDecision:
    state: OwnershipState
    recoverable: bool
    reason: str

    @property
    def grants_admission(self) -> bool:
        return False

    @property
    def grants_execution(self) -> bool:
        return False

    @property
    def grants_publication(self) -> bool:
        return False


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            "claim timestamps must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def classify_ownership(
    claim: WorkClaim,
    *,
    available_states: frozenset[str],
    claimed_states: frozenset[str],
    now: datetime,
    stale_after: timedelta,
) -> OwnershipDecision:
    now = _utc(now)

    if stale_after <= timedelta(0):
        raise ValueError(
            "stale_after must be positive"
        )

    if claim.durable_state in available_states:
        if claim.claimed_at is not None:
            return OwnershipDecision(
                state=OwnershipState.UNKNOWN,
                recoverable=False,
                reason=(
                    "available durable state unexpectedly "
                    "retains claim ownership"
                ),
            )

        return OwnershipDecision(
            state=OwnershipState.AVAILABLE,
            recoverable=False,
            reason=(
                "work is durably available and has no owner"
            ),
        )

    if claim.durable_state not in claimed_states:
        return OwnershipDecision(
            state=OwnershipState.UNKNOWN,
            recoverable=False,
            reason=(
                "durable state is outside the supplied "
                "ownership grammar"
            ),
        )

    if claim.claimed_at is None:
        return OwnershipDecision(
            state=OwnershipState.UNOWNED_ACTIVE,
            recoverable=False,
            reason=(
                "active durable state has no claim timestamp"
            ),
        )

    if claim.owner_present is None:
        return OwnershipDecision(
            state=OwnershipState.UNKNOWN,
            recoverable=False,
            reason=(
                "live owner presence is unknown"
            ),
        )

    claimed_at = _utc(claim.claimed_at)
    age = now - claimed_at
    stale = age >= stale_after

    if claim.owner_present:
        if stale:
            return OwnershipDecision(
                state=OwnershipState.STALE_BUT_OWNED,
                recoverable=False,
                reason=(
                    "claim is stale by age but a live owner "
                    "still exists"
                ),
            )

        return OwnershipDecision(
            state=OwnershipState.OWNED,
            recoverable=False,
            reason=(
                "active durable claim has a live owner"
            ),
        )

    if not stale:
        return OwnershipDecision(
            state=OwnershipState.UNKNOWN,
            recoverable=False,
            reason=(
                "live owner is absent but claim has not "
                "crossed the recovery staleness guard"
            ),
        )

    return OwnershipDecision(
        state=OwnershipState.ORPHANED,
        recoverable=True,
        reason=(
            "active durable claim is stale and has no "
            "live owner"
        ),
    )
