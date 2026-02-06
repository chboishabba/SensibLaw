from __future__ import annotations

import re
from typing import Iterable, List

from src.models.span_signal_hypothesis import SpanSignalHypothesis

_LIST_MARKER_PATTERN = re.compile(
    r"(?m)^(?P<marker>\s*(?:[\u2022\u25aa\u25e6\-*]|\([a-z]\)|\([ivxlcdm]+\))\s+)",
    re.IGNORECASE,
)
_PUNCT_DAMAGE_PATTERN = re.compile(r"([;:,])\1{2,}|([!?])\2{2,}")
_PAGE_NUMBER_PATTERN = re.compile(r"(?m)^\s*\d{1,4}\s*$")
_ALL_CAPS_PATTERN = re.compile(r"\b[A-Z]{4,}\b")


def build_span_signal_hypotheses(text: str, *, span_source: str = "unknown") -> List[SpanSignalHypothesis]:
    """Build deterministic signal hypotheses from text spans."""

    if not text:
        return []

    hypotheses: List[SpanSignalHypothesis] = []
    hypotheses.extend(_extract_non_ascii(text, span_source))
    hypotheses.extend(_extract_encoding_loss(text, span_source))
    hypotheses.extend(_extract_list_markers(text, span_source))
    hypotheses.extend(_extract_punctuation_damage(text, span_source))
    hypotheses.extend(_extract_layout_artifacts(text, span_source))
    hypotheses.extend(_extract_visual_emphasis(text, span_source))

    return sorted(
        hypotheses,
        key=lambda item: (item.span_start, item.span_end, item.signal_type),
    )


def _extract_non_ascii(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for idx, char in enumerate(text):
        if char in {"\n", "\r", "\t"}:
            continue
        if ord(char) > 127:
            yield SpanSignalHypothesis(
                span_start=idx,
                span_end=idx + 1,
                span_source=span_source,
                signal_type="non_ascii_glyph",
                extractor="non_ascii_scan",
                evidence=char,
                confidence=0.6,
                metadata={"codepoint": ord(char)},
            )


def _extract_encoding_loss(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for match in re.finditer(r"\uFFFD", text):
        yield SpanSignalHypothesis(
            span_start=match.start(),
            span_end=match.end(),
            span_source=span_source,
            signal_type="encoding_loss",
            extractor="replacement_char_scan",
            evidence="\uFFFD",
            confidence=0.9,
        )


def _extract_list_markers(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for match in _LIST_MARKER_PATTERN.finditer(text):
        marker = match.group("marker")
        if not marker:
            continue
        start = match.start("marker")
        end = match.end("marker")
        yield SpanSignalHypothesis(
            span_start=start,
            span_end=end,
            span_source=span_source,
            signal_type="list_marker",
            extractor="list_marker_regex",
            evidence=marker.strip(),
            confidence=0.7,
        )


def _extract_punctuation_damage(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for match in _PUNCT_DAMAGE_PATTERN.finditer(text):
        yield SpanSignalHypothesis(
            span_start=match.start(),
            span_end=match.end(),
            span_source=span_source,
            signal_type="punctuation_damage",
            extractor="punctuation_repeat_regex",
            evidence=match.group(0),
            confidence=0.5,
        )


def _extract_layout_artifacts(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for match in _PAGE_NUMBER_PATTERN.finditer(text):
        yield SpanSignalHypothesis(
            span_start=match.start(),
            span_end=match.end(),
            span_source=span_source,
            signal_type="layout_artifact",
            extractor="page_number_line",
            evidence=match.group(0).strip(),
            confidence=0.6,
        )


def _extract_visual_emphasis(text: str, span_source: str) -> Iterable[SpanSignalHypothesis]:
    for match in _ALL_CAPS_PATTERN.finditer(text):
        token = match.group(0)
        if token.isnumeric():
            continue
        yield SpanSignalHypothesis(
            span_start=match.start(),
            span_end=match.end(),
            span_source=span_source,
            signal_type="visual_emphasis",
            extractor="all_caps_token",
            evidence=token,
            confidence=0.4,
        )


__all__ = ["build_span_signal_hypotheses"]
