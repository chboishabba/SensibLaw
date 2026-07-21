#!/usr/bin/env python3
"""Run the complete ordered GWB, AU, or Brexit tranche pipeline.

Parser doctrine is fixed: one media adapter, one canonical text substrate, one
parser spine, then PNF. Local compilation and provisional world projection
complete before registry or PNF-demanded legal acquisition. Wikidata,
Wiktionary, legal-source, and Legal IR outputs remain candidate/review surfaces.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.corpus_source_projection import project_source_families  # noqa: E402
from src.ontology.wikimedia_providers import (  # noqa: E402
    WikidataProvider,
    WikimediaMicrobatchRunner,
    WiktionaryProvider,
)
from src.pnf.external_enrichment_projection import (  # noqa: E402
    summarize_external_lookup_plan,
)
from src.pnf.external_reconciliation import (  # noqa: E402
    build_reconciliation_checkpoint,
)
from src.pnf.legal_adjunct import project_legal_ir  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.postgres_corpus_compilation import compile_directory_postgres  # noqa: E402
from src.runtime.tranche_pipeline import (  # noqa: E402
    PhaseReceipt,
    TranchePhase,
    checkpoint_payload,
    inventory_profile,
    profile_for_tranche,
)
from src.sources.legal_follow import (  # noqa: E402
    follow_legal_source_plan,
    follow_legal_sources,
)
from src.storage.postgres import PostgresCompilerStore  # noqa: E402
from src.storage.postgres.enrichment_planner import (  # noqa: E402
    load_external_lookup_demands,
)
from src.storage.postgres.enrichment_store import (  # noqa: E402
    persist_external_enrichment_results,
)
from src.storage.postgres.legal_adjunct_planner import (  # noqa: E402
    load_legal_pnf_rows,
    load_legal_source_plans,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche", required=True, choices=("GWB", "AU", "BREXIT", "ALL"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-legal-follow", action="store_true")
    parser.add_argument(
        "--seed-legal-follow",
        action="store_true",
        help="Explicitly add a broad jurisdiction profile as seed corpus before PNF.",
    )
    parser.add_argument("--follow-depth", type=int, default=1)
    parser.add_argument("--follow-documents", type=int, default=20)
    parser.add_argument("--max-source-files", type=int)
    parser.add_argument("--max-file-bytes", type=int)
    parser.add_argument("--plan-limit", type=int, default=1_000)
    parser.add_argument("--legal-plan-limit", type=int, default=500)
    parser.add_argument("--microbatch-size", type=int, default=16)
    parser.add_argument("--request-budget-per-provider", type=int, default=64)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--no-wiktionary", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _serialize_results(rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in rows]


def _write_follow_sources(result: Any, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    for index, followed in enumerate(result.documents, start=1):
        document = followed.document
        suffix = ".html" if document.media_type in {"text/html", "application/xhtml+xml"} else ".txt"
        path = raw_dir / f"{index:04d}{suffix}"
        path.write_bytes(document.raw_bytes)
        documents.append(
            {
                "path": str(path),
                "requested_url": document.requested_url,
                "final_url": document.final_url,
                "depth": followed.depth,
                "receipt": document.receipt.to_dict(),
            }
        )
    manifest = {
        "schema_version": "sl.tranche_source_acquisition.v0_2",
        "documents": documents,
        "receipts": [row.to_dict() for row in result.receipts],
        "discovered_urls": list(result.discovered_urls),
        "truncated": result.truncated,
        "authority": "source_acquisition_only",
    }
    _json_write(output_dir / "acquisition_manifest.json", manifest)
    return raw_dir, manifest


def _local_world_summary(cursor: Any, corpus_ref: str, profile: Any) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT factor.factor_type_ref, COUNT(*)
        FROM algebra.factor AS factor
        WHERE factor.document_ref IN (
            SELECT occurrence.document_ref
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
        )
        GROUP BY factor.factor_type_ref
        ORDER BY factor.factor_type_ref
        """,
        (corpus_ref,),
    )
    factor_types = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
    cursor.execute(
        """
        SELECT demand.subject_kind_ref, COUNT(*)
        FROM resolution.demand AS demand
        WHERE demand.factor_ref IN (
            SELECT factor.factor_ref
            FROM algebra.factor AS factor
            WHERE factor.document_ref IN (
                SELECT occurrence.document_ref
                FROM corpus.document_occurrence AS occurrence
                WHERE occurrence.corpus_ref = %s
            )
        )
        GROUP BY demand.subject_kind_ref
        ORDER BY demand.subject_kind_ref
        """,
        (corpus_ref,),
    )
    demand_types = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
    actor_count = sum(
        count
        for kind, count in factor_types.items()
        if kind in {"semantic.mention_identity", "semantic.nominal_description"}
        or kind.startswith("semantic.argument.")
    )
    event_count = sum(
        count
        for kind, count in factor_types.items()
        if kind in {"semantic.eventuality", "semantic.temporal_expression"}
    )
    proposition_count = factor_types.get("semantic.embedded_proposition", 0)
    return {
        "schema_version": "sl.local_world_checkpoint.v0_2",
        "corpus_ref": corpus_ref,
        "profile_ref": profile.profile_ref,
        "factor_types": factor_types,
        "demand_subject_kinds": demand_types,
        "world_fragment": {
            "local_actor_factor_count": actor_count,
            "local_event_factor_count": event_count,
            "local_proposition_factor_count": proposition_count,
            "identity_state": "provisional_local_hypotheses",
        },
        "projection_adapters": list(profile.local_projection_adapters),
        "braid_state": "provisional_before_external_enrichment",
        "authority": "local_world_candidate_only",
    }


