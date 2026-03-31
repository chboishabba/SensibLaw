from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any

from src.reporting.notebooklm_run_loader import iter_dated_artifacts

if False:  # pragma: no cover
    from src.reporting.structure_report import TextUnit


@dataclass(frozen=True, slots=True)
class NotebookLMActivityRow:
    date: str
    seq: int
    ts: str
    event: str
    notebook_id_hash: str | None
    notebook_title: str | None
    note_id_hash: str | None
    conversation_id_hash: str | None
    note_title: str | None
    note_preview: str | None
    note_length: int | None
    query_preview: str | None
    answer_preview: str | None
    conversation_turn_ts: str | None
    provenance_source: str | None


def _iter_date_files(runs_root: str | Path, *, start_date: str | None = None, end_date: str | None = None) -> list[tuple[str, Path]]:
    return iter_dated_artifacts(
        runs_root,
        relative_path=("outputs", "notebooklm", "notebooklm_activity_normalized.jsonl"),
        start_date=start_date,
        end_date=end_date,
    )


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_row(date_text: str, seq: int, record: dict[str, Any]) -> NotebookLMActivityRow:
    provenance = record.get("provenance")
    provenance_source = None
    if isinstance(provenance, dict):
        provenance_source = _clean_text(provenance.get("source"))
    note_length = record.get("note_length") if isinstance(record.get("note_length"), int) else None
    return NotebookLMActivityRow(
        date=date_text,
        seq=seq,
        ts=str(record.get("ts") or f"{date_text}T00:00:00Z"),
        event=str(record.get("event") or "unknown").strip().lower() or "unknown",
        notebook_id_hash=_clean_text(record.get("notebook_id_hash")),
        notebook_title=_clean_text(record.get("notebook_title")),
        note_id_hash=_clean_text(record.get("note_id_hash")),
        conversation_id_hash=_clean_text(record.get("conversation_id_hash")),
        note_title=_clean_text(record.get("note_title")),
        note_preview=_clean_text(record.get("note_preview")),
        note_length=note_length,
        query_preview=_clean_text(record.get("query_preview")),
        answer_preview=_clean_text(record.get("answer_preview")),
        conversation_turn_ts=_clean_text(record.get("conversation_turn_ts")),
        provenance_source=provenance_source,
    )


def iter_notebooklm_activity_rows(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
) -> list[NotebookLMActivityRow]:
    rows: list[NotebookLMActivityRow] = []
    seq = 0
    for date_text, target in _iter_date_files(runs_root, start_date=start_date, end_date=end_date):
        with target.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if str(record.get("signal") or "").strip().lower() != "notebooklm_activity":
                    continue
                if str(record.get("app") or "").strip().lower() != "notebooklm":
                    continue
                row = _to_row(date_text, seq, record)
                seq += 1
                if notebook_id_hash and row.notebook_id_hash != notebook_id_hash:
                    continue
                rows.append(row)
    rows.sort(key=lambda row: (row.ts, row.seq))
    return rows


def list_notebooklm_activity_dates(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    rows = iter_notebooklm_activity_rows(runs_root, start_date=start_date, end_date=end_date)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row.date,
            {
                "date": row.date,
                "eventCount": 0,
                "notebookCount": set(),
                "conversationCount": set(),
                "noteCount": set(),
                "firstTs": None,
                "lastTs": None,
            },
        )
        bucket["eventCount"] += 1
        if row.notebook_id_hash:
            bucket["notebookCount"].add(row.notebook_id_hash)
        if row.conversation_id_hash:
            bucket["conversationCount"].add(row.conversation_id_hash)
        if row.note_id_hash:
            bucket["noteCount"].add(row.note_id_hash)
        if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
            bucket["firstTs"] = row.ts
        if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
            bucket["lastTs"] = row.ts
    return [
        {
            "date": date_text,
            "eventCount": int(bucket["eventCount"]),
            "notebookCount": len(bucket["notebookCount"]),
            "conversationCount": len(bucket["conversationCount"]),
            "noteCount": len(bucket["noteCount"]),
            "firstTs": bucket["firstTs"],
            "lastTs": bucket["lastTs"],
        }
        for date_text, bucket in sorted(grouped.items())
    ]


