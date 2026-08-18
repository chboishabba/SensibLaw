from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.pnf.numeric_hyperfabric import numeric_digest
from src.storage.postgres.spacy_numeric_projection import (
    NumericHeadProjectionError,
    _RawEntity,
    _RawSentence,
    _RawToken,
    _project_numeric_heads,
    _stable_parser_receipt_digest,
)
from src.storage.postgres.spacy_parser_model import ParserPartition


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "src/storage/postgres/spacy_numeric_projection.py"


def _partition(*, lease_epoch: int = 1, lease_token: str = "lease-a") -> ParserPartition:
    return ParserPartition(
        partition_ref="parser-partition:stable",
        run_ref="typed-spacy-run:stable",
        document_ref="document:stable",
        source_ref="parser-source:stable",
        source_locator="/tmp/source.txt",
        parser_contract_ref="parser:spacy:test",
        partition_kind="structural",
        sequence_no=0,
        owner_start_char=0,
        owner_end_char=20,
        context_start_char=0,
        context_end_char=20,
        owner_start_byte=0,
        owner_end_byte=20,
        context_start_byte=0,
        context_end_byte=20,
        lease_token=lease_token,
        lease_epoch=lease_epoch,
        attempt_ref=f"attempt:{lease_epoch}",
    )


def _sentence() -> _RawSentence:
    digest = numeric_digest(b"sentence", 0, 20)
    return _RawSentence(
        sentence_ref="parser-sentence:" + digest.hex(),
        sentence_digest=digest,
        ordinal=0,
        start_char=0,
        end_char=20,
    )


def _token(*, lemma: str = "run", dependency: str = "ROOT") -> _RawToken:
    sentence = _sentence()
    digest = numeric_digest(sentence.sentence_digest, 0, 3, 0)
    return _RawToken(
        token_ref="parser-token:" + digest.hex(),
        token_digest=digest,
        sentence_ref=sentence.sentence_ref,
        ordinal=0,
        start_char=0,
        end_char=3,
        orth="ran",
        lemma=lemma,
        pos="VERB",
        tag="VBD",
        dependency=dependency,
        lemma_origin_id=1,
        pos_origin_id=1,
        tag_origin_id=1,
        dependency_origin_id=1,
        head_is_self=True,
        head_start_char=0,
        head_end_char=3,
        morphology=(("Tense", "Past"),),
    )


def _entity() -> _RawEntity:
    digest = numeric_digest(b"entity", 4, 8)
    return _RawEntity(
        entity_ref="parser-entity:" + digest.hex(),
        entity_digest=digest,
        sentence_ref=_sentence().sentence_ref,
        start_char=4,
        end_char=8,
        entity_type="PERSON",
    )


def _capabilities() -> dict[str, bool]:
    return {
        "tokenization": True,
        "sentence_segmentation": True,
        "part_of_speech": True,
        "morphology": True,
        "dependencies": True,
        "named_entities": True,
    }


def _digest(partition: ParserPartition, token: _RawToken | None = None) -> bytes:
    return _stable_parser_receipt_digest(
        partition=partition,
        sentences=(_sentence(),),
        raw_tokens=(token or _token(),),
        raw_entities=(_entity(),),
        crossings=(),
        capabilities=_capabilities(),
        model_name="en_core_web_sm",
        model_version="test",
    )


def test_receipt_identity_ignores_lease_retry_coordinates() -> None:
    first = _partition(lease_epoch=1, lease_token="lease-a")
    retried = _partition(lease_epoch=9, lease_token="lease-z")

    assert _digest(first) == _digest(retried)


def test_receipt_identity_changes_when_parser_semantic_output_changes() -> None:
    partition = _partition()

    assert _digest(partition, _token(lemma="run")) != _digest(
        partition, _token(lemma="sprint")
    )
    assert _digest(partition, _token(dependency="ROOT")) != _digest(
        partition, _token(dependency="advcl")
    )


def test_receipt_identity_source_excludes_execution_and_cache_coordinates() -> None:
    source = PROJECTION.read_text(encoding="utf-8")
    helper = source.split("def _stable_parser_receipt_digest(", 1)[1].split(
        "def _project_numeric_heads(", 1
    )[0]

    for forbidden in (
        "elapsed_ns",
        "lease_epoch",
        "lease_token",
        "attempt_ref",
        "worker_pid",
        "backend_pid",
        "artifact_digest",
        "docbin_artifact_ref",
    ):
        assert forbidden not in helper


def test_partition_completion_event_identity_is_retry_invariant() -> None:
    source = PROJECTION.read_text(encoding="utf-8")
    completion = source.split("'parser.partition.completed.v1'", 1)[1]
    completion = completion.split("refresh_coverage(", 1)[0]

    assert "_PARSER_COMPLETION_EVENT_IDENTITY_CONTRACT" in completion
    assert "partition.partition_ref.encode" in completion
    assert "partition.lease_epoch" not in completion
    assert "partition.lease_token" not in completion


def test_missing_non_root_dependency_head_fails_closed() -> None:
    root = _token()
    dependent = replace(
        root,
        token_ref="parser-token:dependent",
        token_digest=numeric_digest(b"dependent"),
        ordinal=1,
        start_char=4,
        end_char=7,
        head_is_self=False,
        head_start_char=100,
        head_end_char=103,
    )
    committed = {
        dependent.token_ref: (11, 7, 4, 7),
    }

    with pytest.raises(
        NumericHeadProjectionError,
        match="declared non-root dependency head is absent from its sentence",
    ):
        _project_numeric_heads((dependent,), committed)
