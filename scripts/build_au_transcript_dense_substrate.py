#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
THIS_DIR = Path(__file__).resolve().parent
ARTIFACT_VERSION = "au_real_transcript_dense_substrate_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION

if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from build_au_transcript_structural_checkpoint import (  # noqa: E402
    DEFAULT_TRANSCRIPT_PATHS,
    DEFAULT_OUTPUT_DIR as STRUCTURAL_OUTPUT_DIR,
    _build_payload as _build_structural_payload,
    _coerce_path,
    _excerpt_score,
)
from src.fact_intake import (  # noqa: E402
    build_fact_intake_payload_from_transcript_report,
    build_transcript_fact_review_bundle,
    persist_fact_intake_payload,
    record_fact_workflow_link,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema  # noqa: E402
from src.reporting.structure_report import load_file_units  # noqa: E402
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline  # noqa: E402

_OVERLAY_KEYWORD_HINTS = (
    "act",
    "section",
    "duty",
    "appellant",
    "respondent",
    "defendant",
    "court",
    "appeal",
    "proceeding",
    "liability",
    "abuse",
)
_COUNSEL_PREFIX_RE = re.compile(r"^(MR|MS|MRS|DR|PROF)\b", re.IGNORECASE)
_COURT_PREFIX_RE = re.compile(r"^[A-Z][A-Z .'-]{1,40}(?:CJ|J|ACJ)\s*:")
_PROCEDURAL_KIND_RULES: tuple[tuple[str, dict[str, int]], ...] = (
    (
        "court_intervention",
        {
            "your honours": 4,
            "yes.": 2,
            "yes,": 2,
            "question": 2,
            "?": 2,
        },
    ),
    (
        "party_submission",
        {
            "appellant": 4,
            "respondent": 4,
            "we rely on": 4,
            "we submit": 4,
            "i appear": 3,
            "proper defendant": 4,
        },
    ),
    (
        "statutory_argument",
        {
            "civil liability act": 5,
            "section": 3,
            "act": 2,
            "duty of care": 4,
            "proceeding": 2,
            "appeal": 3,
        },
    ),
)

ProgressCallback = Callable[[str, dict[str, Any]], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _wrap_fact_persist_progress(progress_callback: ProgressCallback | None) -> Callable[[dict[str, Any]], None] | None:
    if progress_callback is None:
        return None

    def emit(update: dict[str, Any]) -> None:
        stage = str(update.get("stage") or "progress")
        progress_callback(f"fact_persist_{stage}", update)

    return emit


def _default_structural_artifact_path() -> Path:
    return STRUCTURAL_OUTPUT_DIR / "au_real_transcript_structural_checkpoint_v1.json"


def _status_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "") for row in rows)
    return {label: int(count) for label, count in sorted(counts.items()) if label}


