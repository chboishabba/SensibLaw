"""Render post-run progress graphs from the existing phase ledger.

The progress JSON written by :class:`src.runtime.progress.PhaseRecorder` is the
single diagnostic source.  This module does not create another event log or
runtime database table; it turns the retained structured events directly into
PNG/SVG review artefacts after a run.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


PROGRESS_PLOT_SCHEMA_VERSION = "sl.progress_plot_manifest.v0_1"


@dataclass(frozen=True, slots=True)
class MetricPoint:
    phase: str
    subject_ref: str
    stage: str
    metric: str
    unit: str
    elapsed_seconds: float
    completed: float
    per_second: float | None
    observed_at: str


@dataclass(frozen=True, slots=True)
class StageInterval:
    phase: str
    subject_ref: str
    stage: str
    started_seconds: float
    ended_seconds: float
    state: str


def load_progress_ledger(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("progress ledger must be an object containing an events array")
    return payload


def metric_points(events: Iterable[Mapping[str, Any]]) -> tuple[MetricPoint, ...]:
    points: list[MetricPoint] = []
    for event in events:
        measures = event.get("measures")
        if not isinstance(measures, Mapping):
            continue
        stage = str(event.get("active_stage") or event.get("message") or "")
        if not stage:
            continue
        elapsed_seconds = float(event.get("elapsed_ms") or 0) / 1_000.0
        for metric, raw in measures.items():
            if not isinstance(raw, Mapping):
                continue
            completed = raw.get("completed")
            if not isinstance(completed, (int, float)):
                continue
            rate = raw.get("per_second")
            points.append(
                MetricPoint(
                    phase=str(event.get("phase") or ""),
                    subject_ref=str(event.get("subject_ref") or ""),
                    stage=stage,
                    metric=str(metric),
                    unit=str(raw.get("unit") or metric),
                    elapsed_seconds=elapsed_seconds,
                    completed=float(completed),
                    per_second=float(rate) if isinstance(rate, (int, float)) else None,
                    observed_at=str(event.get("observed_at") or ""),
                )
            )
    return tuple(points)


def stage_intervals(events: Sequence[Mapping[str, Any]]) -> tuple[StageInterval, ...]:
    opened: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    intervals: list[StageInterval] = []
    for event in events:
        state = str(event.get("state") or "")
        stage = str(event.get("active_stage") or event.get("message") or "")
        if not stage:
            continue
        key = (
            str(event.get("phase") or ""),
            str(event.get("subject_ref") or ""),
            stage,
        )
        elapsed = float(event.get("elapsed_ms") or 0) / 1_000.0
        if state == "stage_started":
            opened[key].append(elapsed)
        elif state == "stage_completed" and opened[key]:
            started = opened[key].pop(0)
            intervals.append(
                StageInterval(
                    phase=key[0],
                    subject_ref=key[1],
                    stage=key[2],
                    started_seconds=started,
                    ended_seconds=max(started, elapsed),
                    state=state,
                )
            )
    return tuple(intervals)


def _safe_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    return cleaned.strip("_") or "unknown"


def _write_rate_graphs(
    points: Sequence[MetricPoint],
    output_dir: Path,
    *,
    formats: Sequence[str],
) -> list[str]:
    outputs: list[str] = []
    grouped: dict[tuple[str, str, str], list[MetricPoint]] = defaultdict(list)
    for point in points:
        if point.per_second is not None:
            grouped[(point.subject_ref, point.stage, point.unit)].append(point)

    for (subject_ref, stage, unit), rows in sorted(grouped.items()):
        by_metric: dict[str, list[MetricPoint]] = defaultdict(list)
        for row in rows:
            by_metric[row.metric].append(row)
        if not by_metric:
            continue
        figure, axis = plt.subplots(figsize=(12, 7))
        for metric, metric_rows in sorted(by_metric.items()):
            ordered = sorted(metric_rows, key=lambda row: row.elapsed_seconds)
            axis.plot(
                [row.elapsed_seconds for row in ordered],
                [row.per_second for row in ordered],
                marker=".",
                linewidth=1.4,
                label=metric,
            )
        axis.set_title(f"{subject_ref or 'run'} — {stage} ({unit}/s)")
        axis.set_xlabel("elapsed seconds")
        axis.set_ylabel(f"{unit} per second")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best", fontsize="small")
        figure.tight_layout()
        stem = f"rates__{_safe_name(subject_ref)}__{_safe_name(stage)}__{_safe_name(unit)}"
        for suffix in formats:
            path = output_dir / f"{stem}.{suffix}"
            figure.savefig(path, dpi=160)
            outputs.append(str(path))
        plt.close(figure)
    return outputs


def _write_stage_timeline(
    intervals: Sequence[StageInterval],
    output_dir: Path,
    *,
    formats: Sequence[str],
) -> list[str]:
    if not intervals:
        return []
    outputs: list[str] = []
    labels = [
        f"{row.subject_ref or row.phase} — {row.stage}"
        for row in sorted(intervals, key=lambda item: (item.started_seconds, item.stage))
    ]
    ordered = sorted(intervals, key=lambda item: (item.started_seconds, item.stage))
    figure_height = max(5.0, min(18.0, 0.38 * len(ordered) + 2.0))
    figure, axis = plt.subplots(figsize=(14, figure_height))
    for index, row in enumerate(ordered):
        axis.barh(
            index,
            row.ended_seconds - row.started_seconds,
            left=row.started_seconds,
            height=0.7,
        )
    axis.set_yticks(range(len(labels)), labels=labels)
    axis.invert_yaxis()
    axis.set_xlabel("elapsed seconds")
    axis.set_title("Document-stage timeline")
    axis.grid(True, axis="x", alpha=0.25)
    figure.tight_layout()
    for suffix in formats:
        path = output_dir / f"stage_timeline.{suffix}"
        figure.savefig(path, dpi=160)
        outputs.append(str(path))
    plt.close(figure)
    return outputs


def render_progress_plots(
    ledger: Mapping[str, Any],
    output_dir: str | Path,
    *,
    formats: Sequence[str] = ("png", "svg"),
) -> dict[str, Any]:
    events = ledger.get("events")
    if not isinstance(events, list):
        raise ValueError("progress ledger requires an events array")
    selected_formats = tuple(dict.fromkeys(str(value).lower() for value in formats))
    if not selected_formats or any(value not in {"png", "svg"} for value in selected_formats):
        raise ValueError("formats must contain png and/or svg")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    points = metric_points(events)
    intervals = stage_intervals(events)
    outputs = [
        *_write_rate_graphs(points, target, formats=selected_formats),
        *_write_stage_timeline(intervals, target, formats=selected_formats),
    ]
    manifest = {
        "schema_version": PROGRESS_PLOT_SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_event_count": len(events),
        "metric_point_count": len(points),
        "stage_interval_count": len(intervals),
        "formats": list(selected_formats),
        "outputs": outputs,
        "authority": "diagnostic_projection_only",
    }
    manifest_path = target / "progress_plot_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**manifest, "manifest_path": str(manifest_path)}


__all__ = [
    "MetricPoint",
    "PROGRESS_PLOT_SCHEMA_VERSION",
    "StageInterval",
    "load_progress_ledger",
    "metric_points",
    "render_progress_plots",
    "stage_intervals",
]
