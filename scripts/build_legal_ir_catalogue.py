#!/usr/bin/env python3
"""Build a deterministic offline Legal IR catalogue from persisted sources.

This command has no acquisition capability. Use ``acquire_legal_source.py`` for
an explicit operator-authorised bounded fetch, then rerun this catalogue build.
"""

from __future__ import annotations

import argparse
import atexit
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.corpus_source_projection import project_source_families  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.curated_postgres_corpus_compilation import (  # noqa: E402
    compile_curated_directory_postgres,
)
from src.runtime.offline_network_guard import OfflineNetworkGuard  # noqa: E402
from src.runtime.progress import PhaseRecorder  # noqa: E402
from src.sources.admission import OFFLINE_HCA_REGRESSION_PROFILE  # noqa: E402
from src.sources.catalogue_metadata import source_metadata_from_rules  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--offline", action="store_true", help="Retained for compatibility; builds are always offline")
    parser.add_argument("--force-refetch", action="store_true", help="Rejected; acquisition is a separate command")
    parser.add_argument("--compile-workers", type=int, default=4)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--copy-workers", type=int, default=4)
    parser.add_argument("--transaction-attempts", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--max-file-bytes", type=int, default=10_000_000)
    parser.add_argument("--progress-jsonl", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.force_refetch:
        parser.error("--force-refetch is unavailable; use scripts/acquire_legal_source.py")
    if not 1 <= args.compile_workers <= 32:
        parser.error("--compile-workers must be between 1 and 32")
    if not 1 <= args.closure_workers <= 32:
        parser.error("--closure-workers must be between 1 and 32")
    if not 1 <= args.owner_partitions <= 128:
        parser.error("--owner-partitions must be between 1 and 128")
    if not 1 <= args.copy_workers <= 16:
        parser.error("--copy-workers must be between 1 and 16")
    return args


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_plan(catalogue: dict[str, object], target_root: Path) -> tuple[tuple[Path, Path], ...]:
    rows: list[tuple[Path, Path]] = []
    for raw_family in catalogue.get("persisted_source_families", []):
        family = dict(raw_family)
        source = (ROOT / str(family["path"])).resolve()
        family_ref = str(family["family_ref"]).replace(":", "_")
        target = target_root / family_ref
        suffixes = {str(value).lower() for value in family.get("source_suffixes", ())}
        maximum = family.get("max_file_bytes")
        if source.is_file():
            candidates = (source,)
        elif source.exists():
            candidates = tuple(path for path in sorted(source.rglob("*")) if path.is_file())
        else:
            candidates = ()
        for path in candidates:
            if suffixes and path.suffix.lower() not in suffixes:
                continue
            if maximum is not None and path.stat().st_size > int(maximum):
                continue
            relative = path.name if source.is_file() else str(path.relative_to(source))
            rows.append((path, target / relative))
    return tuple(rows)


def _copy_one(pair: tuple[Path, Path]) -> str:
    source, destination = pair
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _admission_rules(catalogue: dict[str, object]) -> tuple[dict[str, object], ...]:
    explicit = tuple(dict(row) for row in catalogue.get("source_admission_rules", []))
    if explicit:
        return explicit
    derived = []
    for raw_family in catalogue.get("persisted_source_families", []):
        family = dict(raw_family)
        family_ref = str(family["family_ref"]).replace(":", "_")
        derived.append(
            {
                "glob": f"{family_ref}/**",
                "source_role": str(family.get("source_role") or "unclassified"),
                "semantic_scope": str(family.get("semantic_scope") or "source_material"),
                "jurisdiction_ref": str(family.get("jurisdiction_ref") or ""),
                "authority_level": str(family.get("authority_level") or ""),
                "provider_profile_refs": family.get("provider_profile_refs") or (),
                "temporal_refs": family.get("temporal_refs") or (),
            }
        )
    return tuple(derived)


def _aggregate_timings(outcomes: tuple[object, ...]) -> dict[str, object]:
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    slowest: list[dict[str, object]] = []
    for outcome in outcomes:
        for row in getattr(outcome, "stage_timings", ()):
            stage = str(row["stage"])
            elapsed = int(row["elapsed_ms"])
            totals[stage] = totals.get(stage, 0) + elapsed
            counts[stage] = counts.get(stage, 0) + 1
            slowest.append(
                {
                    "document_ref": getattr(outcome, "document_ref"),
                    "relative_path": getattr(outcome, "relative_path"),
                    "stage": stage,
                    "elapsed_ms": elapsed,
                }
            )
    return {
        "stage_totals_ms": {key: totals[key] for key in sorted(totals)},
        "stage_means_ms": {
            key: totals[key] / counts[key] for key in sorted(totals)
        },
        "slowest_stage_instances": sorted(
            slowest,
            key=lambda row: (-int(row["elapsed_ms"]), str(row["document_ref"])),
        )[:30],
    }


def _allowed_database_hosts(database_url: str) -> tuple[str, ...]:
    parsed = urlparse(database_url)
    host = parsed.hostname
    local = {"localhost", "127.0.0.1", "::1"}
    if host and host not in local:
        raise ValueError("offline catalogue requires a local PostgreSQL endpoint")
    return tuple(sorted(local | ({host} if host else set())))


def main() -> int:
    args = _args()
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    recorder = PhaseRecorder(json_lines=args.progress_jsonl)
    phase_ledger_path = output_root / "phase_ledger.json"
    atexit.register(recorder.write_json, phase_ledger_path)

    source_root = output_root / "source_catalogue"
    source_root.mkdir(parents=True, exist_ok=True)
    copy_plan = _copy_plan(catalogue, source_root)
    with recorder.phase(
        "copy_persisted_sources",
        total=len(copy_plan),
        details={"workers": args.copy_workers, "network": "forbidden"},
    ) as phase:
        with ThreadPoolExecutor(max_workers=args.copy_workers) as executor:
            for copied_path in executor.map(_copy_one, copy_plan):
                phase.advance(subject_ref=copied_path)

    projection_root = output_root / "source_projection"
    with recorder.phase("project_canonical_sources", total=1) as phase:
        projection = project_source_families(
            [source_root],
            output_dir=projection_root,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
        )
        _write_json(projection_root / "manifest.json", projection.to_dict())
        phase.advance(
            subject_ref=str(projection_root / "manifest.json"),
            details={"document_count": len(projection.documents)},
        )

    original_relative_paths = []
    for row in projection.documents:
        original_relative_paths.append(
            Path(row.source_path).resolve().relative_to(source_root).as_posix()
        )
    original_metadata = source_metadata_from_rules(
        original_relative_paths,
        rules=_admission_rules(catalogue),
    )
    source_metadata: dict[str, dict[str, object]] = {}
    for row, original_path in zip(
        projection.documents,
        original_relative_paths,
        strict=True,
    ):
        canonical_relative = Path(row.canonical_path).relative_to("canonical").as_posix()
        source_metadata[canonical_relative] = {
            **original_metadata[original_path],
            "source_revision_ref": row.source_ref,
            "source_projection_ref": row.source_ref,
            "source_anchor_state": row.anchor_state,
        }
    _write_json(output_root / "source_metadata.json", source_metadata)

    runtime = {
        "parser_document_processes": args.compile_workers,
        "owner_partitions_per_document": args.owner_partitions,
        "closure_executors_per_document": args.closure_workers,
        "maximum_transaction_attempts": args.transaction_attempts,
    }
    guard = OfflineNetworkGuard(
        allowed_hosts=_allowed_database_hosts(args.database_url)
    )
    with guard:
        with recorder.phase(
            "compile_curated_pnf",
            details={**runtime, "offline": True, "admission_enforced": True},
        ) as phase:
            result = compile_curated_directory_postgres(
                projection_root / "canonical",
                context=default_compiler_context(),
                database_url=args.database_url,
                admission_profile=OFFLINE_HCA_REGRESSION_PROFILE,
                source_metadata=source_metadata,
                workers=args.compile_workers,
                closure_workers_per_document=args.closure_workers,
                owner_partitions_per_document=args.owner_partitions,
                maximum_transaction_attempts=args.transaction_attempts,
                progress=phase,
            )
    network_receipt = guard.receipt.to_dict()
    if not network_receipt["external_network_absent"]:
        raise RuntimeError("offline catalogue recorded external network attempts")

    aggregate = _aggregate_timings(result.outcomes)
    _write_json(output_root / "source_admission_manifest.json", result.admission)
    _write_json(output_root / "network_absence_receipt.json", network_receipt)
    _write_json(
        output_root / "document_compilation_timings.json",
        {
            "schema_version": "sl.document_compilation_timings.v0_3",
            "runtime": runtime,
            "aggregate": aggregate,
            "documents": [row.to_dict() for row in result.outcomes],
        },
    )
    manifest = {
        "schema_version": "sl.persisted_legal_catalogue_build.v0_4",
        "catalogue_ref": catalogue["catalogue_ref"],
        "corpus_ref": result.persisted.corpus_ref,
        "document_refs": list(result.persisted.document_refs),
        "demand_refs": list(result.persisted.demand_refs),
        "failure_refs": list(result.persisted.failure_refs),
        "source_admission_manifest": "source_admission_manifest.json",
        "network_absence_receipt": "network_absence_receipt.json",
        "document_compilation_timings": "document_compilation_timings.json",
        "aggregate_stage_timings": aggregate,
        "runtime": runtime,
        "acquisition_supported": False,
        "governed_acquisition_command": "scripts/acquire_legal_source.py",
        "identity_promoted": False,
        "legal_truth_closed": False,
        "authority": "candidate_catalogue_build_only",
    }
    _write_json(output_root / "catalogue_build_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 1 if result.persisted.failure_refs else 0


if __name__ == "__main__":
    raise SystemExit(main())
