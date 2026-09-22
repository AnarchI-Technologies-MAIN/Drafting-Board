"""Read-only shadow observer for AnarchI Tide admission.

Authority boundary:
- may read /proc and /proc/pressure
- may perform SELECT-only PostgreSQL queries when DB is already reachable
- may evaluate tide_policy.decide()
- may print an admission proposal

It MUST NOT:
- start Docker
- start containers
- start services
- invoke workers
- mutate PostgreSQL
- publish anything
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tide_policy import HostSnapshot, TideSnapshot, decide
from workload_activity import (
    as_dict as workload_activity_as_dict,
    live_snapshot as live_workload_snapshot,
)


PROC = Path("/proc")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def logical_cpu_count() -> int:
    text = _read_text(PROC / "cpuinfo")
    count = sum(1 for line in text.splitlines() if line.startswith("processor"))
    return max(1, count or (os.cpu_count() or 1))


def load_1m() -> float:
    text = _read_text(PROC / "loadavg").strip()
    try:
        return float(text.split()[0])
    except (IndexError, ValueError):
        return 0.0


def memory_bytes() -> tuple[int, int]:
    values: dict[str, int] = {}

    for line in _read_text(PROC / "meminfo").splitlines():
        if ":" not in line:
            continue

        key, raw = line.split(":", 1)
        pieces = raw.strip().split()

        if not pieces:
            continue

        try:
            value = int(pieces[0])
        except ValueError:
            continue

        # /proc/meminfo is conventionally kB.
        values[key] = value * 1024

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)

    if total > 0:
        return total, available

    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)

            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys), int(status.ullAvailPhys)
        except (AttributeError, OSError):
            pass

    return 0, max(0, available)


def io_some_avg10() -> float:
    text = _read_text(PROC / "pressure" / "io")

    for line in text.splitlines():
        if not line.startswith("some "):
            continue

        for token in line.split():
            if token.startswith("avg10="):
                try:
                    return float(token.split("=", 1)[1])
                except ValueError:
                    return 0.0

    return 0.0


def _vmstat_snapshot() -> dict[str, int]:
    values: dict[str, int] = {}

    for line in _read_text(PROC / "vmstat").splitlines():
        pieces = line.split()

        if len(pieces) != 2:
            continue

        try:
            values[pieces[0]] = int(pieces[1])
        except ValueError:
            continue

    return values


def swap_activity_bytes_per_sec() -> tuple[float, float]:
    """Conservative instantaneous observation.

    We intentionally do not fabricate a rate from cumulative vmstat counters.
    Mutation 002 therefore reports zero rate unless an explicit externally
    measured rate is supplied later.

    The raw cumulative counters are still emitted separately for evidence.
    """

    return 0.0, 0.0


def raw_swap_pages() -> dict[str, int]:
    values = _vmstat_snapshot()

    return {
        "pswpin_pages": values.get("pswpin", 0),
        "pswpout_pages": values.get("pswpout", 0),
    }


def host_snapshot() -> HostSnapshot:
    total, available = memory_bytes()
    swap_in, swap_out = swap_activity_bytes_per_sec()

    return HostSnapshot(
        logical_cpus=logical_cpu_count(),
        load_1m=load_1m(),
        total_memory_bytes=total,
        available_memory_bytes=available,
        swap_in_bytes_per_sec=swap_in,
        swap_out_bytes_per_sec=swap_out,
        io_some_avg10=io_some_avg10(),
    )


def _db_target() -> tuple[str, int]:
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")

    try:
        port = int(os.getenv("POSTGRES_PORT", "5433"))
    except ValueError:
        port = 5432

    return host, port


def postgres_reachable(timeout_seconds: float = 0.25) -> bool:
    host, port = _db_target()

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False



def _psql_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PGHOST"] = os.getenv("POSTGRES_HOST", "127.0.0.1")
    env["PGPORT"] = os.getenv("POSTGRES_PORT", "5433")
    env["PGDATABASE"] = os.getenv("POSTGRES_DB", "anarchi_db")
    env["PGUSER"] = os.getenv("POSTGRES_USER", "anarchi")

    password = os.getenv("POSTGRES_PASSWORD", "")
    if password:
        env["PGPASSWORD"] = password

    return env


def _run_psql_scalar(sql: str) -> list[str]:
    completed = subprocess.run(
        [
            "psql",
            "-X",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"BEGIN READ ONLY; {sql} ROLLBACK;",
        ],
        env=_psql_env(),
        text=True,
        capture_output=True,
        timeout=3,
        check=True,
    )

    return [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
        and line.strip() not in {"BEGIN", "ROLLBACK"}
    ]


def read_queue_snapshot() -> tuple[TideSnapshot, dict[str, Any]]:
    evidence: dict[str, Any] = {
        "database_reachable": False,
        "database_queried": False,
        "database_error": None,
        "counts": {},
        "adapter": "psql-fixed-read-only",
    }

    if not postgres_reachable():
        evidence["database_error"] = "postgres endpoint not reachable"
        return TideSnapshot(), evidence

    evidence["database_reachable"] = True

    try:
        intake_rows = _run_psql_scalar(
            """
            SELECT state || '|' || COUNT(*)
            FROM intake_queries
            GROUP BY state
            ORDER BY state;
            """
        )

        packet_rows = _run_psql_scalar(
            """
            SELECT COUNT(*)
            FROM packet_bucket
            WHERE consumed_at IS NULL;
            """
        )

        generation_rows = _run_psql_scalar(
            """
            SELECT state || '|' || COUNT(*)
            FROM generation_queue
            GROUP BY state
            ORDER BY state;
            """
        )

        counts: dict[str, int] = {}

        for row in intake_rows:
            state, count = row.split("|", 1)
            counts[f"intake_{state}"] = int(count)

        if packet_rows:
            counts["active_packets"] = int(packet_rows[0])

        for row in generation_rows:
            state, count = row.split("|", 1)
            counts[f"generation_{state}"] = int(count)

        evidence["database_queried"] = True
        evidence["counts"] = counts

    except Exception as exc:
        evidence["database_error"] = f"{type(exc).__name__}: {exc}"
        return TideSnapshot(), evidence

    return (
        TideSnapshot(
            queued=counts.get("intake_queued", 0),
            crawling=counts.get("intake_crawling", 0),
            enriched=counts.get("intake_enriched", 0),
            monetizing=counts.get("intake_monetizing", 0),
            ready=counts.get("intake_ready", 0),
            active_packets=counts.get("active_packets", 0),
            generation_queued=counts.get("generation_queued", 0),
            generation_generating=counts.get("generation_generating", 0),
            staged=counts.get("generation_staged", 0),
            quality_hold=counts.get("generation_quality_hold", 0),
            intake_rate_per_minute=0.0,
            drain_rate_per_minute=0.0,
        ),
        evidence,
    )


def observe() -> dict[str, Any]:
    host = host_snapshot()
    tide, database = read_queue_snapshot()
    inventory_known = bool(
        database.get("database_reachable")
        and database.get("database_queried")
    )

    workload_activity_known = True
    workload_activity_error = None

    try:
        workload_snapshot = live_workload_snapshot()
        workload_activity = workload_activity_as_dict(
            workload_snapshot
        )
    except Exception as exc:
        workload_activity_known = False
        workload_activity_error = (
            f"{type(exc).__name__}: {exc}"
        )
        workload_snapshot = None
        workload_activity = {
            "version": None,
            "authority": {
                "admission": False,
                "execution": False,
                "recovery": False,
                "publication": False,
            },
            "active": {
                "crawler": False,
                "generator": False,
                "reviewer": False,
                "illustrator": False,
                "precision_compute": False,
            },
            "counts": {},
            "runtimes": [],
        }

    precision_compute_active = bool(
        workload_snapshot
        and workload_snapshot.precision_compute_active
    )

    crawler_active = bool(
        workload_snapshot
        and workload_snapshot.crawler_active
    )

    decision = decide(
        host,
        tide,
        inventory_known=inventory_known,
        workload_activity_known=workload_activity_known,
        precision_compute_active=precision_compute_active,
        crawler_active=crawler_active,
    )

    return {
        "mode": "shadow",
        "authority": {
            "docker_start": False,
            "container_start": False,
            "worker_start": False,
            "database_write": False,
            "publication": False,
        },
        "host": asdict(host),
        "raw_swap": raw_swap_pages(),
        "tide": asdict(tide),
        "database": database,
        "inventory_known": inventory_known,
        "workload_activity_known": workload_activity_known,
        "workload_activity_error": workload_activity_error,
        "workload_activity": workload_activity,
        "decision": {
            "host_pressure": decision.host_pressure.value,
            "tide_state": decision.tide_state.value,
            "admit_research": decision.admit_research,
            "admit_crawler": decision.admit_crawler,
            "admit_outreach": decision.admit_outreach,
            "admit_generator": decision.admit_generator,
            "admit_publisher": decision.admit_publisher,
            "reason": decision.reason,
        },
    }


def main() -> None:
    print(
        json.dumps(
            observe(),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
