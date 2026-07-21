#!/usr/bin/env python3
"""Build or refresh a checked-in legal catalogue and its persistent PNF database."""

from __future__ import annotations

import argparse
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
from src.policy.postgres_corpus_compilation import compile_directory_postgres  # noqa: E402
from src.runtime.request_governor import RequestGovernor, RequestGovernorPolicy  # noqa: E402
from src.sources.legal_follow import follow_legal_sources  # noqa: E402
from src.storage.postgres import PostgresCompilerStore  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--force-refetch", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_name(index: int, url: str, suffix: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{index:04d}_{digest}{suffix}"


def _copy_source_family(source: Path, target: Path) -> int:
    if not source.exists():
        return 0
    count = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        count += 1
    return count


def main() -> int:
    args = _args()
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
    output_root = args.output_root.resolve()
    source_root = output_root / "source_catalogue"
    existing_root = source_root / "existing_au_tranche"
    driving_root = source_root / "austlii_driving"
    raw_root = driving_root / "raw"
    canonical_root = driving_root / "canonical"
    raw_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    for family in catalogue.get("persisted_source_families", []):
        copied += _copy_source_family(ROOT / family["path"], existing_root / family["family_ref"].replace(":", "_"))

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
    if not args.offline:
        for term_index, term in enumerate(catalogue.get("search_terms", []), start=1):
            search_url = provider["search_url_template"].format(query=quote_plus(term["query"]))
            result = governor.call(
                search_url,
                lambda url=search_url: follow_legal_sources(
                    "AU",
                    seed_urls=(url,),
                    max_depth=int(policy_data["max_depth"]),
                    max_documents=max(1, int(policy_data["max_documents"]) // max(1, len(catalogue["search_terms"]))),
                ),
            )
            for followed in result.documents:
                document = followed.document
                final_url = document.final_url or document.requested_url
                suffix = ".html" if document.media_type in {"text/html", "application/xhtml+xml"} else ".txt"
                name = _safe_name(len(fetched_documents) + 1, final_url, suffix)
                raw_path = raw_root / name
                canonical_path = canonical_root / (Path(name).stem + ".txt")
                if args.force_refetch or not raw_path.exists():
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
                        "receipt": document.receipt.to_dict(),
                    }
                )

    projection = project_source_families(
        [existing_root, raw_root],
        output_dir=output_root / "source_projection",
        max_files=500,
        max_file_bytes=10_000_000,
    )
    _write_json(output_root / "source_projection" / "manifest.json", projection.to_dict())

    store = PostgresCompilerStore.connect(args.database_url)
    try:
        compilation = compile_directory_postgres(
            output_root / "source_projection" / "canonical",
            context=default_compiler_context(),
            store=store,
            execution_phase="legal_catalogue_build",
        )
    finally:
        store.close()

    probe_dir = output_root / "legal_pnf_probe"
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

    manifest = {
        "schema_version": "sl.persisted_legal_catalogue_build.v0_1",
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
        "legal_pnf_probe_root": str(probe_dir.relative_to(output_root)),
        "identity_promoted": False,
        "legal_truth_closed": False,
        "authority": "candidate_catalogue_build_only",
    }
    _write_json(output_root / "catalogue_build_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
