#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.fact_intake.transcript_review_bundle import build_fact_intake_payload_from_transcript_report
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.structure_report import TextUnit, build_structure_report
from src.sensiblaw.interfaces.signals import collect_signal_state, summarize_signal_state
from src.sensiblaw.interfaces.shared_reducer import (
    collect_canonical_relational_bundle,
    collect_canonical_structure_occurrences,
)
from src.text.sentences import segment_sentences
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


SCHEMA_VERSION = "sl.archive_turn_fact_extract.v0_1"


def _row_to_message(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "message_id": str(row["message_id"]),
        "canonical_thread_id": str(row["canonical_thread_id"] or ""),
        "platform": str(row["platform"] or ""),
        "account_id": str(row["account_id"] or ""),
        "timestamp": str(row["ts"] or ""),
        "role": str(row["role"] or ""),
        "title": str(row["title"] or ""),
        "source_id": str(row["source_id"] or ""),
        "source_thread_id": str(row["source_thread_id"] or ""),
        "source_message_id": str(row["source_message_id"] or ""),
        "source_path": str(row["source_path"] or ""),
        "source_bucket": str(row["source_bucket"] or ""),
        "text": str(row["text"] or ""),
    }


def _select_anchor(
    conn: sqlite3.Connection,
    *,
    message_id: str | None,
    thread_id: str | None,
    title_contains: str | None,
) -> sqlite3.Row:
    if message_id:
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
    elif thread_id:
        row = conn.execute(
            """
            SELECT * FROM messages
            WHERE canonical_thread_id = ? AND COALESCE(text, '') <> ''
            ORDER BY ts, message_id
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
    elif title_contains:
        row = conn.execute(
            """
            SELECT * FROM messages
            WHERE COALESCE(title, '') LIKE ? AND COALESCE(text, '') <> ''
            ORDER BY ts, message_id
            LIMIT 1
            """,
            (f"%{title_contains}%",),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM messages
            WHERE COALESCE(text, '') <> ''
            ORDER BY ts DESC, message_id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise ValueError("no archive message matched the supplied selector")
    return row


def load_archive_turn(
    db_path: str | Path,
    *,
    message_id: str | None = None,
    thread_id: str | None = None,
    title_contains: str | None = None,
) -> dict[str, Any]:
    resolved = Path(db_path).expanduser().resolve()
    with sqlite3.connect(str(resolved)) as conn:
        conn.row_factory = sqlite3.Row
        anchor = _select_anchor(
            conn,
            message_id=message_id,
            thread_id=thread_id,
            title_contains=title_contains,
        )
        canonical_thread_id = str(anchor["canonical_thread_id"] or "")
        anchor_role = str(anchor["role"] or "").casefold()
        if anchor_role == "user":
            call = anchor
            response = conn.execute(
                """
                SELECT * FROM messages
                WHERE canonical_thread_id = ?
                  AND ts >= ?
                  AND message_id <> ?
                  AND COALESCE(text, '') <> ''
                ORDER BY ts, message_id
                LIMIT 1
                """,
                (canonical_thread_id, str(anchor["ts"] or ""), str(anchor["message_id"])),
            ).fetchone()
        else:
            response = anchor
            call = conn.execute(
                """
                SELECT * FROM messages
                WHERE canonical_thread_id = ?
                  AND ts <= ?
                  AND message_id <> ?
                  AND role = 'user'
                  AND COALESCE(text, '') <> ''
                ORDER BY ts DESC, message_id DESC
                LIMIT 1
                """,
                (canonical_thread_id, str(anchor["ts"] or ""), str(anchor["message_id"])),
            ).fetchone()
            if call is None:
                call = anchor
        return {
            "db_path": str(resolved),
            "canonical_thread_id": canonical_thread_id,
            "anchor_message_id": str(anchor["message_id"]),
            "call": _row_to_message(call),
            "response": _row_to_message(response),
        }


def _message_units(turn: Mapping[str, Any]) -> list[TextUnit]:
    units: list[TextUnit] = []
    source_id = str(turn.get("canonical_thread_id") or "archive_thread")
    for role in ("call", "response"):
        message = turn.get(role)
        if not isinstance(message, Mapping):
            continue
        text = str(message.get("text") or "").strip()
        if not text:
            continue
        unit_id = str(message.get("message_id") or role)
        units.append(TextUnit(unit_id=unit_id, source_id=source_id, source_type="chat_archive_sample", text=text))
    return units


def _structure_occurrences(text: str) -> list[dict[str, Any]]:
    return [
        {
            "text": occ.text,
            "norm_text": occ.norm_text,
            "kind": occ.kind,
            "start_char": occ.start_char,
            "end_char": occ.end_char,
        }
        for occ in collect_canonical_structure_occurrences(text)
    ]


def _sentences(text: str) -> list[dict[str, Any]]:
    return [
        {
            "index": sentence.index,
            "text": sentence.text,
            "start_char": sentence.start_char,
            "end_char": sentence.end_char,
        }
        for sentence in segment_sentences(text)
    ]


def _unit_debug(unit: TextUnit) -> dict[str, Any]:
    signal_state = collect_signal_state(
        unit.text,
        include_families=("interaction", "directness", "audience", "uncertainty"),
    )
    occurrences = _structure_occurrences(unit.text)
    return {
        "unit_id": unit.unit_id,
        "source_text": unit.text,
        "sentence_split": _sentences(unit.text),
        "structure_occurrences": occurrences,
        "file_path_occurrences": [row for row in occurrences if row["kind"] == "path_ref"],
        "relational_bundle": collect_canonical_relational_bundle(unit.text),
        "signal_summary": summarize_signal_state(signal_state),
        "signal_atoms": {
            family: [
                {
                    "signal_id": atom.signal_id,
                    "family": atom.family,
                    "label": atom.label,
                    "value": atom.value,
                    "confidence": atom.confidence,
                    "spans": [
                        {"start_char": span.start_char, "end_char": span.end_char}
                        for span in atom.spans
                    ],
                    "provenance": list(atom.provenance),
                    "evidence": list(atom.evidence),
                }
                for atom in atoms
            ]
            for family, atoms in signal_state.families.items()
        },
    }


def build_archive_turn_fact_extract(
    turn: Mapping[str, Any],
    *,
    semantic_db_path: str = ":memory:",
    run_id: str | None = None,
) -> dict[str, Any]:
    units = _message_units(turn)
    if not units:
        raise ValueError("archive turn did not contain any text units")
    selected_run_id = run_id or f"archive-turn:{turn.get('anchor_message_id') or units[0].unit_id}"
    with sqlite3.connect(semantic_db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        run_transcript_semantic_pipeline(conn, units, run_id=selected_run_id)
        semantic_report = build_transcript_semantic_report(conn, run_id=selected_run_id, units=units)
    fact_payload = build_fact_intake_payload_from_transcript_report(
        semantic_report,
        source_label=f"archive_turn:{turn.get('canonical_thread_id') or ''}",
        notes="Built from one local archive call/response turn using existing SensibLaw semantic extraction.",
    )
    structure_report = build_structure_report(units, canonical_mode="deterministic_legal", top_n=20)
    return {
        "schema_version": SCHEMA_VERSION,
        "archive_turn": dict(turn),
        "unit_debug": [_unit_debug(unit) for unit in units],
        "semantic_report": semantic_report,
        "fact_intake_payload": fact_payload,
        "structure_report": structure_report,
        "authority_boundary": {
            "uses_existing_sensiblaw_extractors": True,
            "raw_sentence_as_fact": False,
            "candidate_only_until_review": True,
            "semantic_regex_policy": "delegated_to_existing_sensiblaw_pipeline_and_docs",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull one local archive call/response turn and run existing SensibLaw fact/semantic extraction."
    )
    parser.add_argument("--db", default="~/chat_archive.sqlite", help="Path to the local chat archive sqlite DB.")
    parser.add_argument("--message-id", default=None, help="Anchor message_id to extract.")
    parser.add_argument("--thread-id", default=None, help="Canonical thread id to extract from.")
    parser.add_argument("--title-contains", default=None, help="Fallback selector over message title.")
    parser.add_argument("--semantic-db-path", default=":memory:", help="SQLite path for transient semantic pipeline state.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic semantic run id.")
    parser.add_argument("--output", default=None, help="Write JSON artifact to this path instead of stdout.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    args = parser.parse_args()

    turn = load_archive_turn(
        args.db,
        message_id=args.message_id,
        thread_id=args.thread_id,
        title_contains=args.title_contains,
    )
    payload = build_archive_turn_fact_extract(
        turn,
        semantic_db_path=str(args.semantic_db_path),
        run_id=args.run_id,
    )
    json_text = json.dumps(
        payload,
        indent=None if args.compact else 2,
        sort_keys=True,
        ensure_ascii=False,
    )
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_text + "\n", encoding="utf-8")
    else:
        print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
