from __future__ import annotations

from contextlib import contextmanager
from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import (
    _canonical_source_coordinates,
    _operational_build_key,
    _operational_document_ref,
    compile_directory_postgres,
    persist_document_compilation,
)
from src.policy.algebra.revision_identity import factor_revision_ref
from src.policy.corpus_compilation import DocumentCompilation
from src.runtime.progress import PhaseRecorder


class _Cursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, statement: str, values=()) -> None:
        self.calls.append((" ".join(statement.split()), tuple(values)))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _Store:
    def __init__(self) -> None:
        self.transaction_calls = 0
        self.savepoint_calls = 0
        self.occurrences: list[dict[str, object]] = []

    @contextmanager
    def transaction(self):
        self.transaction_calls += 1
        yield _Cursor()

    @contextmanager
    def savepoint(self):
        self.savepoint_calls += 1
        yield _Cursor()

    def persist_context(self, cursor, context) -> None:
        cursor.execute("INSERT INTO context", (context,))

    def persist_manifest(self, cursor, manifest) -> None:
        cursor.execute("INSERT INTO manifest", (manifest,))

    def persist_source_document(self, *args, **kwargs) -> None:
        return None

    def persist_tokens(self, *args, **kwargs) -> None:
        return None

    def persist_annotation_layer(self, *args, **kwargs) -> None:
        return None

    def persist_completed_operational_build(self, *args, **kwargs) -> None:
        return None

    def persist_occurrence(self, cursor, *, corpus_ref, relative_path, document_ref, state):
        self.occurrences.append(
            {
                "corpus_ref": corpus_ref,
                "relative_path": relative_path,
                "document_ref": document_ref,
                "state": state,
            }
        )


def test_document_parent_closure_fails_before_savepoint(monkeypatch, tmp_path: Path) -> None:
    context = default_compiler_context()
    source_text = "Bush met Bush."
    source_bytes = source_text.encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    canonical_text, canonical_sha256, media_adapter_ref = _canonical_source_coordinates(
        media_type="text/plain",
        source_text=source_text,
        source_ref="document-source:test",
    )
    document_ref = _operational_document_ref(
        source_content_sha256=source_sha256,
        canonical_text_sha256=canonical_sha256,
        media_type="text/plain",
        media_adapter_ref=media_adapter_ref,
        context=context,
    )
    build_key_sha256 = _operational_build_key(
        document_ref=document_ref,
        content_sha256=source_sha256,
        canonical_text_sha256=canonical_sha256,
        media_adapter_ref=media_adapter_ref,
        context=context,
    )
    prior_factor = {
        "factor_ref": "factor:prior",
        "factor_type": "semantic.eventuality",
        "alternatives": [],
        "constraints": [],
        "residuals": ["semantic_role_unresolved"],
        "closure_state": "requires_external_resolution",
        "metadata": {"producer_contract": "producer:test:v1"},
    }
    resulting_factor = {
        **prior_factor,
        "residuals": [],
        "closure_state": "closed",
    }
    resulting_factor["metadata"] = {
        "producer_contract": "producer:test:v1",
        "factor_revision_ref": factor_revision_ref(resulting_factor),
    }
    compilation = DocumentCompilation(
        document_ref=document_ref,
        content_sha256=source_sha256,
        media_type="text/plain",
        artifacts={
            "canonical_text": canonical_text,
            "canonical_text_sha256": canonical_sha256,
            "build_key_sha256": build_key_sha256,
            "source_normalisation": {"adapter_ref": media_adapter_ref},
            "licensing": {"mentions": []},
            "annotation_layer": {
                "layer_ref": "layer:test",
                "text_sha256": canonical_sha256,
                "tokenizer_ref": context.annotation_backend_ref,
                "token_annotations": [],
                "span_annotations": [],
                "relation_annotations": [],
            },
            "pnf_graph": {
                "graph_ref": "pnf-graph:test",
                "factors": [],
            },
            "refined_pnf_graph": {
                "graph_ref": "pnf-graph:test",
                "factors": [],
            },
            "typed_meets": [],
            "factor_refinements": [
                {
                    "refinement_ref": "factor-refinement:test",
                    "prior_factor": prior_factor,
                    "resulting_factor": resulting_factor,
                }
            ],
            "binding_candidate_sets": [],
            "factor_anchors": [],
            "binding_candidate_set_builds": [],
            "resolution_demands": [],
            "local_evidence": [],
        },
    )
    monkeypatch.setattr(
        "src.policy.postgres_corpus_compilation.compile_document_operational",
        lambda *_args, **_kwargs: compilation,
    )

    store = _Store()
    entry = {
        "document_ref": document_ref,
        "content_sha256": source_sha256,
        "media_type": "text/plain",
        "canonical_text_sha256": canonical_sha256,
        "media_adapter_ref": media_adapter_ref,
        "adapter_capability_ref": media_adapter_ref,
    }

    with pytest.raises(ValueError, match="resolution.refinement"):
        persist_document_compilation(
            store=store,
            corpus_ref="corpus:test",
            relative_path="source.txt",
            entry=entry,
            source_bytes=source_bytes,
            source_text=source_text,
            context=context,
            execution_phase="local",
            batch_index=1,
        )

    assert store.savepoint_calls == 0


