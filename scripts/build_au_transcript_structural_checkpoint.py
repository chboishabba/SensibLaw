#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
ARTIFACT_VERSION = "au_real_transcript_structural_checkpoint_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
DEFAULT_TRANSCRIPT_PATHS = [
    SENSIBLAW_ROOT / "demo" / "ingest" / "hca_case_s942025" / "media" / "transcripts" / "01_Hearing.txt",
    SENSIBLAW_ROOT / "demo" / "ingest" / "hca_case_s942025" / "media" / "transcripts" / "vimeo_1109898693_en-x-autogen.md",
]

if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from src.reporting.structure_report import build_source_comparison_report, load_file_units  # noqa: E402
from src.sensiblaw.interfaces.shared_reducer import collect_canonical_structure_occurrences  # noqa: E402


_KEYWORD_WEIGHTS = {
    "duty of care": 4,
    "civil liability act": 4,
    "appellant": 3,
    "respondent": 3,
    "proper defendant": 3,
    "unincorporated organization": 3,
    "unincorporated organisation": 3,
    "child abuse proceedings": 3,
}

ProgressCallback = Callable[[str, dict[str, Any]], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _coerce_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _excerpt_score(text: str) -> tuple[int, dict[str, Any]]:
    occs = collect_canonical_structure_occurrences(text, canonical_mode="deterministic_legal")
    structural = [occ for occ in occs if occ.kind.endswith("_ref")]
    kind_counts = Counter(occ.kind for occ in structural)
    lowered = text.casefold()
    keyword_hits = [term for term in _KEYWORD_WEIGHTS if term in lowered]
    keyword_score = sum(_KEYWORD_WEIGHTS[term] for term in keyword_hits)
    score = (len(structural) * 2) + keyword_score
    return score, {
        "structural_ref_count": len(structural),
        "structural_kind_counts": dict(sorted(kind_counts.items())),
        "keyword_hits": keyword_hits,
        "top_structural_refs": [
            {"norm_text": occ.norm_text, "kind": occ.kind}
            for occ in structural[:8]
        ],
    }


def _trim_text(text: str, limit: int = 420) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _top_excerpts(units: list[Any], *, limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in units:
        score, meta = _excerpt_score(unit.text)
        if score <= 0:
            continue
        excerpt_text = _trim_text(unit.text)
        dedupe_key = excerpt_text.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append(
            {
                "unit_id": unit.unit_id,
                "source_id": unit.source_id,
                "score": score,
                "excerpt_text": excerpt_text,
                **meta,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["score"]),
            -int(row["structural_ref_count"]),
            row["source_id"],
            row["unit_id"],
        )
    )
    return rows[:limit]


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
    _emit_progress(progress_callback, "structure_report_started", unit_count=len(units))
    comparison = build_source_comparison_report(units, top_n=10)
    _emit_progress(progress_callback, "structure_report_finished", per_source_count=len(comparison["per_source"]))
    _emit_progress(progress_callback, "excerpt_selection_started", unit_count=len(units))
    selected_excerpts = _top_excerpts(units)
    _emit_progress(progress_callback, "excerpt_selection_finished", selected_excerpt_count=len(selected_excerpts))
    overall = comparison["overall"]
    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "au_real_transcript_structural_checkpoint",
        "transcript_paths": [str(path) for path in transcript_paths],
        "summary": {
            "source_file_count": len(transcript_paths),
            "unit_count": int(overall["unit_count"]),
            "structural_token_count": int(overall["structural_token_count"]),
            "unique_structural_atoms": int(overall["unique_structural_atoms"]),
            "selected_excerpt_count": len(selected_excerpts),
            "top_structural_kinds": overall["structural_kind_counts"],
            "core_reading": "The real AU hearing transcript lane now has a persisted structural/legal checkpoint, even though the generic transcript fact-review path is still too noisy to treat as reviewed fact coverage.",
        },
        "top_structural_atoms": overall["top_structural_atoms"][:10],
        "selected_excerpts": selected_excerpts,
        "per_source_summary": [
            {
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "unit_count": int(row["unit_count"]),
                "structural_token_count": int(row["structural_token_count"]),
                "unique_structural_atoms": int(row["unique_structural_atoms"]),
                "top_structural_atoms": row["top_structural_atoms"][:6],
            }
            for row in comparison["per_source"]
        ],
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# AU Real Transcript Structural Checkpoint",
        "",
        "This artifact promotes the real HCA hearing transcript lane into a",
        "persisted structural/legal checkpoint without overclaiming that the raw",
        "hearing is already clean reviewed fact coverage.",
        "",
        "## Headline",
        "",
        f"- Source files: {summary['source_file_count']}",
        f"- Transcript units: {summary['unit_count']}",
        f"- Structural/legal tokens: {summary['structural_token_count']}",
        f"- Unique structural atoms: {summary['unique_structural_atoms']}",
        f"- Selected high-signal excerpts: {summary['selected_excerpt_count']}",
        f"- Reading: {summary['core_reading']}",
        "",
        "## Source files",
        "",
    ]
    for path in payload["transcript_paths"]:
        lines.append(f"- {path}")
    lines.extend(["", "## Selected high-signal excerpts", ""])
    for row in payload["selected_excerpts"][:8]:
        kinds = ", ".join(f"{kind}={count}" for kind, count in row["structural_kind_counts"].items()) or "-"
        keywords = ", ".join(row["keyword_hits"]) or "-"
        lines.append(
            f"- score={row['score']} kinds={kinds} keywords={keywords}: {row['excerpt_text']}"
        )
    lines.extend(
        [
            "",
            "## Practical reading",
            "",
            "- AU raw transcript backlog is no longer just counted as invisible future work.",
            "- The real hearing lane now has a persisted structural/legal checkpoint built from the actual transcript files.",
            "- The next AU step is still narrower cleanup or projection work so more of this hearing can become reviewed fact/event coverage rather than structural signal only.",
            "",
        ]
    )
    return "\n".join(lines)


def build_checkpoint(
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
    )
    return {
        "summary": payload["summary"],
        "artifact_path": str(artifact_path),
        "summary_path": str(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a persisted structural/legal checkpoint over the real AU hearing transcript files.")
    parser.add_argument("--transcript-file", action="append", default=[], help="Transcript file to include; repeat to override the default real AU set.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the checkpoint into.")
    parser.add_argument("--progress", action="store_true", help="Emit stage progress JSON to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    transcript_paths = [_coerce_path(path) for path in args.transcript_file] or DEFAULT_TRANSCRIPT_PATHS
    result = build_checkpoint(
        Path(args.output_dir).resolve(),
        transcript_paths=transcript_paths,
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
