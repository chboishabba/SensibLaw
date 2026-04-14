#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from src.au_semantic.linkage import ensure_au_semantic_schema
from src.gwb_us_law.linkage import build_gwb_us_law_linkage_report, ensure_gwb_us_law_schema, import_gwb_us_law_seed_payload, run_gwb_us_law_linkage
from src.gwb_us_law.semantic import build_gwb_semantic_report, ensure_gwb_semantic_schema, run_gwb_semantic_pipeline
from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run
from src.zelph_bridge import run_zelph_inference
from src.policy.compiler_contract import build_gwb_public_handoff_contract
from src.policy.product_gate import build_product_gate

ARTIFACT_VERSION = "gwb_public_handoff_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION

DEFAULT_TIMELINE_PATH = SENSIBLAW_ROOT / ".cache_local" / "wiki_timeline_gwb.json"


def _sanitize_id(raw: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_").lower()


def _load_timeline_payload(*, timeline_path: Path | None = None) -> dict[str, Any]:
    selected_path = timeline_path or DEFAULT_TIMELINE_PATH
    if not selected_path.exists():
        raise FileNotFoundError(
            f"timeline payload not found at {selected_path}. Run the GWB timeline build or pass --timeline-path."
        )
    payload = json.loads(selected_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError(f"timeline payload at {selected_path} is not in expected format: missing list events")
    return payload


def _build_reports(*, timeline_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    seed_path = SENSIBLAW_ROOT / "data" / "ontology" / "gwb_us_law_linkage_seed_v1.json"
    seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / "itir.sqlite"
        timeline_out_path = tmpdir_path / "wiki_timeline_gwb.json"
        timeline_out_path.write_text(json.dumps(timeline_payload, sort_keys=True, indent=2), encoding="utf-8")
        persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=timeline_out_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            ensure_bridge_schema(conn)
            ensure_seeded_bridge_slice(conn)
            ensure_au_semantic_schema(conn)
            ensure_gwb_us_law_schema(conn)
            ensure_gwb_semantic_schema(conn)
            import_gwb_us_law_seed_payload(conn, seed_payload)
            linkage_run = run_gwb_us_law_linkage(conn)
            semantic_run = run_gwb_semantic_pipeline(conn)
            linkage_report = build_gwb_us_law_linkage_report(conn, run_id=str(linkage_run["run_id"]))
            semantic_report = build_gwb_semantic_report(conn, run_id=str(semantic_run["run_id"]))
    return linkage_report, semantic_report


def _seed_review_status(row: dict[str, Any]) -> str:
    if int(row.get("matched_event_count") or 0) > 0:
        return "matched"
    if int(row.get("candidate_event_count") or 0) > 0:
        return "candidate_only"
    return "unmatched"


def _seed_support_kind(row: dict[str, Any]) -> str:
    for event in row.get("events", []):
        if any(str(receipt.get("kind")) == "provenance_cue_broad" for receipt in event.get("receipts", [])):
            return "broad_cue"
    return "direct"


def _build_slice(linkage_report: dict[str, Any], semantic_report: dict[str, Any], *, timeline_payload: dict[str, Any]) -> dict[str, Any]:
    selected_relations = []
    for row in semantic_report.get("promoted_relations", []):
        selected_relations.append({
            "event_id": row.get("event_id"),
            "predicate_key": row.get("predicate_key"),
            "confidence_tier": row.get("confidence_tier"),
            "subject": row.get("subject"),
            "object": row.get("object"),
            "receipts": row.get("receipts", []),
        })

    seed_lookup = {str(row.get("seed_id")): row for row in linkage_report.get("per_seed", [])}
    selected_seed_rows = []
    for seed_id, row in seed_lookup.items():
        selected_seed_rows.append({
            "seed_id": seed_id,
            "action_summary": row.get("action_summary"),
            "linkage_kind": row.get("linkage_kind"),
            "review_status": _seed_review_status(row),
            "support_kind": _seed_support_kind(row),
            "matched_event_count": row.get("matched_event_count"),
            "candidate_event_count": row.get("candidate_event_count"),
            "confidence_counts": row.get("confidence_counts", {}),
            "events": [{"event_id": event.get("event_id"), "confidence": event.get("confidence"), "matched": event.get("matched"), "text": event.get("text"), "receipts": event.get("receipts", [])} for event in row.get("events", [])],
        })

    unresolved_mentions = [{"surface_text": row.get("surface_text"), "review_status": "unresolved_surface", "mention_count": row.get("mention_count")} for row in semantic_report.get("unresolved_mentions", [])]
    ambiguous_events = [{"event_id": row.get("event_id"), "text": row.get("text"), "match_count": len(row.get("matches", [])), "matches": [{"seed_id": match.get("seed_id"), "confidence": match.get("confidence"), "matched": match.get("matched")} for match in row.get("matches", [])]} for row in linkage_report.get("ambiguous_events", [])]
    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "public_checked_fixture",
        "timeline_path": str((timeline_payload.get("source_timeline") or {}).get("path") or timeline_payload.get("source") or "wiki_timeline_gwb.json"),
        "timeline_event_count": len(timeline_payload["events"]),
        "linkage_run_id": linkage_report.get("run_id"),
        "semantic_run_id": semantic_report.get("run_id"),
        "summary": {
            "selected_promoted_relation_count": len(selected_relations),
            "selected_seed_lane_count": len(selected_seed_rows),
            "ambiguous_event_count": len(ambiguous_events),
            "unresolved_surface_count": len(unresolved_mentions),
        },
        "selected_promoted_relations": selected_relations,
        "selected_seed_lanes": selected_seed_rows,
        "ambiguous_events": ambiguous_events,
        "unresolved_surfaces": unresolved_mentions,
    }


def _build_scorecard(slice_payload: dict[str, Any], engine_status: str | None) -> dict[str, Any]:
    seed_rows = slice_payload["selected_seed_lanes"]
    return {
        "destination": "complete_gwb_topic_understanding",
        "current_stage": "checked_public_handoff_checkpoint",
        "promoted_relation_count": slice_payload["summary"]["selected_promoted_relation_count"],
        "matched_seed_lane_count": sum(1 for row in seed_rows if row["review_status"] == "matched"),
        "candidate_only_seed_lane_count": sum(1 for row in seed_rows if row["review_status"] == "candidate_only"),
        "broad_cue_seed_lane_count": sum(1 for row in seed_rows if row["support_kind"] == "broad_cue"),
        "direct_support_seed_lane_count": sum(1 for row in seed_rows if row["support_kind"] == "direct"),
        "ambiguous_event_count": slice_payload["summary"]["ambiguous_event_count"],
        "unresolved_surface_count": slice_payload["summary"]["unresolved_surface_count"],
        "zelph_engine_status": engine_status or "unknown",
    }


def _build_summary_text(slice_payload: dict[str, Any]) -> str:
    lines = [
        "# GWB Public Handoff Narrative Summary",
        "",
        "This checked handoff artifact is a bounded public-entity slice over the",
        "George W. Bush wiki timeline lane. It is meant to show what the system",
        "understands from public material in plain language, not just as JSON.",
        "",
        "## What the system recovered cleanly",
        "",
    ]
    for row in slice_payload["selected_promoted_relations"]:
        subj = row["subject"]["canonical_label"]
        obj = row["object"]["canonical_label"]
        pred = row["predicate_key"]
        if pred == "confirmed_by":
            lines.append(f"- {subj} was confirmed by {obj}.")
        elif pred == "ruled_by":
            lines.append(f"- {subj} was linked to court review by {obj}.")
        else:
            lines.append(f"- {subj} {pred.replace('_', ' ')} {obj}.")
    lines.extend(["", "## What the system kept as review lanes", ""])
    for row in slice_payload["selected_seed_lanes"]:
        lines.append(f"- {row['action_summary']}: status={row['review_status']}, support={row['support_kind']}, matched_events={row['matched_event_count']}, candidate_events={row['candidate_event_count']}.")
    lines.extend(["", "## What the system refused to overresolve", ""])
    for row in slice_payload["unresolved_surfaces"]:
        lines.append(f"- `{row['surface_text']}` stayed unresolved.")
    lines.extend(["", "## Why this matters for Zelph", "", "- It is a public and relatively safe real-world handoff slice.", "- It contains both positive public-law relations and explicit review items.", "- It preserves the boundary that SensibLaw extracts and reviews, while", "  Zelph reasons downstream over a bounded exported graph.", ""])
    return "\n".join(lines) + "\n"


def _emit_node(lines: list[str], seen: set[str], node_id: str, *, kind: str, label: str, canonical_key: str) -> None:
    for line in (f'{node_id} "kind" "{kind}"', f'{node_id} "label" "{label}"', f'{node_id} "canonical_key" "{canonical_key}"'):
        if line not in seen:
            seen.add(line)
            lines.append(line)


def _build_facts(slice_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for row in slice_payload["selected_promoted_relations"]:
        subject = row["subject"]
        obj = row["object"]
        subject_id = _sanitize_id(subject["canonical_key"])
        object_id = _sanitize_id(obj["canonical_key"])
        _emit_node(lines, seen, subject_id, kind=str(subject["entity_kind"]), label=str(subject["canonical_label"]), canonical_key=str(subject["canonical_key"]))
        _emit_node(lines, seen, object_id, kind=str(obj["entity_kind"]), label=str(obj["canonical_label"]), canonical_key=str(obj["canonical_key"]))
        for line in (f'{subject_id} "{row["predicate_key"]}" {object_id}', f'{subject_id} "review_status" "promoted_relation"'):
            if line not in seen:
                seen.add(line)
                lines.append(line)
    for row in slice_payload["selected_seed_lanes"]:
        seed_id = _sanitize_id(row["seed_id"])
        for line in (
            f'{seed_id} "kind" "review_item"',
            f'{seed_id} "label" "{row["action_summary"]}"',
            f'{seed_id} "canonical_key" "{row["seed_id"]}"',
            f'{seed_id} "review_status" "{row["review_status"]}"',
            f'{seed_id} "support_kind" "{row["support_kind"]}"',
            f'{seed_id} "linkage_kind" "{row["linkage_kind"]}"',
        ):
            if line not in seen:
                seen.add(line)
                lines.append(line)
    for row in slice_payload["unresolved_surfaces"]:
        surface_id = f'surface_{_sanitize_id(row["surface_text"])}'
        for line in (
            f'{surface_id} "kind" "review_item"',
            f'{surface_id} "label" "{row["surface_text"]}"',
            f'{surface_id} "review_status" "unresolved_surface"',
        ):
            if line not in seen:
                seen.add(line)
                lines.append(line)
    return "\n".join(lines) + "\n"


def _build_rules() -> str:
    return (
        "# GWB public handoff rules\n\n"
        '(actor_george_w_bush "nominated" X) => (actor_george_w_bush "executive_public_law_action" X)\n'
        '(actor_george_w_bush "signed" X) => (actor_george_w_bush "executive_public_law_action" X)\n'
        '(actor_george_w_bush "vetoed" X) => (actor_george_w_bush "executive_public_law_action" X)\n\n'
        '(S "review_status" "ambiguous") => (S "needs_review_due_to_ambiguity" "true")\n'
        '(S "review_status" "candidate_only") => (S "needs_review_due_to_ambiguity" "true")\n'
        '(S "review_status" "unresolved_surface") => (S "needs_review_due_to_ambiguity" "true")\n'
        '(S "support_kind" "broad_cue") => (S "needs_review_due_to_ambiguity" "true")\n\n'
        'actor_george_w_bush "executive_public_law_action" X\n'
        'X "needs_review_due_to_ambiguity" "true"\n'
    )


def build_handoff_artifact(output_dir: Path, *, timeline_path: Path | None = None) -> dict[str, Any]:
    timeline_payload = _load_timeline_payload(timeline_path=timeline_path)
    linkage_report, semantic_report = _build_reports(timeline_payload=timeline_payload)
    slice_payload = _build_slice(linkage_report, semantic_report, timeline_payload=timeline_payload)
    slice_payload["compiler_contract"] = build_gwb_public_handoff_contract(slice_payload)
    slice_payload["promotion_gate"] = build_product_gate(
        lane="gwb",
        product_ref=ARTIFACT_VERSION,
        compiler_contract=slice_payload["compiler_contract"],
    )
    summary_text = _build_summary_text(slice_payload)
    facts_text = _build_facts(slice_payload)
    rules_text = _build_rules()
    engine_payload = run_zelph_inference(facts_text, rules_text)
    scorecard_payload = _build_scorecard(slice_payload, str(engine_payload.get("status") or "unknown"))
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.slice.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
        "facts_path": output_dir / f"{ARTIFACT_VERSION}.facts.zlp",
        "rules_path": output_dir / f"{ARTIFACT_VERSION}.rules.zlp",
        "engine_path": output_dir / f"{ARTIFACT_VERSION}.engine.json",
        "scorecard_path": output_dir / f"{ARTIFACT_VERSION}.scorecard.json",
    }
    paths["slice_path"].write_text(json.dumps(slice_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text, encoding="utf-8")
    paths["facts_path"].write_text(facts_text, encoding="utf-8")
    paths["rules_path"].write_text(rules_text, encoding="utf-8")
    paths["engine_path"].write_text(json.dumps(engine_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["scorecard_path"].write_text(json.dumps(scorecard_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "engine_status": engine_payload.get("status"),
        "scorecard": scorecard_payload,
        "summary": slice_payload["summary"],
        **{k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the checked GWB public-entity Zelph handoff artifact.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the checked handoff artifact into.")
    parser.add_argument("--timeline-path", default=str(DEFAULT_TIMELINE_PATH), help="Path to the GWB timeline JSON payload.")
    args = parser.parse_args()
    timeline_path = Path(args.timeline_path).resolve() if args.timeline_path else None
    print(json.dumps(build_handoff_artifact(Path(args.output_dir).resolve(), timeline_path=timeline_path), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
