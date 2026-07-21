#!/usr/bin/env python3
"""Run a bounded legal-document probe through the universal compiler spine.

The probe preserves source/canonical coordinates, records parser observations and
PNF graphs, projects Legal IR only from legal PNF factors, compares the legacy
obligation lane as a diagnostic oracle, emits a unified LegalSemanticBuild, and
optionally performs candidate-only Wikidata lookups warranted by legal materiality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.corpus_source_projection import project_source_families  # noqa: E402
from src.obligations import extract_obligations_from_text, obligation_to_dict  # noqa: E402
from src.ontology.wikimedia_providers import (  # noqa: E402
    WikidataProvider,
    WikimediaMicrobatchRunner,
)
from src.pnf.legal_probe import build_legal_pnf_probe  # noqa: E402
from src.pnf.legal_semantic_build import build_legal_semantic_build  # noqa: E402
from src.policy.corpus_compilation import compile_document, default_compiler_context  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-file", type=Path)
    source.add_argument("--input-directory", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=40)
    parser.add_argument("--max-file-bytes", type=int, default=5_000_000)
    parser.add_argument("--compare-legacy", action="store_true")
    parser.add_argument("--run-wikidata", action="store_true")
    parser.add_argument("--wikidata-candidate-limit", type=int, default=5)
    parser.add_argument("--wikidata-request-budget", type=int, default=32)
    parser.add_argument("--microbatch-size", type=int, default=8)
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error("--max-files must be positive")
    if args.max_file_bytes < 1:
        parser.error("--max-file-bytes must be positive")
    if args.run_wikidata and not args.compare_legacy:
        parser.error("--run-wikidata requires --compare-legacy for an auditable probe")
    return args


def _write_json(path: Path, value: Mapping[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _document_ref(canonical_sha256: str) -> str:
    payload = f"legal-pnf-probe|{canonical_sha256}".encode()
    return "document:" + hashlib.sha256(payload).hexdigest()


def _compile_projection_row(row: Any, projection_root: Path) -> Mapping[str, Any]:
    canonical_path = projection_root / row.canonical_path
    canonical_text = canonical_path.read_text(encoding="utf-8")
    compilation = compile_document(
        {
            "document_ref": _document_ref(row.canonical_sha256),
            "source_ref": row.source_ref,
            "media_type": "text/plain",
            "content_sha256": row.canonical_sha256,
            "canonical_text": canonical_text,
        },
        default_compiler_context(),
    )
    return compilation.to_dict()


def _legacy_rows(text: str) -> list[dict[str, Any]]:
    return [
        obligation_to_dict(row)
        for row in extract_obligations_from_text(
            text,
            references=[],
            source_id="legal-pnf-probe",
        )
    ]


def main() -> int:
    args = _parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    root = (args.input_file or args.input_directory).resolve()
    projection_root = output_dir / "source_projection"
    manifest = project_source_families(
        [root],
        output_dir=projection_root,
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
    )
    _write_json(projection_root / "manifest.json", manifest.to_dict())

    probe_rows: list[dict[str, Any]] = []
    wikidata_demands: list[dict[str, Any]] = []
    for index, row in enumerate(manifest.documents, start=1):
        compilation = _compile_projection_row(row, projection_root)
        artifacts = compilation.get("artifacts") or {}
        canonical_text = str(artifacts.get("canonical_text") or "")
        legacy = _legacy_rows(canonical_text) if args.compare_legacy else []
        probe = build_legal_pnf_probe(compilation, legacy_rows=legacy)

        # The probe owns discovery; the build owns the typed, versioned merge surface.
        from src.pnf.legal_adjunct import project_legal_ir

        refined_graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
        legal_ir_objects = project_legal_ir(refined_graph.get("factors") or ())
        semantic_build = build_legal_semantic_build(
            compilation=compilation,
            legal_ir=legal_ir_objects,
            legacy_rows=legacy,
            declaration_revision_refs=artifacts.get("semantic_reduction_refs") or (),
        )

        document_dir = output_dir / "documents" / f"{index:04d}_{row.canonical_sha256[:12]}"
        _write_json(document_dir / "compilation.json", compilation)
        _write_json(document_dir / "parser_observations.json", probe["parser_observations"])
        _write_json(document_dir / "pnf_graph.json", probe["pnf_graph"])
        _write_json(document_dir / "refined_pnf_graph.json", probe["refined_pnf_graph"])
        _write_json(document_dir / "legal_ir.json", probe["legal_ir"])
        _write_json(document_dir / "legacy_obligations.json", probe["legacy_observations"])
        _write_json(document_dir / "legacy_witnesses.json", semantic_build["legacy_witnesses"])
        _write_json(document_dir / "comparison_ledger.json", semantic_build["comparison_ledger"])
        _write_json(document_dir / "pnf_coverage_demands.json", semantic_build["coverage_demands"])
        _write_json(document_dir / "legal_ir_projection.json", semantic_build["legal_ir_projection"])
        _write_json(document_dir / "legal_semantic_build.json", semantic_build)
        _write_json(
            document_dir / "entity_resolution_decisions.json",
            probe["entity_resolution_decisions"],
        )
        _write_json(document_dir / "wikidata_plan.json", probe["wikidata_lookup_demands"])
        probe_rows.append(
            {
                "source_path": row.source_path,
                "source_ref": row.source_ref,
                "document_ref": compilation.get("document_ref"),
                "probe_ref": probe["probe_ref"],
                "legal_semantic_build_ref": semantic_build["build"]["build_ref"],
                "summary": {**probe["summary"], **semantic_build["summary"]},
                "document_output_dir": str(document_dir),
                "parser_receipt": artifacts.get("parser_receipt") or {},
            }
        )
        wikidata_demands.extend(probe["wikidata_lookup_demands"])

    wikidata_output: dict[str, Any] = {
        "network_performed": False,
        "authority": "candidate_only",
        "identity_closed": False,
        "results": [],
    }
    if args.run_wikidata and wikidata_demands:
        from src.ontology.external_enrichment import ExternalLookupDemand

        demands = tuple(
            ExternalLookupDemand(
                demand_ref=str(row["demand_ref"]),
                subject_ref=str(row["subject_ref"]),
                surface=str(row["surface"]),
                demand_kind=str(row["demand_kind"]),
                local_type_refs=tuple(row.get("local_type_refs") or ()),
                context_terms=tuple(row.get("context_terms") or ()),
                priority=int(row.get("priority") or 0),
                provenance_refs=tuple(row.get("provenance_refs") or ()),
            )
            for row in wikidata_demands
        )
        runner = WikimediaMicrobatchRunner(
            [WikidataProvider(candidate_limit=args.wikidata_candidate_limit)],
            microbatch_size=args.microbatch_size,
            request_budget_per_provider=args.wikidata_request_budget,
        )
        results = runner.run(demands)
        wikidata_output = {
            "network_performed": True,
            "authority": "candidate_only",
            "identity_closed": False,
            "results": [row.to_dict() for row in results],
        }
    _write_json(output_dir / "wikidata_results.json", wikidata_output)

    summary = {
        "schema_version": "sl.legal_pnf_probe_run.v0_2",
        "source_projection": str(projection_root / "manifest.json"),
        "documents": probe_rows,
        "document_count": len(probe_rows),
        "projection_failure_count": len(manifest.failures),
        "legal_ir_observation_count": sum(
            int(row["summary"]["legal_ir_observation_count"]) for row in probe_rows
        ),
        "coverage_gap_count": sum(
            int(row["summary"]["coverage_gap_count"]) for row in probe_rows
        ),
        "coverage_demand_count": sum(
            int(row["summary"]["coverage_demand_count"]) for row in probe_rows
        ),
        "wikidata_lookup_demand_count": len(wikidata_demands),
        "wikidata_network_performed": wikidata_output["network_performed"],
        "identity_closure_count": 0,
        "legal_conclusion_promotion_count": 0,
        "authority": "diagnostic_build_index",
    }
    _write_json(output_dir / "coverage_scorecard.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
