#!/usr/bin/env python3
"""Score stored Wikipedia snapshot manifests for general-text timeline readiness."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts.wiki_timeline_aoo_extract import main as wiki_timeline_aoo_main  # noqa: E402
from scripts.wiki_timeline_extract import main as wiki_timeline_extract_main  # noqa: E402


SCHEMA_VERSION = "wiki_random_timeline_readiness_report_v0_1"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _run_quiet(fn: Any, argv: list[str]) -> int:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        return int(fn(argv))


def _event_has_action(event: Mapping[str, Any]) -> bool:
    if str(event.get("action") or "").strip():
        return True
    for step in event.get("steps") or []:
        if isinstance(step, Mapping) and str(step.get("action") or "").strip():
            return True
    return False


def _event_has_object(event: Mapping[str, Any]) -> bool:
    object_lanes = (
        event.get("entity_objects"),
        event.get("numeric_objects"),
        event.get("modifier_objects"),
        event.get("objects"),
    )
    for lane in object_lanes:
        if isinstance(lane, list) and any(str(item).strip() for item in lane):
            return True
    for step in event.get("steps") or []:
        if not isinstance(step, Mapping):
            continue
        for lane_name in ("entity_objects", "numeric_objects", "modifier_objects", "objects"):
            lane = step.get(lane_name)
            if isinstance(lane, list) and any(str(item).strip() for item in lane):
                return True
    return False


def _page_row_from_outputs(
    payload: Mapping[str, Any],
    timeline_payload: Mapping[str, Any],
    aoo_payload: Mapping[str, Any],
) -> dict[str, Any]:
    timeline_events = timeline_payload.get("events")
    aoo_events = aoo_payload.get("events")
    timeline_rows = [row for row in timeline_events if isinstance(row, Mapping)] if isinstance(timeline_events, list) else []
    aoo_rows = [row for row in aoo_events if isinstance(row, Mapping)] if isinstance(aoo_events, list) else []

    timeline_candidate_count = len(timeline_rows)
    dated_timeline_candidate_count = sum(1 for row in timeline_rows if isinstance(row.get("anchor"), Mapping))
    aoo_event_count = len(aoo_rows)
    dated_aao_event_count = sum(1 for row in aoo_rows if isinstance(row.get("anchor"), Mapping))
    actor_event_count = sum(1 for row in aoo_rows if isinstance(row.get("actors"), list) and any(isinstance(actor, Mapping) for actor in row.get("actors") or []))
    action_event_count = sum(1 for row in aoo_rows if _event_has_action(row))
    object_event_count = sum(1 for row in aoo_rows if _event_has_object(row))
    claim_bearing_event_count = sum(1 for row in aoo_rows if bool(row.get("claim_bearing")))
    step_count = sum(len(row.get("steps") or []) for row in aoo_rows if isinstance(row.get("steps"), list))

    candidate_retention_score = _ratio(aoo_event_count, timeline_candidate_count)
    actor_coverage_score = _ratio(actor_event_count, aoo_event_count)
    action_coverage_score = _ratio(action_event_count, aoo_event_count)
    object_coverage_score = _ratio(object_event_count, aoo_event_count)
    chronology_support_score = (
        _ratio(dated_aao_event_count, dated_timeline_candidate_count)
        if dated_timeline_candidate_count
        else (1.0 if aoo_event_count else 0.0)
    )
    event_surface_score = round((actor_coverage_score + action_coverage_score + object_coverage_score) / 3.0, 6)
    overall_readiness_score = round((candidate_retention_score + chronology_support_score + event_surface_score) / 3.0, 6)

    issues: list[str] = []
    if timeline_candidate_count == 0:
        issues.append("no_timeline_candidates")
    if timeline_candidate_count > 0 and aoo_event_count == 0:
        issues.append("timeline_candidates_without_aao_events")
    if aoo_event_count > 0 and actor_event_count == 0:
        issues.append("no_actor_surface")
    if aoo_event_count > 0 and action_event_count == 0:
        issues.append("no_action_surface")
    if dated_timeline_candidate_count > 0 and dated_aao_event_count == 0:
        issues.append("chronology_support_missing")

    return {
        "title": str(payload.get("title") or ""),
        "pageid": payload.get("pageid"),
        "revid": payload.get("revid"),
        "source_url": payload.get("source_url"),
        "timeline_candidate_count": timeline_candidate_count,
        "dated_timeline_candidate_count": dated_timeline_candidate_count,
        "aao_event_count": aoo_event_count,
        "dated_aao_event_count": dated_aao_event_count,
        "actor_event_count": actor_event_count,
        "action_event_count": action_event_count,
        "object_event_count": object_event_count,
        "claim_bearing_event_count": claim_bearing_event_count,
        "step_count": step_count,
        "scores": {
            "candidate_retention_score": candidate_retention_score,
            "chronology_support_score": chronology_support_score,
            "actor_coverage_score": actor_coverage_score,
            "action_coverage_score": action_coverage_score,
            "object_coverage_score": object_coverage_score,
            "event_surface_score": event_surface_score,
            "overall_readiness_score": overall_readiness_score,
        },
        "timeline_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "anchor": row.get("anchor"),
                "text": str(row.get("text") or "")[:180],
            }
            for row in timeline_rows[:3]
        ],
        "aao_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "anchor": row.get("anchor"),
                "action": str(row.get("action") or ""),
                "actor_count": len(row.get("actors") or []) if isinstance(row.get("actors"), list) else 0,
                "step_count": len(row.get("steps") or []) if isinstance(row.get("steps"), list) else 0,
                "claim_bearing": bool(row.get("claim_bearing")),
                "text": str(row.get("text") or "")[:180],
            }
            for row in aoo_rows[:3]
        ],
        "issues": issues,
        "parser": aoo_payload.get("parser"),
        "extraction_profile": aoo_payload.get("extraction_profile"),
    }


def score_snapshot_payload(
    payload: Mapping[str, Any],
    *,
    max_events: int = 64,
    no_spacy: bool = False,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wiki-random-timeline-") as tmpdir:
        tmp_root = Path(tmpdir)
        snapshot_path = tmp_root / "snapshot.json"
        timeline_path = tmp_root / "timeline.json"
        aoo_path = tmp_root / "timeline_aoo.json"
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        extract_argv = [
            "--snapshot",
            str(snapshot_path),
            "--out",
            str(timeline_path),
            "--max-events",
            str(max_events),
        ]
        exit_code = _run_quiet(wiki_timeline_extract_main, extract_argv)
        if exit_code != 0:
            raise RuntimeError(f"wiki_timeline_extract failed for {payload.get('title')}")

        aoo_argv = [
            "--timeline",
            str(timeline_path),
            "--out",
            str(aoo_path),
            "--max-events",
            str(max_events),
            "--no-db",
        ]
        if no_spacy:
            aoo_argv.append("--no-spacy")
        exit_code = _run_quiet(wiki_timeline_aoo_main, aoo_argv)
        if exit_code != 0:
            raise RuntimeError(f"wiki_timeline_aoo_extract failed for {payload.get('title')}")

        return _page_row_from_outputs(payload, _load_json(timeline_path), _load_json(aoo_path))


def build_timeline_readiness_report(
    manifest: Mapping[str, Any],
    *,
    sample_limit: int | None = None,
    emit_page_rows: bool = True,
    max_events: int = 64,
    no_spacy: bool = False,
) -> dict[str, Any]:
    sample_rows = manifest.get("samples")
    if not isinstance(sample_rows, list):
        raise ValueError("manifest samples must be a list")
    if sample_limit is not None:
        sample_rows = sample_rows[: max(0, int(sample_limit))]

    page_rows: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    score_sums = {
        "candidate_retention_score": 0.0,
        "chronology_support_score": 0.0,
        "actor_coverage_score": 0.0,
        "action_coverage_score": 0.0,
        "object_coverage_score": 0.0,
        "event_surface_score": 0.0,
        "overall_readiness_score": 0.0,
    }
    total_counts = Counter[str]()

    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        snapshot_path = row.get("snapshot_path")
        if not isinstance(snapshot_path, str):
            continue
        payload = _load_json(Path(snapshot_path))
        page_row = score_snapshot_payload(payload, max_events=max_events, no_spacy=no_spacy)
        page_rows.append(page_row)
        issue_counts.update(page_row["issues"])
        total_counts.update(
            {
                "timeline_candidate_count": int(page_row["timeline_candidate_count"]),
                "dated_timeline_candidate_count": int(page_row["dated_timeline_candidate_count"]),
                "aao_event_count": int(page_row["aao_event_count"]),
                "dated_aao_event_count": int(page_row["dated_aao_event_count"]),
                "actor_event_count": int(page_row["actor_event_count"]),
                "action_event_count": int(page_row["action_event_count"]),
                "object_event_count": int(page_row["object_event_count"]),
                "claim_bearing_event_count": int(page_row["claim_bearing_event_count"]),
                "step_count": int(page_row["step_count"]),
            }
        )
        for key in score_sums:
            score_sums[key] += float(page_row["scores"][key])

    page_count = len(page_rows)
    summary = {
        "page_count": page_count,
        "issue_counts": dict(sorted(issue_counts.items())),
        "total_counts": dict(sorted(total_counts.items())),
        "pages_with_timeline_candidates": sum(1 for row in page_rows if row["timeline_candidate_count"] > 0),
        "pages_with_aao_events": sum(1 for row in page_rows if row["aao_event_count"] > 0),
        "pages_with_dated_aao_events": sum(1 for row in page_rows if row["dated_aao_event_count"] > 0),
        "pages_with_claim_bearing_events": sum(1 for row in page_rows if row["claim_bearing_event_count"] > 0),
        "average_scores": {
            key: round((value / page_count), 6) if page_count else 0.0
            for key, value in score_sums.items()
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest.get("generated_at"),
        "manifest": {
            "wiki": manifest.get("wiki"),
            "requested_count": manifest.get("requested_count"),
            "sampled_count": manifest.get("sampled_count"),
            "namespace": manifest.get("namespace"),
        },
        "supported_surface": {
            "timeline_candidate_surface": "wiki_timeline_extract",
            "aao_surface": "wiki_timeline_aoo_extract",
            "spacy_enabled": not no_spacy,
            "max_events": int(max_events),
        },
        "summary": summary,
        "pages": page_rows if emit_page_rows else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score stored random-page Wikipedia snapshots for general-text timeline readiness."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--emit-page-rows", action="store_true")
    parser.add_argument("--fail-on-empty", action="store_true")
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--no-spacy", action="store_true")
    args = parser.parse_args(argv)

    manifest = _load_json(args.manifest)
    report = build_timeline_readiness_report(
        manifest,
        sample_limit=args.sample_limit,
        emit_page_rows=args.emit_page_rows,
        max_events=args.max_events,
        no_spacy=args.no_spacy,
    )
    if args.fail_on_empty and report["summary"]["page_count"] == 0:
        raise SystemExit("no pages scored")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
