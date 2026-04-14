from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import importlib
import os
from typing import Any

@dataclass(frozen=True, slots=True)
class ObservationLaneAdapter:
    """Bounded contract for source-to-observation ingestion lanes.

    The contract is read/write surface only.
    Lanes stay non-authoritative and should expose only:
    - schema bootstrap
    - capture imports
    - source-unit loaders
    - bounded read-model projections
    """

    lane_key: str
    source_unit_type: str
    source_label: str
    ensure_schema: Any
    import_data: Any
    load_units: Any
    load_activity_rows: Any
    load_import_runs: Any
    build_summary: Any
    query_captures: Any

    @property
    def key(self) -> str:
        return str(self.lane_key).strip().lower()


_OBSERVATION_LANE_CACHE: dict[str, ObservationLaneAdapter] | None = None


def register_observation_lane(adapter: ObservationLaneAdapter, *, replace: bool = False) -> None:
    """Register one bounded observation-lane adapter.

    Parameters
    ----------
    adapter:
        Adapter describing one source lane.
    replace:
        If False (default), duplicate lane keys raise.
        If True, explicit replacement is allowed by caller.
    """

    global _OBSERVATION_LANE_CACHE
    key = adapter.key
    if _OBSERVATION_LANE_CACHE is None:
        _OBSERVATION_LANE_CACHE = {}
    if key in _OBSERVATION_LANE_CACHE and not replace:
        raise ValueError(f"duplicate observation lane key: {key}")
    _OBSERVATION_LANE_CACHE[key] = adapter


def clear_observation_lane_registry_for_tests() -> None:
    """Clear cached lane registry, intended for test isolation."""

    global _OBSERVATION_LANE_CACHE
    _OBSERVATION_LANE_CACHE = None


def _iter_discovery_modules() -> Iterable[str]:
    seen: set[str] = set()
    env_modules = os.environ.get("SENSIBLAW_OBSERVATION_LANE_MODULES")
    if env_modules:
        for item in env_modules.split(","):
            module_name = item.strip()
            if module_name and module_name not in seen:
                seen.add(module_name)
                yield module_name
    for module_name in ("src.reporting.openrecall_import", "src.reporting.worldmonitor_import"):
        if module_name not in seen:
            yield module_name


def _load_lane_from_module(module_name: str) -> None:
    module = importlib.import_module(module_name)
    for name in dir(module):
        if not name.endswith("_OBSERVATION_LANE"):
            continue
        adapter = getattr(module, name, None)
        if isinstance(adapter, ObservationLaneAdapter):
            register_observation_lane(adapter)
    if "OBSERVATION_LANE" in dir(module):
        adapter = getattr(module, "OBSERVATION_LANE", None)
        if isinstance(adapter, ObservationLaneAdapter):
            register_observation_lane(adapter)


def get_observation_lanes() -> dict[str, ObservationLaneAdapter]:
    """Return canonical observation lanes for the current process.

    Keeps lazy import to avoid cycles and to allow independent execution.
    """

    global _OBSERVATION_LANE_CACHE
    if _OBSERVATION_LANE_CACHE is not None:
        return dict(_OBSERVATION_LANE_CACHE)

    for module_name in _iter_discovery_modules():
        _load_lane_from_module(module_name)
    if _OBSERVATION_LANE_CACHE is None:
        _OBSERVATION_LANE_CACHE = {}
    return dict(_OBSERVATION_LANE_CACHE)


def get_observation_lane(source_key: str | None) -> ObservationLaneAdapter | None:
    """Resolve a lane by short key.

    Parameters
    ----------
    source_key:
        Any normalizable key such as ``openrecall`` or ``worldmonitor``.
    """

    if source_key is None:
        return None
    lanes = get_observation_lanes()
    return lanes.get(str(source_key).strip().lower())


def load_observation_units(
    db_path: str | Path,
    lane: str,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    limit: int | None = None,
) -> list["TextUnit"]:
    from src.reporting.structure_report import TextUnit

    adapter = get_observation_lane(lane)
    if adapter is None:
        raise ValueError(f"unknown observation lane: {lane}")
    return adapter.load_units(db_path, import_run_id=import_run_id, date=date, limit=limit)


def load_observation_activity_rows(
    conn: sqlite3.Connection,
    lane: str,
    *,
    date: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    adapter = get_observation_lane(lane)
    if adapter is None:
        raise ValueError(f"unknown observation lane: {lane}")
    return adapter.load_activity_rows(conn, date=date, limit=limit)


def load_observation_import_runs(
    conn: sqlite3.Connection,
    lane: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    adapter = get_observation_lane(lane)
    if adapter is None:
        raise ValueError(f"unknown observation lane: {lane}")
    return adapter.load_import_runs(conn, limit=limit)


def build_observation_summary(
    conn: sqlite3.Connection,
    lane: str,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    adapter = get_observation_lane(lane)
    if adapter is None:
        raise ValueError(f"unknown observation lane: {lane}")
    return adapter.build_summary(
        conn,
        import_run_id=import_run_id,
        date=date,
        source_kind=source_kind,
    )


def query_observation_captures(
    conn: sqlite3.Connection,
    lane: str,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    adapter = get_observation_lane(lane)
    if adapter is None:
        raise ValueError(f"unknown observation lane: {lane}")
    return adapter.query_captures(
        conn,
        import_run_id=import_run_id,
        date=date,
        source_kind=source_kind,
        text_query=text_query,
        limit=limit,
    )


__all__ = [
    "clear_observation_lane_registry_for_tests",
    "ObservationLaneAdapter",
    "register_observation_lane",
    "get_observation_lane",
    "get_observation_lanes",
    "load_observation_activity_rows",
    "load_observation_import_runs",
    "load_observation_units",
    "build_observation_summary",
    "query_observation_captures",
]