def _run_one(args: argparse.Namespace, tranche: str) -> dict[str, Any]:
    profile = profile_for_tranche(tranche)
    output_dir = args.output_root.resolve() / tranche.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[PhaseReceipt] = []
    artifacts: dict[str, Any] = {}

    inventory = inventory_profile(profile, repo_root=ROOT)
    inventory_path = output_dir / "source_inventory.json"
    _json_write(inventory_path, inventory)
    receipts.append(
        PhaseReceipt(
            TranchePhase.SOURCE_INVENTORY,
            "completed",
            (profile.profile_ref,),
            (str(inventory_path),),
            inventory["summary"],
        )
    )
    artifacts["source_inventory"] = str(inventory_path)

    source_roots = [
        ROOT / family.path
        for family in profile.source_families
        if family.path and (ROOT / family.path).exists()
    ]
    acquisition_manifest: dict[str, Any] = {
        "schema_version": "sl.tranche_seed_acquisition.v0_2",
        "documents": [],
        "receipts": [],
        "network_performed": False,
        "mode": "explicit_seed_only",
        "authority": "source_acquisition_only",
    }
    seed_follow_required = not source_roots and bool(profile.legal_follow_profile)
    seed_follow_requested = args.seed_legal_follow and bool(profile.legal_follow_profile)
    if (
        (seed_follow_required or seed_follow_requested)
        and not args.skip_legal_follow
        and not args.offline
    ):
        followed = follow_legal_sources(
            profile.legal_follow_profile,
            max_depth=args.follow_depth,
            max_documents=args.follow_documents,
        )
        followed_root, acquisition_manifest = _write_follow_sources(
            followed, output_dir / "seed_followed_sources"
        )
        source_roots.append(followed_root)
        acquisition_manifest["network_performed"] = True
        acquisition_manifest["mode"] = "explicit_or_required_seed"
    acquisition_path = output_dir / "source_acquisition.json"
    _json_write(acquisition_path, acquisition_manifest)
    receipts.append(
        PhaseReceipt(
            TranchePhase.SOURCE_ACQUISITION,
            "completed" if source_roots else "insufficient_sources",
            (str(inventory_path),),
            (str(acquisition_path),),
            {
                "network_performed": acquisition_manifest["network_performed"],
                "source_root_count": len(source_roots),
                "followed_document_count": len(acquisition_manifest.get("documents") or ()),
                "broad_legal_follow_was_explicit_or_required": bool(
                    acquisition_manifest["network_performed"]
                ),
            },
        )
    )
    artifacts["source_acquisition"] = str(acquisition_path)
    if not source_roots:
        raise RuntimeError(f"{tranche} has no available source family")

    projection = project_source_families(
        source_roots,
        output_dir=output_dir / "source_projection",
        max_files=args.max_source_files,
        max_file_bytes=args.max_file_bytes,
    )
    projection_payload = projection.to_dict()
    projection_path = output_dir / "source_projection" / "manifest.json"
    _json_write(projection_path, projection_payload)
    receipts.append(
        PhaseReceipt(
            TranchePhase.CANONICAL_PROJECTION,
            "completed" if projection.documents else "failed",
            tuple(str(path) for path in source_roots),
            (str(projection_path),),
            projection_payload["summary"],
        )
    )
    artifacts["source_projection"] = str(projection_path)
    if not projection.documents:
        raise RuntimeError(f"{tranche} produced no canonical documents")

    store = PostgresCompilerStore.connect(args.database_url)
    try:
        compilation = compile_directory_postgres(
            output_dir / "source_projection" / "canonical",
            context=default_compiler_context(),
            store=store,
            execution_phase="demand_planning",
        )
        compile_payload = {
            "corpus_ref": compilation.corpus_ref,
            "document_refs": list(compilation.document_refs),
            "demand_refs": list(compilation.demand_refs),
            "failure_refs": list(compilation.failure_refs),
        }
        compile_path = output_dir / "local_pnf_compilation.json"
        _json_write(compile_path, compile_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LOCAL_PNF_COMPILATION,
                "completed" if not compilation.failure_refs else "completed_with_failures",
                (str(projection_path),),
                (compilation.corpus_ref, str(compile_path)),
                {
                    "document_count": len(compilation.document_refs),
                    "demand_count": len(compilation.demand_refs),
                    "failure_count": len(compilation.failure_refs),
                    "network_performed": False,
                },
            )
        )
        artifacts["local_pnf_compilation"] = str(compile_path)

        with store.transaction() as cursor:
            local_world = _local_world_summary(cursor, compilation.corpus_ref, profile)
        local_world_path = output_dir / "local_world_checkpoint.json"
        _json_write(local_world_path, local_world)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LOCAL_WORLD_PROJECTION,
                "completed",
                (compilation.corpus_ref,),
                (str(local_world_path),),
                local_world["world_fragment"],
            )
        )
        artifacts["local_world_checkpoint"] = str(local_world_path)

        with store.transaction() as cursor:
            demands = load_external_lookup_demands(
                cursor,
                corpus_ref=compilation.corpus_ref,
                limit=args.plan_limit,
                include_wiktionary=not args.no_wiktionary,
            )
        plan = summarize_external_lookup_plan(demands)
        plan.update(
            {
                "corpus_ref": compilation.corpus_ref,
                "plan_source": "postgres_open_demands",
                "network_performed": False,
            }
        )
        plan_path = output_dir / "external_enrichment_plan.json"
        _json_write(plan_path, plan)
        receipts.append(
            PhaseReceipt(
                TranchePhase.EXTERNAL_DEMAND_PLANNING,
                "completed",
                (compilation.corpus_ref, str(local_world_path)),
                (str(plan_path),),
                {"lookup_demand_count": len(demands), "network_performed": False},
            )
        )
        artifacts["external_enrichment_plan"] = str(plan_path)

        with store.transaction() as cursor:
            legal_plans = load_legal_source_plans(
                cursor,
                corpus_ref=compilation.corpus_ref,
                limit=args.legal_plan_limit,
            )
        legal_plan_payload = {
            "schema_version": "sl.legal_adjunct_plan.v0_1",
            "corpus_ref": compilation.corpus_ref,
            "plans": [row.to_dict() for row in legal_plans],
            "summary": {
                "plan_count": len(legal_plans),
                "ready_count": sum(row.state == "ready" for row in legal_plans),
                "blocked_count": sum(row.state != "ready" for row in legal_plans),
            },
            "authority": "planning_only",
            "network_performed": False,
        }
        legal_plan_path = output_dir / "legal_adjunct_plan.json"
        _json_write(legal_plan_path, legal_plan_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LEGAL_ADJUNCT_DEMAND_PLANNING,
                "completed",
                (compilation.corpus_ref, str(local_world_path)),
                (str(legal_plan_path),),
                legal_plan_payload["summary"],
            )
        )
        artifacts["legal_adjunct_plan"] = str(legal_plan_path)

        enrichment_output: dict[str, Any] = {
            "schema_version": "sl.wikimedia_enrichment_run.v0_2",
            "plan": plan,
            "demands": [row.to_dict() for row in demands],
            "results": [],
            "network_performed": False,
            "persisted": False,
            "authority": "candidate_only",
        }
        if not args.offline and demands:
            providers = [WikidataProvider(candidate_limit=args.candidate_limit)]
            if not args.no_wiktionary:
                providers.append(WiktionaryProvider())
            runner = WikimediaMicrobatchRunner(
                providers,
                microbatch_size=args.microbatch_size,
                request_budget_per_provider=args.request_budget_per_provider,
            )
            results = runner.run(demands)
            enrichment_output["results"] = _serialize_results(results)
            enrichment_output["network_performed"] = True
            with store.transaction() as cursor:
                persisted = persist_external_enrichment_results(cursor, results)
            enrichment_output["persisted_candidate_set_refs"] = list(persisted)
            enrichment_output["persisted"] = True
        enrichment_path = output_dir / "external_enrichment.json"
        _json_write(enrichment_path, enrichment_output)
        receipts.append(
            PhaseReceipt(
                TranchePhase.EXTERNAL_ACQUISITION,
                "completed" if not args.offline else "skipped_offline",
                (str(plan_path),),
                (str(enrichment_path),),
                {
                    "network_performed": enrichment_output["network_performed"],
                    "result_count": len(enrichment_output["results"]),
                    "identity_closure_count": 0,
                },
            )
        )
        artifacts["external_enrichment"] = str(enrichment_path)

        legal_roots: list[Path] = []
        legal_acquisitions: list[dict[str, Any]] = []
        if not args.offline and not args.skip_legal_follow:
            for index, source_plan in enumerate(legal_plans, start=1):
                result = follow_legal_source_plan(
                    source_plan,
                    max_depth=args.follow_depth,
                    max_documents=args.follow_documents,
                )
                if result is None:
                    legal_acquisitions.append(
                        {
                            "demand_ref": source_plan.demand_ref,
                            "plan_key": source_plan.plan_key,
                            "state": source_plan.state,
                            "documents": [],
                            "authority": "no_acquisition_performed",
                        }
                    )
                    continue
                root, manifest = _write_follow_sources(
                    result,
                    output_dir / "legal_adjunct_sources" / f"{index:04d}",
                )
                legal_roots.append(root)
                legal_acquisitions.append(
                    {
                        "demand_ref": source_plan.demand_ref,
                        "plan_key": source_plan.plan_key,
                        "state": "acquired",
                        "manifest": manifest,
                        "authority": "source_acquisition_only",
                    }
                )
        legal_acquisition_payload = {
            "schema_version": "sl.legal_adjunct_acquisition.v0_1",
            "plans": [row.to_dict() for row in legal_plans],
            "acquisitions": legal_acquisitions,
            "network_performed": bool(legal_roots),
            "authority": "source_acquisition_only",
        }
        legal_acquisition_path = output_dir / "legal_adjunct_acquisition.json"
        _json_write(legal_acquisition_path, legal_acquisition_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LEGAL_ADJUNCT_ACQUISITION,
                "completed" if legal_roots else ("skipped_offline" if args.offline else "no_ready_plans"),
                (str(legal_plan_path),),
                (str(legal_acquisition_path),),
                {
                    "ready_plan_count": sum(row.state == "ready" for row in legal_plans),
                    "acquired_source_root_count": len(legal_roots),
                    "network_performed": bool(legal_roots),
                },
            )
        )
        artifacts["legal_adjunct_acquisition"] = str(legal_acquisition_path)

        adjunct_corpus_ref = ""
        adjunct_compile_payload: dict[str, Any] = {
            "schema_version": "sl.legal_adjunct_pnf_compilation.v0_1",
            "corpus_ref": "",
            "document_refs": [],
            "demand_refs": [],
            "failure_refs": [],
            "state": "no_acquired_documents",
            "same_parser_spine": True,
        }
        if legal_roots:
            adjunct_projection = project_source_families(
                legal_roots,
                output_dir=output_dir / "legal_adjunct_projection",
                max_files=args.max_source_files,
                max_file_bytes=args.max_file_bytes,
            )
            if adjunct_projection.documents:
                adjunct_compilation = compile_directory_postgres(
                    output_dir / "legal_adjunct_projection" / "canonical",
                    context=default_compiler_context(),
                    store=store,
                    execution_phase="legal_adjunct_demand_planning",
                )
                adjunct_corpus_ref = adjunct_compilation.corpus_ref
                adjunct_compile_payload.update(
                    {
                        "corpus_ref": adjunct_corpus_ref,
                        "document_refs": list(adjunct_compilation.document_refs),
                        "demand_refs": list(adjunct_compilation.demand_refs),
                        "failure_refs": list(adjunct_compilation.failure_refs),
                        "state": "completed",
                        "projection_manifest": adjunct_projection.to_dict(),
                    }
                )
        adjunct_compile_path = output_dir / "legal_adjunct_pnf_compilation.json"
        _json_write(adjunct_compile_path, adjunct_compile_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LEGAL_ADJUNCT_PNF_COMPILATION,
                adjunct_compile_payload["state"],
                (str(legal_acquisition_path),),
                tuple(
                    value
                    for value in (adjunct_corpus_ref, str(adjunct_compile_path))
                    if value
                ),
                {
                    "document_count": len(adjunct_compile_payload["document_refs"]),
                    "failure_count": len(adjunct_compile_payload["failure_refs"]),
                    "same_parser_spine": True,
                },
            )
        )
        artifacts["legal_adjunct_pnf_compilation"] = str(adjunct_compile_path)

        legal_ir_rows: tuple[Any, ...] = ()
        if adjunct_corpus_ref:
            with store.transaction() as cursor:
                legal_pnf_rows = load_legal_pnf_rows(cursor, corpus_ref=adjunct_corpus_ref)
            legal_ir_rows = project_legal_ir(legal_pnf_rows)
        legal_ir_payload = {
            "schema_version": "sl.legal_ir_projection.v0_1",
            "source_corpus_ref": adjunct_corpus_ref,
            "observations": [row.to_dict() for row in legal_ir_rows],
            "summary": {
                "observation_count": len(legal_ir_rows),
                "projection_state": (
                    "candidate_observations_available"
                    if legal_ir_rows
                    else "no_legal_pnf_factors_available"
                ),
            },
            "authority": "pnf_projection_only",
            "parser_profile_used": False,
        }
        legal_ir_path = output_dir / "legal_ir_projection.json"
        _json_write(legal_ir_path, legal_ir_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.LEGAL_IR_PROJECTION,
                "completed" if legal_ir_rows else "empty_projection",
                (str(adjunct_compile_path),),
                (str(legal_ir_path),),
                legal_ir_payload["summary"],
            )
        )
        artifacts["legal_ir_projection"] = str(legal_ir_path)

        reconciliation = build_reconciliation_checkpoint(enrichment_output)
        reconciliation["legal_adjunct"] = {
            "plans": [row.to_dict() for row in legal_plans],
            "legal_ir_observations": legal_ir_payload["observations"],
            "applicability_closed": False,
            "violation_closed": False,
            "liability_closed": False,
            "authority": "typed_reconciliation_pending",
        }
        reconciliation_path = output_dir / "external_reconciliation.json"
        _json_write(reconciliation_path, reconciliation)
        receipts.append(
            PhaseReceipt(
                TranchePhase.TYPED_RECONCILIATION,
                "completed",
                (str(enrichment_path), str(legal_ir_path), str(local_world_path)),
                (str(reconciliation_path),),
                {
                    **reconciliation["summary"],
                    "legal_plan_count": len(legal_plans),
                    "legal_ir_observation_count": len(legal_ir_rows),
                    "legal_closure_count": 0,
                },
            )
        )
        artifacts["external_reconciliation"] = str(reconciliation_path)

        review_path = output_dir / "review_packets.json"
        review_payload = {
            "schema_version": "sl.tranche_review_surface.v0_2",
            "corpus_ref": compilation.corpus_ref,
            "review_packets": reconciliation["review_packets"],
            "candidate_overlap_signals": reconciliation["candidate_overlap_signals"],
            "legal_adjunct_review": {
                "plans": [row.to_dict() for row in legal_plans],
                "legal_ir_observations": legal_ir_payload["observations"],
                "available_actions": (
                    "retain_ambiguity",
                    "request_more_evidence",
                    "reject_candidate",
                    "promote_with_authority",
                    "abstain",
                ),
                "automatic_action": None,
            },
            "authority": "review_required",
        }
        _json_write(review_path, review_payload)
        receipts.append(
            PhaseReceipt(
                TranchePhase.REVIEW_PACKET,
                "completed",
                (str(reconciliation_path),),
                (str(review_path),),
                {
                    "review_packet_count": len(review_payload["review_packets"]),
                    "overlap_signal_count": len(review_payload["candidate_overlap_signals"]),
                    "legal_plan_count": len(legal_plans),
                    "promotion_count": 0,
                },
            )
        )
        artifacts["review_packets"] = str(review_path)
    finally:
        store.close()

    checkpoint_path = output_dir / "tranche_checkpoint.json"
    checkpoint_receipt = PhaseReceipt(
        TranchePhase.CHECKPOINT,
        "completed",
        tuple(receipt.receipt_ref for receipt in receipts),
        (str(checkpoint_path),),
        {
            "phase_count": len(receipts) + 1,
            "world_entity_promotion_count": 0,
            "legal_promotion_count": 0,
        },
    )
    checkpoint = checkpoint_payload(
        profile=profile,
        receipts=(*receipts, checkpoint_receipt),
        artifacts=artifacts,
    )
    _json_write(checkpoint_path, checkpoint)
    print(f"tranche={tranche} checkpoint={checkpoint_path}")
    return checkpoint


def main() -> int:
    args = _parse_args()
    tranches = ("GWB", "AU", "BREXIT") if args.tranche == "ALL" else (args.tranche,)
    checkpoints = [_run_one(args, tranche) for tranche in tranches]
    summary = {
        "schema_version": "sl.three_tranche_run.v0_2",
        "tranches": [row["profile"]["tranche"] for row in checkpoints],
        "checkpoint_refs": [
            row["phase_receipts"][-1]["receipt_ref"] for row in checkpoints
        ],
        "authority": "execution_summary_only",
    }
    _json_write(args.output_root.resolve() / "three_tranche_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
