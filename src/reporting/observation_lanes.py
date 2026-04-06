from __future__ import annotations

from dataclasses import dataclass
import sqlite3
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


def get_observation_lanes() -> dict[str, ObservationLaneAdapter]:
    """Return canonical observation lanes for the current process.

    Keeps lazy import to avoid cycles and to allow independent execution.
    """

    global _OBSERVATION_LANE_CACHE
    if _OBSERVATION_LANE_CACHE is not None:
        return dict(_OBSERVATION_LANE_CACHE)

    from src.reporting.openrecall_import import OPENRECALL_OBSERVATION_LANE
    from src.reporting.worldmonitor_import import WORLDMONITOR_OBSERVATION_LANE

    _OBSERVATION_LANE_CACHE = {
        OPENRECALL_OBSERVATION_LANE.key: OPENRECALL_OBSERVATION_LANE,
        WORLDMONITOR_OBSERVATION_LANE.key: WORLDMONITOR_OBSERVATION_LANE,
    }
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
    "ObservationLaneAdapter",
    "get_observation_lane",
    "get_observation_lanes",
    "load_observation_activity_rows",
    "load_observation_import_runs",
    "load_observation_units",
    "build_observation_summary",
    "query_observation_captures",
]
