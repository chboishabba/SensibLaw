from __future__ import annotations

import os
import threading
from io import StringIO
from pathlib import Path
from typing import Any

from src.pnf.document_fibres import (
    DocumentFibrePolicy,
    build_document_structural_carrier,
    parse_document_fibres,
)
from src.runtime.document_stage_metrics import stage_measure_declaration
from src.runtime.progress import PhaseRecorder


def _parser_calls(calls: list[str]):
    def parse(text: str) -> dict[str, Any]:
        calls.append(text)
        sentences = []
        cursor = 0
        for index, word in enumerate(text.split()):
            start = text.index(word, cursor)
            end = start + len(word)
            cursor = end
            token = {
                "index": index,
                "text": word,
                "lemma": word.lower(),
                "pos": "NOUN",
                "tag": "",
                "morph": {},
                "dep": "ROOT",
                "head_index": index,
                "head_text": word,
                "start": start,
                "end": end,
            }
            sentences.append(
                {
                    "text": word,
                    "start": start,
                    "end": end,
                    "tokens": [token],
                }
            )
        return {
            "text": text,
            "sents": sentences,
            "parser_receipt": {
                "contract_ref": "parser:test:v1",
                "capabilities": {
                    "tokenization": True,
                    "sentence_segmentation": True,
                },
                "authority": "parser_observation_only",
            },
        }

    return parse


def test_structural_carrier_has_exact_ownership_and_bounded_overlap() -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    policy = DocumentFibrePolicy(
        parser_limit_chars=100,
        target_chars=40,
        overlap_chars=5,
        workers=2,
    )
    carrier = build_document_structural_carrier(
        document_ref="document:test",
        canonical_text=text,
        policy=policy,
    )

    assert carrier.fibres[0].owner_start == 0
    assert carrier.fibres[-1].owner_end == len(text)
    assert all(
        left.owner_end == right.owner_start
        for left, right in zip(carrier.fibres, carrier.fibres[1:])
    )
    assert all(
        fibre.context_end - fibre.context_start < policy.parser_limit_chars
        for fibre in carrier.fibres
    )


def test_parser_fibres_reconstruct_one_document_and_reuse_checkpoints(
    tmp_path: Path,
) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    policy = DocumentFibrePolicy(
        parser_limit_chars=100,
        target_chars=40,
        overlap_chars=5,
        workers=2,
    )
    first_calls: list[str] = []
    first = parse_document_fibres(
        document_ref="document:test",
        canonical_text=text,
        parser=_parser_calls(first_calls),
        policy=policy,
        checkpoint_dir=tmp_path,
    )
    second_calls: list[str] = []
    second = parse_document_fibres(
        document_ref="document:test",
        canonical_text=text,
        parser=_parser_calls(second_calls),
        policy=policy,
        checkpoint_dir=tmp_path,
    )

    assert first["text"] == text
    assert second["text"] == text
    assert len(first_calls) == first["parser_receipt"]["fibre_count"]
    assert second_calls == []
    assert second["parser_receipt"]["reused_fibre_count"] == len(first_calls)
    assert (
        second["parser_receipt"]["cross_fibre_fixed_point"]["semantic_object"]
        == "document"
    )
    assert (
        second["parser_receipt"]["cross_fibre_fixed_point"]["fibre_semantic_authority"]
        is False
    )


def test_parser_fibres_report_typed_stage_progress(tmp_path: Path) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    policy = DocumentFibrePolicy(
        parser_limit_chars=100,
        target_chars=40,
        overlap_chars=5,
        workers=2,
    )
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", total=1, heartbeat_seconds=None) as phase:
        with phase.stage(
            "parser_annotation",
            measures=stage_measure_declaration("parser_annotation"),
        ) as stage:
            parsed = parse_document_fibres(
                document_ref="document:test",
                canonical_text=text,
                parser=_parser_calls([]),
                policy=policy,
                checkpoint_dir=tmp_path,
                progress=stage,
            )

    running_events = [
        event
        for event in recorder.events
        if event["state"] == "running"
        and event.get("active_stage") == "parser_annotation"
    ]
    assert running_events
    assert running_events[-1]["measures"]["fibres"]["completed"] >= 1
    assert running_events[-1]["measures"]["tokens"]["completed"] > 0
    assert parsed["parser_receipt"]["fibre_count"] >= 1


