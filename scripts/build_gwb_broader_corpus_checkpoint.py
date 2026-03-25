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
ARTIFACT_VERSION = "gwb_broader_corpus_checkpoint_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
DEFAULT_HANDOFF_SLICE_PATH = (
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_public_handoff_v1" / "gwb_public_handoff_v1.slice.json"
)
DEFAULT_PUBLIC_BIOS_TIMELINE_PATH = (
    SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "wiki_timeline_gwb_public_bios_v1_rich.json"
)
DEFAULT_CORPUS_TIMELINE_PATH = (
    SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1.json"
)

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


def _relation_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(((row.get("subject") or {}).get("canonical_key")) or ""),
        str(row.get("predicate_key") or ""),
        str(((row.get("object") or {}).get("canonical_key")) or ""),
    )


def _read_checked_handoff_slice(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "source_family": "checked_handoff",
        "timeline_path": str(path.relative_to(REPO_ROOT)),
        "selected_promoted_relations": payload.get("selected_promoted_relations", []),
        "selected_seed_lanes": payload.get("selected_seed_lanes", []),
        "ambiguous_events": payload.get("ambiguous_events", []),
        "unresolved_surfaces": payload.get("unresolved_surfaces", []),
    }


def _run_extraction_for_timeline(source_family: str, timeline_path: Path) -> dict[str, Any]:
    from build_gwb_zelph_handoff import _build_reports, _build_slice

    timeline_payload = _load_json(timeline_path)
    linkage_report, semantic_report = _build_reports(timeline_payload=timeline_payload)
    slice_payload = _build_slice(linkage_report, semantic_report, timeline_payload=timeline_payload)
    return {
        "source_family": source_family,
        "timeline_path": str(timeline_path.relative_to(REPO_ROOT)),
        "selected_promoted_relations": slice_payload.get("selected_promoted_relations", []),
        "selected_seed_lanes": slice_payload.get("selected_seed_lanes", []),
        "ambiguous_events": slice_payload.get("ambiguous_events", []),
        "unresolved_surfaces": slice_payload.get("unresolved_surfaces", []),
    }


