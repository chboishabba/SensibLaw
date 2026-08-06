"""Install binary-only semantic checkpoint persistence.

The semantic execution modules predate the repository-wide JSON prohibition.
This execution-policy layer replaces their physical readers, writers, and path
constructors before any document work begins.  Semantic functions and identities
remain unchanged; no active checkpoint crosses a text serialization boundary.
"""

from __future__ import annotations

import os
from pathlib import Path
import pickle
from typing import Any, Mapping


_INSTALL_MARKER = "_no_json_checkpoint_execution_installed"


def _atomic_write_binary(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = pickle.dumps(dict(payload), protocol=5)
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _read_binary(path: Path) -> dict[str, Any] | None:
    try:
        value = pickle.loads(path.read_bytes())
    except (OSError, EOFError, pickle.PickleError, AttributeError, ValueError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _safe_ref(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in value
    )


def install_no_json_checkpoint_execution() -> bool:
    from src.policy import parallel_semantic_execution as semantic
    from src.policy import parallel_typing_tail as typing_tail

    if getattr(semantic, _INSTALL_MARKER, False):
        return False

    semantic._atomic_write_json = _atomic_write_binary
    semantic._read_json = _read_binary

    def closure_handoff_checkpoint_path(self: Any) -> Path | None:
        root = self.closure_activation_checkpoint_root
        return None if root is None else root / "handoff-state.pkl"

    def closure_receipt_path(self: Any, job_ref: str) -> Path | None:
        root = self.closure_checkpoint_root
        return None if root is None else root / f"{_safe_ref(job_ref)}.pkl"

    def activation_leaf_path(root: Path | None, leaf_ref: str) -> Path | None:
        return None if root is None else root / f"{_safe_ref(leaf_ref)}.pkl"

    def replay_artifact_path(context: Any, artifact_ref: str) -> Path | None:
        root = context.closure_replay_artifact_root
        return None if root is None else root / f"{_safe_ref(artifact_ref)}.pkl"

    def write_receipts(self: Any) -> None:
        if self.checkpoint_root is None:
            return
        closure = semantic.closure_amplification_report(self.closure_counters)
        receipt = {
            "schema_version": semantic.SEMANTIC_EXECUTION_SCHEMA_VERSION,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "parser_contract_ref": self.parser_contract_ref,
            "build_key_sha256": self.build_key_sha256,
            "typing_contract_ref": semantic.TYPING_EXECUTION_CONTRACT,
            "closure_replay_contract_ref": semantic.CLOSURE_REPLAY_CONTRACT,
            "closure_activation_contract_ref": semantic.CLOSURE_ACTIVATION_CONTRACT,
            "configuration": {
                "typing_workers": self.typing_workers,
                "typing_leaf_capacity": self.leaf_capacity,
                "hierarchy_arity": self.hierarchy_arity,
                "closure_activation_leaf_size": self.closure_activation_leaf_size,
            },
            "state": self.state,
            "error": self.error,
            "kernel_timeline": list(self.kernel_timeline),
            "typing_hierarchies": dict(sorted(self.typing_receipts.items())),
            "closure_audit": {
                "events": list(self.closure_events),
                "activation": dict(self.closure_activation),
                **closure,
            },
            "amplification": dict(self.amplification),
            "semantic_authority": "one_document",
            "partition_semantic_effect": "none",
            "text_serialization": False,
        }
        _atomic_write_binary(
            self.checkpoint_root / "semantic-execution-receipt.pkl",
            receipt,
        )
        _atomic_write_binary(
            self.checkpoint_root / "semantic-amplification-report.pkl",
            {
                "schema_version": "sensiblaw.semantic-amplification-report.v2",
                "document_ref": self.document_ref,
                **dict(self.amplification),
                "closure": closure,
                "text_serialization": False,
            },
        )

    semantic.SemanticExecutionContext.closure_handoff_checkpoint_path = property(
        closure_handoff_checkpoint_path
    )
    semantic.SemanticExecutionContext.closure_receipt_path = closure_receipt_path
    semantic.SemanticExecutionContext.write_receipts = write_receipts
    semantic._closure_activation_leaf_path = activation_leaf_path
    semantic._replay_artifact_path = replay_artifact_path

    typing_tail._atomic_write_json = _atomic_write_binary
    typing_tail._read_json = _read_binary

    def typing_leaf_path(root: Path | None, operation: str, leaf_ref: str) -> Path | None:
        if root is None:
            return None
        return root / operation / f"{_safe_ref(leaf_ref)}.pkl"

    typing_tail._leaf_path = typing_leaf_path
    setattr(semantic, _INSTALL_MARKER, True)
    return True


__all__ = ["install_no_json_checkpoint_execution"]
