from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any

if False:  # pragma: no cover
    from src.reporting.structure_report import TextUnit


@dataclass(frozen=True, slots=True)
class NotebookLMObserverRow:
    date: str
    seq: int
    ts: str
    event: str
    notebook_id_hash: str | None
    notebook_title: str | None
    note_id_hash: str | None
    source_title: str | None
    source_type: str | None
    source_status: str | None
    source_url: str | None
    source_created_at: str | None
    source_summary: str | None
    source_keywords: tuple[str, ...]
    artifact_id_hash: str | None
    artifact_title: str | None
    artifact_type: str | None
    artifact_status: str | None
    artifact_created_at: str | None
    provenance_source: str | None
    has_context: bool | None


def _is_date_text(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit()


def _resolve_runs_root(runs_root: str | Path) -> Path:
    return Path(runs_root).expanduser().resolve()


def _iter_date_files(
    runs_root: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for entry in sorted(runs_root.iterdir() if runs_root.exists() else []):
        if not entry.is_dir() or not _is_date_text(entry.name):
            continue
        date_text = entry.name
        if start_date and date_text < start_date:
            continue
        if end_date and date_text > end_date:
            continue
        notes_path = entry / "logs" / "notes" / f"{date_text}.jsonl"
        if notes_path.exists():
            out.append((date_text, notes_path))
    return out


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_str_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out = [str(item).strip() for item in value if str(item).strip()]
    return tuple(out)


def _to_row(date_text: str, seq: int, record: dict[str, Any]) -> NotebookLMObserverRow:
    has_context_raw = record.get("has_context")
    if isinstance(has_context_raw, bool):
        has_context = has_context_raw
    elif isinstance(has_context_raw, (int, float)):
        has_context = bool(has_context_raw)
    else:
        has_context = None
    provenance = record.get("provenance")
    provenance_source = None
    if isinstance(provenance, dict):
        provenance_source = _clean_text(provenance.get("source"))
    return NotebookLMObserverRow(
        date=date_text,
        seq=seq,
        ts=str(record.get("ts") or f"{date_text}T00:00:00Z"),
        event=str(record.get("event") or record.get("event_type") or "unknown").strip().lower() or "unknown",
        notebook_id_hash=_clean_text(record.get("notebook_id_hash")),
        notebook_title=_clean_text(record.get("notebook_title")),
        note_id_hash=_clean_text(record.get("note_id_hash")),
        source_title=_clean_text(record.get("source_title")),
        source_type=_clean_text(record.get("source_type")),
        source_status=_clean_text(record.get("source_status")),
        source_url=_clean_text(record.get("source_url")),
        source_created_at=_clean_text(record.get("source_created_at")),
        source_summary=_clean_text(record.get("source_summary")),
        source_keywords=_clean_str_list(record.get("source_keywords")),
        artifact_id_hash=_clean_text(record.get("artifact_id_hash")),
        artifact_title=_clean_text(record.get("artifact_title")),
        artifact_type=_clean_text(record.get("artifact_type")),
        artifact_status=_clean_text(record.get("artifact_status")),
        artifact_created_at=_clean_text(record.get("artifact_created_at")),
        provenance_source=provenance_source,
        has_context=has_context,
    )


def iter_notebooklm_observer_rows(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
) -> list[NotebookLMObserverRow]:
    root = _resolve_runs_root(runs_root)
    rows: list[NotebookLMObserverRow] = []
    seq = 0
    for date_text, notes_path in _iter_date_files(root, start_date=start_date, end_date=end_date):
        with notes_path.open("r", encoding="utf-8") as handle:
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
                if str(record.get("signal") or "").strip().lower() != "notes_meta":
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


def list_notebooklm_observer_dates(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    rows = iter_notebooklm_observer_rows(runs_root, start_date=start_date, end_date=end_date)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row.date,
            {
                "date": row.date,
                "eventCount": 0,
                "notebookCount": set(),
                "sourceCount": set(),
                "artifactCount": set(),
                "firstTs": None,
                "lastTs": None,
            },
        )
        bucket["eventCount"] += 1
        if row.notebook_id_hash:
            bucket["notebookCount"].add(row.notebook_id_hash)
        if row.note_id_hash:
            bucket["sourceCount"].add(row.note_id_hash)
        if row.artifact_id_hash:
            bucket["artifactCount"].add(row.artifact_id_hash)
        if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
            bucket["firstTs"] = row.ts
        if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
            bucket["lastTs"] = row.ts
    out = []
    for date_text in sorted(grouped):
        bucket = grouped[date_text]
        out.append(
            {
                "date": date_text,
                "eventCount": int(bucket["eventCount"]),
                "notebookCount": len(bucket["notebookCount"]),
                "sourceCount": len(bucket["sourceCount"]),
                "artifactCount": len(bucket["artifactCount"]),
                "firstTs": bucket["firstTs"],
                "lastTs": bucket["lastTs"],
            }
        )
    return out


def build_notebooklm_observer_report(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    event_limit: int = 50,
) -> dict[str, Any]:
    rows = iter_notebooklm_observer_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    event_counts = Counter(row.event for row in rows)
    notebooks: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.notebook_id_hash:
            bucket = notebooks.setdefault(
                row.notebook_id_hash,
                {
                    "notebookIdHash": row.notebook_id_hash,
                    "title": row.notebook_title,
                    "eventCount": 0,
                    "sourceCount": set(),
                    "artifactCount": set(),
                    "firstTs": None,
                    "lastTs": None,
                },
            )
            bucket["eventCount"] += 1
            if not bucket["title"] and row.notebook_title:
                bucket["title"] = row.notebook_title
            if row.note_id_hash:
                bucket["sourceCount"].add(row.note_id_hash)
            if row.artifact_id_hash:
                bucket["artifactCount"].add(row.artifact_id_hash)
            if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
                bucket["firstTs"] = row.ts
            if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
                bucket["lastTs"] = row.ts
        if row.note_id_hash:
            bucket = sources.setdefault(
                row.note_id_hash,
                {
                    "noteIdHash": row.note_id_hash,
                    "notebookIdHash": row.notebook_id_hash,
                    "title": row.source_title,
                    "type": row.source_type,
                    "status": row.source_status,
                    "url": row.source_url,
                    "summary": row.source_summary,
                    "keywords": list(row.source_keywords),
                    "eventCount": 0,
                    "firstTs": None,
                    "lastTs": None,
                },
            )
            bucket["eventCount"] += 1
            for field, value in (
                ("title", row.source_title),
                ("type", row.source_type),
                ("status", row.source_status),
                ("url", row.source_url),
                ("summary", row.source_summary),
            ):
                if not bucket[field] and value:
                    bucket[field] = value
            if not bucket["keywords"] and row.source_keywords:
                bucket["keywords"] = list(row.source_keywords)
            if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
                bucket["firstTs"] = row.ts
            if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
                bucket["lastTs"] = row.ts
        if row.artifact_id_hash:
            bucket = artifacts.setdefault(
                row.artifact_id_hash,
                {
                    "artifactIdHash": row.artifact_id_hash,
                    "notebookIdHash": row.notebook_id_hash,
                    "title": row.artifact_title,
                    "type": row.artifact_type,
                    "status": row.artifact_status,
                    "createdAt": row.artifact_created_at,
                    "eventCount": 0,
                    "firstTs": None,
                    "lastTs": None,
                },
            )
            bucket["eventCount"] += 1
            for field, value in (
                ("title", row.artifact_title),
                ("type", row.artifact_type),
                ("status", row.artifact_status),
                ("createdAt", row.artifact_created_at),
            ):
                if not bucket[field] and value:
                    bucket[field] = value
            if bucket["firstTs"] is None or row.ts < bucket["firstTs"]:
                bucket["firstTs"] = row.ts
            if bucket["lastTs"] is None or row.ts > bucket["lastTs"]:
                bucket["lastTs"] = row.ts
    recent_events = [
        {
            "date": row.date,
            "ts": row.ts,
            "event": row.event,
            "notebookIdHash": row.notebook_id_hash,
            "notebookTitle": row.notebook_title,
            "noteIdHash": row.note_id_hash,
            "sourceTitle": row.source_title,
            "artifactIdHash": row.artifact_id_hash,
            "artifactTitle": row.artifact_title,
            "provenanceSource": row.provenance_source,
            "hasContext": row.has_context,
        }
        for row in rows[-max(1, event_limit) :]
    ]
    return {
        "scope": {
            "runsRoot": str(_resolve_runs_root(runs_root)),
            "startDate": start_date,
            "endDate": end_date,
            "notebookIdHash": notebook_id_hash,
        },
        "summary": {
            "eventCount": len(rows),
            "notebookCount": len(notebooks),
            "sourceCount": len(sources),
            "artifactCount": len(artifacts),
            "sourceSummaryCount": sum(1 for row in rows if row.source_summary),
            "firstTs": rows[0].ts if rows else None,
            "lastTs": rows[-1].ts if rows else None,
            "eventCounts": dict(sorted(event_counts.items(), key=lambda item: (-item[1], item[0]))),
        },
        "dates": list_notebooklm_observer_dates(
            runs_root,
            start_date=start_date,
            end_date=end_date,
        ),
        "notebooks": sorted(
            (
                {
                    **bucket,
                    "sourceCount": len(bucket["sourceCount"]),
                    "artifactCount": len(bucket["artifactCount"]),
                }
                for bucket in notebooks.values()
            ),
            key=lambda row: (-int(row["eventCount"]), str(row["title"] or row["notebookIdHash"])),
        ),
        "sources": sorted(
            sources.values(),
            key=lambda row: (-int(row["eventCount"]), str(row["title"] or row["noteIdHash"])),
        ),
        "artifacts": sorted(
            artifacts.values(),
            key=lambda row: (-int(row["eventCount"]), str(row["title"] or row["artifactIdHash"])),
        ),
        "recentEvents": recent_events,
    }


def query_notebooklm_observer_events(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    event: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    rows = iter_notebooklm_observer_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    needle = (text_query or "").strip().casefold()
    filtered = []
    for row in rows:
        if event and row.event != event.strip().lower():
            continue
        if needle:
            hay = "\n".join(
                part
                for part in (
                    row.notebook_title,
                    row.source_title,
                    row.source_summary,
                    row.artifact_title,
                    " ".join(row.source_keywords),
                )
                if part
            ).casefold()
            if needle not in hay:
                continue
        filtered.append(
            {
                "date": row.date,
                "ts": row.ts,
                "event": row.event,
                "notebookIdHash": row.notebook_id_hash,
                "notebookTitle": row.notebook_title,
                "noteIdHash": row.note_id_hash,
                "sourceTitle": row.source_title,
                "sourceType": row.source_type,
                "sourceStatus": row.source_status,
                "sourceUrl": row.source_url,
                "sourceSummary": row.source_summary,
                "sourceKeywords": list(row.source_keywords),
                "artifactIdHash": row.artifact_id_hash,
                "artifactTitle": row.artifact_title,
                "artifactType": row.artifact_type,
                "artifactStatus": row.artifact_status,
                "provenanceSource": row.provenance_source,
                "hasContext": row.has_context,
            }
        )
    return filtered[-max(1, limit) :]


def load_notebooklm_units(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    limit: int | None = None,
) -> list["TextUnit"]:
    from src.reporting.structure_report import TextUnit  # noqa: PLC0415

    rows = iter_notebooklm_observer_rows(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
    )
    units: list[TextUnit] = []
    seen_unit_ids: set[str] = set()
    for row in rows:
        if not row.note_id_hash:
            continue
        parts = []
        if row.notebook_title:
            parts.append(f"[Notebook] {row.notebook_title}")
        if row.source_title:
            parts.append(f"[Source] {row.source_title}")
        if row.source_type:
            parts.append(f"[Type] {row.source_type}")
        if row.source_summary:
            parts.append(row.source_summary)
        if row.source_keywords:
            parts.append(f"[Keywords] {', '.join(row.source_keywords)}")
        text = "\n".join(part for part in parts if part).strip()
        if not text:
            continue
        unit_id = f"notebooklm:{row.note_id_hash}"
        if unit_id in seen_unit_ids:
            continue
        seen_unit_ids.add(unit_id)
        units.append(
            TextUnit(
                unit_id=unit_id,
                source_id=row.note_id_hash,
                source_type="notebooklm_source_summary",
                text=text,
            )
        )
        if limit is not None and len(units) >= max(1, limit):
            break
    return units
