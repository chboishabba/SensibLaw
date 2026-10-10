from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.ontology.wikidata_nat_hf_partial_read import _default_repl_runner, node_of_name_chunks
from src.policy.carriers.canonical import canonical_sha256


DIAGNOSIS_SCHEMA_VERSION = "sl.nat_zelph_hf_crash_diagnosis.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _signal_fields(exit_code: int) -> dict[str, Any]:
    if exit_code < 0:
        signal_number = -exit_code
        return {
            "termination_kind": "signal",
            "signal_number": signal_number,
            "signal_name": "SIGSEGV" if signal_number == 11 else f"signal_{signal_number}",
        }
    if exit_code == 0:
        return {
            "termination_kind": "clean_exit",
            "signal_number": None,
            "signal_name": None,
        }
    return {
        "termination_kind": "nonzero_exit",
        "signal_number": None,
        "signal_name": None,
    }


def _tail(text: str, line_count: int = 40) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-line_count:])


def diagnose_hosted_partial_chunk(
    manifest: Mapping[str, Any],
    *,
    qid: str,
    chunk_index: int | None = None,
    zelph_bin: str | None = None,
    timeout_seconds: float = 120.0,
    repl_runner: Callable[..., tuple[int, str]] | None = None,
) -> dict[str, Any]:
    """Run staged fresh-process probes to isolate hosted partial-load crashes."""

    binary = _text(zelph_bin or os.environ.get("ZELPH_BIN") or shutil.which("zelph"))
    if not binary:
        raise ValueError("Zelph binary unavailable; set ZELPH_BIN")

    chunks = node_of_name_chunks(manifest, language="wikidata")
    if not chunks:
        raise ValueError("manifest has no Wikidata nodeOfName chunks")
    selected = (
        next((row for row in chunks if int(row["chunkIndex"]) == int(chunk_index)), None)
        if chunk_index is not None
        else chunks[0]
    )
    if selected is None:
        raise ValueError(f"nodeOfName chunk {chunk_index} not found")
    selected_index = int(selected["chunkIndex"])

    runner = repl_runner or _default_repl_runner
    with tempfile.TemporaryDirectory(prefix="sensiblaw-nat-hf-diagnose-") as tmp:
        manifest_path = Path(tmp) / "wikidata.hf-v2.json"
        manifest_path.write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )
        load = (
            f".load-partial {manifest_path} left=none right=none "
            f"nameOfNode=none nodeOfName={selected_index} manifest={manifest_path}"
        )
        stages = [
            (
                "manifest_meta_only",
                f".load-partial {manifest_path} left=none right=none nameOfNode=none nodeOfName=none manifest={manifest_path} meta-only\n.exit\n",
            ),
            ("node_of_name_chunk_load_only", f"{load}\n.exit\n"),
            ("node_of_name_chunk_plus_lang", f"{load}\n.lang wikidata\n.exit\n"),
            (
                "node_of_name_chunk_plus_node_probe",
                f"{load}\n.lang wikidata\n.node {qid}\n.exit\n",
            ),
        ]

        results: list[dict[str, Any]] = []
        first_failure_stage: str | None = None
        for stage_name, payload in stages:
            try:
                exit_code, output = runner(
                    binary, payload, timeout_seconds=timeout_seconds
                )
                row = {
                    "stage": stage_name,
                    "exit_code": int(exit_code),
                    **_signal_fields(int(exit_code)),
                    "output_tail": _tail(output),
                }
            except Exception as exc:
                row = {
                    "stage": stage_name,
                    "exit_code": None,
                    "termination_kind": "runner_exception",
                    "signal_number": None,
                    "signal_name": None,
                    "exception_type": type(exc).__name__,
                    "exception_detail": str(exc),
                    "output_tail": "",
                }
            results.append(row)
            if first_failure_stage is None and row.get("exit_code") != 0:
                first_failure_stage = stage_name

    payload_without_ref = {
        "schema_version": DIAGNOSIS_SCHEMA_VERSION,
        "qid": qid,
        "chunk_index": selected_index,
        "object_path": _text(selected.get("objectPath")),
        "size_bytes": selected.get("length"),
        "zelph_binary": binary,
        "stages": results,
        "first_failure_stage": first_failure_stage,
        "diagnostic_only": True,
        "source_support_paid": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["diagnosis_ref"] = "nat-zelph-hf-crash-diagnosis:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = ["DIAGNOSIS_SCHEMA_VERSION", "diagnose_hosted_partial_chunk"]
