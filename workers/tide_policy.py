"""Deterministic work-admission law for the AnarchI Editorial Foundry.

This module has no Docker, database, network, filesystem, publication,
or process-control authority.

It receives observations and returns an admission proposal.

Doctrine:
    STATE REQUESTS WORK.
    ADMISSION PERMITS WORK.
    WORKERS EXECUTE WORK.

Publication is intentionally outside Tide authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HostPressure(str, Enum):
    HEALTHY = "HEALTHY"
    PRESSURED = "PRESSURED"
    HOT = "HOT"


class TideState(str, Enum):
    UNKNOWN = "UNKNOWN"
    DRY = "DRY"
    LOW = "LOW"
    BALANCED = "BALANCED"
    BACKLOGGED = "BACKLOGGED"
    RISING = "RISING"
    PRESSURED = "PRESSURED"
    HOT = "HOT"


@dataclass(frozen=True)
class HostSnapshot:
    logical_cpus: int
    load_1m: float
    total_memory_bytes: int
    available_memory_bytes: int
    swap_in_bytes_per_sec: float = 0.0
    swap_out_bytes_per_sec: float = 0.0
    io_some_avg10: float = 0.0


@dataclass(frozen=True)
class TideSnapshot:
    queued: int = 0
    crawling: int = 0
    enriched: int = 0
    monetizing: int = 0
    ready: int = 0

    active_packets: int = 0

    generation_queued: int = 0
    generation_generating: int = 0
    staged: int = 0
    quality_hold: int = 0

    intake_rate_per_minute: float = 0.0
    drain_rate_per_minute: float = 0.0


@dataclass(frozen=True)
class TideThresholds:
    # Bootstrap pressure thresholds.
    # These are operating defaults, not canonical infrastructure law.

    pressured_memory_ratio: float = 0.25
    hot_memory_ratio: float = 0.12

    pressured_load_per_cpu: float = 1.00
    hot_load_per_cpu: float = 1.50

    pressured_io_some_avg10: float = 10.0
    hot_io_some_avg10: float = 25.0

    hot_swap_bytes_per_sec: float = 64 * 1024 * 1024

    # LOW is an admission hint, not a capacity ceiling.
    low_work_units: int = 3

    # These are backlog-pressure hints, not storage capacity limits.
    # They answer "is there already enough work downstream?"
    backlog_intake_queued: int = 8
    backlog_active_packets: int = 48
    backlog_generation_active: int = 4


@dataclass(frozen=True)
class AdmissionDecision:
    host_pressure: HostPressure
    tide_state: TideState

    admit_research: bool
    admit_crawler: bool
    admit_outreach: bool
    admit_generator: bool

    # Tide must never acquire publication authority.
    admit_publisher: bool

    reason: str


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def classify_host_pressure(
    host: HostSnapshot,
    thresholds: TideThresholds = TideThresholds(),
) -> HostPressure:
    memory_ratio = _ratio(
        host.available_memory_bytes,
        host.total_memory_bytes,
    )

    load_ratio = _ratio(
        host.load_1m,
        max(1, host.logical_cpus),
    )

    swap_rate = (
        max(0.0, host.swap_in_bytes_per_sec)
        + max(0.0, host.swap_out_bytes_per_sec)
    )

    if (
        memory_ratio <= thresholds.hot_memory_ratio
        or load_ratio >= thresholds.hot_load_per_cpu
        or host.io_some_avg10 >= thresholds.hot_io_some_avg10
        or swap_rate >= thresholds.hot_swap_bytes_per_sec
    ):
        return HostPressure.HOT

    if (
        memory_ratio <= thresholds.pressured_memory_ratio
        or load_ratio >= thresholds.pressured_load_per_cpu
        or host.io_some_avg10 >= thresholds.pressured_io_some_avg10
        or swap_rate > 0
    ):
        return HostPressure.PRESSURED

    return HostPressure.HEALTHY


def work_units(tide: TideSnapshot) -> int:
    return sum(
        (
            tide.queued,
            tide.crawling,
            tide.enriched,
            tide.monetizing,
            tide.ready,
            tide.active_packets,
            tide.generation_queued,
            tide.generation_generating,
            tide.staged,
            tide.quality_hold,
        )
    )


def backlog_velocity(tide: TideSnapshot) -> float:
    return tide.intake_rate_per_minute - tide.drain_rate_per_minute


def backlog_pressure(
    tide: TideSnapshot,
    thresholds: TideThresholds = TideThresholds(),
) -> bool:
    generation_active = (
        tide.generation_queued
        + tide.generation_generating
        + tide.staged
        + tide.quality_hold
    )

    return (
        tide.queued >= thresholds.backlog_intake_queued
        or tide.active_packets >= thresholds.backlog_active_packets
        or generation_active >= thresholds.backlog_generation_active
    )


def classify_tide(
    host_pressure: HostPressure,
    tide: TideSnapshot,
    thresholds: TideThresholds = TideThresholds(),
) -> TideState:
    if host_pressure is HostPressure.HOT:
        return TideState.HOT

    if host_pressure is HostPressure.PRESSURED:
        return TideState.PRESSURED

    units = work_units(tide)

    if units == 0:
        return TideState.DRY

    if backlog_velocity(tide) > 0:
        return TideState.RISING

    if backlog_pressure(tide, thresholds):
        return TideState.BACKLOGGED

    if units <= thresholds.low_work_units:
        return TideState.LOW

    return TideState.BALANCED


def decide(
    host: HostSnapshot,
    tide: TideSnapshot,
    thresholds: TideThresholds = TideThresholds(),
    inventory_known: bool = True,
    workload_activity_known: bool = True,
    precision_compute_active: bool = False,
    crawler_active: bool = False,
) -> AdmissionDecision:
    pressure = classify_host_pressure(host, thresholds)

    if not inventory_known:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=TideState.UNKNOWN,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=False,
            admit_generator=False,
            admit_publisher=False,
            reason="durable inventory is unknown; deny all work admission",
        )

    if not workload_activity_known:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=TideState.UNKNOWN,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=False,
            admit_generator=False,
            admit_publisher=False,
            reason=(
                "live workload ownership is unknown; "
                "deny all new work admission"
            ),
        )

    state = classify_tide(pressure, tide, thresholds)

    # Machine on fire:
    # begin no new work. Already-running bounded cycles are allowed to return.
    if state is TideState.HOT:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=False,
            admit_generator=False,
            admit_publisher=False,
            reason="host pressure is HOT; deny all new admissions",
        )

    # A bounded heavy worker already owns the floor.
    # Tide does not preempt it and must not admit another heavy cycle.
    if precision_compute_active:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=tide.enriched > 0,
            admit_generator=False,
            admit_publisher=False,
            reason=(
                "precision compute already owns the floor; "
                "deny new crawler and generator admission"
            ),
        )

    if crawler_active:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=tide.enriched > 0,
            admit_generator=False,
            admit_publisher=False,
            reason=(
                "crawler already owns a bounded floor cycle; "
                "deny additional heavy admission until it returns"
            ),
        )

    # Pressure is rising:
    # close upstream intake and deny disk-heavy crawling and model compute.
    # Only lightweight downstream transformations may continue draining work.
    if state is TideState.PRESSURED:
        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=False,
            admit_outreach=tide.enriched > 0,
            admit_generator=False,
            admit_publisher=False,
            reason=(
                "host is PRESSURED; deny research, crawling, and heavy "
                "generation while permitting lightweight downstream drain"
            ),
        )

    # Enough durable work already exists downstream.
    # Precision/model compute owns the quiet floor when generation work exists.
    # Crawlers consume spare capacity and must not compete with that work.
    if state is TideState.BACKLOGGED:
        generator_work = (
            tide.ready > 0
            or tide.generation_queued > 0
        )

        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=(
                tide.queued > 0
                and not generator_work
            ),
            admit_outreach=tide.enriched > 0,
            admit_generator=generator_work,
            admit_publisher=False,
            reason=(
                "durable backlog exists; prioritize precision generation, "
                "restrain crawler while generator work is available"
                if generator_work
                else
                "durable backlog exists; no generator work is available, "
                "permit bounded crawler drain"
            ),
        )

    # Backlog is growing faster than it is draining.
    # Downstream precision compute takes priority over crawler IO.
    if state is TideState.RISING:
        generator_work = (
            tide.ready > 0
            or tide.generation_queued > 0
        )

        return AdmissionDecision(
            host_pressure=pressure,
            tide_state=state,
            admit_research=False,
            admit_crawler=(
                tide.queued > 0
                and not generator_work
            ),
            admit_outreach=tide.enriched > 0,
            admit_generator=generator_work,
            admit_publisher=False,
            reason=(
                "backlog velocity is positive; prioritize precision "
                "generation and restrain crawler"
                if generator_work
                else
                "backlog velocity is positive; no generator work is "
                "available, permit bounded crawler drain"
            ),
        )

    # DRY / LOW / BALANCED on a healthy host.
    # Precision/model work still owns the quiet floor when available.
    generator_work = (
        tide.ready > 0
        or tide.generation_queued > 0
    )

    return AdmissionDecision(
        host_pressure=pressure,
        tide_state=state,
        admit_research=True,
        admit_crawler=(
            tide.queued > 0
            and not generator_work
        ),
        admit_outreach=tide.enriched > 0,
        admit_generator=generator_work,
        admit_publisher=False,
        reason=(
            "host healthy and tide controlled; prioritize precision "
            "generation and restrain crawler"
            if generator_work
            else
            "host healthy and tide controlled; bounded admission permitted"
        ),
    )
