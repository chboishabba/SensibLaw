from __future__ import annotations

import pytest

from src.pnf.stage_cache import (
    MemoryStageCache,
    StageCacheEntry,
    StageReuseReceipt,
)


def _entry(payload: dict[str, object] | None = None) -> StageCacheEntry:
    return StageCacheEntry(
        stage_build_key="stage-key:1",
        document_ref="document:1",
        stage="parser",
        contract_ref="spacy:v1",
        input_refs=("text:1",),
        declaration_refs=(),
        output_ref="parser-output:1",
        output_payload=payload or {"sents": []},
    )


def test_memory_stage_cache_reuses_identical_content_addressed_output() -> None:
    cache = MemoryStageCache()
    entry = _entry()
    cache.persist(entry)
    cache.persist(entry)

    assert cache.load(entry.stage_build_key) == entry


def test_stage_cache_rejects_key_collision() -> None:
    cache = MemoryStageCache()
    cache.persist(_entry())

    with pytest.raises(ValueError, match="collision"):
        cache.persist(_entry({"sents": [{"tokens": []}]}))


def test_reuse_receipt_never_promotes_semantic_state() -> None:
    receipt = StageReuseReceipt(
        document_ref="document:1",
        stage="parser",
        stage_build_key="stage-key:1",
        reused=True,
        source_output_ref="parser-output:1",
    )

    assert receipt.to_dict()["semantic_state_promoted"] is False
