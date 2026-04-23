from __future__ import annotations

import importlib

from sensiblaw.interfaces import (
    collect_canonical_operational_structure_occurrences,
    parse_canonical_message_header,
    parse_canonical_text,
    parse_canonical_time_range_header,
    split_presemantic_semicolon_clauses,
    split_presemantic_text_clauses,
    split_presemantic_text_segments,
    strip_presemantic_enumeration_prefix,
    tokenize_presemantic_text,
)
from src.nlp.spacy_adapter import parse as parse_internal
from src.text.message_transcript import (
    parse_message_header as parse_internal_message_header,
    parse_time_range_header as parse_internal_time_range_header,
)
from src.text.operational_structure import collect_operational_structure_occurrences
from src.text.shared_text_normalization import (
    split_semicolon_clauses,
    split_text_clauses,
    split_text_segments,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)


def test_public_interfaces_package_import_exposes_parser_boundary() -> None:
    imported = importlib.import_module("sensiblaw.interfaces")

    assert imported.parse_canonical_text is parse_canonical_text
    assert imported.collect_canonical_operational_structure_occurrences is collect_canonical_operational_structure_occurrences


def test_parser_adapter_matches_internal_spacy_parse_contract() -> None:
    text = "This is a test. Here's another sentence!"
    assert parse_canonical_text(text) == parse_internal(text)


def test_parser_adapter_matches_internal_operational_structure_contract() -> None:
    text = "User: please run this.\n$ pytest SensibLaw/tests/test_lexeme_layer.py -q\n"
    assert collect_canonical_operational_structure_occurrences(text) == collect_operational_structure_occurrences(text)


def test_parser_adapter_matches_internal_message_header_contract() -> None:
    line = "1/1/21, 10:00 AM - Alice: Happy New Year!"
    assert parse_canonical_message_header(line) == parse_internal_message_header(line)


def test_parser_adapter_matches_internal_time_range_header_contract() -> None:
    line = "[00:00:00,030 -> 00:00:21,970] Thanks."
    assert parse_canonical_time_range_header(line) == parse_internal_time_range_header(line)


def test_parser_adapter_matches_internal_presemantic_normalization_contract() -> None:
    text = "The organisation emphasised that I was there."
    assert tokenize_presemantic_text(text) == tokenize_canonical_text(text)
    assert strip_presemantic_enumeration_prefix("  2.1) The respondent cut off my internet") == strip_enumeration_prefix(
        "  2.1) The respondent cut off my internet"
    )
    assert split_presemantic_text_segments("First sentence. Second sentence!") == split_text_segments(
        "First sentence. Second sentence!"
    )
    assert split_presemantic_text_clauses(
        "I opened the gate, but he stayed outside; I then called."
    ) == split_text_clauses("I opened the gate, but he stayed outside; I then called.")
    assert split_presemantic_semicolon_clauses("one; two ; three") == split_semicolon_clauses("one; two ; three")
