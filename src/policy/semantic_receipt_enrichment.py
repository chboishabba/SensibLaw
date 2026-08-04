"""Complete durable semantic identity receipts after artifact projection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

_INSTALL_MARKER = "_semantic_receipt_enrichment_installed"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _checkpoint_root(kwargs: Mapping[str, Any]) -> Path | None:
    explicit = os.environ.get("SENSIBLAW_SEMANTIC_CHECKPOINT_DIR")
    if explicit:
        return Path(explicit)
    parser_checkpoint = kwargs.get("parser_checkpoint_dir")
    if parser_checkpoint:
        return Path(str(parser_checkpoint)).parent / "semantic_checkpoints"
    return None


def enrich_semantic_receipt(
    path: str | Path,
    *,
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Add completed compiler-stage identities without changing semantics."""

    target = Path(path)
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("semantic execution receipt must be a JSON object")
    receipt = dict(value)
    amplification = dict(receipt.get("amplification") or {})
    identity = dict(amplification.get("identity_receipt") or {})
    identity["stage_build_keys"] = dict(artifacts.get("stage_build_keys") or {})
    identity["operational_build_key_sha256"] = str(
        artifacts.get("build_key_sha256") or ""
    )
    identity["semantic_reduction_refs"] = sorted(
        str(value) for value in artifacts.get("semantic_reduction_refs") or ()
    )
    identity["constraint_assessment_refs"] = sorted(
        str(row.get("assessment_ref") or row.get("constraint_ref") or "")
        for row in artifacts.get("constraint_assessments") or ()
        if isinstance(row, Mapping)
    )
    streaming_build = artifacts.get("streaming_semantic_build") or {}
    if isinstance(streaming_build, Mapping) and streaming_build.get("reference_backed"):
        # ``reference_parity`` imports the canonical policy carrier.  This
        # module is itself imported by the eager execution-strategy installer
        # during policy package initialization, so importing it at module load
        # time forms a cycle when a caller starts at ``reference_parity``.
        # The function is only needed for a completed receipt, well after the
        # strategy installer has finished; defer it to retain that boundary.
        from src.runtime.reference_parity import reference_semantic_surface

        # Typing hierarchy receipts live in the execution receipt rather than in
        # the streaming-build compatibility view. Bind them into the compact
        # parity surface before hashing so partition-independent typing identity
        # remains part of exact reference/resume acceptance.
        parity_build = {
            **dict(streaming_build),
            "typing_hierarchies": dict(receipt.get("typing_hierarchies") or {}),
        }
        reference_surface = reference_semantic_surface(parity_build)
        identity["reference_semantic_surface"] = reference_surface
        identity["reference_receipt_path"] = str(
            streaming_build.get("reference_receipt_path") or ""
        )
        identity["reference_finalization_contract"] = str(
            streaming_build.get("reference_finalization_contract") or ""
        )
        receipt["reference_backed_execution"] = {
            "state": "complete",
            "surface_ref": reference_surface["surface_ref"],
            "families": reference_surface["families"],
            "logical_typing_refs": reference_surface["logical_typing_refs"],
            "full_document_payload_embedded": False,
            "postgresql_authority_target": True,
        }
    amplification["identity_receipt"] = identity
    receipt["amplification"] = amplification
    receipt["identity_enrichment"] = {
        "state": "complete",
        "source": "completed_operational_artifacts",
        "physical_partition_fields_included": False,
    }
    _atomic_write_json(target, receipt)
    return receipt


def install_semantic_receipt_enrichment() -> bool:
    """Wrap the completed operational compile after semantic instrumentation."""

    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False
    original = operational.compile_document_operational

    def compile_wrapper(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        root = _checkpoint_root(kwargs)
        if root is not None:
            path = root / "semantic-execution-receipt.json"
            if path.exists():
                enrich_semantic_receipt(path, artifacts=result.artifacts)
        return result

    operational.compile_document_operational = compile_wrapper
    operational._instrumented_compile_document_operational = original
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = [
    "enrich_semantic_receipt",
    "install_semantic_receipt_enrichment",
]
