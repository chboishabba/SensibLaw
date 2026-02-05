from __future__ import annotations

import re
from typing import Iterable, List

from src.models.document import Document
from src.models.span_role_hypothesis import SpanRoleHypothesis

_QUOTED_MEANS = re.compile(r'"(?P<lemma>[^"]{1,80})"\s+means\b', re.IGNORECASE)
_SMART_QUOTED_MEANS = re.compile(r"“(?P<lemma>[^”]{1,80})”\s+means\b", re.IGNORECASE)


def build_span_role_hypotheses(document: Document) -> List[SpanRoleHypothesis]:
    """Build deterministic span-only role hypotheses from a document body."""

    if not document.body:
        return []

    hypotheses: List[SpanRoleHypothesis] = []
    hypotheses.extend(_extract_defined_terms(document.body))

    return sorted(
        hypotheses,
        key=lambda item: (item.span_start, item.span_end, item.role_hypothesis or ""),
    )


def _extract_defined_terms(text: str) -> Iterable[SpanRoleHypothesis]:
    for pattern in (_QUOTED_MEANS, _SMART_QUOTED_MEANS):
        for match in pattern.finditer(text):
            term_start = match.start("lemma")
            term_end = match.end("lemma")
            yield SpanRoleHypothesis(
                span_start=term_start,
                span_end=term_end,
                span_source="body_char",
                role_hypothesis="defined_term",
                extractor="defined_term_regex",
                evidence="definition",
                confidence=0.9,
                metadata={"term_text": match.group("lemma")},
            )


__all__ = ["build_span_role_hypotheses"]
