#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
THIS_DIR = Path(__file__).resolve().parent
ARTIFACT_VERSION = "gwb_broader_promotion_diagnostics_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
PUBLIC_BIOS_TIMELINE_PATH = (
    SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "wiki_timeline_gwb_public_bios_v1_rich.json"
)
CORPUS_TIMELINE_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1.json"

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[str, dict[str, Any]], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_family_run(source_family: str, timeline_path: Path) -> dict[str, Any]:
    from build_gwb_zelph_handoff import _build_reports

    payload = _load_json(timeline_path)
    linkage_report, semantic_report = _build_reports(timeline_payload=payload)
    return {
        "source_family": source_family,
        "timeline_path": str(timeline_path.relative_to(REPO_ROOT)),
        "linkage_report": linkage_report,
        "semantic_report": semantic_report,
    }


def _seed_support_kind(events: list[dict[str, Any]]) -> str:
    for event in events:
        receipts = event.get("receipts", [])
        if any(str(receipt.get("kind")) == "provenance_cue_broad" for receipt in receipts):
            return "broad_cue"
    return "direct"


def _sample_seed_events(events: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    sampled = []
    for event in events[:limit]:
        sampled.append(
            {
                "event_id": str(event.get("event_id") or ""),
                "confidence": str(event.get("confidence") or ""),
                "matched": bool(event.get("matched")),
                "receipt_kinds": [str(receipt.get("kind") or "") for receipt in event.get("receipts", [])],
                "text": str(event.get("text") or "")[:280],
            }
        )
    return sampled


def _build_seed_diagnostics(family_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for family in family_runs:
        source_family = str(family["source_family"])
        per_seed = family["linkage_report"].get("per_seed", [])
        for row in per_seed:
            seed_id = str(row.get("seed_id") or "")
            bucket = merged.setdefault(
                seed_id,
                {
                    "seed_id": seed_id,
                    "action_summary": row.get("action_summary"),
                    "linkage_kind": row.get("linkage_kind"),
                    "families": [],
                },
            )
            review_status = "matched" if int(row.get("matched_event_count") or 0) > 0 else "candidate_only"
            bucket["families"].append(
                {
                    "source_family": source_family,
                    "review_status": review_status,
                    "support_kind": _seed_support_kind(list(row.get("events", []))),
                    "matched_event_count": int(row.get("matched_event_count") or 0),
                    "candidate_event_count": int(row.get("candidate_event_count") or 0),
                    "confidence_counts": dict(row.get("confidence_counts") or {}),
                    "sample_events": _sample_seed_events(list(row.get("events", []))),
                }
            )
    rows = [row for row in merged.values() if any(f["source_family"] != "checked_handoff" for f in row["families"])]
    rows.sort(key=lambda row: row["seed_id"])
    return rows


def _build_family_summary(family: dict[str, Any]) -> dict[str, Any]:
    linkage = family["linkage_report"]
    semantic = family["semantic_report"]
    per_seed = list(linkage.get("per_seed", []))
    unmatched_seed_ids = list(linkage.get("unmatched_seed_ids", []))
    candidate_only_seed_count = sum(
        1 for row in per_seed if int(row.get("matched_event_count") or 0) == 0 and int(row.get("candidate_event_count") or 0) > 0
    )
    matched_seed_count = sum(1 for row in per_seed if int(row.get("matched_event_count") or 0) > 0)
    unresolved = list(semantic.get("unresolved_mentions", []))
    per_event = list(semantic.get("per_event", []))
    mention_heavy_events = [
        {
            "event_id": str(row.get("event_id") or ""),
            "match_count": len(row.get("matches", [])),
            "mention_count": len(row.get("mentions", [])),
            "text": str(row.get("text") or "")[:280],
        }
        for row in sorted(per_event, key=lambda item: (-len(item.get("mentions", [])), -len(item.get("matches", [])), str(item.get("event_id") or "")))
        if row.get("mentions") or row.get("matches")
    ][:5]
    return {
        "source_family": family["source_family"],
        "timeline_path": family["timeline_path"],
        "matched_seed_count": matched_seed_count,
        "candidate_only_seed_count": candidate_only_seed_count,
        "unmatched_seed_count": len(unmatched_seed_ids),
        "ambiguous_event_count": len(linkage.get("ambiguous_events", [])),
        "unresolved_mention_count": len(unresolved),
        "relation_candidate_count": int((semantic.get("summary") or {}).get("relation_candidate_count") or 0),
        "promoted_relation_count": int((semantic.get("summary") or {}).get("promoted_relation_count") or 0),
        "text_debug_unavailable_reason": str(((semantic.get("review_summary") or {}).get("text_debug") or {}).get("unavailable_reason") or ""),
        "top_unresolved_surfaces": [str(row.get("surface_text") or "") for row in unresolved[:8]],
        "mention_heavy_events": mention_heavy_events,
    }


def _build_summary(family_summaries: list[dict[str, Any]], seed_diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_family_count": len(family_summaries),
        "families_with_matched_seed_support": sum(1 for row in family_summaries if row["matched_seed_count"] > 0),
        "families_with_relation_candidates": sum(1 for row in family_summaries if row["relation_candidate_count"] > 0),
        "families_with_promoted_relations": sum(1 for row in family_summaries if row["promoted_relation_count"] > 0),
        "broader_seed_diagnostic_count": len(seed_diagnostics),
        "core_reading": "Broader GWB sources now yield several promoted relations across public-bios and corpus lanes, but most broader-source lanes remain linkage-heavy and semantics-light.",
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    lines = [
        "# GWB Broader Promotion Diagnostics Summary",
        "",
        "This artifact explains why broader GWB source families are widening",
        "seed support without widening promoted relation coverage.",
        "",
        "## Headline",
        "",
        f"- Source families inspected: {payload['summary']['source_family_count']}",
        f"- Families with matched seed support: {payload['summary']['families_with_matched_seed_support']}",
        f"- Families with relation candidates: {payload['summary']['families_with_relation_candidates']}",
        f"- Families with promoted relations: {payload['summary']['families_with_promoted_relations']}",
        f"- Diagnostic seed lanes captured: {payload['summary']['broader_seed_diagnostic_count']}",
        "",
        f"- Reading: {payload['summary']['core_reading']}",
        "",
        "## Per-family diagnosis",
        "",
    ]
    for row in payload["source_family_summaries"]:
        lines.append(
            f"- {row['source_family']}: matched_seed_count={row['matched_seed_count']}, "
            f"candidate_only_seed_count={row['candidate_only_seed_count']}, "
            f"relation_candidate_count={row['relation_candidate_count']}, "
            f"promoted_relation_count={row['promoted_relation_count']}, "
            f"unresolved_mention_count={row['unresolved_mention_count']}."
        )
        if row["text_debug_unavailable_reason"]:
            lines.append(f"  text_debug_unavailable_reason: {row['text_debug_unavailable_reason']}")
    lines.extend(["", "## Practical reading", ""])
    lines.append("- The immediate blocker is not source availability.")
    lines.append("- The immediate blocker is lack of text-rich semantic events with defensible anchors in broader-source material.")
    lines.append("- The next repair should target event shaping and semantic anchoring diagnostics before any promotion-policy loosening.")
    lines.append("")
    return "\n".join(lines)


def build_diagnostics(output_dir: Path, *, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    _emit_progress(progress_callback, "family_runs_started", section="diagnostics", completed=0, total=2, message="Building broader promotion diagnostics.")
    family_runs = [
        _build_family_run("public_bios_timeline", PUBLIC_BIOS_TIMELINE_PATH),
        _build_family_run("corpus_book_timeline", CORPUS_TIMELINE_PATH),
    ]
    _emit_progress(progress_callback, "family_runs_finished", section="diagnostics", completed=2, total=2, message="Family reports built.")
    family_summaries = [_build_family_summary(row) for row in family_runs]
    seed_diagnostics = _build_seed_diagnostics(family_runs)
    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "gwb_broader_promotion_diagnostics",
        "summary": _build_summary(family_summaries, seed_diagnostics),
        "source_family_summaries": family_summaries,
        "seed_diagnostics": seed_diagnostics,
    }
    summary_text = _build_summary_text(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(summary_text, encoding="utf-8")
    LOGGER.info("Wrote broader GWB promotion diagnostics to %s", artifact_path)
    _emit_progress(progress_callback, "diagnostics_written", section="diagnostics", message="Diagnostics artifact written.", artifact_path=str(artifact_path))
    return {"summary": payload["summary"], "artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diagnostics for broader GWB promotion failures.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write diagnostics into.")
    parser.add_argument("--progress", action="store_true", help="Emit progress to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    result = build_diagnostics(
        Path(args.output_dir).resolve(),
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
