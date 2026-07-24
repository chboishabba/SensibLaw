#!/usr/bin/env python3
"""Run the curated offline PNF → persisted law → Legal IR parity proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.obligations import extract_obligations_from_text, obligation_to_dict  # noqa: E402
from src.pnf.curated_legal_ir_flow import run_curated_legal_ir_flow  # noqa: E402
from src.pnf.legal_ir_parity import SemanticIdentitySnapshot  # noqa: E402
from src.pnf.legal_semantic_build import (  # noqa: E402
    build_legal_semantic_build,
    normalize_legacy_witnesses,
)
from src.policy.carriers.canonical import canonical_sha256  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.fibred_operational_corpus_compilation import (  # noqa: E402
    FIBRED_OPERATIONAL_COMPILER_CONTRACT,
    compile_document_fibred_operational,
)
from src.runtime.offline_network_guard import OfflineNetworkGuard  # noqa: E402
from src.sources.admission import OFFLINE_HCA_REGRESSION_PROFILE, admit_source  # noqa: E402
from src.storage.postgres.batched_compiler_store import (  # noqa: E402
    BatchedPostgresCompilerStore,
)
from src.storage.postgres.legal_source_store import (  # noqa: E402
    load_compatible_legal_sources,
    load_legal_source_payload,
    persist_legal_source_plans,
    persist_parity_receipt,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--control-snapshot", type=Path)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _snapshot(path: Path | None) -> SemanticIdentitySnapshot | None:
    if path is None:
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
    return SemanticIdentitySnapshot(
        proposal_refs=tuple(row.get("proposal_refs") or ()),
        factor_refs=tuple(row.get("factor_refs") or ()),
        graph_refs=tuple(row.get("graph_refs") or ()),
        fibre_ledger_refs=tuple(row.get("fibre_ledger_refs") or ()),
        residual_refs=tuple(row.get("residual_refs") or ()),
        demand_refs=tuple(row.get("demand_refs") or ()),
        legal_ir_refs=tuple(row.get("legal_ir_refs") or ()),
        typed_meet_refs=tuple(row.get("typed_meet_refs") or ()),
        legacy_witness_refs=tuple(row.get("legacy_witness_refs") or ()),
    )


def _allowed_hosts(database_url: str) -> tuple[str, ...]:
    host = urlparse(database_url).hostname
    local = {"localhost", "127.0.0.1", "::1"}
    if host and host not in local:
        raise ValueError("offline parity requires a local PostgreSQL endpoint")
    return tuple(sorted(local | ({host} if host else set())))


def _compile(
    *,
    document_ref: str,
    source_ref: str,
    canonical_text: str,
    closure_workers: int,
    owner_partitions: int,
) -> dict[str, object]:
    digest = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    compilation = compile_document_fibred_operational(
        {
            "document_ref": document_ref,
            "source_ref": source_ref,
            "media_type": "text/plain",
            "content_sha256": digest,
            "canonical_text": canonical_text,
        },
        default_compiler_context(),
        closure_workers=closure_workers,
        owner_partitions=owner_partitions,
    )
    return compilation.to_dict()


def main() -> int:
    args = _args()
    root = args.input_directory.resolve()
    metadata = json.loads(args.source_metadata.read_text(encoding="utf-8"))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ordinary: list[dict[str, object]] = []
    legacy_builds: list[dict[str, object]] = []
    witness_refs: list[str] = []

    store = BatchedPostgresCompilerStore.connect(args.database_url)
    guard = OfflineNetworkGuard(allowed_hosts=_allowed_hosts(args.database_url))
    try:
        with guard:
            for path in sorted(value for value in root.rglob("*") if value.is_file()):
                relative_path = path.relative_to(root).as_posix()
                source_row = dict(metadata.get(relative_path) or {})
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                source_row.setdefault("source_revision_ref", f"source-revision:{digest}")
                receipt = admit_source(
                    source_row,
                    profile=OFFLINE_HCA_REGRESSION_PROFILE,
                )
                if not receipt.compile_eligible:
                    continue
                text = path.read_text(encoding="utf-8")
                document_ref = "document:curated-parity:" + canonical_sha256(
                    {
                        "source_revision_ref": receipt.source_revision_ref,
                        "content_sha256": digest,
                    }
                )
                compilation = _compile(
                    document_ref=document_ref,
                    source_ref=receipt.source_revision_ref,
                    canonical_text=text,
                    closure_workers=args.closure_workers,
                    owner_partitions=args.owner_partitions,
                )
                ordinary.append(compilation)
                legacy_rows = [
                    obligation_to_dict(row)
                    for row in extract_obligations_from_text(
                        text,
                        references=[],
                        source_id=receipt.source_revision_ref,
                    )
                ]
                witnesses = normalize_legacy_witnesses(
                    legacy_rows,
                    document_ref=document_ref,
                )
                witness_refs.extend(row.witness_ref for row in witnesses)
                semantic_build = build_legal_semantic_build(
                    compilation=compilation,
                    legal_ir=(),
                    legacy_rows=legacy_rows,
                    declaration_revision_refs=(FIBRED_OPERATIONAL_COMPILER_CONTRACT,),
                )
                legacy_builds.append(
                    {
                        "document_ref": document_ref,
                        "legacy_witnesses": [row.to_dict() for row in witnesses],
                        "comparison_ledger": semantic_build["comparison_ledger"],
                        "coverage_demands": semantic_build["coverage_demands"],
                    }
                )

            def source_lookup(demand):
                with store.transaction() as cursor:
                    return load_compatible_legal_sources(cursor, demand)

            def payload_lookup(source_revision_ref: str):
                with store.transaction() as cursor:
                    return load_legal_source_payload(
                        cursor,
                        source_revision_ref=source_revision_ref,
                    )

            def compile_legal_source(payload):
                return _compile(
                    document_ref=str(payload["document_ref"]),
                    source_ref=str(payload["source_revision_ref"]),
                    canonical_text=str(payload["canonical_text"]),
                    closure_workers=args.closure_workers,
                    owner_partitions=args.owner_partitions,
                )

            result = run_curated_legal_ir_flow(
                corpus_ref="corpus:curated-legal-ir-parity",
                admission_profile_ref=OFFLINE_HCA_REGRESSION_PROFILE.profile_ref,
                compiler_contract_ref=FIBRED_OPERATIONAL_COMPILER_CONTRACT,
                ordinary_compilations=ordinary,
                source_lookup=source_lookup,
                payload_lookup=payload_lookup,
                compile_legal_source=compile_legal_source,
                legacy_witness_refs=witness_refs,
                control_snapshot=_snapshot(args.control_snapshot),
                network_attempt_count=0,
            )
        network_receipt = guard.receipt.to_dict()
        if not network_receipt["external_network_absent"]:
            raise RuntimeError("parity run attempted external network access")
        with store.transaction() as cursor:
            persist_legal_source_plans(cursor, result.plans)
            persist_parity_receipt(cursor, result.parity_receipt.to_dict())

        _write_json(output / "ordinary_compilations.json", ordinary)
        _write_json(output / "legacy_differential.json", legacy_builds)
        _write_json(output / "legal_ir_flow.json", result.to_dict())
        _write_json(output / "identity_snapshot.json", result.identity_snapshot.to_dict())
        _write_json(output / "parity_receipt.json", result.parity_receipt.to_dict())
        _write_json(output / "network_absence_receipt.json", network_receipt)
        print(json.dumps(result.parity_receipt.to_dict(), indent=2, sort_keys=True))
        if result.parity_receipt.unexpected_failure_refs:
            return 1
        if (
            result.parity_receipt.identity_parity is False
            and args.control_snapshot is not None
        ):
            return 1
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
