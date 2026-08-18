#!/usr/bin/env python3
"""Run the complete ordered GWB, AU, or Brexit tranche pipeline.

Parser doctrine is fixed: one media adapter, one canonical text substrate, one
parser spine, then PNF. Local compilation and provisional world projection
complete before registry or PNF-demanded legal acquisition. Wikidata,
Wiktionary, legal-source, and Legal IR outputs remain candidate/review surfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

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
from src.policy.postgres_corpus_compilation import (  # noqa: E402
    OPERATIONAL_COMPILER_CONTRACT,
    compile_directory_postgres,
)
from src.policy.work_conserving_ordered_compilation import (  # noqa: E402
    compile_directory_postgres_work_conserving_ordered,
)
from src.runtime.progress import PhaseRecorder  # noqa: E402
from src.runtime.execution_resource_ledger import (  # noqa: E402
    ExecutionResourceLedger,
    environment_fingerprint,
)
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


class _CalibrationRollback(RuntimeError):
    """Carry a completed calibration result out of an intentionally rolled back run."""

    def __init__(self, compilation: Any):
        self.compilation = compilation
        super().__init__("calibration transaction rolled back")


def _redacted_database_target(database_url: str) -> str:
    """Return a report-safe database target without password material."""

    parsed = urlsplit(database_url)
    username = f"{parsed.username}@" if parsed.username else ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"{username}{host}{port}", parsed.path, "", ""))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tranche", required=True, choices=("GWB", "AU", "BREXIT", "ALL")
    )
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
    parser.add_argument(
        "--input-path",
        type=Path,
        action="append",
        help=(
            "Explicit source file or directory. When supplied, it replaces the "
            "profile's default source roots while retaining its configuration."
        ),
    )
    parser.add_argument("--plan-limit", type=int, default=1_000)
    parser.add_argument("--legal-plan-limit", type=int, default=500)
    parser.add_argument("--microbatch-size", type=int, default=16)
    parser.add_argument("--request-budget-per-provider", type=int, default=64)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument(
        "--document-workers",
        type=int,
        default=1,
        help="Concurrent documents; inner stages borrow from the shared worker budget.",
    )
    parser.add_argument(
        "--closure-workers",
        type=int,
        default=4,
        help="Closure workers per document for the PostgreSQL compile phase.",
    )
    parser.add_argument(
        "--owner-partitions",
        type=int,
        default=8,
        help="Owner partitions per document for the PostgreSQL compile phase.",
    )
    parser.add_argument(
        "--parser-workers",
        type=int,
        default=2,
        help="Parser-fibre workers used only for oversized documents.",
    )
    parser.add_argument(
        "--worker-budget",
        type=int,
        default=4,
        help="Total CPU worker budget shared across documents and inner stages.",
    )
    parser.add_argument(
        "--parser-limit-chars",
        type=int,
        default=1_000_000,
        help="Safety threshold above which parser-fibre execution is required.",
    )
    parser.add_argument(
        "--parser-target-chars",
        type=int,
        default=400_000,
        help="Owned characters per oversized-document parser fibre.",
    )
    parser.add_argument(
        "--parser-overlap-chars",
        type=int,
        default=8_192,
        help="Bilateral context overlap for parser fibres.",
    )
    parser.add_argument("--no-wiktionary", action="store_true")
    parser.add_argument(
        "--calibration",
        action="store_true",
        help=(
            "Run the normal local compiler and persistence path inside one "
            "rolled-back PostgreSQL transaction, then stop before downstream "
            "phases. This never publishes a completed build or occurrence."
        ),
    )
    parser.add_argument(
        "--strict-exact",
        action="store_true",
        help="Record the PostgreSQL leased strict execution strategy for this run.",
    )
    parser.add_argument(
        "--ledger-root",
        type=Path,
        help="Persist exact-0008 execution ledgers and reports below this directory.",
    )
    parser.add_argument(
        "--trial-ref",
        default="calibration",
        help="Stable trial label included in exact-0008 ledger references.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    parent_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _json_read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _load_tranche_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "sl.complete_tranche_run_state.v0_1",
            "phases": {},
            "artifacts": {},
            "receipts": [],
        }
    state = _json_read(path)
    state.setdefault("schema_version", "sl.complete_tranche_run_state.v0_1")
    state.setdefault("phases", {})
    state.setdefault("artifacts", {})
    state.setdefault("receipts", [])
    return state


def _save_tranche_state(path: Path, state: Mapping[str, Any]) -> None:
    _json_write(path, dict(state))


def _record_phase_checkpoint(
    *,
    tranche_state: dict[str, Any],
    tranche_state_path: Path,
    phase: TranchePhase,
    receipt: PhaseReceipt,
    artifacts: Mapping[str, Any],
) -> None:
    tranche_state["phases"][phase.name] = {
        "phase_ref": phase.phase_ref,
        "state": receipt.state,
        "input_refs": list(receipt.input_refs),
        "output_refs": list(receipt.output_refs),
        "detail": dict(receipt.detail),
        "receipt_ref": receipt.receipt_ref,
    }
    tranche_state["receipts"] = [
        row.to_dict() if isinstance(row, PhaseReceipt) else row
        for row in tranche_state.get("receipts") or []
        if row is not None
    ]
    tranche_state["receipts"].append(receipt.to_dict())
    tranche_state["artifacts"].update(
        {key: str(value) for key, value in artifacts.items()}
    )
    tranche_state["last_phase"] = phase.name
    tranche_state["last_receipt_ref"] = receipt.receipt_ref
    _save_tranche_state(tranche_state_path, tranche_state)


def _load_phase_checkpoint(
    *,
    tranche_state: Mapping[str, Any],
    phase: TranchePhase,
    output_refs: Iterable[Path],
    loader: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any] | None, PhaseReceipt | None]:
    phase_state = (tranche_state.get("phases") or {}).get(phase.name)
    if not isinstance(phase_state, Mapping):
        return None, None
    if any(not path.exists() for path in output_refs):
        return None, None
    payload = loader()
    receipt = PhaseReceipt(
        phase,
        str(phase_state.get("state") or "completed"),
        tuple(str(value) for value in phase_state.get("input_refs") or ()),
        tuple(str(value) for value in phase_state.get("output_refs") or ()),
        dict(phase_state.get("detail") or {}),
    )
    return payload, receipt


def _serialize_results(rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in rows]


def _write_follow_sources(result: Any, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    for index, followed in enumerate(result.documents, start=1):
        document = followed.document
        suffix = (
            ".html"
            if document.media_type in {"text/html", "application/xhtml+xml"}
            else ".txt"
        )
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


def _calibration_row_counts(
    store: PostgresCompilerStore, document_refs: tuple[str, ...]
) -> dict[str, int]:
    """Prove the rolled-back publication boundary is empty for this trial."""

    if not document_refs:
        return {
            "source_documents": 0,
            "occurrences": 0,
            "builds": 0,
            "artifact_manifests": 0,
        }
    with store.transaction() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM corpus.document
            WHERE document_ref = ANY(%s)
            """,
            (list(document_refs),),
        )
        source_documents = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM corpus.document_occurrence
            WHERE document_ref = ANY(%s)
            """,
            (list(document_refs),),
        )
        occurrences = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM execution.document_compilation_build
            WHERE document_ref = ANY(%s)
            """,
            (list(document_refs),),
        )
        builds = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM execution.artifact_manifest
            WHERE document_ref = ANY(%s)
            """,
            (list(document_refs),),
        )
        artifact_manifests = int(cursor.fetchone()[0])
    return {
        "source_documents": source_documents,
        "occurrences": occurrences,
        "builds": builds,
        "artifact_manifests": artifact_manifests,
    }


def _run_one(args: argparse.Namespace, tranche: str) -> dict[str, Any]:
    profile = profile_for_tranche(tranche)
    output_dir = args.output_root.resolve() / tranche.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    resource_ledger = None
    if args.ledger_root is not None:
        environment = environment_fingerprint()
        environment.update(
            {
                "calibration": bool(args.calibration),
                "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
                "tranche": tranche,
                "source_projection_ref": str(
                    output_dir / "source_projection" / "manifest.json"
                ),
            }
        )
        resource_ledger = ExecutionResourceLedger(
            run_ref=f"exact-0008:{args.trial_ref}:{tranche.lower()}",
            document_ref=f"tranche:{tranche.lower()}",
            environment=environment,
        )
        resource_ledger.sample("tranche:start", phase="lifecycle")
    receipts: list[PhaseReceipt] = []
    artifacts: dict[str, Any] = {}
    tranche_state_path = output_dir / "tranche_run_state.json"
    tranche_state = _load_tranche_state(tranche_state_path)
    tranche_state.update(
        {
            "schema_version": "sl.complete_tranche_run_state.v0_1",
            "tranche": tranche,
            "profile_ref": profile.profile_ref,
            "output_dir": str(output_dir),
            "database_target": _redacted_database_target(args.database_url),
        }
    )
    _save_tranche_state(tranche_state_path, tranche_state)

    inventory_path = output_dir / "source_inventory.json"
    inventory, inventory_receipt = _load_phase_checkpoint(
        tranche_state=tranche_state,
        phase=TranchePhase.SOURCE_INVENTORY,
        output_refs=(inventory_path,),
        loader=lambda: _json_read(inventory_path),
    )
    if inventory is None:
        inventory = inventory_profile(profile, repo_root=ROOT)
        _json_write(inventory_path, inventory)
        inventory_receipt = PhaseReceipt(
            TranchePhase.SOURCE_INVENTORY,
            "completed",
            (profile.profile_ref,),
            (str(inventory_path),),
            inventory["summary"],
        )
        _record_phase_checkpoint(
            tranche_state=tranche_state,
            tranche_state_path=tranche_state_path,
            phase=TranchePhase.SOURCE_INVENTORY,
            receipt=inventory_receipt,
            artifacts={"source_inventory": inventory_path},
        )
    receipts.append(inventory_receipt)
    artifacts["source_inventory"] = str(inventory_path)

    explicit_source_paths = tuple(path.resolve() for path in (args.input_path or ()))
    if explicit_source_paths:
        missing_paths = [path for path in explicit_source_paths if not path.exists()]
        if missing_paths:
            raise ValueError(
                "explicit input paths do not exist: "
                + ", ".join(str(path) for path in missing_paths)
            )
        source_roots = list(explicit_source_paths)
    else:
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
        "mode": "explicit_input_only"
        if explicit_source_paths
        else "explicit_seed_only",
        "explicit_input_paths": [str(path) for path in explicit_source_paths],
        "authority": "source_acquisition_only",
    }
    seed_follow_required = not source_roots and bool(profile.legal_follow_profile)
    seed_follow_requested = args.seed_legal_follow and bool(
        profile.legal_follow_profile
    )
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
    acquisition_payload, acquisition_receipt = _load_phase_checkpoint(
        tranche_state=tranche_state,
        phase=TranchePhase.SOURCE_ACQUISITION,
        output_refs=(acquisition_path,),
        loader=lambda: _json_read(acquisition_path),
    )
    if acquisition_payload is None:
        _json_write(acquisition_path, acquisition_manifest)
        acquisition_receipt = PhaseReceipt(
            TranchePhase.SOURCE_ACQUISITION,
            "completed" if source_roots else "insufficient_sources",
            (str(inventory_path),),
            (str(acquisition_path),),
            {
                "network_performed": acquisition_manifest["network_performed"],
                "source_root_count": len(source_roots),
                "followed_document_count": len(
                    acquisition_manifest.get("documents") or ()
                ),
                "broad_legal_follow_was_explicit_or_required": bool(
                    acquisition_manifest["network_performed"]
                ),
            },
        )
        _record_phase_checkpoint(
            tranche_state=tranche_state,
            tranche_state_path=tranche_state_path,
            phase=TranchePhase.SOURCE_ACQUISITION,
            receipt=acquisition_receipt,
            artifacts={"source_acquisition": acquisition_path},
        )
    receipts.append(acquisition_receipt)
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
    if resource_ledger is not None:
        resource_ledger.sample(
            "source_projection:after",
            phase="artifact_projection",
            semantic_counts={"manifest_documents": len(projection.documents)},
        )
    projection_path = output_dir / "source_projection" / "manifest.json"
    if resource_ledger is not None:
        resource_ledger.environment["source_projection_sha256"] = hashlib.sha256(
            json.dumps(
                projection_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
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
    compile_progress = PhaseRecorder(stream=sys.stderr, json_lines=False)
    compile_state_path = output_dir / "local_pnf_compilation_state.json"
    try:
        compile_kwargs = {
            "context": default_compiler_context(),
            "store": store,
            "execution_phase": "demand_planning",
            "progress": compile_progress,
            "state_path": compile_state_path,
            "document_executor_ref": "document-executor:postgres-operational:v0_1",
            "document_executor_contract_ref": OPERATIONAL_COMPILER_CONTRACT,
            "persistence_strategy_ref": "persistence:postgres-savepoint:v0_1",
            "admission_policy_ref": "admission:inventoried-only:v0_1",
            "closure_workers": args.closure_workers,
            "owner_partitions": args.owner_partitions,
            "parser_workers": args.parser_workers,
            "parser_limit_chars": args.parser_limit_chars,
            "parser_target_chars": args.parser_target_chars,
            "parser_overlap_chars": args.parser_overlap_chars,
            "document_workers": args.document_workers,
            "worker_budget": args.worker_budget,
            "database_url": args.database_url,
            "resource_ledger": resource_ledger,
            "execution_strategy_ref": (
                "postgresql-leased-exact-execution:v1"
                if args.strict_exact
                else "local-compatibility-replay"
            ),
        }
        compiler = (
            compile_directory_postgres_work_conserving_ordered
            if args.strict_exact
            else compile_directory_postgres
        )
        if args.calibration:
            # ``PostgresCompilerStore.transaction`` nests as savepoints under
            # this outer transaction, so this exercises source, partition,
            # artifact and publication writes exactly as production does while
            # the final exception rolls every write back atomically.
            try:
                with store.connection.transaction():
                    calibration_compilation = compiler(
                        output_dir / "source_projection" / "canonical",
                        **compile_kwargs,
                    )
                    raise _CalibrationRollback(calibration_compilation)
            except _CalibrationRollback as rollback:
                compilation = rollback.compilation
        else:
            compilation = compiler(
                output_dir / "source_projection" / "canonical",
                **compile_kwargs,
            )
        compile_progress.write_json(output_dir / "local_pnf_compile_progress.json")
        if resource_ledger is not None:
            resource_ledger.sample(
                "stage_ledger:after_compilation",
                phase="stage_ledger",
                semantic_counts={
                    "compiled_documents": len(compilation.document_refs),
                    "demands": len(compilation.demand_refs),
                    "failures": len(compilation.failure_refs),
                },
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
                "completed"
                if not compilation.failure_refs
                else "completed_with_failures",
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
        _record_phase_checkpoint(
            tranche_state=tranche_state,
            tranche_state_path=tranche_state_path,
            phase=TranchePhase.LOCAL_PNF_COMPILATION,
            receipt=receipts[-1],
            artifacts={
                "local_pnf_compilation": compile_path,
                "local_pnf_compile_progress": output_dir
                / "local_pnf_compile_progress.json",
            },
        )

        if compilation.failure_refs:
            raise RuntimeError(
                "local PNF compilation produced failure refs: "
                + ", ".join(compilation.failure_refs)
            )

        if args.calibration:
            calibration_path = output_dir / "tranche_calibration.json"
            calibration = {
                "schema_version": "sl.complete_tranche_calibration.v0_1",
                "tranche": tranche,
                "profile_ref": profile.profile_ref,
                "publication_mode": "rolled_back",
                "source_projection": str(projection_path),
                "local_pnf_compilation": str(compile_path),
                "document_refs": list(compilation.document_refs),
                "failure_refs": list(compilation.failure_refs),
                "rollback_row_counts": _calibration_row_counts(
                    store, tuple(compilation.document_refs)
                ),
            }
            _json_write(calibration_path, calibration)
            if resource_ledger is not None:
                resource_ledger.sample(
                    "publication:rolled_back",
                    phase="publication",
                    details={"publication_mode": "rolled_back"},
                    collect_gc=True,
                )
                ledger_root = args.ledger_root.resolve()
                raw_path = ledger_root / f"{args.trial_ref}-{tranche.lower()}.jsonl"
                report_path = (
                    ledger_root / f"{args.trial_ref}-{tranche.lower()}.report.json"
                )
                environment_path = (
                    ledger_root / f"{args.trial_ref}-{tranche.lower()}.environment.json"
                )
                stage_path = (
                    ledger_root / f"{args.trial_ref}-{tranche.lower()}.stage.json"
                )
                resource_ledger.write_jsonl(raw_path)
                report = resource_ledger.write_report(report_path)
                _json_write(environment_path, resource_ledger.environment)
                _json_write(
                    stage_path,
                    {
                        "schema_version": "sensiblaw.stage-ledger.v1",
                        "run_ref": resource_ledger.run_ref,
                        "samples": [
                            sample.to_dict()
                            for sample in resource_ledger.samples
                            if sample.phase
                            in {
                                "lifecycle",
                                "stage_ledger",
                                "artifact_projection",
                                "publication",
                            }
                        ],
                    },
                )
                calibration["resource_ledger"] = str(raw_path)
                calibration["ownership_report"] = str(report_path)
                calibration["environment_fingerprint"] = str(environment_path)
                calibration["stage_ledger"] = str(stage_path)
                calibration["ownership_report_summary"] = {
                    "sample_count": report["sample_count"],
                    "peak_pss_bytes": report["peak"]["pss_bytes"],
                }
                _json_write(calibration_path, calibration)
            print(f"tranche={tranche} calibration={calibration_path}")
            return {
                "profile": profile.to_dict(),
                "calibration": calibration,
                "calibration_ref": str(calibration_path),
            }

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
        _record_phase_checkpoint(
            tranche_state=tranche_state,
            tranche_state_path=tranche_state_path,
            phase=TranchePhase.LOCAL_WORLD_PROJECTION,
            receipt=receipts[-1],
            artifacts={"local_world_checkpoint": local_world_path},
        )

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
                "completed"
                if legal_roots
                else ("skipped_offline" if args.offline else "no_ready_plans"),
                (str(legal_plan_path),),
                (str(legal_acquisition_path),),
                {
                    "ready_plan_count": sum(
                        row.state == "ready" for row in legal_plans
                    ),
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
                adjunct_progress = PhaseRecorder(stream=sys.stderr, json_lines=False)
                adjunct_state_path = (
                    output_dir / "legal_adjunct_pnf_compilation_state.json"
                )
                adjunct_compilation = compile_directory_postgres(
                    output_dir / "legal_adjunct_projection" / "canonical",
                    context=default_compiler_context(),
                    store=store,
                    execution_phase="legal_adjunct_demand_planning",
                    progress=adjunct_progress,
                    state_path=adjunct_state_path,
                    document_executor_ref="document-executor:postgres-operational:v0_1",
                    document_executor_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
                    persistence_strategy_ref="persistence:postgres-savepoint:v0_1",
                    admission_policy_ref="admission:inventoried-only:v0_1",
                    closure_workers=args.closure_workers,
                    owner_partitions=args.owner_partitions,
                    parser_workers=args.parser_workers,
                    parser_limit_chars=args.parser_limit_chars,
                    parser_target_chars=args.parser_target_chars,
                    parser_overlap_chars=args.parser_overlap_chars,
                    document_workers=args.document_workers,
                    worker_budget=args.worker_budget,
                    database_url=args.database_url,
                )
                adjunct_progress.write_json(
                    output_dir / "legal_adjunct_pnf_compile_progress.json"
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
        _record_phase_checkpoint(
            tranche_state=tranche_state,
            tranche_state_path=tranche_state_path,
            phase=TranchePhase.LEGAL_ADJUNCT_PNF_COMPILATION,
            receipt=receipts[-1],
            artifacts={
                "legal_adjunct_pnf_compilation": adjunct_compile_path,
                "legal_adjunct_pnf_compile_progress": output_dir
                / "legal_adjunct_pnf_compile_progress.json",
            },
        )

        legal_ir_rows: tuple[Any, ...] = ()
        if adjunct_corpus_ref:
            with store.transaction() as cursor:
                legal_pnf_rows = load_legal_pnf_rows(
                    cursor, corpus_ref=adjunct_corpus_ref
                )
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
                    "overlap_signal_count": len(
                        review_payload["candidate_overlap_signals"]
                    ),
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
    if args.calibration:
        # The compiler consults this only to bypass completed-build reuse. The
        # outer transaction in ``_run_one`` remains the publication boundary.
        os.environ["SENSIBLAW_TRANCHE_CALIBRATION"] = "1"
    tranches = ("GWB", "AU", "BREXIT") if args.tranche == "ALL" else (args.tranche,)
    checkpoints = [_run_one(args, tranche) for tranche in tranches]
    summary = {
        "schema_version": (
            "sl.complete_tranche_calibration_summary.v0_1"
            if args.calibration
            else "sl.three_tranche_run.v0_2"
        ),
        "tranches": [row["profile"]["tranche"] for row in checkpoints],
        "checkpoint_refs": (
            [row["calibration_ref"] for row in checkpoints]
            if args.calibration
            else [row["phase_receipts"][-1]["receipt_ref"] for row in checkpoints]
        ),
        "authority": "execution_summary_only",
    }
    _json_write(args.output_root.resolve() / "three_tranche_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
