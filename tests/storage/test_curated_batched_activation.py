from src.storage.postgres import binding_candidate_store
from src.storage.postgres.batched_binding_candidate_store import (
    persist_binding_candidate_sets_batched,
)
from src.storage.postgres.batched_compiler_store import BatchedPostgresCompilerStore


def test_curated_store_activates_batched_binding_persistence() -> None:
    assert BatchedPostgresCompilerStore.__name__ == "BatchedPostgresCompilerStore"
    assert (
        binding_candidate_store.persist_binding_candidate_sets
        is persist_binding_candidate_sets_batched
    )