def build_notebooklm_activity_report(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    event_limit: int = 50,
) -> dict[str, Any]:
    rows = iter_notebooklm_activity_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    event_counts = Counter(row.event for row in rows)
    notebooks: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.notebook_id_hash:
            continue
        bucket = notebooks.setdefault(
            row.notebook_id_hash,
            {
                "notebookIdHash": row.notebook_id_hash,
                "title": row.notebook_title,
                "eventCount": 0,
                "conversationCount": set(),
                "noteCount": set(),
                "firstTs": None,
                "lastTs": None,
            },
        )
        bucket["eventCount"] += 1
        if not bucket["title"] and row.notebook_title:
            bucket["title"] = row.notebook_title
        if row.conversation_id_hash:
            bucket["conversationCount"].add(row.conversation_id_hash)
        if row.note_id_hash:
            bucket["noteCount"].add(row.note_id_hash)
        if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
            bucket["firstTs"] = row.ts
        if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
            bucket["lastTs"] = row.ts
    notebook_rows = [
        {
            "notebookIdHash": key,
            "title": value.get("title"),
            "eventCount": int(value.get("eventCount") or 0),
            "conversationCount": len(value.get("conversationCount") or set()),
            "noteCount": len(value.get("noteCount") or set()),
            "firstTs": value.get("firstTs"),
            "lastTs": value.get("lastTs"),
        }
        for key, value in sorted(notebooks.items(), key=lambda item: ((item[1].get("title") or ""), item[0]))
    ]
    recent_events = [
        {
            "date": row.date,
            "ts": row.ts,
            "event": row.event,
            "notebookIdHash": row.notebook_id_hash,
            "notebookTitle": row.notebook_title,
            "conversationIdHash": row.conversation_id_hash,
            "noteIdHash": row.note_id_hash,
            "noteTitle": row.note_title,
            "notePreview": row.note_preview,
            "queryPreview": row.query_preview,
            "answerPreview": row.answer_preview,
            "conversationTurnTs": row.conversation_turn_ts,
            "provenanceSource": row.provenance_source,
        }
        for row in rows[-max(0, event_limit) :]
    ]
    return {
        "summary": {
            "eventCount": len(rows),
            "notebookCount": len({row.notebook_id_hash for row in rows if row.notebook_id_hash}),
            "conversationCount": len({row.conversation_id_hash for row in rows if row.conversation_id_hash}),
            "noteCount": len({row.note_id_hash for row in rows if row.note_id_hash}),
            "eventCounts": dict(event_counts),
        },
        "notebooks": notebook_rows,
        "recentEvents": recent_events,
        "dates": list_notebooklm_activity_dates(runs_root, start_date=start_date, end_date=end_date),
    }


def query_notebooklm_activity_events(
    runs_root: str | Path,
    *,
    event: str | None = None,
    text_query: str | None = None,
    notebook_id_hash: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = iter_notebooklm_activity_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    event_filter = str(event or "").strip().lower()
    query = str(text_query or "").strip().casefold()
    out: list[dict[str, Any]] = []
    for row in rows:
        if event_filter and row.event != event_filter:
            continue
        if query:
            haystacks = [row.notebook_title, row.note_title, row.note_preview, row.query_preview, row.answer_preview]
            if not any(query in str(value or "").casefold() for value in haystacks):
                continue
        out.append(
            {
                "date": row.date,
                "ts": row.ts,
                "event": row.event,
                "notebookIdHash": row.notebook_id_hash,
                "notebookTitle": row.notebook_title,
                "conversationIdHash": row.conversation_id_hash,
                "noteIdHash": row.note_id_hash,
                "noteTitle": row.note_title,
                "notePreview": row.note_preview,
                "queryPreview": row.query_preview,
                "answerPreview": row.answer_preview,
                "conversationTurnTs": row.conversation_turn_ts,
                "provenanceSource": row.provenance_source,
            }
        )
        if len(out) >= max(1, limit):
            break
    return out


def load_notebooklm_activity_units(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    limit: int = 50,
) -> list["TextUnit"]:
    from src.reporting.structure_report import TextUnit

    rows = iter_notebooklm_activity_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    units: list[TextUnit] = []
    for row in rows:
        parts: list[str] = []
        if row.notebook_title:
            parts.append(f"[Notebook] {row.notebook_title}")
        if row.event == "conversation_observed":
            if row.query_preview:
                parts.append(f"[Question] {row.query_preview}")
            if row.answer_preview:
                parts.append(f"[Answer] {row.answer_preview}")
        elif row.event == "note_observed":
            if row.note_title:
                parts.append(f"[Note] {row.note_title}")
            if row.note_preview:
                parts.append(row.note_preview)
        text = "\n".join(parts).strip()
        if not text:
            continue
        unit_key = row.conversation_id_hash or row.note_id_hash or f"{row.date}:{row.seq}"
        units.append(
            TextUnit(
                unit_id=f"notebooklm-activity:{unit_key}",
                source_id=row.notebook_id_hash or unit_key,
                source_type="notebooklm_activity_preview",
                text=text,
            )
        )
        if len(units) >= max(1, limit):
            break
    return units
