from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.reporting.structure_report import TextUnit
from src.text.message_transcript import parse_message_header, parse_time_range_header


@dataclass(frozen=True, slots=True)
class SpeakerInferenceReceipt:
    unit_id: str
    source_id: str
    source_type: str
    observed_label: str | None
    inferred_speaker: str | None
    confidence: str
    reasons: tuple[str, ...]
    abstained: bool
    abstain_reason: str | None


def _norm_label(value: str) -> str:
    out: list[str] = []
    last_underscore = False
    for ch in value.casefold():
        if ch.isalnum():
            out.append(ch)
            last_underscore = False
        else:
            if not last_underscore:
                out.append("_")
                last_underscore = True
    return "".join(out).strip("_") or "unknown"


def _parse_bracketed_sender_prefix(text: str) -> str | None:
    if not text.startswith("["):
        return None
    close = text.find("]")
    if close <= 1:
        return None
    remainder = text[close + 1 :].lstrip()
    if ":" not in remainder:
        return None
    speaker = remainder.split(":", 1)[0].strip().strip("[]")
    if not speaker or len(speaker) > 120:
        return None
    return speaker


def infer_speakers(
    units: Iterable[TextUnit],
    *,
    known_participants_by_source: dict[str, list[str]] | None = None,
) -> list[SpeakerInferenceReceipt]:
    known_participants_by_source = known_participants_by_source or {}
    receipts: list[SpeakerInferenceReceipt] = []
    for unit in units:
        text = unit.text.strip()
        header = parse_message_header(text)
        if header is not None:
            speaker = header.speaker.strip()
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=speaker,
                    inferred_speaker=f"speaker:{_norm_label(speaker)}",
                    confidence="high",
                    reasons=("explicit_header",),
                    abstained=False,
                    abstain_reason=None,
                )
            )
            continue
        bracketed_speaker = _parse_bracketed_sender_prefix(text)
        if bracketed_speaker is not None:
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=bracketed_speaker,
                    inferred_speaker=f"speaker:{_norm_label(bracketed_speaker)}",
                    confidence="high",
                    reasons=("explicit_bracketed_sender",),
                    abstained=False,
                    abstain_reason=None,
                )
            )
            continue
        range_header = parse_time_range_header(text)
        if range_header is not None:
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=None,
                    inferred_speaker=None,
                    confidence="none",
                    reasons=("timing_range_only",),
                    abstained=True,
                    abstain_reason="timing_only",
                )
            )
            continue
        prefix = text.split(":", 1)[0].strip().casefold() if ":" in text else ""
        if prefix in {"user", "assistant", "system", "developer", "tool"}:
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=prefix,
                    inferred_speaker=f"role:{prefix}",
                    confidence="medium",
                    reasons=("explicit_role_prefix",),
                    abstained=False,
                    abstain_reason=None,
                )
            )
            continue
        participants = known_participants_by_source.get(unit.source_id, [])
        if prefix in {"q", "a"} and len(participants) >= 2:
            mapped = participants[0] if prefix == "q" else participants[1]
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=prefix,
                    inferred_speaker=f"speaker:{_norm_label(mapped)}",
                    confidence="low",
                    reasons=("qa_marker", "known_participants"),
                    abstained=False,
                    abstain_reason=None,
                )
            )
            continue
        if len(participants) == 1:
            mapped = participants[0]
            receipts.append(
                SpeakerInferenceReceipt(
                    unit_id=unit.unit_id,
                    source_id=unit.source_id,
                    source_type=unit.source_type,
                    observed_label=None,
                    inferred_speaker=f"speaker:{_norm_label(mapped)}",
                    confidence="low",
                    reasons=("single_known_participant",),
                    abstained=False,
                    abstain_reason=None,
                )
            )
            continue
        receipts.append(
            SpeakerInferenceReceipt(
                unit_id=unit.unit_id,
                source_id=unit.source_id,
                source_type=unit.source_type,
                observed_label=None,
                inferred_speaker=None,
                confidence="none",
                reasons=("insufficient_evidence",),
                abstained=True,
                abstain_reason="insufficient_evidence",
            )
        )
    return _coalesce_receipts(receipts)


def _coalesce_receipts(receipts: list[SpeakerInferenceReceipt]) -> list[SpeakerInferenceReceipt]:
    if len(receipts) < 3:
        return receipts
    updated = list(receipts)
    for index in range(1, len(updated) - 1):
        current = updated[index]
        previous = updated[index - 1]
        following = updated[index + 1]
        if not current.abstained or current.abstain_reason != "insufficient_evidence":
            continue
        if previous.source_id != current.source_id or following.source_id != current.source_id:
            continue
        if previous.abstained or following.abstained:
            continue
        if previous.inferred_speaker != following.inferred_speaker:
            continue
        if previous.inferred_speaker is None:
            continue
        updated[index] = SpeakerInferenceReceipt(
            unit_id=current.unit_id,
            source_id=current.source_id,
            source_type=current.source_type,
            observed_label=current.observed_label,
            inferred_speaker=previous.inferred_speaker,
            confidence="low",
            reasons=current.reasons + ("neighbor_consensus",),
            abstained=False,
            abstain_reason=None,
        )
    return updated