def test_compile_directory_postgres_reuses_completed_documents(
    monkeypatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "document.txt").write_text("Bush met Bush.", encoding="utf-8")

    store = _Store()
    monkeypatch.setattr(
        "src.policy.postgres_corpus_compilation.load_completed_operational_build",
        lambda *_args, **_kwargs: ("demand:cached",),
    )
    monkeypatch.setattr(
        "src.policy.postgres_corpus_compilation.persist_document_compilation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit should skip document compilation")
        ),
    )

    result = compile_directory_postgres(
        corpus,
        context=default_compiler_context(),
        store=store,
    )

    assert result.failure_refs == ()
    assert result.demand_refs == ("demand:cached",)
    assert len(result.document_refs) == 1
    assert store.occurrences[0]["state"] == "reused_compilation"


def test_compile_directory_postgres_resume_state_skips_completed_documents(
    monkeypatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_text("Bush met Bush.", encoding="utf-8")
    (corpus / "b.txt").write_text("Alice met Bob.", encoding="utf-8")

    store = _Store()
    load_calls: list[str] = []

    def _load_completed(*_args, **kwargs):
        load_calls.append(str(kwargs.get("document_ref") or ""))
        return None

    executor_calls: list[tuple[str, int, int]] = []

    def _document_executor(**kwargs):
        entry = kwargs["entry"]
        executor_calls.append(
            (
                str(entry["document_ref"]),
                int(kwargs["closure_workers"]),
                int(kwargs["owner_partitions"]),
            )
        )
        return (f"demand:{entry['document_ref']}",)

    state_path = tmp_path / "resume_state.json"
    progress = PhaseRecorder(stream=StringIO(), json_lines=True)

    monkeypatch.setattr(
        "src.policy.postgres_corpus_compilation.load_completed_operational_build",
        _load_completed,
    )
    first = compile_directory_postgres(
        corpus,
        context=default_compiler_context(),
        store=store,
        document_executor=_document_executor,
        document_executor_ref="document-executor:test-operational:v1",
        document_executor_contract_ref="executor:test-operational:v1",
        persistence_strategy_ref="persistence:test-savepoint:v1",
        admission_policy_ref="admission:test:v1",
        closure_workers=4,
        owner_partitions=8,
        progress=progress,
        state_path=state_path,
    )

    assert first.failure_refs == ()
    assert len(first.document_refs) == 2
    assert len(executor_calls) == 2
    assert set(load_calls) == set(first.document_refs)
    assert state_path.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["document_executor_ref"] == "document-executor:test-operational:v1"
    assert state["document_executor_contract_ref"] == "executor:test-operational:v1"
    assert state["persistence_strategy_ref"] == "persistence:test-savepoint:v1"
    assert state["admission_policy_ref"] == "admission:test:v1"
    assert state["closure_workers"] == 4
    assert state["owner_partitions"] == 8
    assert set(state["documents"]) == set(first.document_refs)
    assert all(
        state["documents"][document_ref]["state"] == "compiled"
        for document_ref in first.document_refs
    )
    assert any(
        event.get("worker") == "document-executor:test-operational:v1:doc-0001"
        for event in progress.events
    )

    executor_calls.clear()
    load_calls.clear()
    monkeypatch.setattr(
        "src.policy.postgres_corpus_compilation.load_completed_operational_build",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("resume state should bypass cache lookup")
        ),
    )
    second = compile_directory_postgres(
        corpus,
        context=default_compiler_context(),
        store=store,
        document_executor=_document_executor,
        document_executor_ref="document-executor:test-operational:v1",
        document_executor_contract_ref="executor:test-operational:v1",
        persistence_strategy_ref="persistence:test-savepoint:v1",
        admission_policy_ref="admission:test:v1",
        closure_workers=4,
        owner_partitions=8,
        state_path=state_path,
    )

    assert second == first
    assert executor_calls == []
    assert load_calls == []
