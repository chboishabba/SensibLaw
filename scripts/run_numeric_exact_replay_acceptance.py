#!/usr/bin/env python3
"""Run exact acceptance using portable numeric publication identity.

The historical exact-parallel wrapper may return non-zero solely because no
legacy semantic checkpoint exists.  This wrapper preserves that subprocess and
its strict PostgreSQL checks, but makes numeric publication authoritative:

* strict publication must be accepted;
* a portable numeric semantic receipt must be present;
* when a reference receipt is supplied, its SHA-256 must match exactly.

A first cold run with no reference writes the baseline receipt and succeeds.
Subsequent exact replay can therefore establish parity without constructing any
legacy artifact/projection manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.numeric_semantic_parity import (  # noqa: E402
    compare_numeric_receipts,
    numeric_receipt_from_progress,
)


def _value(arguments: list[str], flag: str) -> str | None:
    try:
        index = arguments.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(arguments):
        raise SystemExit(f"{flag} requires a value")
    return arguments[index + 1]


def _remove_pair(arguments: list[str], flag: str) -> tuple[list[str], str | None]:
    value = _value(arguments, flag)
    if value is None:
        return arguments, None
    index = arguments.index(flag)
    return arguments[:index] + arguments[index + 2 :], value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    forwarded = list(sys.argv[1:])
    forwarded, reference_raw = _remove_pair(
        forwarded, "--reference-numeric-semantic-receipt"
    )
    forwarded, output_raw = _remove_pair(
        forwarded, "--numeric-semantic-receipt-output"
    )
    acceptance_raw = _value(forwarded, "--acceptance-root")
    output_root_raw = _value(forwarded, "--output-root")
    tranche = (_value(forwarded, "--tranche") or "GWB").lower()
    if acceptance_raw is None or output_root_raw is None:
        raise SystemExit("--acceptance-root and --output-root are required")

    acceptance_root = Path(acceptance_raw).resolve()
    output_root = Path(output_root_raw).resolve()
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_exact_0008_parallel_acceptance.py"),
        *forwarded,
    ]
    child = subprocess.run(command, cwd=ROOT, check=False)

    strict_path = acceptance_root / "strict" / "acceptance-receipt.json"
    strict = _json(strict_path) if strict_path.exists() else {}
    publication = strict.get("publication_verification")
    numeric_publication = (
        bool(strict.get("accepted"))
        and isinstance(publication, Mapping)
        and publication.get("state") == "verified"
        and publication.get("publication_authority") == "numeric_pnf"
    )

    progress_path = output_root / tranche / "local_pnf_compile_progress.json"
    current = numeric_receipt_from_progress(progress_path)
    receipt_output = (
        Path(output_raw).resolve()
        if output_raw is not None
        else acceptance_root / "numeric-semantic-receipt.json"
    )
    if current is not None:
        _write(receipt_output, current)

    reference = (
        _json(Path(reference_raw).resolve()) if reference_raw is not None else None
    )
    parity = compare_numeric_receipts(reference, current) if reference else {
        "semantic_parity": None,
        "state": "baseline_numeric_receipt_recorded" if current else "numeric_receipt_missing",
    }
    accepted = numeric_publication and current is not None and (
        reference is None or parity.get("semantic_parity") is True
    )
    report = {
        "schema_version": "sensiblaw.numeric-exact-replay-acceptance.v1",
        "state": "completed" if accepted else "failed",
        "accepted": accepted,
        "strict_numeric_publication": numeric_publication,
        "legacy_wrapper_returncode": child.returncode,
        "legacy_wrapper_returncode_authoritative": False,
        "numeric_semantic_receipt": current,
        "numeric_semantic_parity": parity,
        "reference_numeric_semantic_receipt": reference_raw,
        "strict_acceptance_receipt": str(strict_path),
        "progress_evidence": str(progress_path),
    }
    _write(acceptance_root / "numeric-replay-acceptance.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