def _merge_families(families: list[dict[str, Any]]) -> dict[str, Any]:
    merged_relations: dict[tuple[str, str, str], dict[str, Any]] = {}
    checked_handoff_relation_keys: set[tuple[str, str, str]] = set()
    merged_seed_lanes: dict[str, dict[str, Any]] = {}

    for family in families:
        source_family = str(family["source_family"])
        for row in family.get("selected_promoted_relations", []):
            key = _relation_key(row)
            if source_family == "checked_handoff":
                checked_handoff_relation_keys.add(key)
            merged = merged_relations.get(key)
            if merged is None:
                merged = {
                    "subject": row.get("subject"),
                    "predicate_key": row.get("predicate_key"),
                    "object": row.get("object"),
                    "confidence_tiers": [],
                    "source_families": [],
                }
                merged_relations[key] = merged
            confidence_tier = str(row.get("confidence_tier") or "")
            if confidence_tier and confidence_tier not in merged["confidence_tiers"]:
                merged["confidence_tiers"].append(confidence_tier)
            if source_family not in merged["source_families"]:
                merged["source_families"].append(source_family)

        for row in family.get("selected_seed_lanes", []):
            seed_id = str(row.get("seed_id") or "")
            merged = merged_seed_lanes.get(seed_id)
            if merged is None:
                merged = {
                    "seed_id": seed_id,
                    "action_summary": row.get("action_summary"),
                    "linkage_kind": row.get("linkage_kind"),
                    "source_families": [],
                    "matched_source_families": [],
                    "support_kinds": [],
                    "review_statuses": [],
                }
                merged_seed_lanes[seed_id] = merged
            if source_family not in merged["source_families"]:
                merged["source_families"].append(source_family)
            review_status = str(row.get("review_status") or "")
            support_kind = str(row.get("support_kind") or "")
            if review_status and review_status not in merged["review_statuses"]:
                merged["review_statuses"].append(review_status)
            if support_kind and support_kind not in merged["support_kinds"]:
                merged["support_kinds"].append(support_kind)
            if review_status == "matched" and source_family not in merged["matched_source_families"]:
                merged["matched_source_families"].append(source_family)

    merged_relation_rows = sorted(
        merged_relations.values(),
        key=lambda row: (
            str(((row.get("subject") or {}).get("canonical_label")) or ""),
            str(row.get("predicate_key") or ""),
            str(((row.get("object") or {}).get("canonical_label")) or ""),
        ),
    )
    new_relation_rows = [
        row for key, row in sorted(merged_relations.items(), key=lambda item: item[0]) if key not in checked_handoff_relation_keys
    ]
    merged_seed_rows = sorted(merged_seed_lanes.values(), key=lambda row: row["seed_id"])

    family_summaries = []
    for family in families:
        family_summaries.append(
            {
                "source_family": family["source_family"],
                "timeline_path": family["timeline_path"],
                "promoted_relation_count": len(family.get("selected_promoted_relations", [])),
                "matched_seed_lane_count": sum(
                    1 for row in family.get("selected_seed_lanes", []) if str(row.get("review_status") or "") == "matched"
                ),
                "ambiguous_event_count": len(family.get("ambiguous_events", [])),
                "unresolved_surface_count": len(family.get("unresolved_surfaces", [])),
            }
        )

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "broader_gwb_corpus_checkpoint",
        "summary": {
            "source_family_count": len(families),
            "distinct_promoted_relation_count": len(merged_relation_rows),
            "new_relation_count_vs_checked_handoff": len(new_relation_rows),
            "distinct_seed_lane_count": len(merged_seed_rows),
            "seed_lanes_supported_in_multiple_families": sum(
                1 for row in merged_seed_rows if len(row.get("matched_source_families", [])) >= 2
            ),
        },
        "source_family_summaries": family_summaries,
        "merged_promoted_relations": merged_relation_rows,
        "new_relations_vs_checked_handoff": new_relation_rows,
        "merged_seed_lanes": merged_seed_rows,
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GWB Broader Corpus Checkpoint Summary",
        "",
        "This artifact is the first broader GWB extraction checkpoint beyond the",
        "bounded checked handoff. It combines the checked handoff lane with fresh",
        "deterministic extraction over the public-bios and corpus/book timelines.",
        "",
        "## Merged coverage summary",
        "",
        f"- Source families: {summary['source_family_count']}",
        f"- Distinct promoted relations: {summary['distinct_promoted_relation_count']}",
        f"- New relations beyond checked handoff: {summary['new_relation_count_vs_checked_handoff']}",
        f"- Distinct seed lanes: {summary['distinct_seed_lane_count']}",
        f"- Seed lanes matched in multiple source families: {summary['seed_lanes_supported_in_multiple_families']}",
        "",
        "## Per-source-family summary",
        "",
    ]
    for row in payload["source_family_summaries"]:
        lines.append(
            f"- {row['source_family']}: {row['promoted_relation_count']} promoted relations, "
            f"{row['matched_seed_lane_count']} matched seed lanes, "
            f"{row['ambiguous_event_count']} ambiguous events, "
            f"{row['unresolved_surface_count']} unresolved surfaces."
        )
    lines.extend(["", "## New relations beyond checked handoff", ""])
    if payload["new_relations_vs_checked_handoff"]:
        for row in payload["new_relations_vs_checked_handoff"][:12]:
            lines.append(
                f"- {row['subject']['canonical_label']} {row['predicate_key'].replace('_', ' ')} "
                f"{row['object']['canonical_label']} "
                f"(from: {', '.join(row['source_families'])})."
            )
    else:
        lines.append("- No new promoted relations were added beyond the checked handoff in the current broader pass.")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This is still a checkpoint, not full GWB/topic closure.",
            "- It is the first machine-readable broader extraction pass over the",
            "  public-bios and corpus/book timeline lanes rather than only an",
            "  inventory of source families.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def build_broader_checkpoint(output_dir: Path, *, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    from build_gwb_public_bios_rich_timeline import build_public_bios_timeline

    _emit_progress(progress_callback, "public_bios_timeline_started", section="checkpoint_inputs", message="Rebuilding richer public bios timeline.")
    build_public_bios_timeline(
        raw_root=SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "raw",
        out_path=DEFAULT_PUBLIC_BIOS_TIMELINE_PATH,
        max_docs=20,
        max_snippets_per_doc=12,
        snippet_chars=420,
        progress_callback=progress_callback,
    )
    _emit_progress(progress_callback, "public_bios_timeline_finished", section="checkpoint_inputs", message="Public bios timeline ready.")
    families = [
        _read_checked_handoff_slice(DEFAULT_HANDOFF_SLICE_PATH),
        _run_extraction_for_timeline("public_bios_timeline", DEFAULT_PUBLIC_BIOS_TIMELINE_PATH),
        _run_extraction_for_timeline("corpus_book_timeline", DEFAULT_CORPUS_TIMELINE_PATH),
    ]
    _emit_progress(progress_callback, "family_merge_started", section="checkpoint_merge", completed=0, total=len(families), message="Merging source families.")
    payload = _merge_families(families)
    summary_text = _build_summary_text(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
    }
    paths["slice_path"].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text, encoding="utf-8")
    LOGGER.info("Wrote broader GWB checkpoint to %s", paths["slice_path"])
    _emit_progress(progress_callback, "family_merge_finished", section="checkpoint_merge", completed=len(families), total=len(families), message="Broader checkpoint written.")
    return {
        "summary": payload["summary"],
        **{k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the first broader GWB corpus extraction checkpoint.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the broader GWB checkpoint into.")
    parser.add_argument("--progress", action="store_true", help="Emit progress to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    payload = build_broader_checkpoint(
        Path(args.output_dir).resolve(),
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
