from __future__ import annotations

from pathlib import Path
from typing import Any

from src.pnf.document_fibres import (
    DocumentFibrePolicy,
    build_document_structural_carrier,
    parse_document_fibres,
)


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
    assert second["parser_receipt"]["cross_fibre_fixed_point"][
        "semantic_object"
    ] == "document"
    assert second["parser_receipt"]["cross_fibre_fixed_point"][
        "fibre_semantic_authority"
    ] is False
