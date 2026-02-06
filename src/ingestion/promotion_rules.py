from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from src.models.document import Document
from src.models.promotion import PromotionCandidate, PromotionReceipt
from src.models.span_role_hypothesis import SpanRoleHypothesis
from src.models.span_signal_hypothesis import SpanSignalHypothesis

_MODAL_PATTERN = re.compile(r"\b(must not|must|may|shall|is liable to|is guilty of)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PromotionConfig:
    min_repetition: int = 3
    min_separation_tokens: int = 50
    modal_window_tokens: int = 40
    char_per_token_estimate: int = 4

    def min_separation_chars(self) -> int:
        return self.min_separation_tokens * self.char_per_token_estimate

    def modal_window_chars(self) -> int:
        return self.modal_window_tokens * self.char_per_token_estimate


def evaluate_promotions(
    document: Document,
    role_hypotheses: Sequence[SpanRoleHypothesis],
    signal_hypotheses: Sequence[SpanSignalHypothesis] | None = None,
    *,
    config: PromotionConfig | None = None,
) -> tuple[List[PromotionCandidate], List[PromotionReceipt]]:
    """Evaluate promotion gates for span role hypotheses."""

    config = config or PromotionConfig()
    signal_hypotheses = list(signal_hypotheses or [])
    candidates: List[PromotionCandidate] = []
    receipts: List[PromotionReceipt] = []

    ordered = sorted(
        role_hypotheses,
        key=lambda item: (
            item.span_start,
            item.span_end,
            item.role_hypothesis or "",
        ),
    )

    normalized_labels = _build_normalized_labels(document, ordered)
    repeated_labels = _find_repeated_labels(ordered, normalized_labels, config)

    for index, hypothesis in enumerate(ordered, start=1):
        hypothesis_record = hypothesis.to_record()
        if hypothesis_record.get("span_id") is None:
            hypothesis_record["span_id"] = index
        label = normalized_labels.get(id(hypothesis), "")
        if not label:
            receipts.append(
                PromotionReceipt(
                    gate_id="no_label",
                    status="rejected",
                    reason="missing_label",
                    hypothesis=hypothesis_record,
                    evidence={},
                )
            )
            continue

        blocked = _is_blocked_by_signal(hypothesis, signal_hypotheses)
        if blocked:
            receipts.append(
                PromotionReceipt(
                    gate_id="signal_block",
                    status="blocked",
                    reason="signal_overlap",
                    hypothesis=hypothesis_record,
                    evidence={"signals": [sig.to_record() for sig in blocked]},
                )
            )
            continue

        if hypothesis.role_hypothesis == "defined_term":
            candidates.append(
                PromotionCandidate(
                    normalized_label=label,
                    gate_id="defined_term",
                    hypothesis=hypothesis,
                )
            )
            receipts.append(
                PromotionReceipt(
                    gate_id="defined_term",
                    status="promoted",
                    reason="gate_passed",
                    hypothesis=hypothesis_record,
                    evidence={"label": label},
                )
            )
            continue

        if label in repeated_labels:
            candidates.append(
                PromotionCandidate(
                    normalized_label=label,
                    gate_id="repetition",
                    hypothesis=hypothesis,
                )
            )
            receipts.append(
                PromotionReceipt(
                    gate_id="repetition",
                    status="promoted",
                    reason="gate_passed",
                    hypothesis=hypothesis_record,
                    evidence={"label": label},
                )
            )
            continue

        if hypothesis.role_hypothesis in {"actor", "object", "construct"}:
            if _has_modal_nearby(document, hypothesis, config):
                candidates.append(
                    PromotionCandidate(
                        normalized_label=label,
                        gate_id="modal_participation",
                        hypothesis=hypothesis,
                    )
                )
                receipts.append(
                    PromotionReceipt(
                        gate_id="modal_participation",
                        status="promoted",
                        reason="gate_passed",
                        hypothesis=hypothesis_record,
                        evidence={"label": label},
                    )
                )
                continue

        receipts.append(
            PromotionReceipt(
                gate_id="no_gate",
                status="rejected",
                reason="no_gate_matched",
                hypothesis=hypothesis_record,
                evidence={"label": label},
            )
        )

    return candidates, receipts


def _build_normalized_labels(
    document: Document, hypotheses: Iterable[SpanRoleHypothesis]
) -> dict[int, str]:
    labels: dict[int, str] = {}
    for hypothesis in hypotheses:
        text = _span_text(document, hypothesis)
        if not text:
            continue
        labels[id(hypothesis)] = _normalize_label(text)
    return labels


def _span_source_for_document(document: Document) -> str:
    return document.metadata.canonical_id or document.metadata.citation or "unknown"


def _span_text(document: Document, hypothesis: SpanRoleHypothesis) -> str:
    if hypothesis.span_source != _span_source_for_document(document):
        return ""
    return document.body[hypothesis.span_start : hypothesis.span_end]


def _normalize_label(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _find_repeated_labels(
    hypotheses: Sequence[SpanRoleHypothesis],
    normalized_labels: dict[int, str],
    config: PromotionConfig,
) -> set[str]:
    label_positions: dict[str, List[int]] = {}
    for hypothesis in hypotheses:
        label = normalized_labels.get(id(hypothesis))
        if not label:
            continue
        label_positions.setdefault(label, []).append(hypothesis.span_start)

    repeated: set[str] = set()
    min_sep = config.min_separation_chars()
    for label, positions in label_positions.items():
        positions = sorted(positions)
        if len(positions) < config.min_repetition:
            continue
        far_enough = 0
        last_pos = None
        for pos in positions:
            if last_pos is None or pos - last_pos >= min_sep:
                far_enough += 1
                last_pos = pos
        if far_enough >= config.min_repetition:
            repeated.add(label)
    return repeated


def _has_modal_nearby(
    document: Document,
    hypothesis: SpanRoleHypothesis,
    config: PromotionConfig,
) -> bool:
    if hypothesis.span_source != _span_source_for_document(document):
        return False
    window = config.modal_window_chars()
    start = max(0, hypothesis.span_start - window)
    end = min(len(document.body), hypothesis.span_end + window)
    snippet = document.body[start:end]
    return bool(_MODAL_PATTERN.search(snippet))


def _is_blocked_by_signal(
    hypothesis: SpanRoleHypothesis,
    signal_hypotheses: Sequence[SpanSignalHypothesis],
) -> List[SpanSignalHypothesis]:
    blocked = []
    if not hypothesis.span_source:
        return blocked
    for signal in signal_hypotheses:
        if signal.span_source != hypothesis.span_source:
            continue
        if _overlaps(hypothesis.span_start, hypothesis.span_end, signal.span_start, signal.span_end):
            blocked.append(signal)
    return blocked


def _overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


__all__ = ["PromotionConfig", "evaluate_promotions"]
