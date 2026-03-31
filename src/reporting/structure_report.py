from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable

from src.text.message_transcript import parse_message_header, parse_time_range_header
from src.sensiblaw.interfaces.shared_reducer import collect_canonical_structure_occurrences
from src.reporting.text_unit_builders import build_indexed_text_unit, build_timestamped_speaker_text


@dataclass(frozen=True, slots=True)
class TextUnit:
    unit_id: str
    source_id: str
    source_type: str
    text: str


_TIMESTAMP_BULLET_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})\]\s*(?P<text>.+?)\s*$"
)
_COURT_SPEAKER_RE = re.compile(r"^(?P<label>[A-Z][A-Z .,'’‑-]{1,96}|Q|A):\s*(?P<body>.*)$")
_WRAPPED_SPEAKER_SUFFIX_RE = re.compile(r"^(?:SC|KC|CJ|DCJ|AC|JA|J|QC)\s*:\s*.*$")


def _trim_snippet(text: str, start: int, end: int, radius: int = 48) -> str:
    prefix = max(0, start - radius)
    suffix = min(len(text), end + radius)
    snippet = text[prefix:suffix].replace("\n", " ").strip()
    return snippet[:160]


def _split_markdown_units(text: str, source_id: str, source_type: str) -> list[TextUnit]:
    units: list[TextUnit] = []
    lines = text.splitlines()
    buffer: list[str] = []
    current_label = "preamble"
    count = 0
    for line in lines:
        stripped = line.strip()
        if line.startswith("#"):
            if buffer:
                count += 1
                units.append(TextUnit(f"{source_id}#{count}", source_id, source_type, "\n".join(buffer).strip()))
                buffer = []
            current_label = stripped.lstrip("#").strip() or f"heading_{count+1}"
            buffer.append(line)
            continue
        if not stripped and buffer:
            count += 1
            units.append(TextUnit(f"{source_id}#{count}", source_id, source_type, "\n".join(buffer).strip()))
            buffer = []
            current_label = f"block_{count+1}"
            continue
        if stripped:
            buffer.append(line)
    if buffer:
        count += 1
        units.append(TextUnit(f"{source_id}#{count}", source_id, source_type, "\n".join(buffer).strip()))
    if not units and text.strip():
        units.append(TextUnit(f"{source_id}#1", source_id, source_type, text.strip()))
    return units


def _split_transcript_units(text: str, source_id: str) -> list[TextUnit]:
    asr_units = _split_timestamp_bullet_transcript_units(text, source_id)
    if asr_units:
        return asr_units
    court_units = _split_court_transcript_units(text, source_id)
    if court_units:
        return court_units

    lines = text.splitlines()
    structured_units: list[TextUnit] = []
    current: list[str] = []
    count = 0

    def flush() -> None:
        nonlocal current, count
        payload = "\n".join(current).strip()
        if payload:
            count += 1
            structured_units.append(TextUnit(f"{source_id}#{count}", source_id, "transcript_file", payload))
        current = []

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            flush()
            idx += 1
            continue
        if parse_message_header(stripped) is not None:
            flush()
            current = [stripped]
            idx += 1
            while idx < len(lines):
                nxt = lines[idx]
                nxt_stripped = nxt.strip()
                if parse_message_header(nxt_stripped) is not None or parse_time_range_header(nxt_stripped) is not None:
                    break
                current.append(nxt)
                idx += 1
            flush()
            continue
        if parse_time_range_header(stripped) is not None:
            flush()
            current = [stripped]
            idx += 1
            while idx < len(lines):
                nxt = lines[idx]
                nxt_stripped = nxt.strip()
                if parse_message_header(nxt_stripped) is not None or parse_time_range_header(nxt_stripped) is not None:
                    break
                current.append(nxt)
                idx += 1
            flush()
            continue
        current.append(line)
        idx += 1

    flush()
    if structured_units:
        return structured_units

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if not blocks:
        return [TextUnit(f"{source_id}#1", source_id, "transcript_file", text.strip())] if text.strip() else []
    return [TextUnit(f"{source_id}#{index}", source_id, "transcript_file", block) for index, block in enumerate(blocks, start=1)]


