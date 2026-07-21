from __future__ import annotations

from src.pnf.cached_parser import parse_with_stage_cache
from src.pnf.stage_cache import MemoryStageCache


def test_cached_parser_executes_once_for_same_stage_key() -> None:
    cache = MemoryStageCache()
    calls = 0

    def parser() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"sents": [], "parser_receipt": {"contract_ref": "spacy:v1"}}

    first, first_receipt = parse_with_stage_cache(
        document_ref="document:1",
        canonical_text_digest="text:1",
        parser_contract_ref="spacy:v1",
        parser=parser,
        cache=cache,
    )
    second, second_receipt = parse_with_stage_cache(
        document_ref="document:1",
        canonical_text_digest="text:1",
        parser_contract_ref="spacy:v1",
        parser=parser,
        cache=cache,
    )

    assert calls == 1
    assert first == second
    assert first_receipt.reused is False
    assert second_receipt.reused is True
    assert first_receipt.source_output_ref == second_receipt.source_output_ref
