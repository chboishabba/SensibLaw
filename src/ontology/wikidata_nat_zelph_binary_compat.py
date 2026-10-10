from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.ontology.wikidata_nat_hf_partial_read import _default_repl_runner
from src.policy.carriers.canonical import canonical_sha256


COMPAT_SCHEMA_VERSION = "sl.nat_zelph_binary_compat.v0_1"
KNOWN_GOOD_ITIR_ZELPH_COMMIT = "df54f7740b78f011f41a86bf01b44713b8fb2132"
KNOWN_GOOD_ITIR_RUNTIME = "zelph 0.9.6-dev"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def candidate_zelph_binaries(*, repo_root: Path | None = None) -> list[str]:
    """Return candidate binaries in preference order.

    Explicit ``ZELPH_BIN`` wins.  Otherwise prefer the repo-adjacent ITIR
    build that was previously validated for v2 manifest meta-only and
    nodeOfName partial loads, then fall back to PATH.
    """

    candidates: list[str] = []
    explicit = _text(os.environ.get("ZELPH_BIN"))
    if explicit:
        candidates.append(explicit)

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    for path in [
        root.parent / "ITIR-suite" / "aur" / "zelph" / "build-local" / "bin" / "zelph",
        root / "aur" / "zelph" / "build-local" / "bin" / "zelph",
    ]:
        if path.exists() and os.access(path, os.X_OK):
            candidates.append(str(path))

    path_binary = shutil.which("zelph")
    if path_binary:
        candidates.append(path_binary)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        resolved = str(Path(item).resolve()) if Path(item).exists() else item
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def _binary_banner(binary: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for args in ([binary, "--version"], [binary, "-V"]):
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(1.0, float(timeout_seconds)),
            )
            text = ((proc.stdout or "") + (proc.stderr or "")).strip()
            attempts.append({"argv": args[1:], "exit_code": proc.returncode, "output": text})
            if text:
                return {"banner": text.splitlines()[0], "banner_attempts": attempts}
        except Exception as exc:
            attempts.append({
                "argv": args[1:],
                "exit_code": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {"banner": "", "banner_attempts": attempts}


def probe_zelph_manifest_compatibility(
    manifest: Mapping[str, Any],
    *,
    binary: str,
    timeout_seconds: float = 30.0,
    repl_runner: Any | None = None,
) -> dict[str, Any]:
    """Run the minimum v2 ABI smoke test: manifest-backed ``meta-only``."""

    runner = repl_runner or _default_repl_runner
    with tempfile.TemporaryDirectory(prefix="sensiblaw-zelph-compat-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
        manifest_path.write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )
        payload = (
            f".load-partial {manifest_path} left=none right=none "
            f"nameOfNode=none nodeOfName=none manifest={manifest_path} meta-only\n.exit\n"
        )
        try:
            exit_code, output = runner(
                binary, payload, timeout_seconds=timeout_seconds
            )
        except Exception as exc:
            return {
                "compatible": False,
                "failure_kind": "runner_exception",
                "exit_code": None,
                "termination_kind": "runner_exception",
                "signal_number": None,
                "signal_name": None,
                "detail": f"{type(exc).__name__}: {exc}",
                "output_tail": "",
            }

    exit_code = int(exit_code)
    signal_number = -exit_code if exit_code < 0 else None
    compatible = exit_code == 0
    return {
        "compatible": compatible,
        "failure_kind": None if compatible else "manifest_meta_only_failed",
        "exit_code": exit_code,
        "termination_kind": (
            "clean_exit" if exit_code == 0 else "signal" if exit_code < 0 else "nonzero_exit"
        ),
        "signal_number": signal_number,
        "signal_name": "SIGSEGV" if signal_number == 11 else (f"signal_{signal_number}" if signal_number else None),
        "detail": "",
        "output_tail": "\n".join((output or "").splitlines()[-40:]),
    }


def select_compatible_zelph_binary(
    manifest: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    timeout_seconds: float = 30.0,
    repl_runner: Any | None = None,
) -> dict[str, Any]:
    """Probe candidates in order and return the first v2-compatible binary."""

    rows: list[dict[str, Any]] = []
    selected: str | None = None
    for binary in candidate_zelph_binaries(repo_root=repo_root):
        banner = _binary_banner(binary)
        probe = probe_zelph_manifest_compatibility(
            manifest,
            binary=binary,
            timeout_seconds=timeout_seconds,
            repl_runner=repl_runner,
        )
        row = {"binary": binary, **banner, **probe}
        rows.append(row)
        if probe["compatible"]:
            selected = binary
            break

    payload_without_ref = {
        "schema_version": COMPAT_SCHEMA_VERSION,
        "selected_binary": selected,
        "compatible": selected is not None,
        "candidates": rows,
        "known_good_itir_reference": {
            "commit": KNOWN_GOOD_ITIR_ZELPH_COMMIT,
            "runtime": KNOWN_GOOD_ITIR_RUNTIME,
            "validated_surface": ["manifest_v2_meta_only", "nodeOfName_0_partial_read"],
        },
        "source_support_paid": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["compatibility_ref"] = "nat-zelph-binary-compat:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = [
    "COMPAT_SCHEMA_VERSION",
    "KNOWN_GOOD_ITIR_RUNTIME",
    "KNOWN_GOOD_ITIR_ZELPH_COMMIT",
    "candidate_zelph_binaries",
    "probe_zelph_manifest_compatibility",
    "select_compatible_zelph_binary",
]