def _split_timestamp_bullet_transcript_units(text: str, source_id: str) -> list[TextUnit]:
    lines = text.splitlines()
    matches = [match for match in (_TIMESTAMP_BULLET_RE.match(line) for line in lines) if match]
    if len(matches) < 5:
        return []

    units: list[TextUnit] = []
    parts: list[str] = []
    chunk_start: str | None = None
    chunk_end: str | None = None
    count = 0

    def flush() -> None:
        nonlocal parts, chunk_start, chunk_end, count
        payload = " ".join(parts).strip()
        if payload:
            count += 1
            label = f"[{chunk_start} -> {chunk_end}] " if chunk_start and chunk_end else ""
            units.append(TextUnit(f"{source_id}#{count}", source_id, "transcript_file", f"{label}{payload}".strip()))
        parts = []
        chunk_start = None
        chunk_end = None

    for match in matches:
        segment_text = re.sub(r"\s+", " ", str(match.group("text") or "").strip())
        if not segment_text:
            continue
        if chunk_start is None:
            chunk_start = str(match.group("start"))
        chunk_end = str(match.group("end"))
        parts.append(segment_text)
        if (
            segment_text.endswith((".", "?", "!"))
            and len(" ".join(parts)) >= 180
        ) or len(" ".join(parts)) >= 420:
            flush()

    flush()
    return units


def _split_court_transcript_units(text: str, source_id: str) -> list[TextUnit]:
    raw_lines = text.splitlines()
    lines: list[str] = []
    idx = 0
    while idx < len(raw_lines):
        stripped = raw_lines[idx].strip()
        if idx + 1 < len(raw_lines):
            next_stripped = raw_lines[idx + 1].strip()
            if stripped and ":" not in stripped and _WRAPPED_SPEAKER_SUFFIX_RE.match(next_stripped):
                candidate = f"{stripped} {next_stripped}"
                if _COURT_SPEAKER_RE.match(candidate):
                    lines.append(candidate)
                    idx += 2
                    continue
        lines.append(raw_lines[idx])
        idx += 1

    speaker_indexes = [index for index, line in enumerate(lines) if _COURT_SPEAKER_RE.match(line.strip())]
    if not speaker_indexes:
        return []

    start_index = speaker_indexes[0]
    transcript_marker_indexes = [index for index, line in enumerate(lines) if line.strip().upper() == "TRANSCRIPT OF PROCEEDINGS"]
    if transcript_marker_indexes:
        marker_index = transcript_marker_indexes[0]
        start_index = next((index for index in speaker_indexes if index > marker_index), speaker_indexes[0])

    units: list[TextUnit] = []
    current: list[str] = []
    current_speaker: str | None = None
    count = 0

    def flush() -> None:
        nonlocal current, count
        payload = "\n".join(current).strip()
        if payload:
            count += 1
            units.append(TextUnit(f"{source_id}#{count}", source_id, "transcript_file", payload))
        current = []

    for line in lines[start_index:]:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _COURT_SPEAKER_RE.match(stripped):
            flush()
            current_speaker = stripped.split(":", 1)[0].strip()
            current = [stripped]
            continue
        if current:
            if current_speaker and len("\n".join(current)) >= 1200:
                flush()
                current = [f"{current_speaker}: {stripped}"]
                continue
            current.append(stripped)

    flush()
    return units


def _split_shell_units(text: str, source_id: str) -> list[TextUnit]:
    lines = text.splitlines()
    units: list[TextUnit] = []
    buffer: list[str] = []
    count = 0
    for line in lines:
        if line.startswith(("$ ", "% ", "❯ ", "# ")):
            if buffer:
                count += 1
                units.append(TextUnit(f"{source_id}#{count}", source_id, "shell_log", "\n".join(buffer).strip()))
                buffer = []
        buffer.append(line)
    if buffer:
        count += 1
        units.append(TextUnit(f"{source_id}#{count}", source_id, "shell_log", "\n".join(buffer).strip()))
    return [unit for unit in units if unit.text.strip()]


