#!/usr/bin/env python3
"""Run the four controlled numeric-production performance experiments.

The four experiments intentionally remain distinct:

* cold: first compilation in the supplied authority database;
* exact: identical source/configuration, requiring numeric receipt equality;
* edit: caller-supplied locally edited source, reporting changed receipt fibres;
* domain: a different same-domain source under the accumulated corpus context.

This driver never treats an edited or merely similar document as semantic parity.
Exact equality is required only for exact replay. Tokens, not documents, are the
canonical cross-document denominator.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic_ns
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


_FIBRE_ROOTS = (
    "parser_root_sha256",
    "object_root_sha256",
    "factor_root_sha256",
    "residual_root_sha256",
    "export_root_sha256",
    "proof_root_sha256",
)
_WORK_FIELDS = (
    "spacy_parser_work_ns",
    "numeric_projection_worker_work_ns",
    "sentence_closure_worker_work_ns",
    "sentence_closure_coordinator_ns",
    "sentence_adjacency_ns",
    "hierarchy_work_ns",
    "paragraph_adjacency_ns",
    "lookup_publication_ns",
    "summary_work_ns",
    "post_parser_worker_work_ns",
    "post_parser_coordinator_ns",
    "post_parser_work_ns",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--cold-input", type=Path, required=True)
    parser.add_argument("--edit-input", type=Path, required=True)
    parser.add_argument("--domain-input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--tranche", choices=("GWB", "AU", "BREXIT"), default="GWB")
    parser.add_argument("--parser-workers", type=int, default=2)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument(
        "--require-empty-receipt-table",
        action="store_true",
        help="Fail before cold measurement unless this database has no numeric receipts.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _assert_empty(database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM execution.numeric_semantic_publication_receipt"
            )
            count = int(cursor.fetchone()[0])
    if count:
        raise RuntimeError(
            f"cold benchmark requested an empty numeric receipt table; found {count} rows"
        )


def _numeric_timing(progress_path: Path) -> dict[str, Any]:
    if not progress_path.exists():
        return {"state": "missing", "evidence_path": str(progress_path)}
    payload = _json(progress_path)
    selected: Mapping[str, Any] | None = None
    for event in payload.get("events") or ():
        if not isinstance(event, Mapping):
            continue
        details = event.get("details")
        if isinstance(details, Mapping) and "spacy_parser_work_ns" in details:
            selected = details
    if selected is None:
        return {"state": "unknown", "evidence_path": str(progress_path)}
    result: dict[str, Any] = {
        "state": "measured",
        "evidence_path": str(progress_path),
        "timing_basis": selected.get("timing_basis"),
        "token_count": int(selected.get("token_count") or 0),
        "sentence_count": int(selected.get("sentence_count") or 0),
        "partition_count": int(selected.get("partition_count") or 0),
    }
    for field in _WORK_FIELDS:
        value = int(selected.get(field) or 0)
        result[field] = value
        result[field.removesuffix("_ns") + "_seconds"] = value / 1_000_000_000
    tokens = int(result["token_count"])
    post = int(result.get("post_parser_work_ns") or 0)
    parser = int(result.get("spacy_parser_work_ns") or 0)
    result["post_parser_to_spacy_work_ratio"] = (
        post / parser if parser > 0 else None
    )
    result["post_parser_work_ns_per_token"] = post / tokens if tokens > 0 else None
    result["spacy_work_ns_per_token"] = parser / tokens if tokens > 0 else None
    return result


def _run(
    *,
    label: str,
    input_path: Path,
    root: Path,
    args: argparse.Namespace,
    reference: Path | None = None,
) -> dict[str, Any]:
    output_root = root / label / "output"
    acceptance_root = root / label / "acceptance"
    receipt_path = acceptance_root / "numeric-semantic-receipt.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_numeric_exact_replay_acceptance.py"),
        "--database-url",
        args.database_url,
        "--postgres-mode",
        "existing",
        "--input-path",
        str(input_path.resolve()),
        "--output-root",
        str(output_root),
        "--acceptance-root",
        str(acceptance_root),
        "--strict-exact",
        "--tranche",
        args.tranche,
        "--parser-workers",
        str(args.parser_workers),
        "--closure-workers",
        str(args.closure_workers),
        "--owner-partitions",
        str(args.owner_partitions),
        "--worker-budget",
        str(args.worker_budget),
        "--numeric-semantic-receipt-output",
        str(receipt_path),
    ]
    if reference is not None:
        command.extend(("--reference-numeric-semantic-receipt", str(reference)))
    started = monotonic_ns()
    completed = subprocess.run(command, cwd=ROOT, check=False)
    wall_ns = monotonic_ns() - started
    report_path = acceptance_root / "numeric-replay-acceptance.json"
    report = _json(report_path) if report_path.exists() else {}
    receipt = _json(receipt_path) if receipt_path.exists() else None
    progress_path = output_root / args.tranche.lower() / "local_pnf_compile_progress.json"
    timing = _numeric_timing(progress_path)
    return {
        "label": label,
        "input_path": str(input_path.resolve()),
        "returncode": completed.returncode,
        "wall_seconds": wall_ns / 1_000_000_000,
        "accepted": bool(report.get("accepted")),
        "numeric_semantic_parity": report.get("numeric_semantic_parity"),
        "receipt": receipt,
        "receipt_path": str(receipt_path),
        "receipt_compute_seconds": (
            int(receipt.get("receipt_compute_ns") or 0) / 1_000_000_000
            if receipt is not None
            else None
        ),
        "receipt_source": receipt.get("receipt_source") if receipt else None,
        "numeric_work_timing": timing,
        "acceptance_report": str(report_path),
    }


def _changed_fibres(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    return [name for name in _FIBRE_ROOTS if left.get(name) != right.get(name)]


def main() -> int:
    args = _parse_args()
    for path in (args.cold_input, args.edit_input, args.domain_input):
        if not path.is_file():
            raise FileNotFoundError(path)
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.require_empty_receipt_table:
        _assert_empty(args.database_url)

    cold = _run(label="cold", input_path=args.cold_input, root=root, args=args)
    cold_receipt_path = Path(cold["receipt_path"])
    exact = _run(
        label="exact-replay",
        input_path=args.cold_input,
        root=root,
        args=args,
        reference=cold_receipt_path,
    )
    edit = _run(label="small-edit", input_path=args.edit_input, root=root, args=args)
    domain = _run(
        label="same-domain-new-document",
        input_path=args.domain_input,
        root=root,
        args=args,
    )

    cold_receipt = cold.get("receipt") or {}
    edit_receipt = edit.get("receipt") or {}
    domain_receipt = domain.get("receipt") or {}
    cold_timing = cold.get("numeric_work_timing") or {}
    domain_timing = domain.get("numeric_work_timing") or {}
    cold_work_per_token = cold_timing.get("post_parser_work_ns_per_token")
    domain_work_per_token = domain_timing.get("post_parser_work_ns_per_token")
    report = {
        "schema_version": "sensiblaw.numeric-reuse-experiments.v1",
        "experiments": {
            "cold": cold,
            "exact_replay": exact,
            "small_edit": edit,
            "same_domain_new_document": domain,
        },
        "exact_replay_receipt_equal": bool(
            exact.get("numeric_semantic_parity", {}).get("semantic_parity")
            if isinstance(exact.get("numeric_semantic_parity"), Mapping)
            else False
        ),
        "exact_replay_receipt_loaded_without_reconstruction": (
            exact.get("receipt_source") == "durable_build"
            and float(exact.get("receipt_compute_seconds") or 0) == 0.0
        ),
        "small_edit_changed_fibres": _changed_fibres(cold_receipt, edit_receipt),
        "small_edit_dependency_locality": {
            "state": "requires_leaf_dependency_closure_evidence",
            "claim_made": False,
            "reason": (
                "family roots establish which semantic fibres changed; this driver "
                "does not infer leaf-level dependency closure from root inequality"
            ),
        },
        "same_domain_receipt_distinct": (
            bool(cold_receipt)
            and bool(domain_receipt)
            and cold_receipt.get("receipt_sha256") != domain_receipt.get("receipt_sha256")
        ),
        "same_domain_work_nonincrease": {
            "state": (
                "measured"
                if cold_work_per_token is not None and domain_work_per_token is not None
                else "unknown"
            ),
            "cold_post_parser_work_ns_per_token": cold_work_per_token,
            "same_domain_post_parser_work_ns_per_token": domain_work_per_token,
            "nonincrease": (
                domain_work_per_token <= cold_work_per_token
                if cold_work_per_token is not None and domain_work_per_token is not None
                else None
            ),
            "scope": "empirical_same-domain_observation_not_universal_theorem",
        },
    }
    _write(root / "numeric-reuse-experiments.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    required = (
        cold.get("accepted")
        and exact.get("accepted")
        and edit.get("accepted")
        and domain.get("accepted")
        and report["exact_replay_receipt_equal"]
        and report["exact_replay_receipt_loaded_without_reconstruction"]
    )
    return 0 if required else 1


if __name__ == "__main__":
    raise SystemExit(main())
