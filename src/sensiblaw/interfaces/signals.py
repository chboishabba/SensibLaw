from __future__ import annotations

"""Public descriptive signal helpers built atop parser-first SL surfaces.

This module intentionally exposes only descriptive evidence. It does not
implement route selection, execution policy, or any Telegram-specific contract.
"""

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable

from .parser_adapter import (
    StructureOccurrence,
    collect_canonical_operational_structure_occurrences,
    parse_canonical_text,
)

SIGNAL_STATE_VERSION = "sl.signals.v1"

_WH_WORDS = {
    "what",
    "when",
    "where",
    "who",
    "whom",
    "whose",
    "why",
    "how",
    "which",
}
_AUX_STARTERS = {
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "would",
    "will",
    "should",
    "have",
    "has",
    "had",
}
_IMPERATIVE_STARTERS = {
    "ask",
    "check",
    "compare",
    "describe",
    "explain",
    "greet",
    "help",
    "list",
    "message",
    "reply",
    "run",
    "say",
    "send",
    "show",
    "summarize",
    "tell",
    "write",
}
_GREETING_WORDS = {
    "gm",
    "good morning",
    "good afternoon",
    "good evening",
    "hello",
    "hey",
    "hi",
    "yo",
}
_SECOND_PERSON = {"you", "your", "yours", "you're", "youre", "u"}
_GROUP_AUDIENCE = {"all", "everyone", "everybody", "folks", "team", "yall", "y'all"}
_TURN_PREFIXES = {"q", "a", "user", "assistant", "system", "developer", "tool"}
_EXPLICIT_ADDRESS_RE = re.compile(
    r"^\s*(?P<label>@?[A-Za-z][\w.-]{1,31})\s*,\s*(?P<rest>.+)$"
)
_TARGETED_OTHER_RE = re.compile(
    r"\b(?P<verb>say|tell|greet|message)\b(?P<body>.{0,80}?)\bto\s+(?P<target>@?[A-Za-z][\w.-]{1,31})\b",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class SignalSpan:
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class SignalAtom:
    signal_id: str
    family: str
    label: str
    value: str | bool | int | float
    confidence: float
    spans: tuple[SignalSpan, ...]
    provenance: tuple[str, ...]
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SignalState:
    version: str
    canonical_text: str
    families: dict[str, tuple[SignalAtom, ...]]


def _slug(value: str) -> str:
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


def _make_signal(
    *,
    family: str,
    label: str,
    value: str | bool | int | float,
    confidence: float,
    spans: Iterable[SignalSpan] = (),
    provenance: Iterable[str] = (),
    evidence: Iterable[str] = (),
) -> SignalAtom:
    span_tuple = tuple(spans)
    provenance_tuple = tuple(provenance)
    evidence_tuple = tuple(str(item) for item in evidence if str(item).strip())
    seed = "|".join(
        [
            family,
            label,
            str(value),
            f"{confidence:.4f}",
            ",".join(f"{span.start_char}:{span.end_char}" for span in span_tuple),
            ",".join(provenance_tuple),
            ",".join(evidence_tuple),
        ]
    )
    signal_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return SignalAtom(
        signal_id=signal_id,
        family=family,
        label=label,
        value=value,
        confidence=round(float(confidence), 4),
        spans=span_tuple,
        provenance=provenance_tuple,
        evidence=evidence_tuple,
    )


def _flatten_tokens(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    return [token for sentence in parsed.get("sents", ()) for token in sentence.get("tokens", ())]


def _question_like_tokens(tokens: list[dict[str, Any]]) -> list[SignalAtom]:
    atoms: list[SignalAtom] = []
    for token in tokens:
        text = str(token.get("text") or "")
        lowered = text.casefold()
        if text == "?":
            atoms.append(
                _make_signal(
                    family="interaction",
                    label="question_marker",
                    value=True,
                    confidence=1.0,
                    spans=(SignalSpan(int(token["start"]), int(token["end"])),),
                    provenance=("parsed:question_punctuation",),
                    evidence=(text,),
                )
            )
        elif lowered in _WH_WORDS:
            atoms.append(
                _make_signal(
                    family="interaction",
                    label="wh_interrogative",
                    value=lowered,
                    confidence=0.9,
                    spans=(SignalSpan(int(token["start"]), int(token["end"])),),
                    provenance=("parsed:wh_token",),
                    evidence=(text,),
                )
            )
    if tokens:
        first = tokens[0]
        first_text = str(first.get("text") or "").casefold()
        if first_text in _AUX_STARTERS:
            atoms.append(
                _make_signal(
                    family="interaction",
                    label="aux_interrogative",
                    value=first_text,
                    confidence=0.75,
                    spans=(SignalSpan(int(first["start"]), int(first["end"])),),
                    provenance=("parsed:aux_fronting",),
                    evidence=(str(first.get("text") or ""),),
                )
            )
    return atoms


def _imperative_like_tokens(
    text: str,
    parsed: dict[str, Any],
) -> list[SignalAtom]:
    atoms: list[SignalAtom] = []

    for sentence in parsed.get("sents", ()):
        sentence_tokens = [
            token
            for token in sentence.get("tokens", ())
            if str(token.get("text") or "").strip() and str(token.get("text") or "") not in {":", ",", ".", "!", "?"}
        ]
        if len(sentence_tokens) >= 2 and str(sentence_tokens[0].get("text") or "").casefold() in _TURN_PREFIXES:
            sentence_tokens = sentence_tokens[1:]
        if not sentence_tokens:
            continue
        first = sentence_tokens[0]
        first_text = str(first.get("text") or "")
        first_lower = first_text.casefold()
        if first_lower == "please":
            atoms.append(
                _make_signal(
                    family="interaction",
                    label="imperative_marker",
                    value="please",
                    confidence=0.9,
                    spans=(SignalSpan(int(first["start"]), int(first["end"])),),
                    provenance=("surface:please_prefix",),
                    evidence=(first_text,),
                )
            )
        elif first_lower in _IMPERATIVE_STARTERS:
            atoms.append(
                _make_signal(
                    family="interaction",
                    label="imperative_marker",
                    value=first_lower,
                    confidence=0.8,
                    spans=(SignalSpan(int(first["start"]), int(first["end"])),),
                    provenance=("surface:imperative_starter",),
                    evidence=(first_text,),
                )
            )

    explicit = _EXPLICIT_ADDRESS_RE.match(text)
    if explicit is not None:
        rest = explicit.group("rest")
        rest_start = explicit.start("rest")
        for match in re.finditer(r"[A-Za-z]+", rest):
            token_text = match.group(0)
            token_lower = token_text.casefold()
            if token_lower in {"can", "could", "would", "will"}:
                break
            if token_lower == "please" or token_lower in _IMPERATIVE_STARTERS:
                atoms.append(
                    _make_signal(
                        family="interaction",
                        label="imperative_marker",
                        value=token_lower,
                        confidence=0.85,
                        spans=(SignalSpan(rest_start + match.start(), rest_start + match.end()),),
                        provenance=("surface:explicit_address_imperative",),
                        evidence=(token_text,),
                    )
                )
                break
            break
    return atoms


def _extract_directness_signals(
    text: str,
    *,
    parsed: dict[str, Any],
) -> list[SignalAtom]:
    tokens = _flatten_tokens(parsed)
    atoms: list[SignalAtom] = []
    seen: set[tuple[str, int, int]] = set()

    for token in tokens:
        token_text = str(token.get("text") or "")
        lowered = token_text.casefold()
        if lowered in _SECOND_PERSON:
            key = ("second_person", int(token["start"]), int(token["end"]))
            if key in seen:
                continue
            seen.add(key)
            atoms.append(
                _make_signal(
                    family="directness",
                    label="second_person",
                    value=lowered,
                    confidence=0.7,
                    spans=(SignalSpan(int(token["start"]), int(token["end"])),),
                    provenance=("parsed:second_person",),
                    evidence=(token_text,),
                )
            )

    explicit = _EXPLICIT_ADDRESS_RE.match(text)
    if explicit is not None:
        label = explicit.group("label")
        start = explicit.start("label")
        end = explicit.end("label")
        atoms.append(
            _make_signal(
                family="directness",
                label="explicit_address",
                value=_slug(label),
                confidence=0.9,
                spans=(SignalSpan(start, end),),
                provenance=("surface:explicit_address",),
                evidence=(label,),
            )
        )

    target = _TARGETED_OTHER_RE.search(text)
    if target is not None:
        verb = target.group("verb").casefold()
        atoms.append(
            _make_signal(
                family="directness",
                label="speech_act_request",
                value=verb,
                confidence=0.85,
                spans=(SignalSpan(target.start("verb"), target.end("verb")),),
                provenance=("surface:speech_act_request",),
                evidence=(target.group("verb"),),
            )
        )

    return atoms


def _extract_audience_signals(
    text: str,
    *,
    parsed: dict[str, Any],
    directness_atoms: list[SignalAtom],
) -> list[SignalAtom]:
    tokens = _flatten_tokens(parsed)
    atoms: list[SignalAtom] = []
    lowered_tokens = [str(token.get("text") or "").casefold() for token in tokens]
    group_hits = [token for token in tokens if str(token.get("text") or "").casefold() in _GROUP_AUDIENCE]
    if group_hits:
        atoms.append(
            _make_signal(
                family="audience",
                label="group_addressable",
                value=True,
                confidence=0.85,
                spans=tuple(SignalSpan(int(token["start"]), int(token["end"])) for token in group_hits),
                provenance=("parsed:group_audience",),
                evidence=tuple(str(token.get("text") or "") for token in group_hits),
            )
        )

    target = _TARGETED_OTHER_RE.search(text)
    if target is not None:
        atoms.append(
            _make_signal(
                family="audience",
                label="targeted_other",
                value=_slug(target.group("target")),
                confidence=0.9,
                spans=(SignalSpan(target.start("target"), target.end("target")),),
                provenance=("surface:target_recipient_pattern",),
                evidence=(target.group("target"),),
            )
        )

    has_single_recipient = any(atom.label in {"explicit_address", "second_person"} for atom in directness_atoms)
    has_group = any(atom.label == "group_addressable" for atom in atoms)
    if has_single_recipient and not has_group:
        spans = tuple(
            span
            for atom in directness_atoms
            if atom.label in {"explicit_address", "second_person"}
            for span in atom.spans
        )
        evidence = tuple(item for atom in directness_atoms if atom.label in {"explicit_address", "second_person"} for item in atom.evidence)
        atoms.append(
            _make_signal(
                family="audience",
                label="single_recipient",
                value=True,
                confidence=0.75,
                spans=spans,
                provenance=("derived:directness",),
                evidence=evidence,
            )
        )

    if not atoms and lowered_tokens:
        atoms.append(
            _make_signal(
                family="audience",
                label="broadcast_like",
                value=True,
                confidence=0.4,
                provenance=("derived:default_audience",),
            )
        )

    return atoms


def extract_interaction_signals(
    text: str,
    *,
    parsed: dict[str, Any] | None = None,
    structural_occurrences: list[StructureOccurrence] | None = None,
) -> list[SignalAtom]:
    """Emit descriptive interaction-mode evidence over canonical text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    parsed_payload = parsed if parsed is not None else parse_canonical_text(text)
    structures = (
        structural_occurrences
        if structural_occurrences is not None
        else collect_canonical_operational_structure_occurrences(text)
    )
    tokens = _flatten_tokens(parsed_payload)
    atoms: list[SignalAtom] = []
    atoms.extend(_question_like_tokens(tokens))
    atoms.extend(_imperative_like_tokens(text, parsed_payload))

    qa_atoms = [
        _make_signal(
            family="interaction",
            label="qa_turn",
            value=occ.norm_text,
            confidence=0.7,
            spans=(SignalSpan(occ.start_char, occ.end_char),),
            provenance=("structure:qa_ref",),
            evidence=(occ.text,),
        )
        for occ in structures
        if occ.kind == "qa_ref"
    ]
    atoms.extend(qa_atoms)

    directness_atoms = _extract_directness_signals(text, parsed=parsed_payload)
    explicit_address = any(atom.label == "explicit_address" for atom in directness_atoms)
    second_person = any(atom.label == "second_person" for atom in directness_atoms)
    question_like = any(atom.label in {"question_marker", "wh_interrogative", "aux_interrogative", "qa_turn"} for atom in atoms)
    imperative_like = any(atom.label == "imperative_marker" for atom in atoms)

    raw = text.strip()
    lowered = raw.casefold()
    greeting_only = lowered in _GREETING_WORDS or any(lowered.startswith(f"{value} ") for value in _GREETING_WORDS)

    mode_label = "statement"
    confidence = 0.55
    provenance = ["derived:interaction_mode"]
    evidence: list[str] = []
    spans: list[SignalSpan] = []

    if question_like and imperative_like:
        mode_label = "directed_request"
        confidence = 0.9
        evidence.append("question_plus_imperative")
    elif question_like and explicit_address:
        mode_label = "directed_request"
        confidence = 0.9
        evidence.append("question_plus_direct_address")
    elif imperative_like and explicit_address:
        mode_label = "directed_request"
        confidence = 0.9
        evidence.append("imperative_plus_direct_address")
    elif question_like:
        mode_label = "interrogative"
        confidence = 0.85
        evidence.append("question_like")
    elif imperative_like:
        mode_label = "imperative"
        confidence = 0.8
        evidence.append("imperative_like")
    elif greeting_only and not second_person:
        mode_label = "ambient"
        confidence = 0.7
        evidence.append("greeting_only")
    else:
        evidence.append("default_statement")
        if explicit_address or second_person:
            evidence.append("addressed_statement")

    for atom in atoms:
        if atom.label in {"question_marker", "wh_interrogative", "aux_interrogative", "imperative_marker", "qa_turn"}:
            spans.extend(atom.spans)
    for atom in directness_atoms:
        if atom.label == "explicit_address":
            spans.extend(atom.spans)

    atoms.append(
        _make_signal(
            family="interaction",
            label=mode_label,
            value=True,
            confidence=confidence,
            spans=spans,
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )
    )
    return atoms


def _extract_uncertainty_signals(
    *,
    interaction_atoms: list[SignalAtom],
    directness_atoms: list[SignalAtom],
) -> list[SignalAtom]:
    atoms: list[SignalAtom] = []
    question_like = any(atom.label in {"question_marker", "wh_interrogative", "aux_interrogative", "qa_turn"} for atom in interaction_atoms)
    imperative_like = any(atom.label == "imperative_marker" for atom in interaction_atoms)
    explicit_address = any(atom.label == "explicit_address" for atom in directness_atoms)
    projected_modes = {atom.label for atom in interaction_atoms if atom.label in {"ambient", "statement", "interrogative", "imperative", "directed_request"}}

    if question_like and imperative_like and not explicit_address:
        atoms.append(
            _make_signal(
                family="uncertainty",
                label="mixed_mode",
                value=True,
                confidence=0.75,
                provenance=("derived:mode_conflict",),
                evidence=("question_like", "imperative_like"),
            )
        )

    if projected_modes == {"statement"} and not directness_atoms:
        atoms.append(
            _make_signal(
                family="uncertainty",
                label="low_evidence",
                value=True,
                confidence=0.6,
                provenance=("derived:low_signal_density",),
                evidence=("statement_only",),
            )
        )

    if len(projected_modes) > 1:
        atoms.append(
            _make_signal(
                family="uncertainty",
                label="ambiguous_mode",
                value=True,
                confidence=0.7,
                provenance=("derived:multiple_projected_modes",),
                evidence=tuple(sorted(projected_modes)),
            )
        )

    return atoms


def collect_signal_state(
    text: str,
    *,
    include_families: tuple[str, ...] = ("interaction",),
    parsed: dict[str, Any] | None = None,
    structural_occurrences: list[StructureOccurrence] | None = None,
) -> SignalState:
    """Collect a grouped descriptive signal state over canonical text."""

    normalized_families = tuple(dict.fromkeys(include_families))
    parsed_payload = parsed if parsed is not None else parse_canonical_text(text)
    structures = (
        structural_occurrences
        if structural_occurrences is not None
        else collect_canonical_operational_structure_occurrences(text)
    )

    families: dict[str, tuple[SignalAtom, ...]] = {}
    interaction_atoms: list[SignalAtom] = []
    directness_atoms: list[SignalAtom] = []

    if "interaction" in normalized_families:
        interaction_atoms = extract_interaction_signals(
            text,
            parsed=parsed_payload,
            structural_occurrences=structures,
        )
        families["interaction"] = tuple(interaction_atoms)

    if "directness" in normalized_families or "audience" in normalized_families or "uncertainty" in normalized_families:
        directness_atoms = _extract_directness_signals(text, parsed=parsed_payload)
        if "directness" in normalized_families:
            families["directness"] = tuple(directness_atoms)

    if "audience" in normalized_families:
        families["audience"] = tuple(
            _extract_audience_signals(
                text,
                parsed=parsed_payload,
                directness_atoms=directness_atoms,
            )
        )

    if "uncertainty" in normalized_families:
        families["uncertainty"] = tuple(
            _extract_uncertainty_signals(
                interaction_atoms=interaction_atoms,
                directness_atoms=directness_atoms,
            )
        )

    return SignalState(
        version=SIGNAL_STATE_VERSION,
        canonical_text=text,
        families=families,
    )


def summarize_signal_state(state: SignalState) -> dict[str, list[str]]:
    """Return a compact summary projection of grouped signal labels."""

    summary: dict[str, list[str]] = {}
    for family, atoms in state.families.items():
        labels: list[str] = []
        seen: set[str] = set()
        for atom in atoms:
            if atom.label not in seen:
                labels.append(atom.label)
                seen.add(atom.label)
        summary[family] = labels
    return summary


__all__ = [
    "SIGNAL_STATE_VERSION",
    "SignalAtom",
    "SignalSpan",
    "SignalState",
    "collect_signal_state",
    "extract_interaction_signals",
    "summarize_signal_state",
]
