from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans

from .wiki_lexical import (
    build_revision_comment_zelph_facts,
    classify_revision_comment,
    parse_revision_statement,
    revision_node_id,
)


@dataclass(frozen=True, slots=True)
class LexicalProjection:
    pack_names: tuple[str, ...]
    facts: tuple[str, ...]
    signal_classes: tuple[str, ...]
    source_signal_classes: tuple[str, ...]
    metadata: Mapping[str, Any]


_CHAT_ARCHIVE_SOURCE_TYPES = {
    "chat_archive_sample",
    "facebook_messages_archive_sample",
    "openrecall_capture",
}
_TRANSCRIPT_SOURCE_TYPES = {
    "transcript_file",
    "interview_note",
    "support_worker_note",
    "annotation_note",
    "editor_note",
    "professional_note",
    "professional_interpretation",
}
_AU_SOURCE_TYPES = {
    "judgment_extract",
    "timeline_payload",
    "legal_record",
}

_UNCERTAINTY_TOKENS = {"maybe", "might", "unclear", "unsure", "approximately", "possibly"}
_SEQUENCE_TOKENS = {"before", "after", "then", "later", "earlier", "next", "followup", "follow-up"}
_EXECUTION_TOKENS = {"todo", "run", "execute", "check", "verify", "follow", "handoff", "next"}
_CORRECTION_TOKENS = {"actually", "correction", "corrected", "update", "updated", "sorry", "revised"}
_APPEAL_TOKENS = {"appeal", "appealed", "appellate", "appellant"}
_PROCEDURAL_TOKENS = {"held", "ruled", "ordered", "judgment", "court", "tribunal", "hearing"}
_ASSERTION_TOKENS = {"alleged", "allegation", "claimed", "claim", "denied", "denial"}
_HANDOFF_TOKENS = {"handoff", "escalate", "escalated", "support", "worker", "professional", "note"}


def _quote_zelph_text(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _token_texts(text: str) -> list[str]:
    return [token for token, _start, _end in tokenize_canonical_with_spans(text)]


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if str(value).strip()))