def _fact_signal_score(fact: dict[str, Any], excerpts_by_id: dict[str, dict[str, Any]], statements_by_id: dict[str, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    excerpt_texts = [
        str((excerpts_by_id.get(excerpt_id) or {}).get("excerpt_text") or "")
        for excerpt_id in fact.get("excerpt_ids", [])
        if excerpt_id in excerpts_by_id
    ]
    statement_texts = [
        str((statements_by_id.get(statement_id) or {}).get("statement_text") or "")
        for statement_id in fact.get("statement_ids", [])
        if statement_id in statements_by_id
    ]
    text = "\n".join(part for part in excerpt_texts + statement_texts if part.strip()) or str(fact.get("fact_text") or "")
    score, meta = _excerpt_score(text)
    status_bonus = 0 if str(fact.get("candidate_status") or "") == "candidate" else 1
    review_bonus = min(len(fact.get("observations", [])), 4)
    total = score + status_bonus + review_bonus
    return total, {
        "excerpt_preview": " ".join(text.split())[:420],
        "keyword_hits": list(meta["keyword_hits"]),
        "structural_ref_count": int(meta["structural_ref_count"]),
        "structural_kind_counts": dict(meta["structural_kind_counts"]),
    }


def _selected_overlay(bundle: dict[str, Any], *, limit: int = 24) -> dict[str, Any]:
    excerpts_by_id = {str(row.get("excerpt_id") or ""): row for row in bundle.get("excerpts", [])}
    statements_by_id = {str(row.get("statement_id") or ""): row for row in bundle.get("statements", [])}
    review_by_fact = {str(row.get("fact_id") or ""): row for row in bundle.get("review_queue", [])}
    scored: list[dict[str, Any]] = []
    for fact in bundle.get("facts", []):
        fact_id = str(fact.get("fact_id") or "")
        if not fact_id:
            continue
        lowered = str(fact.get("fact_text") or "").casefold()
        if not any(term in lowered for term in _OVERLAY_KEYWORD_HINTS):
            continue
        score, meta = _fact_signal_score(fact, excerpts_by_id, statements_by_id)
        if score <= 0:
            continue
        scored.append(
            {
                "fact_id": fact_id,
                "score": score,
                "candidate_status": str(fact.get("candidate_status") or ""),
                "fact_text": str(fact.get("fact_text") or ""),
                "statement_ids": list(fact.get("statement_ids", [])),
                "excerpt_ids": list(fact.get("excerpt_ids", [])),
                "source_ids": list(fact.get("source_ids", [])),
                "review_row": review_by_fact.get(fact_id),
                **meta,
            }
        )
    scored.sort(
        key=lambda row: (
            -int(row["score"]),
            -int(row["structural_ref_count"]),
            row["fact_id"],
        )
    )
    selected = scored[:limit]
    selected_fact_ids = {row["fact_id"] for row in selected}
    selected_review_queue = [row for row in bundle.get("review_queue", []) if str(row.get("fact_id") or "") in selected_fact_ids]
    reason_counts = Counter(
        reason
        for row in selected_review_queue
        for reason in row.get("reason_codes", [])
    )
    return {
        "overlay_kind": "fact_review_bundle_projection",
        "bundle_version": str(bundle.get("version") or ""),
        "selection_rule": "top dense transcript facts ranked by structural/legal excerpt score with bundle review context attached",
        "selected_fact_count": len(selected),
        "selected_review_queue_count": len(selected_review_queue),
        "selected_reason_counts": {label: int(count) for label, count in sorted(reason_counts.items())},
        "selected_facts": selected,
        "selected_review_queue": selected_review_queue,
    }


def _procedural_turn_score(text: str) -> tuple[int, str | None, list[str]]:
    lowered = str(text or "").casefold()
    total_scores: dict[str, int] = {}
    cue_hits: dict[str, list[str]] = {}
    if _COURT_PREFIX_RE.match(str(text or "")):
        total_scores["court_intervention"] = total_scores.get("court_intervention", 0) + 4
        cue_hits.setdefault("court_intervention", []).append("court_prefix")
    if _COUNSEL_PREFIX_RE.match(str(text or "")):
        total_scores["party_submission"] = total_scores.get("party_submission", 0) + 3
        cue_hits.setdefault("party_submission", []).append("counsel_prefix")
    for kind, weights in _PROCEDURAL_KIND_RULES:
        for cue, weight in weights.items():
            if cue in lowered:
                total_scores[kind] = total_scores.get(kind, 0) + weight
                cue_hits.setdefault(kind, []).append(cue)
    if not total_scores:
        return 0, None, []
    best_kind = max(sorted(total_scores), key=lambda kind: total_scores[kind])
    return total_scores[best_kind], best_kind, cue_hits.get(best_kind, [])


def _procedural_overlay(semantic_report: dict[str, Any], bundle: dict[str, Any], *, limit: int = 24) -> dict[str, Any]:
    facts_by_event_id: dict[str, dict[str, Any]] = {}
    review_by_fact = {str(row.get("fact_id") or ""): row for row in bundle.get("review_queue", [])}
    excerpts_by_id = {str(row.get("excerpt_id") or ""): row for row in bundle.get("excerpts", [])}
    for fact in bundle.get("facts", []):
        provenance = fact.get("provenance") if isinstance(fact.get("provenance"), dict) else {}
        source_event_id = str(provenance.get("source_event_id") or "")
        if source_event_id and source_event_id not in facts_by_event_id:
            facts_by_event_id[source_event_id] = fact

    selected_rows: list[dict[str, Any]] = []
    for event in semantic_report.get("per_event", []):
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id") or "")
        text = str(event.get("text") or "")
        score, procedural_kind, cue_hits = _procedural_turn_score(text)
        if score <= 0 or not procedural_kind:
            continue
        fact = facts_by_event_id.get(event_id) or {}
        excerpt_preview = " ".join(text.split())[:420]
        fact_id = str(fact.get("fact_id") or "")
        review_row = review_by_fact.get(fact_id) if fact_id else None
        statement_ids = list(fact.get("statement_ids", [])) if isinstance(fact, dict) else []
        excerpt_ids = list(fact.get("excerpt_ids", [])) if isinstance(fact, dict) else []
        excerpt_texts = [
            str((excerpts_by_id.get(excerpt_id) or {}).get("excerpt_text") or "")
            for excerpt_id in excerpt_ids
            if excerpt_id in excerpts_by_id
        ]
        if excerpt_texts:
            excerpt_preview = " ".join(" ".join(excerpt_texts).split())[:420]
        selected_rows.append(
            {
                "event_id": event_id,
                "fact_id": fact_id or None,
                "procedural_kind": procedural_kind,
                "procedural_score": score,
                "cue_hits": cue_hits,
                "fact_status": str(fact.get("candidate_status") or "") if isinstance(fact, dict) else "",
                "statement_ids": statement_ids,
                "excerpt_ids": excerpt_ids,
                "review_row": review_row,
                "excerpt_preview": excerpt_preview,
            }
        )
    selected_rows.sort(
        key=lambda row: (
            -int(row["procedural_score"]),
            str(row["procedural_kind"]),
            str(row["event_id"]),
        )
    )
    selected = selected_rows[:limit]
    selected_fact_ids = {str(row["fact_id"]) for row in selected if row.get("fact_id")}
    selected_review_queue = [row for row in bundle.get("review_queue", []) if str(row.get("fact_id") or "") in selected_fact_ids]
    kind_counts = Counter(str(row["procedural_kind"]) for row in selected)
    return {
        "overlay_kind": "au_hearing_procedural_projection",
        "selection_rule": "top hearing turns ranked by procedural cue score over the dense transcript substrate",
        "selected_candidate_count": len(selected),
        "selected_review_queue_count": len(selected_review_queue),
        "selected_kind_counts": {label: int(count) for label, count in sorted(kind_counts.items())},
        "selected_candidates": selected,
        "selected_review_queue": selected_review_queue,
    }


def _build_payload(transcript_paths: list[Path], *, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    _emit_progress(progress_callback, "load_units_started", source_file_count=len(transcript_paths))
    units = []
    for path in transcript_paths:
        units.extend(load_file_units(path, "transcript_file"))
        _emit_progress(
            progress_callback,
            "source_loaded",
            path=str(path),
            cumulative_unit_count=len(units),
        )
    _emit_progress(progress_callback, "load_units_finished", unit_count=len(units))
    if transcript_paths == [path.resolve() for path in DEFAULT_TRANSCRIPT_PATHS] and _default_structural_artifact_path().exists():
        _emit_progress(progress_callback, "structural_checkpoint_reused", path=str(_default_structural_artifact_path()))
        structural_payload = json.loads(_default_structural_artifact_path().read_text(encoding="utf-8"))
    else:
        _emit_progress(progress_callback, "structural_checkpoint_started", source_file_count=len(transcript_paths))
        structural_payload = _build_structural_payload(transcript_paths, progress_callback=progress_callback)
        _emit_progress(
            progress_callback,
            "structural_checkpoint_finished",
            unit_count=int(structural_payload["summary"]["unit_count"]),
        )
    with tempfile.TemporaryDirectory(prefix="au_dense_substrate_") as tmp_dir:
        db_path = Path(tmp_dir) / "itir.sqlite"
        _emit_progress(progress_callback, "semantic_pipeline_started", db_path=str(db_path), unit_count=len(units))
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            ensure_gwb_semantic_schema(conn)
            semantic_run = run_transcript_semantic_pipeline(
                conn,
                units,
                run_id="au-transcript-dense-substrate-v1",
            )
            _emit_progress(
                progress_callback,
                "semantic_pipeline_finished",
                semantic_run_id=str(semantic_run["run_id"]),
                relation_candidate_count=int(semantic_run.get("relation_candidate_count") or 0),
                promoted_relation_count=int(semantic_run.get("promoted_relation_count") or 0),
            )
            _emit_progress(progress_callback, "semantic_report_started", semantic_run_id=str(semantic_run["run_id"]))
            semantic_report = build_transcript_semantic_report(conn, run_id=str(semantic_run["run_id"]), units=units)
            _emit_progress(progress_callback, "semantic_report_finished", observation_count=len(semantic_report.get("observations", [])))
            _emit_progress(progress_callback, "fact_payload_started", semantic_run_id=str(semantic_run["run_id"]))
            fact_payload = build_fact_intake_payload_from_transcript_report(
                semantic_report,
                source_label="wave6:real_au_transcript_hearing_v1",
                notes="Dense transcript substrate over the real HCA hearing files.",
            )
            _emit_progress(progress_callback, "fact_payload_finished", fact_run_id=str(fact_payload["run"]["run_id"]))
            _emit_progress(progress_callback, "fact_payload_persist_started", fact_run_id=str(fact_payload["run"]["run_id"]))
            persist_fact_intake_payload(
                conn,
                fact_payload,
                progress_callback=_wrap_fact_persist_progress(progress_callback),
            )
            record_fact_workflow_link(
                conn,
                workflow_kind="transcript_semantic",
                workflow_run_id=str(semantic_run["run_id"]),
                fact_run_id=str(fact_payload["run"]["run_id"]),
                source_label=str(fact_payload["run"].get("source_label") or ""),
            )
            _emit_progress(progress_callback, "fact_payload_persist_finished", fact_run_id=str(fact_payload["run"]["run_id"]))
            _emit_progress(progress_callback, "overlay_bundle_started", fact_run_id=str(fact_payload["run"]["run_id"]))
            bundle = build_transcript_fact_review_bundle(conn, fact_run_id=str(fact_payload["run"]["run_id"]), semantic_report=semantic_report)
            _emit_progress(
                progress_callback,
                "overlay_bundle_finished",
                fact_count=int(bundle["summary"].get("fact_count") or 0),
                review_queue_count=len(bundle.get("review_queue", [])),
            )

    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "au_real_transcript_dense_substrate",
        "transcript_paths": [str(path) for path in transcript_paths],
        "summary": {
            "source_file_count": len(transcript_paths),
            "unit_count": int(semantic_run.get("unit_count") or 0),
            "fact_count": int(bundle["summary"].get("fact_count") or 0),
            "observation_count": int(bundle["summary"].get("observation_count") or 0),
            "event_count": int(bundle["summary"].get("event_count") or 0),
            "review_queue_count": len(bundle.get("review_queue", [])),
            "promoted_relation_count": int(semantic_run.get("promoted_relation_count") or 0),
            "relation_candidate_count": int(semantic_run.get("relation_candidate_count") or 0),
            "abstained_resolution_count": int(semantic_run.get("abstained_resolution_count") or 0),
            "structural_token_count": int(structural_payload["summary"]["structural_token_count"]),
            "unique_structural_atoms": int(structural_payload["summary"]["unique_structural_atoms"]),
            "procedural_overlay_candidate_count": 0,
            "core_reading": "This AU artifact treats the real hearing as a dense transcript-derived substrate and keeps the narrower fact-review bundle as a secondary overlay/projection.",
        },
        "run": {
            "semantic_run_id": str(semantic_run["run_id"]),
            "fact_run_id": str(fact_payload["run"]["run_id"]),
            "source_label": str(fact_payload["run"].get("source_label") or ""),
            "bundle_version": str(bundle.get("version") or ""),
        },
        "status_counts": {
            "statement_status_counts": _status_counts(bundle.get("statements", []), "statement_status"),
            "observation_status_counts": _status_counts(bundle.get("observations", []), "observation_status"),
            "fact_status_counts": _status_counts(bundle.get("facts", []), "candidate_status"),
        },
        "structural_checkpoint": {
            "summary": structural_payload["summary"],
            "selected_excerpts": structural_payload["selected_excerpts"][:12],
        },
        "bundle_summary": bundle["summary"],
        "semantic_summary": semantic_report.get("summary", {}),
        "overlay_projection": _selected_overlay(bundle),
        "procedural_overlay": _procedural_overlay(semantic_report, bundle),
    }
    payload["summary"]["procedural_overlay_candidate_count"] = int(payload["procedural_overlay"]["selected_candidate_count"])
    _emit_progress(
        progress_callback,
        "overlay_projection_finished",
        selected_fact_count=int(payload["overlay_projection"]["selected_fact_count"]),
        selected_review_queue_count=int(payload["overlay_projection"]["selected_review_queue_count"]),
    )
    _emit_progress(
        progress_callback,
        "procedural_overlay_finished",
        selected_candidate_count=int(payload["procedural_overlay"]["selected_candidate_count"]),
        selected_review_queue_count=int(payload["procedural_overlay"]["selected_review_queue_count"]),
    )
    return payload


def _build_summary_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    overlay = payload["overlay_projection"]
    lines = [
        "# AU Real Transcript Dense Substrate",
        "",
        "This artifact treats the real HCA hearing as a dense transcript-derived",
        "substrate. The reviewed fact-review bundle is retained as a smaller",
        "secondary overlay rather than as the primary representation.",
        "",
        "## Headline",
        "",
        f"- Source files: {summary['source_file_count']}",
        f"- Transcript units: {summary['unit_count']}",
        f"- Facts: {summary['fact_count']}",
        f"- Observations: {summary['observation_count']}",
        f"- Events: {summary['event_count']}",
        f"- Review queue items: {summary['review_queue_count']}",
        f"- Structural/legal tokens: {summary['structural_token_count']}",
        f"- Unique structural atoms: {summary['unique_structural_atoms']}",
        f"- Procedural overlay candidates: {summary['procedural_overlay_candidate_count']}",
        f"- Reading: {summary['core_reading']}",
        "",
        "## Overlay projection",
        "",
        f"- Bundle version: {payload['run']['bundle_version']}",
        f"- Selected dense facts for secondary review overlay: {overlay['selected_fact_count']}",
        f"- Selected review queue rows: {overlay['selected_review_queue_count']}",
        "",
        "## Procedural overlay",
        "",
        f"- Selected hearing procedural candidates: {payload['procedural_overlay']['selected_candidate_count']}",
        f"- Selected review queue rows: {payload['procedural_overlay']['selected_review_queue_count']}",
        "",
        "## Selected overlay facts",
        "",
    ]
    for row in overlay["selected_facts"][:8]:
        reasons = ", ".join((row.get("review_row") or {}).get("reason_codes", [])) or "-"
        keywords = ", ".join(row["keyword_hits"]) or "-"
        lines.append(
            f"- score={row['score']} status={row['candidate_status']} keywords={keywords} reasons={reasons}: {row['excerpt_preview']}"
        )
    lines.extend(["", "## Selected procedural candidates", ""])
    for row in payload["procedural_overlay"]["selected_candidates"][:8]:
        reasons = ", ".join((row.get("review_row") or {}).get("reason_codes", [])) or "-"
        cues = ", ".join(row["cue_hits"]) or "-"
        lines.append(
            f"- score={row['procedural_score']} kind={row['procedural_kind']} cues={cues} reasons={reasons}: {row['excerpt_preview']}"
        )
    lines.extend(
        [
            "",
            "## Practical reading",
            "",
            "- Dense transcript fact counts are expected at this layer.",
            "- The secondary overlay is still smaller and review-oriented.",
            "- The procedural overlay starts to separate party submissions, court interventions, and statute-heavy turns from the flatter transcript substrate.",
            "- The next AU step is to improve how much of this dense substrate can be surfaced as procedurally meaningful reviewed coverage without discarding substrate density.",
            "",
        ]
    )
    return "\n".join(lines)


def build_dense_substrate(
    output_dir: Path,
    *,
    transcript_paths: list[Path] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    selected_paths = [path.resolve() for path in (transcript_paths or DEFAULT_TRANSCRIPT_PATHS)]
    _emit_progress(progress_callback, "build_started", output_dir=str(output_dir), source_file_count=len(selected_paths))
    payload = _build_payload(selected_paths, progress_callback=progress_callback)
    summary_text = _build_summary_text(payload)
    _emit_progress(progress_callback, "artifact_write_started", output_dir=str(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    _emit_progress(
        progress_callback,
        "build_finished",
        artifact_path=str(artifact_path),
        summary_path=str(summary_path),
        unit_count=int(payload["summary"]["unit_count"]),
        fact_count=int(payload["summary"]["fact_count"]),
    )
    return {
        "summary": payload["summary"],
        "artifact_path": str(artifact_path),
        "summary_path": str(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a dense transcript-derived AU substrate artifact plus secondary fact-review overlay projection.")
    parser.add_argument("--transcript-file", action="append", default=[], help="Transcript file to include; repeat to override the default AU set.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the artifact into.")
    parser.add_argument("--progress", action="store_true", help="Emit stage progress JSON to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    transcript_paths = [_coerce_path(path) for path in args.transcript_file] or DEFAULT_TRANSCRIPT_PATHS
    result = build_dense_substrate(
        Path(args.output_dir).resolve(),
        transcript_paths=transcript_paths,
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
