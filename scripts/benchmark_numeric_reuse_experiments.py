#!/usr/bin/env python3
"""Run reproducible cold/exact/edit/same-domain numeric reuse experiments."""

from __future__ import annotations

import argparse
import hashlib
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
_INPUT_NAMES = ("cold", "edit", "domain")
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


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token_count(path: Path) -> int:
    from sensiblaw.interfaces import tokenize_canonical_with_spans

    return len(tokenize_canonical_with_spans(path.read_text(encoding="utf-8")))


def load_fixture_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a versioned benchmark bundle before database access."""

    manifest_path = path.resolve()
    manifest = _json(manifest_path)
    if manifest.get("schema_version") != "sensiblaw.numeric-reuse-fixture.v1":
        raise ValueError("unsupported numeric reuse fixture manifest schema")
    if not isinstance(manifest.get("fixture_id"), str) or not manifest["fixture_id"]:
        raise ValueError("fixture manifest requires a non-empty fixture_id")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("fixture manifest requires an inputs object")
    resolved: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for name in _INPUT_NAMES:
        entry = inputs.get(name)
        if not isinstance(entry, Mapping):
            raise ValueError(f"fixture manifest requires inputs.{name}")
        relative_path = entry.get("path")
        expected_digest = entry.get("sha256")
        expected_bytes = entry.get("bytes")
        expected_tokens = entry.get("token_count")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"fixture input {name} requires a path")
        if not isinstance(expected_digest, str) or len(expected_digest) != 64:
            raise ValueError(f"fixture input {name} requires a SHA-256 digest")
        if not isinstance(expected_bytes, int) or expected_bytes < 1:
            raise ValueError(f"fixture input {name} requires positive byte expectation")
        if not isinstance(expected_tokens, int) or expected_tokens < 1:
            raise ValueError(
                f"fixture input {name} requires positive token expectation"
            )
        input_path = (manifest_path.parent / relative_path).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        actual_digest = _digest(input_path)
        if actual_digest != expected_digest:
            raise ValueError(f"fixture digest drift for {name}: {input_path}")
        if input_path.stat().st_size != expected_bytes:
            raise ValueError(f"fixture byte-count drift for {name}: {input_path}")
        if _token_count(input_path) != expected_tokens:
            raise ValueError(f"fixture token-count drift for {name}: {input_path}")
        resolved[name] = input_path
        digests[name] = actual_digest
    if digests["cold"] == digests["edit"]:
        raise ValueError("fixture cold and edit inputs must differ")
    if digests["cold"] == digests["domain"]:
        raise ValueError("fixture domain input must differ from cold input")
    manifest["resolved_inputs"] = resolved
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--fixture-manifest", type=Path)
    parser.add_argument("--cold-input", type=Path)
    parser.add_argument("--edit-input", type=Path)
    parser.add_argument("--domain-input", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--tranche", choices=("GWB", "AU", "BREXIT"), default="GWB")
    parser.add_argument("--parser-workers", type=int, default=2)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument("--require-empty-receipt-table", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    explicit = (args.cold_input, args.edit_input, args.domain_input)
    if args.fixture_manifest and any(explicit):
        parser.error("--fixture-manifest cannot be combined with explicit input paths")
    if not args.fixture_manifest and not all(explicit):
        parser.error("supply --fixture-manifest or all three explicit input paths")
    return args


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _assert_empty(database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
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
        "token_count": int(selected.get("token_count") or 0),
        "timing_basis": selected.get("timing_basis"),
    }
    for field in _WORK_FIELDS:
        result[field] = int(selected.get(field) or 0)
    tokens = result["token_count"]
    post_parser_work = result["post_parser_work_ns"]
    result["post_parser_work_ns_per_token"] = (
        post_parser_work / tokens if tokens else None
    )
    return result


def _run(
    label: str,
    input_path: Path,
    root: Path,
    args: argparse.Namespace,
    reference: Path | None = None,
) -> dict[str, Any]:
    output_root, acceptance_root = root / label / "output", root / label / "acceptance"
    receipt_path = acceptance_root / "numeric-semantic-receipt.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/run_numeric_exact_replay_acceptance.py"),
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
    report_path = acceptance_root / "numeric-replay-acceptance.json"
    report = _json(report_path) if report_path.exists() else {}
    receipt = _json(receipt_path) if receipt_path.exists() else None
    progress_path = (
        output_root / args.tranche.lower() / "local_pnf_compile_progress.json"
    )
    return {
        "label": label,
        "input_path": str(input_path.resolve()),
        "input_sha256": _digest(input_path),
        "returncode": completed.returncode,
        "wall_seconds": (monotonic_ns() - started) / 1_000_000_000,
        "accepted": bool(report.get("accepted")),
        "numeric_semantic_parity": report.get("numeric_semantic_parity"),
        "receipt": receipt,
        "receipt_path": str(receipt_path),
        "receipt_compute_seconds": int(receipt.get("receipt_compute_ns") or 0)
        / 1_000_000_000
        if receipt
        else None,
        "receipt_source": receipt.get("receipt_source") if receipt else None,
        "numeric_work_timing": _numeric_timing(progress_path),
        "acceptance_report": str(report_path),
    }


def main() -> int:
    args = _parse_args()
    fixture: Mapping[str, Any] | None = None
    if args.fixture_manifest:
        fixture = load_fixture_manifest(args.fixture_manifest)
        inputs = fixture["resolved_inputs"]
    else:
        inputs = {
            name: getattr(args, f"{name}_input").resolve() for name in _INPUT_NAMES
        }
        for path in inputs.values():
            if not path.is_file():
                raise FileNotFoundError(path)
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.require_empty_receipt_table:
        _assert_empty(args.database_url)
    cold = _run("cold", inputs["cold"], root, args)
    exact = _run("exact-replay", inputs["cold"], root, args, Path(cold["receipt_path"]))
    edit = _run("small-edit", inputs["edit"], root, args)
    domain = _run("same-domain-new-document", inputs["domain"], root, args)
    cold_receipt, edit_receipt, domain_receipt = (
        item.get("receipt") or {} for item in (cold, edit, domain)
    )
    cold_work_per_token = cold["numeric_work_timing"].get(
        "post_parser_work_ns_per_token"
    )
    domain_work_per_token = domain["numeric_work_timing"].get(
        "post_parser_work_ns_per_token"
    )
    parity = exact.get("numeric_semantic_parity")
    report = {
        "schema_version": "sensiblaw.numeric-reuse-experiments.v1",
        "fixture": {
            "fixture_id": fixture["fixture_id"],
            "manifest_path": str(args.fixture_manifest.resolve()),
            "same_domain_size_caveat": fixture.get("same_domain_size_caveat"),
        }
        if fixture
        else None,
        "experiments": {
            "cold": cold,
            "exact_replay": exact,
            "small_edit": edit,
            "same_domain_new_document": domain,
        },
        "exact_replay_receipt_equal": bool(
            parity.get("semantic_parity") if isinstance(parity, Mapping) else False
        ),
        "exact_replay_receipt_loaded_without_reconstruction": exact.get(
            "receipt_source"
        )
        == "durable_build"
        and float(exact.get("receipt_compute_seconds") or 0) == 0.0,
        "small_edit_changed_fibres": [
            name
            for name in _FIBRE_ROOTS
            if cold_receipt.get(name) != edit_receipt.get(name)
        ],
        "small_edit_dependency_locality": {
            "state": "requires_leaf_dependency_closure_evidence",
            "claim_made": False,
        },
        "same_domain_receipt_distinct": bool(
            cold_receipt
            and domain_receipt
            and cold_receipt.get("receipt_sha256")
            != domain_receipt.get("receipt_sha256")
        ),
        "same_domain_work_per_token": {
            "state": (
                "measured"
                if cold_work_per_token is not None and domain_work_per_token is not None
                else "unknown"
            ),
            "cold_post_parser_work_ns_per_token": cold_work_per_token,
            "same_domain_post_parser_work_ns_per_token": domain_work_per_token,
            "scope": "empirical_same-domain_observation_not_universal_theorem",
        },
        "same_domain_size_caveat": "token-normalised empirical evidence only; source sizes differ and this is not a universal claim",
    }
    _write(root / "numeric-reuse-experiments.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return (
        0
        if all(
            (
                cold["accepted"],
                exact["accepted"],
                edit["accepted"],
                domain["accepted"],
                report["exact_replay_receipt_equal"],
                report["exact_replay_receipt_loaded_without_reconstruction"],
            )
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
