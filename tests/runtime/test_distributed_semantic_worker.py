from __future__ import annotations

from src.runtime import distributed_semantic_worker as public_runtime
from src.storage.postgres import distributed_semantic_execution as strict_execution


def test_runtime_module_reexports_strict_typed_worker_surface() -> None:
    assert (
        public_runtime.DistributedSemanticWorker
        is strict_execution.DistributedSemanticWorker
    )
    assert public_runtime.ImmutableJobManifest is strict_execution.ImmutableJobManifest
    assert public_runtime.Lease is strict_execution.Lease
    assert (
        public_runtime.enqueue_canonical_closure_jobs
        is strict_execution.enqueue_canonical_closure_jobs
    )
    assert public_runtime.lease_next_job is strict_execution.lease_next_job
    assert (
        public_runtime.replay_accepted_deltas is strict_execution.replay_accepted_deltas
    )
    assert (
        public_runtime.semantic_delta_admission
        is strict_execution.semantic_delta_admission
    )


def test_runtime_module_exposes_only_current_strict_contract_names() -> None:
    assert set(public_runtime.__all__) == {
        "DistributedSemanticWorker",
        "ImmutableJobManifest",
        "Lease",
        "enqueue_canonical_closure_jobs",
        "lease_next_job",
        "replay_accepted_deltas",
        "semantic_delta_admission",
    }
    assert not hasattr(public_runtime, "SemanticJobResult")
