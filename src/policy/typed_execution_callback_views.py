"""Dual-interface callback views for typed PostgreSQL replay.

The canonical compiler still has in-process callbacks written against mapping
carriers.  Typed execution returns domain objects.  These views expose both
attribute and Mapping interfaces without serialization and without changing
PostgreSQL authority.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from src.pnf.streaming_fixed_point import SolverReceipt
from src.storage.postgres.distributed_semantic_execution import ImmutableJobManifest


class ManifestCallbackView(Mapping[str, Any]):
    def __init__(self, manifest: ImmutableJobManifest) -> None:
        self.manifest = manifest
        self._row = {
            "job_ref": manifest.job_ref,
            "input_manifest": {
                "input_revision": manifest.input_revision,
                "input_payload": manifest.to_solver_job().to_dict(),
            },
        }

    def __getitem__(self, key: str) -> Any:
        return self._row[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._row)

    def __len__(self) -> int:
        return len(self._row)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.manifest, name)


class ReceiptCallbackView(Mapping[str, Any]):
    def __init__(self, receipt: SolverReceipt) -> None:
        self.receipt = receipt
        self._row = receipt.to_dict()

    def __getitem__(self, key: str) -> Any:
        return self._row[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._row)

    def __len__(self) -> int:
        return len(self._row)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.receipt, name)


def install_typed_execution_callback_views() -> bool:
    from src.storage.postgres import distributed_semantic_execution as execution

    if getattr(execution, "_typed_callback_views_installed", False):
        return False
    original = execution.replay_accepted_deltas

    def replay_accepted_deltas(
        cursor: Any,
        *,
        run_ref: str,
        owner_ref: str,
        apply: Any,
        starting_revision: int = 0,
        rehydrate: Any | None = None,
    ) -> int:
        def apply_view(receipt: SolverReceipt, revision: int) -> None:
            apply(ReceiptCallbackView(receipt), revision)

        def rehydrate_view(manifest: ImmutableJobManifest) -> None:
            if rehydrate is not None:
                rehydrate(ManifestCallbackView(manifest))

        return original(
            cursor,
            run_ref=run_ref,
            owner_ref=owner_ref,
            apply=apply_view,
            starting_revision=starting_revision,
            rehydrate=rehydrate_view if rehydrate is not None else None,
        )

    execution.replay_accepted_deltas = replay_accepted_deltas
    execution._typed_callback_views_installed = True
    return True


__all__ = [
    "ManifestCallbackView",
    "ReceiptCallbackView",
    "install_typed_execution_callback_views",
]