def load_chat_units(db_path: str | Path, run_id: str | None = None) -> list[TextUnit]:
    resolved = Path(db_path).expanduser().resolve()
    with sqlite3.connect(str(resolved)) as conn:
        conn.row_factory = sqlite3.Row
        if run_id is None:
            row = conn.execute(
                "SELECT run_id FROM chat_test_ingest_runs ORDER BY created_at DESC, run_id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return []
            run_id = str(row["run_id"])
        rows = conn.execute(
            """
            SELECT row_order, text
            FROM chat_test_messages
            WHERE run_id = ?
            ORDER BY row_order
            """,
            (run_id,),
        ).fetchall()
        return [
            build_indexed_text_unit(
                source_id=run_id,
                source_type="chat_test_db",
                index=int(row["row_order"]),
                text=str(row["text"]),
            )
            for row in rows
            if str(row["text"]).strip()
        ]


def load_messenger_units(db_path: str | Path, run_id: str | None = None) -> list[TextUnit]:
    resolved = Path(db_path).expanduser().resolve()
    with sqlite3.connect(str(resolved)) as conn:
        conn.row_factory = sqlite3.Row
        if run_id is None:
            row = conn.execute(
                "SELECT run_id FROM messenger_test_ingest_runs ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return []
            run_id = str(row["run_id"])
        rows = conn.execute(
            """
            SELECT row_order, ts, sender, text
            FROM messenger_test_messages
            WHERE run_id = ?
            ORDER BY row_order
            """,
            (run_id,),
        ).fetchall()
        return [
            build_indexed_text_unit(
                source_id=run_id,
                source_type="messenger_test_db",
                index=int(row["row_order"]),
                text=build_timestamped_speaker_text(
                    ts=str(row["ts"]),
                    speaker=str(row["sender"]),
                    text=str(row["text"]),
                ),
            )
            for row in rows
            if str(row["text"]).strip()
        ]


def load_openrecall_units(
    db_path: str | Path,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    limit: int | None = None,
) -> list[TextUnit]:
    from src.reporting.openrecall_import import load_openrecall_units as _load_openrecall_units  # noqa: PLC0415

    return _load_openrecall_units(
        db_path,
        import_run_id=import_run_id,
        date=date,
        limit=limit,
    )


def load_notebooklm_units(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    limit: int | None = None,
) -> list[TextUnit]:
    from src.reporting.notebooklm_observer import load_notebooklm_units as _load_notebooklm_units  # noqa: PLC0415

    return _load_notebooklm_units(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
        limit=limit,
    )


def load_notebooklm_interaction_units(
    runs_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    notebook_id_hash: str | None = None,
    limit: int | None = None,
) -> list[TextUnit]:
    from src.reporting.notebooklm_activity import (  # noqa: PLC0415
        load_notebooklm_activity_units as _load_notebooklm_activity_units,
    )

    return _load_notebooklm_activity_units(
        runs_root,
        start_date=start_date,
        end_date=end_date,
        notebook_id_hash=notebook_id_hash,
        limit=limit or 50,
    )


def load_file_units(path: str | Path, source_type: str | None = None) -> list[TextUnit]:
    resolved = Path(path).expanduser().resolve()
    text = resolved.read_text(encoding="utf-8")
    source_id = str(resolved)
    inferred = source_type
    if inferred is None:
        lowered = resolved.name.casefold()
        if lowered.endswith(("context.md", "compactified_context.md")):
            inferred = "context_file"
        elif "transcript" in lowered or resolved.suffix.casefold() in {".srt", ".vtt"}:
            inferred = "transcript_file"
        elif resolved.suffix.casefold() in {".sh", ".log"}:
            inferred = "shell_log"
        else:
            inferred = "text_file"
    if inferred == "context_file":
        return _split_markdown_units(text, source_id, inferred)
    if inferred == "transcript_file":
        return _split_transcript_units(text, source_id)
    if inferred == "shell_log":
        return _split_shell_units(text, source_id)
    return _split_markdown_units(text, source_id, inferred)


def _utility_score(kind: str, count: int, unit_count: int, neighbor_count: int, cross_kind_count: int) -> int:
    score = (count * 2) + (unit_count * 3) + (neighbor_count * 4) + (cross_kind_count * 2)
    if kind in {"message_boundary_ref", "quote_block_ref", "code_block_ref"}:
        score -= 3
    if count == 1 and unit_count == 1:
        score -= 4
    return score


def build_structure_report(
    units: Iterable[TextUnit],
    *,
    canonical_mode: str = "deterministic_legal",
    top_n: int = 15,
) -> dict:
    unit_list = [unit for unit in units if unit.text.strip()]
    all_occs = []
    per_unit_counts: list[int] = []
    kind_counter: Counter[str] = Counter()
    structural_kind_counter: Counter[str] = Counter()
    atom_counter: Counter[tuple[str, str]] = Counter()
    atom_units: dict[tuple[str, str], set[str]] = defaultdict(set)
    atom_examples: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    atom_neighbors: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    atom_neighbor_kinds: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_counter: Counter[tuple[tuple[str, str], tuple[str, str]]] = Counter()
    unit_kind_counter: Counter[str] = Counter()
    for unit in unit_list:
        occs = collect_canonical_structure_occurrences(unit.text, canonical_mode=canonical_mode)
        all_occs.extend(occs)
        per_unit_counts.append(len(occs))
        for occ in occs:
            kind_counter[occ.kind] += 1
            if occ.kind.endswith("_ref"):
                structural_kind_counter[occ.kind] += 1
            atom_key = (occ.norm_text, occ.kind)
            if occ.kind.endswith("_ref"):
                atom_counter[atom_key] += 1
                atom_units[atom_key].add(unit.unit_id)
                if len(atom_examples[atom_key]) < 3:
                    atom_examples[atom_key].append(
                        {
                            "unit_id": unit.unit_id,
                            "snippet": _trim_snippet(unit.text, occ.start_char, occ.end_char),
                        }
                    )
        unit_atoms = sorted({(occ.norm_text, occ.kind) for occ in occs if occ.kind.endswith("_ref")})
        for _, kind in unit_atoms:
            unit_kind_counter[kind] += 1
        for left, right in itertools.combinations(unit_atoms, 2):
            pair_counter[(left, right)] += 1
            atom_neighbors[left].add(right)
            atom_neighbors[right].add(left)
            atom_neighbor_kinds[left].add(right[1])
            atom_neighbor_kinds[right].add(left[1])
    raw_chars = sum(len(unit.text) for unit in unit_list)
    unique_pairs = len({(occ.norm_text, occ.kind) for occ in all_occs})
    atom_rows = []
    for atom_key, count in atom_counter.items():
        norm_text, kind = atom_key
        unit_count = len(atom_units[atom_key])
        neighbor_count = len(atom_neighbors[atom_key])
        cross_kind_count = len(atom_neighbor_kinds[atom_key])
        atom_rows.append(
            {
                "norm_text": norm_text,
                "kind": kind,
                "count": count,
                "unit_count": unit_count,
                "reuse_ratio": 1.0 - (1.0 / count) if count else 0.0,
                "neighbor_count": neighbor_count,
                "cross_kind_neighbor_count": cross_kind_count,
                "utility_score": _utility_score(kind, count, unit_count, neighbor_count, cross_kind_count),
                "examples": atom_examples[atom_key],
            }
        )
    atom_rows.sort(key=lambda row: (-row["count"], -row["unit_count"], row["kind"], row["norm_text"]))
    useful_rows = sorted(atom_rows, key=lambda row: (-row["utility_score"], -row["count"], row["norm_text"]))
    interlinked_rows = sorted(atom_rows, key=lambda row: (-row["neighbor_count"], -row["unit_count"], -row["count"], row["norm_text"]))
    kind_buckets: dict[str, list[dict]] = defaultdict(list)
    for row in atom_rows:
        kind_buckets[row["kind"]].append(row)
    kind_top = {kind: rows[:top_n] for kind, rows in sorted(kind_buckets.items())}
    pair_rows = [
        {
            "left": left[0],
            "left_kind": left[1],
            "right": right[0],
            "right_kind": right[1],
            "count": count,
        }
        for (left, right), count in pair_counter.most_common(top_n)
    ]
    top_useful_rows = [row for row in useful_rows if row["utility_score"] > 0][:top_n]
    suspect_rows = [row for row in atom_rows if row["count"] == 1 and row["unit_count"] == 1][:top_n]
    source_counter = Counter(unit.source_type for unit in unit_list)
    return {
        "source_type_counts": dict(sorted(source_counter.items())),
        "unit_count": len(unit_list),
        "raw_characters": raw_chars,
        "token_count": len(all_occs),
        "avg_chars_per_token": (raw_chars / len(all_occs)) if all_occs else 0.0,
        "avg_tokens_per_unit": (sum(per_unit_counts) / len(per_unit_counts)) if per_unit_counts else 0.0,
        "unique_norm_kind_pairs": unique_pairs,
        "reuse_ratio": 1.0 - (unique_pairs / len(all_occs)) if all_occs else 0.0,
        "kind_counts": dict(sorted(kind_counter.items())),
        "kind_unit_counts": dict(sorted(unit_kind_counter.items())),
        "structural_token_count": sum(structural_kind_counter.values()),
        "structural_kind_counts": dict(sorted(structural_kind_counter.items())),
        "unique_structural_atoms": len(atom_rows),
        "top_structural_atoms": atom_rows[:top_n],
        "top_structural_atoms_by_kind": kind_top,
        "top_useful_atoms": top_useful_rows,
        "suspect_atoms": suspect_rows,
        "top_interlinked_atoms": interlinked_rows[:top_n],
        "top_cooccurring_pairs": pair_rows,
    }


def build_source_comparison_report(
    units: Iterable[TextUnit],
    *,
    canonical_mode: str = "deterministic_legal",
    top_n: int = 15,
) -> dict:
    unit_list = [unit for unit in units if unit.text.strip()]
    grouped: dict[str, list[TextUnit]] = defaultdict(list)
    for unit in unit_list:
        grouped[unit.source_id].append(unit)
    per_source = []
    for source_id, source_units in sorted(grouped.items()):
        report = build_structure_report(source_units, canonical_mode=canonical_mode, top_n=top_n)
        per_source.append(
            {
                "source_id": source_id,
                "source_type": source_units[0].source_type,
                **report,
            }
        )
    return {
        "overall": build_structure_report(unit_list, canonical_mode=canonical_mode, top_n=top_n),
        "per_source": per_source,
    }


def emit_comparison_summary(payload: dict, *, top_n: int = 5) -> str:
    lines = ["source comparison:", "source | type | units | tokens | structural | top-kinds | top-atoms"]
    for row in payload["per_source"]:
        top_kinds = ", ".join(
            f"{kind}={count}" for kind, count in sorted(
                row["structural_kind_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )[:top_n]
        ) or "-"
        top_atoms = ", ".join(atom["norm_text"] for atom in row["top_structural_atoms"][:top_n]) or "-"
        lines.append(
            f"{row['source_id']} | {row['source_type']} | {row['unit_count']} | {row['token_count']} | "
            f"{row['structural_token_count']} | {top_kinds} | {top_atoms}"
        )
    return "\n".join(lines)


def emit_human_summary(report: dict, *, top_n: int = 10) -> str:
    lines = [
        f"units={report['unit_count']} raw_chars={report['raw_characters']} tokens={report['token_count']} avg_chars/token={report['avg_chars_per_token']:.4f}",
        f"unique_atoms={report['unique_structural_atoms']} reuse_ratio={report['reuse_ratio']:.4f}",
        "top reused atoms:",
    ]
    for row in report["top_structural_atoms"][:top_n]:
        lines.append(f"- {row['norm_text']} [{row['kind']}] x{row['count']} units={row['unit_count']}")
    lines.append("top useful atoms:")
    for row in report["top_useful_atoms"][:top_n]:
        lines.append(
            f"- {row['norm_text']} [{row['kind']}] score={row['utility_score']} count={row['count']} neighbors={row['neighbor_count']}"
        )
    lines.append("top interlinked atoms:")
    for row in report["top_interlinked_atoms"][:top_n]:
        lines.append(f"- {row['norm_text']} [{row['kind']}] neighbors={row['neighbor_count']} units={row['unit_count']}")
    return "\n".join(lines)
