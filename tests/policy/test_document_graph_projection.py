from __future__ import annotations

import json
import re
import subprocess
import sys

from src.policy.document_graph_projection import (
    DOCUMENT_GRAPH_PROJECTION_CONTRACT,
    collect_document_relational_bundle,
)
from src.sensiblaw.interfaces.shared_reducer import (
    collect_canonical_relational_bundle,
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
    assert events[-1][1]["batch_index"] == events[-1][1]["total_batches"]


def test_operational_import_selects_graph_compilation_bridge() -> None:
    script = """
import json
from src.policy import operational_corpus_compilation as operational
print(json.dumps({
    'module': operational.legacy.__name__,
    'contract': operational.legacy.GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT,
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["module"] == "src.policy.graph_optimal_corpus_compilation"
    assert payload["contract"] == "document-graph-corpus-compilation-bridge:v0_1"
