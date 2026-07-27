from __future__ import annotations

import copy
import json
import re
import subprocess
import sys

from src.policy import entity_resolution as mention_legacy
from src.policy.document_graph_mentions import (
    DOCUMENT_GRAPH_MENTION_CONTRACT,
    build_document_mention_licensing_carrier,
)
from src.policy.document_graph_projection import (
    DOCUMENT_GRAPH_PROJECTION_CONTRACT,
    collect_document_relational_bundle,
)
from src.sensiblaw.interfaces.shared_reducer import (
    collect_canonical_relational_bundle,
    tokenize_canonical_with_spans,
)


def _parsed_fixture(sentence_count: int = 8) -> tuple[str, dict]:
    sentence_texts = [
        f"Actor{index} builds system{index}{'?' if index == 3 else '.'}"
        for index in range(sentence_count)
    ]
    text = " ".join(sentence_texts)
    sentences = []
    cursor = 0
    token_index = 0
    for sentence_no, sentence_text in enumerate(sentence_texts):
        start = text.index(sentence_text, cursor)
        end = start + len(sentence_text)
        matches = list(re.finditer(r"[A-Za-z0-9]+|[?.]", sentence_text))
        indexes = list(range(token_index, token_index + len(matches)))
        verb_index = indexes[1]
        tokens = []
        for local_index, match in enumerate(matches):
            surface = match.group(0)
            index = indexes[local_index]
            if local_index == 0:
                pos, tag, dep, head = "PROPN", "NNP", "nsubj", verb_index
            elif local_index == 1:
                pos, tag, dep, head = "VERB", "VBZ", "ROOT", index
            elif local_index == 2:
                pos, tag, dep, head = "NOUN", "NN", "obj", verb_index
            else:
                pos, tag, dep, head = "PUNCT", ".", "punct", verb_index
            tokens.append(
                {
                    "index": index,
                    "text": surface,
                    "lemma": surface.casefold(),
                    "pos": pos,
                    "tag": tag,
                    "dep": dep,
                    "head_index": head,
                    "head_text": matches[1].group(0),
                    "start": start + match.start(),
                    "end": start + match.end(),
                    "morph": {},
                }
            )
        sentences.append(
            {
                "text": sentence_text,
                "start": start,
                "end": end,
                "tokens": tokens,
                "fibre_ref": f"fixture-fibre:{sentence_no}",
            }
        )
        token_index += len(matches)
        cursor = end
    return text, {
        "text": text,
        "sents": sentences,
        "parser_receipt": {
            "worker_count": 4,
            "partition_count": 4,
            "execution_mode": "fixture",
        },
    }


def _semantic_payload(bundle: dict) -> dict:
    return {
        "version": bundle["version"],
        "canonical_text": bundle["canonical_text"],
        "atoms": bundle["atoms"],
        "relations": bundle["relations"],
    }


def _mention_payload(carrier: dict) -> dict:
    return {
        key: value
        for key, value in carrier.items()
        if key != "licensing_execution_receipt"
    }


def test_parallel_mention_licensing_matches_serial_carrier() -> None:
    text, parsed = _parsed_fixture()
    tokens = tuple(tokenize_canonical_with_spans(text))
    serial = mention_legacy.build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:test",
        document_ref="document:test",
        parsed_document=parsed,
        tokens=tokens,
    )
    parallel = build_document_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:test",
        document_ref="document:test",
        parsed_document=parsed,
        tokens=tokens,
        worker_budget=4,
        partitions_per_worker=2,
        min_parallel_tokens=1,
        verify_serial=True,
    )

    assert _mention_payload(parallel) == serial
    receipt = parallel["licensing_execution_receipt"]
    assert receipt["contract_ref"] == DOCUMENT_GRAPH_MENTION_CONTRACT
    assert receipt["execution_mode"] == "process_token_fibres"
    assert receipt["requested_workers"] == 4
    assert receipt["granted_workers"] == 4
    assert receipt["budget_invariant_satisfied"] is True
    assert receipt["serial_parallel_parity"] is True
    assert receipt["semantic_fingerprint"] == receipt["serial_fingerprint"]
    assert receipt["worker_pids"]


def test_parallel_mention_licensing_preserves_non_token_aligned_parser_spans() -> None:
    text, parsed = _parsed_fixture()
    parsed = copy.deepcopy(parsed)
    first_sentence_tokens = parsed["sents"][0]["tokens"]
    first_sentence_tokens[1]["end"] = first_sentence_tokens[2]["end"]
    first_sentence_tokens[1]["text"] = text[
        first_sentence_tokens[1]["start"] : first_sentence_tokens[1]["end"]
    ]
    tokens = tuple(tokenize_canonical_with_spans(text))

    serial = mention_legacy.build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:test",
        document_ref="document:test",
        parsed_document=parsed,
        tokens=tokens,
    )
    parallel = build_document_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:test",
        document_ref="document:test",
        parsed_document=parsed,
        tokens=tokens,
        worker_budget=4,
        partitions_per_worker=2,
        min_parallel_tokens=1,
        verify_serial=True,
    )
    assert _mention_payload(parallel) == serial
    assert parallel["licensing_execution_receipt"]["serial_parallel_parity"] is True