def test_adaptive_partitioning_is_independent_of_parser_safety_limit(
    tmp_path: Path,
) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    policy = DocumentFibrePolicy(
        parser_limit_chars=1_000,
        target_chars=40,
        overlap_chars=5,
        workers=2,
    )
    parsed = parse_document_fibres(
        document_ref="document:adaptive",
        canonical_text=text,
        parser=_parser_calls([]),
        policy=policy,
        checkpoint_dir=tmp_path,
    )

    assert len(text) < policy.parser_limit_chars
    assert parsed["parser_receipt"]["execution_mode"] == "adaptive_fibres"
    assert parsed["parser_receipt"]["parallelism_reason"] == "workload_threshold"
    assert parsed["parser_receipt"]["worker_count"] == policy.workers
    assert parsed["parser_receipt"]["partition_count"] >= 2
    assert parsed["parser_receipt"]["workload_estimate"]["canonical_chars"] == len(text)


def test_public_parser_fibres_share_one_process_and_bound_in_flight_work(
    tmp_path: Path,
) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 30).strip()
    process_ids: list[int] = []
    thread_ids: list[int] = []
    delegate = _parser_calls([])

    def parser(value: str) -> dict[str, Any]:
        process_ids.append(os.getpid())
        thread_ids.append(threading.get_ident())
        return delegate(value)

    policy = DocumentFibrePolicy(
        parser_limit_chars=120,
        target_chars=40,
        overlap_chars=5,
        workers=2,
    )
    parsed = parse_document_fibres(
        document_ref="document:threaded-parser",
        canonical_text=text,
        parser=parser,
        policy=policy,
        checkpoint_dir=tmp_path,
    )

    receipt = parsed["parser_receipt"]
    assert set(process_ids) == {os.getpid()}
    assert thread_ids
    assert receipt["execution_backend"] == "thread_pool"
    assert 1 <= receipt["peak_in_flight_fibres"] <= policy.workers
    assert receipt["fibre_count"] > policy.workers


def test_fibred_parse_replays_owned_sentences_without_a_merged_list(
    tmp_path: Path,
) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    parsed = parse_document_fibres(
        document_ref="document:streaming-carrier",
        canonical_text=text,
        parser=_parser_calls([]),
        policy=DocumentFibrePolicy(
            parser_limit_chars=100,
            target_chars=40,
            overlap_chars=5,
            workers=2,
        ),
        checkpoint_dir=tmp_path,
    )

    sentences = parsed["sents"]
    assert not isinstance(sentences, list)
    first = [
        (
            sentence["start"],
            sentence["end"],
            tuple(token["index"] for token in sentence["tokens"]),
        )
        for sentence in sentences
    ]
    second = [
        (
            sentence["start"],
            sentence["end"],
            tuple(token["index"] for token in sentence["tokens"]),
        )
        for sentence in sentences
    ]

    assert first == second
    assert len(first) == len(sentences)


def test_document_receipt_uses_compact_fibre_summaries(tmp_path: Path) -> None:
    text = ("Alpha beta gamma delta.\n\n" * 12).strip()
    parsed = parse_document_fibres(
        document_ref="document:summary-only",
        canonical_text=text,
        parser=_parser_calls([]),
        policy=DocumentFibrePolicy(
            parser_limit_chars=100, target_chars=40, overlap_chars=5, workers=2
        ),
        checkpoint_dir=tmp_path,
    )

    summaries = tuple(tmp_path.glob("*.summary.json"))
    checkpoints = tuple(tmp_path.glob("*.json"))
    assert len(summaries) == parsed["parser_receipt"]["fibre_count"]
    assert len(checkpoints) == len(summaries) * 2
    summary = summaries[0].read_text(encoding="utf-8")
    assert '"owned_sentence_count"' in summary
    assert '"parsed_document"' not in summary
