#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import build_fact_review_workbench_payload, build_fact_intake_payload_from_text_units, persist_fact_intake_payload
from src.reporting.structure_report import TextUnit


_MODE_SAMPLES: dict[str, tuple[str, str, dict[str, object]]] = {
    "wiki_revision": (
        "wiki_article",
        "Revision by BD2412: Reverted unsourced claim after later legal filing and restored sourced wording.",
        {"source_signal_classes": ["public_summary", "wiki_article"]},
    ),
    "chat_archive": (
        "openrecall_capture",
        "Actually, correction: please verify this later; I am not sure the task is ready for handoff.",
        {"lexical_projection_mode": "chat_archive"},
    ),
    "transcript_handoff": (
        "professional_note",
        "Support worker handoff: maybe escalate this later. Professional note says follow up next week.",
        {"lexical_projection_mode": "transcript_handoff"},
    ),
    "au_legal": (
        "legal_record",
        "The appellant appealed. The court held that the order should stand, although the respondent denied the allegation.",
        {"lexical_projection_mode": "au_legal", "source_signal_classes": ["legal_record", "strong_legal_source"]},
    ),
}


def _seed_units(mode: str, count: int) -> tuple[list[TextUnit], dict[str, object]]:
    source_type, text, provenance = _MODE_SAMPLES[mode]
    units = [
        TextUnit(
            unit_id=f"{mode}:unit:{index}",
            source_id=f"{mode}:source:{index}",
            source_type=source_type,
            text=text,
        )
        for index in range(count)
    ]
    return units, provenance


def _load_corpus_entries(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Corpus file has no entries: {path}")
    return [row for row in entries if isinstance(row, dict)]


def _seed_units_from_corpus(path: Path, count: int) -> tuple[list[TextUnit], list[dict[str, object]]]:
    entries = _load_corpus_entries(path)
    repeated: list[dict[str, object]] = []
    for index in range(count):
        repeated.append(entries[index % len(entries)])
    units = [
        TextUnit(
            unit_id=f"{path.stem}:unit:{index}",
            source_id=f"{path.stem}:source:{index}",
            source_type=str(row.get("source_type") or "context_file"),
            text=str(row.get("text") or ""),
        )
        for index, row in enumerate(repeated)
    ]
    return units, repeated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark fact-intake semantic materialization across bounded source modes.")
    parser.add_argument("--mode", choices=sorted(_MODE_SAMPLES.keys()), default=None)
    parser.add_argument("--corpus-file", type=Path, default=None, help="Optional benchmark corpus JSON file under tests/fixtures/fact_semantic_bench.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite database path. Defaults to a temp file.")
    args = parser.parse_args(argv)
    if args.mode is None and args.corpus_file is None:
        parser.error("one of --mode or --corpus-file is required")
    if args.mode is not None and args.corpus_file is not None:
        parser.error("use either --mode or --corpus-file, not both")

    corpus_entries: list[dict[str, object]] = []
    if args.corpus_file is not None:
        units, corpus_entries = _seed_units_from_corpus(args.corpus_file, max(int(args.count), 1))
        payload = build_fact_intake_payload_from_text_units(units, source_label=f"benchmark:{args.corpus_file.stem}:{args.count}")
        for source, entry in zip(payload["sources"], corpus_entries):
            source["source_type"] = str(entry.get("source_type") or source["source_type"])
            source["provenance"] = dict(entry.get("provenance") or {})
    else:
        units, provenance = _seed_units(args.mode, max(int(args.count), 1))
        payload = build_fact_intake_payload_from_text_units(units, source_label=f"benchmark:{args.mode}:{args.count}")
        for source in payload["sources"]:
            source["provenance"] = dict(provenance)

    temp_ctx = None
    db_path = args.db_path
    if db_path is None:
        temp_ctx = tempfile.TemporaryDirectory(prefix="fact-semantic-bench-")
        db_path = Path(temp_ctx.name) / "bench.sqlite"

    start = time.perf_counter()
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        persist_summary = persist_fact_intake_payload(conn, payload)
        run_id = payload["run"]["run_id"]
        workbench = build_fact_review_workbench_payload(conn, run_id=run_id)
        refresh = conn.execute(
            """
            SELECT refresh_status, current_stage, facts_serialized_count, assertion_count, relation_count, policy_count
            FROM semantic_refresh_runs
            WHERE run_id = ?
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)

    payload_out = {
        "mode": args.mode,
        "corpus_file": str(args.corpus_file) if args.corpus_file is not None else None,
        "count": int(args.count),
        "db_path": str(db_path),
        "elapsed_ms": elapsed_ms,
        "elapsed_ms_per_doc": round(elapsed_ms / max(int(args.count), 1), 6),
        "persist_summary": persist_summary,
        "zelph": {
            "active_packs": workbench.get("zelph", {}).get("active_packs", []),
            "facts_serialized_count": workbench.get("zelph", {}).get("facts_serialized_count", 0),
            "inferred_fact_count": workbench.get("zelph", {}).get("inferred_fact_count", 0),
            "rule_status": workbench.get("zelph", {}).get("rule_status"),
        },
        "refresh": {
            "refresh_status": str(refresh["refresh_status"]) if refresh is not None else None,
            "current_stage": str(refresh["current_stage"]) if refresh is not None and refresh["current_stage"] is not None else None,
            "facts_serialized_count": int(refresh["facts_serialized_count"]) if refresh is not None else 0,
            "assertion_count": int(refresh["assertion_count"]) if refresh is not None else 0,
            "relation_count": int(refresh["relation_count"]) if refresh is not None else 0,
            "policy_count": int(refresh["policy_count"]) if refresh is not None else 0,
        },
    }
    if corpus_entries:
        payload_out["corpus_summary"] = {
            "source_types": sorted({str(row.get("source_type") or "") for row in corpus_entries}),
            "expected_class_count": sum(len(list(row.get("expected_classes") or [])) for row in corpus_entries),
            "expected_policy_count": sum(len(list(row.get("expected_policies") or [])) for row in corpus_entries),
            "long_entry_count": sum(1 for row in corpus_entries if str(row.get("length_bucket") or "") == "long"),
        }
    print(json.dumps(payload_out, indent=2, sort_keys=True))

    if temp_ctx is not None:
        temp_ctx.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