def test_parallel_projection_matches_serial_document_payload() -> None:
    text, parsed = _parsed_fixture()
    serial = collect_canonical_relational_bundle(text, parsed_document=parsed)
    parallel = collect_document_relational_bundle(
        text,
        parsed_document=parsed,
        worker_budget=4,
        partitions_per_worker=2,
        min_parallel_sentences=2,
        verify_serial=True,
    )

    assert _semantic_payload(parallel) == _semantic_payload(serial)
    receipt = parallel["projection_receipt"]
    assert receipt["contract_ref"] == DOCUMENT_GRAPH_PROJECTION_CONTRACT
    assert receipt["execution_mode"] == "process_sentence_fibres"
    assert receipt["requested_workers"] == 4
    assert receipt["granted_workers"] == 4
    assert receipt["partition_count"] >= 4
    assert receipt["budget_invariant_satisfied"] is True
    assert receipt["peak_active_workers"] <= 4
    assert receipt["serial_parallel_parity"] is True
    assert receipt["semantic_fingerprint"] == receipt["serial_fingerprint"]
    assert receipt["worker_pids"]
    assert all("worker_pid" in row and "compute_ms" in row for row in receipt["partitions"])
    assert all(
        row["end_char"] - row["start_char"] < len(text)
        for row in receipt["partitions"]
    )


def test_projection_is_deterministic_across_worker_budgets() -> None:
    text, parsed = _parsed_fixture(12)
    payloads = []
    for worker_budget in (1, 2, 4):
        result = collect_document_relational_bundle(
            text,
            parsed_document=parsed,
            worker_budget=worker_budget,
            partitions_per_worker=2,
            min_parallel_sentences=2,
            verify_serial=worker_budget > 1,
        )
        payloads.append(_semantic_payload(result))
        assert result["projection_receipt"]["peak_active_workers"] <= worker_budget
    assert payloads[0] == payloads[1] == payloads[2]


def test_projection_progress_reports_partition_completion() -> None:
    text, parsed = _parsed_fixture()
    events = []
    collect_document_relational_bundle(
        text,
        parsed_document=parsed,
        worker_budget=2,
        partitions_per_worker=2,
        min_parallel_sentences=2,
        progress_callback=lambda event, payload: events.append((event, dict(payload))),
    )
    assert events
    assert events[-1][0] == "relational_bundle_progress"
    assert events[-1][1]["sentences_done"] == len(parsed["sents"])
    assert events[-1][1]["tokens_done"] == sum(
        len(sentence["tokens"]) for sentence in parsed["sents"]
    )
    assert events[-1][1]["words_done"] == sum(
        len(sentence["text"].split()) for sentence in parsed["sents"]
    )
    assert events[-1][1]["batch_index"] == events[-1][1]["total_batches"]


def test_tranche_import_order_selects_graph_compilation_proxy() -> None:
    script = """
import json
from src.policy.corpus_compilation import default_compiler_context
from src.policy import postgres_corpus_compilation as postgres
from src.policy import operational_corpus_compilation as operational
from src.policy import corpus_compilation as selected
print(json.dumps({
    'module': selected.__name__,
    'contract': selected.GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT,
    'operational_selected': operational.legacy is selected,
    'postgres_uses_operational': (
        postgres.compile_document_operational is operational.compile_document_operational
    ),
    'context_module': default_compiler_context.__module__,
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["module"] == "src.policy.corpus_compilation"
    assert payload["contract"] == "document-graph-corpus-compilation-bridge:v0_2"
    assert payload["operational_selected"] is True
    assert payload["postgres_uses_operational"] is True
    assert payload["context_module"] == "src.policy.corpus_compilation"


def test_compiler_proxy_forwards_monkeypatches(monkeypatch) -> None:
    from src.policy import corpus_compilation as selected

    def injected_parser(text: str):
        return {"text": text, "sents": []}

    monkeypatch.setattr(selected, "parse_canonical_text", injected_parser)
    assert selected.parse_canonical_text is injected_parser
    assert selected._proxy_legacy.parse_canonical_text is injected_parser
    assert selected.build_mention_licensing_carrier is not (
        selected._proxy_legacy.build_mention_licensing_carrier
    )
    assert selected._semantic_annotation_layer is not (
        selected._proxy_legacy._semantic_annotation_layer
    )