def _surface_node(kind: str, identifier: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", identifier.strip() or "unknown")
    return f"{kind}_{safe}"


def _build_surface_lexical_facts(*, parent_node: str, kind: str, identifier: str, text: str) -> list[str]:
    tokens = _token_texts(text)
    node = _surface_node(kind, identifier)
    facts = [
        f'{_quote_zelph_text(parent_node)} "has lexical surface" {_quote_zelph_text(node)}.',
        f'{_quote_zelph_text(node)} "surface kind" {_quote_zelph_text(kind)}.',
        f'{_quote_zelph_text(node)} "surface text" {_quote_zelph_text(text)}.',
    ]
    for token in tokens:
        facts.append(f'{_quote_zelph_text(node)} "has lexeme" {_quote_zelph_text(token.casefold())}.')
    return facts


def _projection_mode(fact: Mapping[str, Any]) -> str | None:
    mode = str(fact.get("lexical_projection_mode") or "").strip()
    return mode or None


def _source_types(fact: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in fact.get("source_types", []) if str(value).strip()}


def _statement_roles(fact: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in fact.get("statement_roles", []) if str(value).strip()}


def _source_signal_classes(fact: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in fact.get("source_signal_classes", []) if str(value).strip()}


def _wiki_projection(fact: Mapping[str, Any]) -> LexicalProjection:
    facts: list[str] = []
    signal_classes: list[str] = []
    source_signal_classes: list[str] = []
    revision_count = 0
    for index, statement_text in enumerate(fact.get("statement_texts", []), start=1):
        parsed = parse_revision_statement(str(statement_text))
        if not parsed:
            continue
        revision_count += 1
        revision_id = f"{fact.get('fact_id')}_{index}"
        revision_node = revision_node_id(revision_id)
        fact_node = _surface_node("fact", str(fact.get("fact_id") or "unknown"))
        facts.append(f'{_quote_zelph_text(fact_node)} "has revision comment" {_quote_zelph_text(revision_node)}.')
        facts.extend(
            build_revision_comment_zelph_facts(
                revision_id=revision_id,
                author=parsed["author"],
                comment_text=parsed["comment"],
            )
        )
        signal_classes.extend(classify_revision_comment(parsed["comment"]))
    if revision_count:
        source_signal_classes.extend(["public_summary", "wiki_article"])
    return LexicalProjection(
        pack_names=("wiki_revision",) if revision_count else (),
        facts=_dedupe(facts),
        signal_classes=_dedupe(signal_classes),
        source_signal_classes=_dedupe(source_signal_classes),
        metadata={"revision_comment_count": revision_count},
    )


def _chat_archive_projection(fact: Mapping[str, Any]) -> LexicalProjection:
    facts: list[str] = []
    signal_classes: list[str] = []
    surfaces = 0
    fact_node = _surface_node("fact", str(fact.get("fact_id") or "unknown"))
    for index, statement_text in enumerate(fact.get("statement_texts", []), start=1):
        text = str(statement_text or "").strip()
        if not text:
            continue
        surfaces += 1
        facts.extend(
            _build_surface_lexical_facts(
                parent_node=fact_node,
                kind="chat_surface",
                identifier=f"{fact.get('fact_id')}_{index}",
                text=text,
            )
        )
        tokens = {token.casefold() for token in _token_texts(text)}
        if tokens & _UNCERTAINTY_TOKENS or "not sure" in text.casefold():
            signal_classes.append("uncertainty_preserved")
        if tokens & _SEQUENCE_TOKENS:
            signal_classes.append("sequence_signal")
        if tokens & _EXECUTION_TOKENS:
            signal_classes.append("execution_handoff_signal")
        if tokens & _CORRECTION_TOKENS:
            signal_classes.append("self_correction_signal")
    return LexicalProjection(
        pack_names=("chat_archive",) if surfaces else (),
        facts=_dedupe(facts),
        signal_classes=_dedupe(signal_classes),
        source_signal_classes=(),
        metadata={"archive_surface_count": surfaces},
    )


def _au_legal_projection(fact: Mapping[str, Any]) -> LexicalProjection:
    facts: list[str] = []
    signal_classes: list[str] = []
    surfaces = 0
    fact_node = _surface_node("fact", str(fact.get("fact_id") or "unknown"))
    for index, statement_text in enumerate(fact.get("statement_texts", []), start=1):
        text = str(statement_text or "").strip()
        if not text:
            continue
        surfaces += 1
        facts.extend(
            _build_surface_lexical_facts(
                parent_node=fact_node,
                kind="au_surface",
                identifier=f"{fact.get('fact_id')}_{index}",
                text=text,
            )
        )
        tokens = {token.casefold() for token in _token_texts(text)}
        if tokens & _APPEAL_TOKENS:
            signal_classes.append("appeal_stage_signal")
        if tokens & _PROCEDURAL_TOKENS:
            signal_classes.append("procedural_outcome")
        if tokens & _ASSERTION_TOKENS:
            signal_classes.append("party_assertion")
    return LexicalProjection(
        pack_names=("au_legal",) if surfaces else (),
        facts=_dedupe(facts),
        signal_classes=_dedupe(signal_classes),
        source_signal_classes=(),
        metadata={"au_surface_count": surfaces},
    )


def _transcript_handoff_projection(fact: Mapping[str, Any]) -> LexicalProjection:
    facts: list[str] = []
    signal_classes: list[str] = []
    surfaces = 0
    fact_node = _surface_node("fact", str(fact.get("fact_id") or "unknown"))
    for index, statement_text in enumerate(fact.get("statement_texts", []), start=1):
        text = str(statement_text or "").strip()
        if not text:
            continue
        surfaces += 1
        facts.extend(
            _build_surface_lexical_facts(
                parent_node=fact_node,
                kind="transcript_surface",
                identifier=f"{fact.get('fact_id')}_{index}",
                text=text,
            )
        )
        tokens = {token.casefold() for token in _token_texts(text)}
        if tokens & _UNCERTAINTY_TOKENS or "not sure" in text.casefold():
            signal_classes.append("uncertainty_preserved")
        if tokens & _SEQUENCE_TOKENS:
            signal_classes.append("sequence_signal")
        if tokens & _HANDOFF_TOKENS:
            signal_classes.append("handoff_context_signal")
        if "professional" in tokens or "clinician" in tokens:
            signal_classes.append("professional_handoff_signal")
    return LexicalProjection(
        pack_names=("transcript_handoff",) if surfaces else (),
        facts=_dedupe(facts),
        signal_classes=_dedupe(signal_classes),
        source_signal_classes=(),
        metadata={"transcript_surface_count": surfaces},
    )


def build_fact_lexical_projection(fact: Mapping[str, Any]) -> LexicalProjection:
    mode = _projection_mode(fact)
    source_types = _source_types(fact)
    statement_roles = _statement_roles(fact)
    source_signals = _source_signal_classes(fact)
    projections: list[LexicalProjection] = []

    if mode == "wiki_revision" or "wiki_article" in source_types:
        projections.append(_wiki_projection(fact))
    if mode == "chat_archive" or source_types & _CHAT_ARCHIVE_SOURCE_TYPES:
        projections.append(_chat_archive_projection(fact))
    if mode == "au_legal" or "au_timeline_statement" in statement_roles or source_types & _AU_SOURCE_TYPES:
        projections.append(_au_legal_projection(fact))
    if (
        mode == "transcript_handoff"
        or "transcript_statement" in statement_roles
        or source_types & _TRANSCRIPT_SOURCE_TYPES
        or source_signals & {"support_worker_note", "professional_note", "later_annotation"}
    ):
        projections.append(_transcript_handoff_projection(fact))

    pack_names: list[str] = []
    facts: list[str] = []
    signal_classes: list[str] = []
    source_signal_classes: list[str] = []
    metadata: dict[str, Any] = {"projection_mode": mode or "auto"}
    for projection in projections:
        pack_names.extend(projection.pack_names)
        facts.extend(projection.facts)
        signal_classes.extend(projection.signal_classes)
        source_signal_classes.extend(projection.source_signal_classes)
        metadata.update(projection.metadata)

    return LexicalProjection(
        pack_names=_dedupe(pack_names),
        facts=_dedupe(facts),
        signal_classes=_dedupe(signal_classes),
        source_signal_classes=_dedupe(source_signal_classes),
        metadata=metadata,
    )
