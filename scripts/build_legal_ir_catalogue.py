#!/usr/bin/env python3
"""Build or refresh a checked-in legal catalogue and its persistent PNF database."""

from __future__ import annotations

import argparse
import atexit
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.corpus_source_projection import project_source_families  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.parallel_postgres_corpus_compilation import (  # noqa: E402
    compile_directory_postgres_parallel,
)
from src.runtime.progress import PhaseRecorder  # noqa: E402
from src.runtime.request_governor import RequestGovernor, RequestGovernorPolicy  # noqa: E402
from src.sources.legal_follow import follow_legal_sources  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--force-refetch", action="store_true")
    parser.add_argument(
        "--compile-workers",
        type=int,
        default=max(1, min(4, (os.cpu_count() or 2) // 2)),
        help="Document-level PostgreSQL compiler workers (1-32)",
    )
    parser.add_argument(
        "--copy-workers",
        type=int,
        default=4,
        help="Bounded source-family copy workers",
    )
    parser.add_argument("--progress-jsonl", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if not 1 <= args.compile_workers <= 32:
        parser.error("--compile-workers must be between 1 and 32")
    if not 1 <= args.copy_workers <= 16:
        parser.error("--copy-workers must be between 1 and 16")
    return args


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_name(index: int, url: str, suffix: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{index:04d}_{digest}{suffix}"


def _source_file_plan(
    source: Path,
    target: Path,
    *,
    max_file_bytes: int | None = None,
    source_suffixes: tuple[str, ...] = (),
) -> tuple[tuple[Path, Path], ...]:
    if not source.exists():
        return ()
    return tuple(
        (path, target / path.relative_to(source))
        for path in sorted(source.rglob("*"))
        if path.is_file()
        and (not source_suffixes or path.suffix.lower() in source_suffixes)
        and (max_file_bytes is None or path.stat().st_size <= max_file_bytes)
    )


def _copy_one(pair: tuple[Path, Path]) -> str:
    source, destination = pair
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def main() -> int:
    args = _args()
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    recorder = PhaseRecorder(json_lines=args.progress_jsonl)
    phase_ledger_path = output_root / "phase_ledger.json"
    atexit.register(recorder.write_json, phase_ledger_path)

    source_root = output_root / "source_catalogue"
    existing_root = source_root / "existing_au_tranche"
    driving_root = source_root / "austlii_driving"
    raw_root = driving_root / "raw"
    canonical_root = driving_root / "canonical"
    raw_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    copy_plan: list[tuple[Path, Path]] = []
    for family in catalogue.get("persisted_source_families", []):
        max_file_bytes = family.get("max_file_bytes")
        source_suffixes = tuple(
            str(value).lower() for value in family.get("source_suffixes", ())
        )
        copy_plan.extend(
            _source_file_plan(
                ROOT / family["path"],
                existing_root / family["family_ref"].replace(":", "_"),
                max_file_bytes=(int(max_file_bytes) if max_file_bytes is not None else None),
                source_suffixes=source_suffixes,
            )
        )
    with recorder.phase(
        "copy_persisted_sources",
        total=len(copy_plan),
        details={"workers": args.copy_workers},
    ) as phase:
        with ThreadPoolExecutor(max_workers=args.copy_workers, thread_name_prefix="source-copy") as executor:
            for copied_path in executor.map(_copy_one, copy_plan):
                phase.advance(subject_ref=copied_path)
    copied = len(copy_plan)

    policy_data = catalogue["request_policy"]
    governor = RequestGovernor(
        RequestGovernorPolicy(
            minimum_interval_seconds=float(policy_data["minimum_interval_seconds"]),
            maximum_attempts=int(policy_data["maximum_attempts"]),
            backoff_seconds=float(policy_data["backoff_seconds"]),
            request_budget=int(policy_data["request_budget"]),
        )
    )
    provider = catalogue["provider"]
    fetched_documents: list[dict[str, object]] = []
    terms = tuple(catalogue.get("search_terms", []))
    with recorder.phase(
        "acquire_sources",
        total=0 if args.offline else len(terms),
        message="offline reuse" if args.offline else "bounded AustLII discovery",
        details={"provider": provider["endpoint_ref"], "governed": True},
    ) as phase:
        if not args.offline:
            for term in terms:
                search_url = provider["search_url_template"].format(query=quote_plus(term["query"]))
                result = governor.call(
                    search_url,
                    lambda url=search_url: follow_legal_sources(
                        "AU",
                        seed_urls=(url,),
                        max_depth=int(policy_data["max_depth"]),
                        max_documents=max(1, int(policy_data["max_documents"]) // max(1, len(terms))),
                    ),
                )
                term_count = 0
                for followed in result.documents:
                    document = followed.document
                    final_url = document.final_url or document.requested_url
                    suffix = ".html" if document.media_type in {"text/html", "application/xhtml+xml"} else ".txt"
                    name = _safe_name(len(fetched_documents) + 1, final_url, suffix)
                    raw_path = raw_root / name
                    canonical_path = canonical_root / (Path(name).stem + ".txt")
                    reused = raw_path.exists() and not args.force_refetch
                    if not reused:
                        raw_path.write_bytes(document.raw_bytes)
                        canonical_path.write_text(document.canonical_text, encoding="utf-8")
                    fetched_documents.append(
                        {
                            "jurisdiction": term["jurisdiction"],
                            "search_term": term["query"],
                            "search_url": search_url,
                            "requested_url": document.requested_url,
                            "final_url": document.final_url,
                            "raw_path": str(raw_path.relative_to(output_root)),
                            "canonical_path": str(canonical_path.relative_to(output_root)),
                            "reused": reused,
                            "receipt": document.receipt.to_dict(),
                        }
                    )
                    term_count += 1
                phase.advance(
                    subject_ref=term["query"],
                    message=f"{term_count} documents",
                    details={"jurisdiction": term["jurisdiction"], "document_count": term_count},
                )

    with recorder.phase("project_canonical_sources", total=1) as phase:
        projection = project_source_families(
            [existing_root, raw_root],
            output_dir=output_root / "source_projection",
            max_files=500,
            max_file_bytes=10_000_000,
        )
        _write_json(output_root / "source_projection" / "manifest.json", projection.to_dict())
        phase.advance(
            subject_ref=str(output_root / "source_projection" / "manifest.json"),
            details={"source_family_count": 2},
        )

    outcomes: tuple[object, ...]
    with recorder.phase(
        "compile_pnf",
        details={"workers": args.compile_workers, "parallel_boundary": "document"},
    ) as phase:
        compilation, outcomes = compile_directory_postgres_parallel(
            output_root / "source_projection" / "canonical",
            context=default_compiler_context(),
            database_url=args.database_url,
            workers=args.compile_workers,
            execution_phase="demand_planning",
            progress=phase,
        )
    _write_json(
        output_root / "document_compilation_timings.json",
        {
            "schema_version": "sl.document_compilation_timings.v0_1",
            "workers": args.compile_workers,
            "documents": [row.to_dict() for row in outcomes],
        },
    )

    probe_dir = output_root / "legal_pnf_probe"
    with recorder.phase(
        "project_legal_ir",
        total=len(compilation.document_refs),
        message="document-local PNF/Legal IR/legacy differential probe",
    ) as phase:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_legal_pnf_probe.py"),
                "--input-directory",
                str(source_root),
                "--output-dir",
                str(probe_dir),
                "--compare-legacy",
                "--max-files",
                "500",
            ],
            check=True,
        )
        phase.completed = len(compilation.document_refs)

    recorder.write_json(phase_ledger_path)
    manifest = {
        "schema_version": "sl.persisted_legal_catalogue_build.v0_2",
        "catalogue_ref": catalogue["catalogue_ref"],
        "provider": provider,
        "existing_tranche_file_count": copied,
        "fetched_document_count": len(fetched_documents),
        "fetched_documents": fetched_documents,
        "request_governor": governor.summary(),
        "corpus_ref": compilation.corpus_ref,
        "document_refs": list(compilation.document_refs),
        "demand_refs": list(compilation.demand_refs),
        "failure_refs": list(compilation.failure_refs),
        "compile_workers": args.compile_workers,
        "copy_workers": args.copy_workers,
        "document_compilation_timings": "document_compilation_timings.json",
        "phase_ledger": str(phase_ledger_path.relative_to(output_root)),
        "phase_summary": recorder.to_dict()["phase_summary"],
        "legal_pnf_probe_root": str(probe_dir.relative_to(output_root)),
        "parallelism_boundary": "immutable_document_build",
        "request_governor_serialized": True,
        "final_manifest_reduction_serialized": True,
        "identity_promoted": False,
        "legal_truth_closed": False,
        "authority": "candidate_catalogue_build_only",
    }
    _write_json(output_root / "catalogue_build_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
