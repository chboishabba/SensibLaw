#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import (
    build_fact_intake_payload_from_text_units,
    build_fact_intake_report,
    build_fact_review_workbench_payload,
    persist_fact_intake_payload,
)
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


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _entry_provenance(entry: dict[str, object]) -> dict[str, object]:
    provenance = dict(entry.get("provenance") or {})
    provenance["benchmark_entry_id"] = str(entry.get("id") or "").strip()
    provenance["benchmark_expected_classes"] = _string_list(entry.get("expected_classes"))
    provenance["benchmark_expected_policies"] = _string_list(entry.get("expected_policies"))
    provenance["benchmark_length_bucket"] = str(entry.get("length_bucket") or "").strip()
    return provenance


def _collect_entry_diagnostics(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    corpus_entries: list[dict[str, object]],
    report: dict[str, object],
    workbench: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    entries_by_id = {
        str(entry.get("id") or "").strip(): entry
        for entry in corpus_entries
        if str(entry.get("id") or "").strip()
    }
    source_entry_id_by_source_id: dict[str, str] = {}
    entry_occurrences: dict[str, int] = defaultdict(int)
    for source in report.get("sources", []):
        if not isinstance(source, dict):
            continue
        provenance = source.get("provenance") if isinstance(source.get("provenance"), dict) else {}
        entry_id = str(provenance.get("benchmark_entry_id") or "").strip()
        source_id = str(source.get("source_id") or "").strip()
        if not entry_id or not source_id:
            continue
        source_entry_id_by_source_id[source_id] = entry_id
        entry_occurrences[entry_id] += 1

    fact_ids_by_entry_id: dict[str, set[str]] = defaultdict(set)
    entry_ids_by_fact_id: dict[str, set[str]] = defaultdict(set)
    sample_facts_by_entry_id: dict[str, list[dict[str, object]]] = defaultdict(list)
    realized_fact_classes_by_entry_id: dict[str, set[str]] = defaultdict(set)
    realized_source_classes_by_entry_id: dict[str, set[str]] = defaultdict(set)
    realized_policies_by_entry_id: dict[str, set[str]] = defaultdict(set)
    for fact in workbench.get("facts", []):
        if not isinstance(fact, dict):
            continue
        fact_id = str(fact.get("fact_id") or "").strip()
        entry_ids = {
            source_entry_id_by_source_id[source_id]
            for source_id in fact.get("source_ids", [])
            if source_id in source_entry_id_by_source_id
        }
        if not entry_ids:
            continue
        sample_fact = {
            "fact_id": fact_id,
            "label": str(fact.get("canonical_label") or fact.get("fact_text") or "")[:160],
            "policy_outcomes": sorted({str(value) for value in fact.get("policy_outcomes", []) if str(value).strip()}),
            "signal_classes": sorted({str(value) for value in fact.get("signal_classes", []) if str(value).strip()}),
        }
        for entry_id in entry_ids:
            if fact_id:
                fact_ids_by_entry_id[entry_id].add(fact_id)
                entry_ids_by_fact_id[fact_id].add(entry_id)
            realized_fact_classes_by_entry_id[entry_id].update(
                str(value) for value in fact.get("signal_classes", []) if str(value).strip()
            )
            realized_source_classes_by_entry_id[entry_id].update(
                str(value) for value in fact.get("source_signal_classes", []) if str(value).strip()
            )
            realized_policies_by_entry_id[entry_id].update(
                str(value) for value in fact.get("policy_outcomes", []) if str(value).strip()
            )
            if len(sample_facts_by_entry_id[entry_id]) < 3:
                sample_facts_by_entry_id[entry_id].append(sample_fact)

    class_count_by_entry_id: dict[str, int] = defaultdict(int)
    for row in conn.execute(
        """
        SELECT target_kind, target_id, class_key
        FROM entity_class_assertions
        WHERE run_id = ? AND assertion_status = 'active'
        """,
        (run_id,),
    ).fetchall():
        target_kind = str(row["target_kind"])
        target_id = str(row["target_id"])
        entry_ids: set[str] = set()
        if target_kind == "source" and target_id in source_entry_id_by_source_id:
            entry_ids.add(source_entry_id_by_source_id[target_id])
        elif target_kind == "fact":
            entry_ids.update(entry_ids_by_fact_id.get(target_id, set()))
        for entry_id in entry_ids:
            class_count_by_entry_id[entry_id] += 1

    policy_count_by_entry_id: dict[str, int] = defaultdict(int)
    for row in conn.execute(
        """
        SELECT target_id
        FROM policy_outcomes
        WHERE run_id = ? AND target_kind = 'fact' AND outcome_status = 'active'
        """,
        (run_id,),
    ).fetchall():
        target_id = str(row["target_id"])
        for entry_id in entry_ids_by_fact_id.get(target_id, set()):
            policy_count_by_entry_id[entry_id] += 1

    relation_count_by_entry_id: dict[str, int] = defaultdict(int)
    for row in conn.execute(
        """
        SELECT relation_id, subject_kind, subject_id, object_kind, object_id
        FROM entity_relations
        WHERE run_id = ? AND relation_status = 'active'
        """,
        (run_id,),
    ).fetchall():
        entry_ids: set[str] = set()
        for endpoint_kind, endpoint_id in (
            (str(row["subject_kind"]), str(row["subject_id"])),
            (str(row["object_kind"]), str(row["object_id"])),
        ):
            if endpoint_kind == "source" and endpoint_id in source_entry_id_by_source_id:
                entry_ids.add(source_entry_id_by_source_id[endpoint_id])
            elif endpoint_kind == "fact":
                entry_ids.update(entry_ids_by_fact_id.get(endpoint_id, set()))
        for entry_id in entry_ids:
            relation_count_by_entry_id[entry_id] += 1

    diagnostics: list[dict[str, object]] = []
    matched_class_count = 0
    total_expected_class_count = 0
    matched_policy_count = 0
    total_expected_policy_count = 0
    entries_with_missing_classes: list[str] = []
    entries_with_missing_policies: list[str] = []
    entry_pass_count = 0

    for entry_id in sorted(entries_by_id):
        entry = entries_by_id[entry_id]
        expected_classes = sorted(set(_string_list(entry.get("expected_classes"))))
        expected_policies = sorted(set(_string_list(entry.get("expected_policies"))))
        realized_signal_classes = sorted(realized_fact_classes_by_entry_id.get(entry_id, set()))
        realized_source_signal_classes = sorted(realized_source_classes_by_entry_id.get(entry_id, set()))
        realized_class_set = set(realized_signal_classes) | set(realized_source_signal_classes)
        realized_policy_outcomes = sorted(realized_policies_by_entry_id.get(entry_id, set()))
        missing_expected_classes = sorted(set(expected_classes) - realized_class_set)
        missing_expected_policies = sorted(set(expected_policies) - set(realized_policy_outcomes))
        unexpected_signal_classes = sorted(realized_class_set - set(expected_classes))
        unexpected_policy_outcomes = sorted(set(realized_policy_outcomes) - set(expected_policies))

        matched_class_count += len(set(expected_classes) & realized_class_set)
        total_expected_class_count += len(expected_classes)
        matched_policy_count += len(set(expected_policies) & set(realized_policy_outcomes))
        total_expected_policy_count += len(expected_policies)
        if missing_expected_classes:
            entries_with_missing_classes.append(entry_id)
        if missing_expected_policies:
            entries_with_missing_policies.append(entry_id)
        if not missing_expected_classes and not missing_expected_policies:
            entry_pass_count += 1

        diagnostics.append(
            {
                "entry_id": entry_id,
                "source_type": str(entry.get("source_type") or ""),
                "length_bucket": str(entry.get("length_bucket") or ""),
                "occurrence_count": int(entry_occurrences.get(entry_id, 0)),
                "expected_classes": expected_classes,
                "expected_policies": expected_policies,
                "realized_signal_classes": realized_signal_classes,
                "realized_source_signal_classes": realized_source_signal_classes,
                "realized_policy_outcomes": realized_policy_outcomes,
                "missing_expected_classes": missing_expected_classes,
                "missing_expected_policies": missing_expected_policies,
                "unexpected_signal_classes": unexpected_signal_classes,
                "unexpected_policy_outcomes": unexpected_policy_outcomes,
                "fact_count": len(fact_ids_by_entry_id.get(entry_id, set())),
                "assertion_count": int(class_count_by_entry_id.get(entry_id, 0)),
                "relation_count": int(relation_count_by_entry_id.get(entry_id, 0)),
                "policy_count": int(policy_count_by_entry_id.get(entry_id, 0)),
                "sample_facts": sample_facts_by_entry_id.get(entry_id, []),
                "entry_pass": not missing_expected_classes and not missing_expected_policies,
            }
        )

    expectation_summary = {
        "entry_count": len(entries_by_id),
        "entry_pass_count": entry_pass_count,
        "class_expectation_recall": round(
            matched_class_count / total_expected_class_count,
            6,
        )
        if total_expected_class_count
        else 1.0,
        "policy_expectation_recall": round(
            matched_policy_count / total_expected_policy_count,
            6,
        )
        if total_expected_policy_count
        else 1.0,
        "entries_with_missing_classes": entries_with_missing_classes,
        "entries_with_missing_policies": entries_with_missing_policies,
    }
    return diagnostics, expectation_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark fact-intake semantic materialization across bounded source modes.")
    parser.add_argument("--mode", choices=sorted(_MODE_SAMPLES.keys()), default=None)
    parser.add_argument("--corpus-file", type=Path, default=None, help="Optional benchmark corpus JSON file under tests/fixtures/fact_semantic_bench.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite database path. Defaults to a temp file.")
    parser.add_argument("--deferred", action="store_true", help="Defer semantic materialization to background.")
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
            source["provenance"] = _entry_provenance(entry)
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
        persist_summary = persist_fact_intake_payload(conn, payload, deferred_refresh=args.deferred)

        run_id = payload["run"]["run_id"]
        report = build_fact_intake_report(conn, run_id=run_id)
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
        entry_diagnostics: list[dict[str, object]] = []
        expectation_summary: dict[str, object] | None = None
        if corpus_entries:
            entry_diagnostics, expectation_summary = _collect_entry_diagnostics(
                conn,
                run_id=run_id,
                corpus_entries=corpus_entries,
                report=report,
                workbench=workbench,
            )
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
            "refresh_status": str(refresh["refresh_status"]) if refresh is not None else (persist_summary.get("refresh_status") if "refresh_status" in persist_summary else None),
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
            "entry_count": len({str(row.get("id") or "").strip() for row in corpus_entries if str(row.get("id") or "").strip()}),
            "expected_class_count": sum(len(list(row.get("expected_classes") or [])) for row in corpus_entries),
            "expected_policy_count": sum(len(list(row.get("expected_policies") or [])) for row in corpus_entries),
            "long_entry_count": sum(1 for row in corpus_entries if str(row.get("length_bucket") or "") == "long"),
        }
        payload_out["entry_diagnostics"] = entry_diagnostics
        payload_out["expectation_summary"] = expectation_summary or {}
    print(json.dumps(payload_out, indent=2, sort_keys=True))

    if temp_ctx is not None:
        temp_ctx.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
