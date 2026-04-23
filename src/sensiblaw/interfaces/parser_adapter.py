from __future__ import annotations

"""Supported cross-product access to SL parser-first text helpers.

This module exposes the existing deterministic parser, transcript-header,
operational-structure, and pre-semantic normalization helpers through the
public ``sensiblaw.interfaces`` package so downstream consumers do not need
to import ``src.*`` modules directly.
"""

from typing import Any

from ._compat import install_src_package_aliases

install_src_package_aliases()

try:
    from src.nlp.spacy_adapter import parse as _parse_with_spacy
    from src.text.message_transcript import (
        MessageHeader,
        TimeRangeHeader,
        parse_message_header as _parse_message_header,
        parse_time_range_header as _parse_time_range_header,
    )
    from src.text.operational_structure import (
        StructureOccurrence,
        collect_operational_structure_occurrences as _collect_operational_structure_occurrences,
    )
    from src.text.shared_text_normalization import (
        split_semicolon_clauses as _split_semicolon_clauses,
        split_text_clauses as _split_text_clauses,
        split_text_segments as _split_text_segments,
        strip_enumeration_prefix as _strip_enumeration_prefix,
        tokenize_canonical_text as _tokenize_canonical_text,
    )
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    raise


def parse_canonical_text(text: str) -> dict[str, Any]:
    """Return deterministic sentence/token structure for canonical text."""

    return _parse_with_spacy(text)


def collect_canonical_operational_structure_occurrences(text: str) -> list[StructureOccurrence]:
    """Return deterministic operational/transcript structure occurrences."""

    return _collect_operational_structure_occurrences(text)


def parse_canonical_message_header(line: str) -> MessageHeader | None:
    """Parse a transcript/chat message header if one is present."""

    return _parse_message_header(line)


def parse_canonical_time_range_header(line: str) -> TimeRangeHeader | None:
    """Parse a transcript time-range header if one is present."""

    return _parse_time_range_header(line)


def tokenize_presemantic_text(text: str) -> frozenset[str]:
    """Return deterministic pre-semantic canonical tokens."""

    return _tokenize_canonical_text(text)


def split_presemantic_text_segments(text: str) -> list[str]:
    """Return deterministic sentence-like text segments."""

    return _split_text_segments(text)


def split_presemantic_text_clauses(text: str) -> list[str]:
    """Return deterministic clause-like segments."""

    return _split_text_clauses(text)


def split_presemantic_semicolon_clauses(text: str) -> list[str]:
    """Return deterministic semicolon-delimited clauses."""

    return _split_semicolon_clauses(text)


def strip_presemantic_enumeration_prefix(text: str) -> str:
    """Strip a leading enumeration prefix from text."""

    return _strip_enumeration_prefix(text)


__all__ = [
    "MessageHeader",
    "StructureOccurrence",
    "TimeRangeHeader",
    "collect_canonical_operational_structure_occurrences",
    "parse_canonical_message_header",
    "parse_canonical_text",
    "parse_canonical_time_range_header",
    "split_presemantic_semicolon_clauses",
    "split_presemantic_text_clauses",
    "split_presemantic_text_segments",
    "strip_presemantic_enumeration_prefix",
    "tokenize_presemantic_text",
]
