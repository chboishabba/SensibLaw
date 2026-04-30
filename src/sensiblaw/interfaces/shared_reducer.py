from __future__ import annotations

"""Supported cross-product access to SL canonical lexer/reducer outputs."""

from dataclasses import dataclass
import hashlib
import re
import time
from typing import Any

from ._compat import install_src_package_aliases

install_src_package_aliases()

try:
    from src.text.deterministic_legal_tokenizer import (
        LexemeToken,
        tokenize_detailed,
        tokenize_with_spans,
    )
    from src.text.lexeme_index import (
        LexemeOccurrence,
        LexemeTokenizerProfile,
        collect_lexeme_occurrences,
        collect_lexeme_occurrences_with_profile,
        get_tokenizer_profile,
    )
    from src.text.operational_structure import StructureOccurrence, collect_operational_structure_occurrences
    from src.text.structure_index import collect_structure_occurrences
    from src.text.residual_lattice import (
        CandidateResidual,
        PredicateIndex,
        PredicatePNF,
        PredicateAtom,
        QualifierState,
        Residual,
        ResidualLevel,
        RoleState,
        TypedArg,
        WrapperState,
        coerce_predicate_atom,
        comparable,
        build_predicate_index,
        build_predicate_ref_map,
        collect_candidate_predicate_refs,
        collect_candidate_residuals,
        compute_indexed_residual,
        compute_residual,
        join_role_states,
        join_residual,
        join_typed_args,
        meet_atom,
    )
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from text.deterministic_legal_tokenizer import (
        LexemeToken,
        tokenize_detailed,
        tokenize_with_spans,
    )
    from text.lexeme_index import (
        LexemeOccurrence,
        LexemeTokenizerProfile,
        collect_lexeme_occurrences,
        collect_lexeme_occurrences_with_profile,
        get_tokenizer_profile,
    )
    from text.operational_structure import StructureOccurrence, collect_operational_structure_occurrences
    from text.structure_index import collect_structure_occurrences
    from text.residual_lattice import (
        CandidateResidual,
        PredicateIndex,
        PredicatePNF,
        PredicateAtom,
        QualifierState,
        Residual,
        ResidualLevel,
        RoleState,
        TypedArg,
        WrapperState,
        coerce_predicate_atom,
        comparable,
        build_predicate_index,
        build_predicate_ref_map,
        collect_candidate_predicate_refs,
        collect_candidate_residuals,
        compute_indexed_residual,
        compute_residual,
        join_role_states,
        join_residual,
        join_typed_args,
        meet_atom,
    )
try:
    from src.text.sentences import segment_sentences
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from text.sentences import segment_sentences
try:
    from src.ingestion.media_adapter import CanonicalUnit
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from ingestion.media_adapter import CanonicalUnit
try:
    from src.nlp.spacy_adapter import parse as parse_with_spacy
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    raise


_YEAR_RE = re.compile(r"^\d{4}$")
_RELATIONAL_BUNDLE_BATCH_MAX_SENTENCES = 32
_RELATIONAL_BUNDLE_BATCH_MAX_CHARS = 8192


@dataclass(frozen=True, slots=True)
class RelationalAtom:
    atom_id: str
    text: str
    span_start: int
    span_end: int


def _dedupe_relation_key(relation: dict[str, Any]) -> tuple[Any, ...]:
    parts: list[Any] = [relation["type"]]
    for role in relation["roles"]:
        parts.append((role["role"], role.get("atom"), role.get("value")))
    return tuple(parts)


def _detect_question_span(parsed: dict[str, Any]) -> tuple[bool, tuple[int, int] | None]:
    for sentence in parsed.get("sents", ()):
        tokens = sentence.get("tokens", ())
        if any(token["text"] == "?" for token in tokens):
            question_mark = next(token for token in tokens if token["text"] == "?")
            return True, (question_mark["start"], question_mark["end"])

        token_by_index = {token["index"]: token for token in tokens}
        for token in tokens:
            if token.get("tag") in {"WP", "WRB", "WDT"}:
                return True, (token["start"], token["end"])
            if token["dep"] == "aux":
                head = token_by_index.get(token["head_index"])
                if head is not None and head["pos"] in {"VERB", "AUX"} and token["index"] < head["index"]:
                    return True, (token["start"], token["end"])

    return False, None


def _iter_sentence_batches(text: str) -> list[dict[str, Any]]:
    sentences = segment_sentences(text)
    if not sentences:
        return []

    batches: list[dict[str, Any]] = []
    batch_start_index = 0
    while batch_start_index < len(sentences):
        batch_end_index = batch_start_index
        batch_start_char = sentences[batch_start_index].start_char
        batch_end_char = sentences[batch_start_index].end_char
        while batch_end_index + 1 < len(sentences):
            candidate = sentences[batch_end_index + 1]
            candidate_count = (batch_end_index + 1) - batch_start_index + 1
            candidate_end_char = candidate.end_char
            candidate_chars = candidate_end_char - batch_start_char
            if candidate_count > _RELATIONAL_BUNDLE_BATCH_MAX_SENTENCES:
                break
            if candidate_chars > _RELATIONAL_BUNDLE_BATCH_MAX_CHARS:
                break
            batch_end_index += 1
            batch_end_char = candidate_end_char
        batches.append(
            {
                "text": text[batch_start_char:batch_end_char],
                "start_char": batch_start_char,
                "end_char": batch_end_char,
                "sentences": sentences[batch_start_index : batch_end_index + 1],
            }
        )
        batch_start_index = batch_end_index + 1
    return batches


def collect_canonical_relational_bundle(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    progress_callback=None,
) -> dict[str, Any]:
    """Emit a deterministic relation bundle over canonical text."""

    del canonical_mode  # reserved for future profile-routing parity
    sentence_batches = _iter_sentence_batches(text)
    total_sentences = sum(len(batch["sentences"]) for batch in sentence_batches)
    total_words = len([token for token in text.split() if token.strip()])

    atoms_by_key: dict[tuple[str, int, int], RelationalAtom] = {}
    relations: list[dict[str, Any]] = []
    relation_keys: set[tuple[Any, ...]] = set()

    def ensure_atom(token: dict[str, Any]) -> RelationalAtom:
        key = (token["text"], token["start"], token["end"])
        existing = atoms_by_key.get(key)
        if existing is not None:
            return existing
        atom = RelationalAtom(
            atom_id=f"a{len(atoms_by_key) + 1}",
            text=token["text"],
            span_start=key[1],
            span_end=key[2],
        )
        atoms_by_key[key] = atom
        return atom

    def append_relation(type_: str, roles: list[dict[str, str]]) -> None:
        relation = {
            "id": f"e{len(relations) + 1}",
            "type": type_,
            "roles": roles,
        }
        relation_key = _dedupe_relation_key(relation)
        if relation_key in relation_keys:
            return
        relation_keys.add(relation_key)
        relations.append(relation)

    nounish = {"NOUN", "PROPN", "PRON", "NUM"}
    predicate_deps = {"ROOT", "acl", "xcomp", "ccomp", "advcl"}
    object_deps = {"dobj", "obj", "attr", "oprd"}
    modifier_deps = {"compound", "amod", "nmod", "appos", "conj"}
    sentences_done = 0
    words_done = 0
    total_batches = len(sentence_batches)

    for batch_index, batch in enumerate(sentence_batches, start=1):
        batch_text = str(batch["text"])
        batch_start_char = int(batch["start_char"])
        parsed = parse_with_spacy(batch_text)
        sent_tokens: list[dict[str, Any]] = []
        for sentence in parsed.get("sents", ()):
            for token in sentence.get("tokens", ()):
                adjusted = dict(token)
                adjusted["start"] = int(token["start"]) + batch_start_char
                adjusted["end"] = int(token["end"]) + batch_start_char
                sent_tokens.append(adjusted)
        token_by_index = {token["index"]: token for token in sent_tokens}

        for token in sent_tokens:
            if token["dep"] in predicate_deps and token["pos"] in {"VERB", "AUX"}:
                children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"] and child["dep"] in object_deps and child["pos"] in nounish
                ]
                for child in children:
                    head_atom = ensure_atom(token)
                    argument_atom = ensure_atom(child)
                    append_relation(
                        "predicate",
                        [
                            {"role": "head", "atom": head_atom.atom_id},
                            {"role": "argument", "atom": argument_atom.atom_id},
                        ],
                    )

            if token["dep"] in modifier_deps:
                head = token_by_index.get(token["head_index"])
                if head is not None and head["pos"] in nounish:
                    head_atom = ensure_atom(head)
                    modifier_atom = ensure_atom(token)
                    append_relation(
                        "modifier",
                        [
                            {"role": "head", "atom": head_atom.atom_id},
                            {"role": "modifier", "atom": modifier_atom.atom_id},
                        ],
                    )

            if token["dep"] == "conj":
                head = token_by_index.get(token["head_index"])
                if head is not None:
                    head_atom = ensure_atom(head)
                    item_atom = ensure_atom(token)
                    append_relation(
                        "conjunction",
                        [
                            {"role": "item", "atom": head_atom.atom_id},
                            {"role": "item", "atom": item_atom.atom_id},
                        ],
                    )

            if token["dep"] in {"npadvmod", "tmod", "pobj"} and _YEAR_RE.match(token["text"]):
                anchor_atom = ensure_atom(token)
                append_relation(
                    "temporal",
                    [{"role": "anchor", "atom": anchor_atom.atom_id}],
                )

        is_question, question_span = _detect_question_span(parsed)
        if is_question:
            role: dict[str, Any] = {"role": "mode", "value": "question"}
            if question_span is not None:
                role["span_start"] = int(question_span[0]) + batch_start_char
                role["span_end"] = int(question_span[1]) + batch_start_char
            append_relation("composition", [role])

        sentences_done += len(batch["sentences"])
        words_done += len([token for token in batch_text.split() if token.strip()])
        if progress_callback is not None:
            progress_callback(
                "relational_bundle_progress",
                {
                    "batch_index": batch_index,
                    "total_batches": total_batches,
                    "sentences_done": sentences_done,
                    "total_sentences": total_sentences,
                    "words_done": words_done,
                    "total_words": total_words,
                    "atom_count": len(atoms_by_key),
                    "relation_count": len(relations),
                },
            )

    atoms = [
        {
            "id": atom.atom_id,
            "text": atom.text,
            "span": [atom.span_start, atom.span_end],
        }
        for atom in sorted(atoms_by_key.values(), key=lambda value: (value.span_start, value.span_end, value.atom_id))
    ]
    return {
        "version": "relational_bundle_v1",
        "canonical_text": text,
        "atoms": atoms,
        "relations": relations,
    }


def collect_canonical_predicate_atoms(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
) -> list[PredicateAtom]:
    """Expose bounded predicate-ready atoms derived from the shared reducer.

    This stays parser-first and reducer-first. It does not infer domains or
    semantic classes. It only projects explicit predicate relations and their
    attached modifier relations into the residual carrier.
    """

    bundle = collect_canonical_relational_bundle(text, canonical_mode=canonical_mode)
    return _collect_canonical_predicate_atoms_from_bundle(bundle)


def collect_canonical_predicate_pnfs(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
) -> list[PredicatePNF]:
    """Expose canonical predicate normal forms derived from the shared reducer."""

    bundle = collect_canonical_relational_bundle(text, canonical_mode=canonical_mode)
    return _collect_canonical_predicate_atoms_from_bundle(bundle)


def _body_qualified_unit_text(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
) -> str:
    body_units = [
        unit
        for unit in sorted(units, key=lambda item: (item.start_char, item.end_char, item.unit_id))
        if isinstance(unit, CanonicalUnit) and unit.metadata.get("body_qualified") is True and unit.text.strip()
    ]
    return "\n\n".join(unit.text.strip() for unit in body_units)


def collect_canonical_predicate_atoms_from_units(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
    *,
    canonical_mode: str = "deterministic_legal",
) -> list[PredicateAtom]:
    """Project predicate atoms only from body-qualified canonical units."""

    text = _body_qualified_unit_text(units)
    if not text:
        return []
    return collect_canonical_predicate_atoms(text, canonical_mode=canonical_mode)


def collect_canonical_predicate_pnfs_from_units(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
    *,
    canonical_mode: str = "deterministic_legal",
) -> list[PredicatePNF]:
    """Project predicate normal forms only from body-qualified canonical units."""

    text = _body_qualified_unit_text(units)
    if not text:
        return []
    return collect_canonical_predicate_pnfs(text, canonical_mode=canonical_mode)


def _collect_canonical_predicate_atoms_from_bundle(bundle: dict[str, Any]) -> list[PredicateAtom]:
    atoms_by_id = {
        str(atom["id"]): atom
        for atom in bundle.get("atoms", ())
        if isinstance(atom, dict) and atom.get("id") is not None
    }
    head_modifier_evidence: dict[str, tuple[dict[str, Any], ...]] = {}

    for relation in bundle.get("relations", ()):
        if not isinstance(relation, dict) or relation.get("type") != "modifier":
            continue
        head_id = None
        modifier_id = None
        for role in relation.get("roles", ()):
            if not isinstance(role, dict):
                continue
            if role.get("role") == "head" and role.get("atom") is not None:
                head_id = str(role["atom"])
            if role.get("role") == "modifier" and role.get("atom") is not None:
                modifier_id = str(role["atom"])
        if head_id is None or modifier_id is None:
            continue
        modifier_atom = atoms_by_id.get(modifier_id)
        if not isinstance(modifier_atom, dict):
            continue
        modifier_text = str(modifier_atom.get("text", "")).strip().lower()
        modifier_span = modifier_atom.get("span") or ()
        if not modifier_text or len(modifier_span) != 2:
            continue
        modifier_ref = f"mod:{modifier_span[0]}-{modifier_span[1]}"
        evidence_item = {
            "text": modifier_text,
            "span_start": int(modifier_span[0]),
            "span_end": int(modifier_span[1]),
            "provenance_ref": modifier_ref,
        }
        existing = head_modifier_evidence.get(head_id, ())
        if not any(
            item["text"] == evidence_item["text"]
            and item["span_start"] == evidence_item["span_start"]
            and item["span_end"] == evidence_item["span_end"]
            for item in existing
        ):
            head_modifier_evidence[head_id] = (*existing, evidence_item)

    predicate_atoms: list[PredicateAtom] = []
    for relation in bundle.get("relations", ()):
        if not isinstance(relation, dict) or relation.get("type") != "predicate":
            continue

        head_id = None
        argument_id = None
        for role in relation.get("roles", ()):
            if not isinstance(role, dict):
                continue
            if role.get("role") == "head" and role.get("atom") is not None:
                head_id = str(role["atom"])
            if role.get("role") == "argument" and role.get("atom") is not None:
                argument_id = str(role["atom"])

        if head_id is None or argument_id is None:
            continue

        head_atom = atoms_by_id.get(head_id)
        argument_atom = atoms_by_id.get(argument_id)
        if not isinstance(head_atom, dict) or not isinstance(argument_atom, dict):
            continue

        predicate = str(head_atom.get("text", "")).strip().lower()
        argument = str(argument_atom.get("text", "")).strip().lower()
        if not predicate or not argument:
            continue

        head_span = head_atom.get("span") or ()
        argument_span = argument_atom.get("span") or ()
        relation_id = str(relation.get("id", "")).strip() or None
        provenance_parts: list[str] = []
        if relation_id is not None:
            provenance_parts.append(relation_id)
        if len(head_span) == 2:
            provenance_parts.append(f"head:{head_span[0]}-{head_span[1]}")
        if len(argument_span) == 2:
            provenance_parts.append(f"arg:{argument_span[0]}-{argument_span[1]}")

        modifiers: dict[str, Any] = {}
        if head_id in head_modifier_evidence:
            modifier_evidence = head_modifier_evidence[head_id]
            modifiers["modifier_evidence"] = modifier_evidence
            for evidence_item in modifier_evidence:
                provenance_ref = str(evidence_item["provenance_ref"]).strip()
                if provenance_ref and provenance_ref not in provenance_parts:
                    provenance_parts.append(provenance_ref)

        argument_provenance = ()
        if len(argument_span) == 2:
            argument_provenance = (f"arg:{argument_span[0]}-{argument_span[1]}",)
        polarity = "negative" if any(
            item["text"] in {"not", "never", "no"}
            for item in modifiers.get("modifier_evidence", ())
        ) else "positive"
        typed_roles = {
            "argument": TypedArg(
                value=argument,
                provenance=argument_provenance,
                status="bound",
            )
        }
        predicate_atoms.append(
            PredicateAtom(
                predicate=predicate,
                structural_signature=predicate,
                roles=typed_roles,
                qualifiers=QualifierState(polarity=polarity),
                wrapper=WrapperState(status="structural_projection", evidence_only=True),
                modifiers=modifiers,
                provenance=tuple(provenance_parts),
                atom_id=relation_id,
            )
        )

    return predicate_atoms


def _predicate_atom_dict(atom: PredicateAtom) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "predicate": atom.predicate,
        "structural_signature": atom.structural_signature,
        "roles": {key: value.to_dict() for key, value in atom.roles.items()},
        "qualifiers": atom.qualifiers.to_dict(),
        "wrapper": atom.wrapper.to_dict(),
        "provenance": list(atom.provenance),
    }
    if atom.modifiers:
        payload["modifiers"] = dict(atom.modifiers)
    if atom.atom_id is not None:
        payload["atom_id"] = atom.atom_id
    return payload


def _structure_occurrence_ref(occurrence: StructureOccurrence) -> str:
    seed = "|".join(
        (
            occurrence.kind,
            occurrence.norm_text,
            str(occurrence.start_char),
            str(occurrence.end_char),
            str(occurrence.flags),
        )
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _structure_signal_atom(occurrence: StructureOccurrence) -> dict[str, Any]:
    provenance_ref = _structure_occurrence_ref(occurrence)
    return {
        "kind": occurrence.kind,
        "norm_text": occurrence.norm_text,
        "span_start": occurrence.start_char,
        "span_end": occurrence.end_char,
        "provenance_ref": provenance_ref,
    }


def _emit_structural_feed_progress(
    progress_callback,
    *,
    stage: str,
    started_at: float,
    completed_steps: int,
    total_steps: int,
    body_chars: int,
    predicate_atom_count: int | None = None,
    legal_signal_count: int | None = None,
    operational_signal_count: int | None = None,
    signal_atom_count: int | None = None,
    provenance_ref_count: int | None = None,
    work_unit: str | None = None,
    work_completed: int | None = None,
    work_total: int | None = None,
) -> None:
    if progress_callback is None:
        return
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    stage_fraction_complete = 0.0 if total_steps <= 0 else float(completed_steps) / float(total_steps)
    work_fraction_complete = None
    eta_seconds = None
    if work_unit is not None and work_completed is not None and work_total is not None and work_total > 0:
        work_fraction_complete = float(work_completed) / float(work_total)
        if 0.0 < work_fraction_complete < 1.0 and elapsed_seconds > 0:
            eta_seconds = round((elapsed_seconds / work_fraction_complete) - elapsed_seconds, 3)
    elif 0.0 < stage_fraction_complete < 1.0 and elapsed_seconds > 0:
        eta_seconds = round((elapsed_seconds / stage_fraction_complete) - elapsed_seconds, 3)
    progress_callback(
        "structural_feed_progress",
        {
            "stage": stage,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "stage_fraction_complete": round(stage_fraction_complete, 4),
            "work_fraction_complete": round(work_fraction_complete, 4) if work_fraction_complete is not None else None,
            "work_unit": work_unit,
            "work_completed": work_completed,
            "work_total": work_total,
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
            "body_chars": body_chars,
            "predicate_atom_count": predicate_atom_count,
            "legal_signal_count": legal_signal_count,
            "operational_signal_count": operational_signal_count,
            "signal_atom_count": signal_atom_count,
            "provenance_ref_count": provenance_ref_count,
        },
    )


def collect_canonical_structural_ir_feed(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    progress_callback=None,
) -> dict[str, Any]:
    """Emit a bounded structural IR feed for downstream consumer contracts.

    This stays reducer-first and provenance-aware. It exposes predicate atoms,
    structural signal atoms, and a small constraint receipt without assigning
    semantic authority to lexical overlap alone.
    """

    feed_started_at = time.monotonic()
    body_chars = len(text)
    total_steps = 6
    _emit_structural_feed_progress(
        progress_callback,
        stage="relational_bundle_started",
        started_at=feed_started_at,
        completed_steps=0,
        total_steps=total_steps,
        body_chars=body_chars,
    )
    def bundle_progress_callback(stage: str, details: dict[str, Any]) -> None:
        if stage != "relational_bundle_progress":
            return
        total_sentences = int(details.get("total_sentences") or 0)
        sentences_done = int(details.get("sentences_done") or 0)
        fraction_complete = 0.0
        if total_sentences > 0:
            fraction_complete = float(sentences_done) / float(total_sentences)
        bundle_elapsed_seconds = round(time.monotonic() - feed_started_at, 3)
        bundle_eta_seconds = None
        if fraction_complete > 0.0 and fraction_complete < 1.0 and bundle_elapsed_seconds > 0:
            bundle_eta_seconds = round((bundle_elapsed_seconds / fraction_complete) - bundle_elapsed_seconds, 3)
        progress_callback(
            "structural_feed_progress",
            {
                "stage": "relational_bundle_progress",
                "completed_steps": round(fraction_complete, 4),
                "total_steps": 1.0,
                "stage_fraction_complete": round(fraction_complete / float(total_steps), 4),
                "work_fraction_complete": round(
                    (float(details.get("words_done") or 0) / float(details.get("total_words") or 1)),
                    4,
                ) if int(details.get("total_words") or 0) > 0 else None,
                "work_unit": "words",
                "work_completed": int(details.get("words_done") or 0),
                "work_total": int(details.get("total_words") or 0),
                "elapsed_seconds": bundle_elapsed_seconds,
                "eta_seconds": bundle_eta_seconds,
                "body_chars": body_chars,
                "sentences_done": sentences_done,
                "total_sentences": total_sentences,
                "words_done": int(details.get("words_done") or 0),
                "total_words": int(details.get("total_words") or 0),
                "batch_index": int(details.get("batch_index") or 0),
                "total_batches": int(details.get("total_batches") or 0),
                "predicate_atom_count": None,
                "legal_signal_count": None,
                "operational_signal_count": None,
                "signal_atom_count": None,
                "provenance_ref_count": None,
                "relation_count": int(details.get("relation_count") or 0),
                "atom_count": int(details.get("atom_count") or 0),
            },
        )

    bundle = collect_canonical_relational_bundle(
        text,
        canonical_mode=canonical_mode,
        progress_callback=bundle_progress_callback if progress_callback is not None else None,
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="relational_bundle",
        started_at=feed_started_at,
        completed_steps=1,
        total_steps=total_steps,
        body_chars=body_chars,
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="predicate_projection_started",
        started_at=feed_started_at,
        completed_steps=1,
        total_steps=total_steps,
        body_chars=body_chars,
    )
    predicate_atoms = _collect_canonical_predicate_atoms_from_bundle(bundle)
    _emit_structural_feed_progress(
        progress_callback,
        stage="predicate_projection",
        started_at=feed_started_at,
        completed_steps=2,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="legal_structure_started",
        started_at=feed_started_at,
        completed_steps=2,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
    )
    legal_occurrences = tuple(collect_lexeme_occurrences(text, canonical_mode=canonical_mode))
    _emit_structural_feed_progress(
        progress_callback,
        stage="legal_structure",
        started_at=feed_started_at,
        completed_steps=3,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="operational_structure_started",
        started_at=feed_started_at,
        completed_steps=3,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
    )
    operational_occurrences = tuple(collect_operational_structure_occurrences(text))
    _emit_structural_feed_progress(
        progress_callback,
        stage="operational_structure",
        started_at=feed_started_at,
        completed_steps=4,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
        operational_signal_count=len(operational_occurrences),
    )
    deduped_occurrences: dict[tuple[str, str, int, int], StructureOccurrence] = {}
    for occurrence in (*legal_occurrences, *operational_occurrences):
        structure_occurrence = StructureOccurrence(
            text=occurrence.text,
            norm_text=occurrence.norm_text,
            kind=occurrence.kind,
            start_char=occurrence.start_char,
            end_char=occurrence.end_char,
            flags=occurrence.flags,
        )
        deduped_occurrences[
            (
                structure_occurrence.kind,
                structure_occurrence.norm_text,
                structure_occurrence.start_char,
                structure_occurrence.end_char,
            )
        ] = structure_occurrence
    structure_occurrences = sorted(
        deduped_occurrences.values(),
        key=lambda occurrence: (
            occurrence.start_char,
            occurrence.end_char,
            occurrence.kind,
            occurrence.norm_text,
        ),
    )
    tokenizer_receipt = get_canonical_tokenizer_profile_receipt()

    _emit_structural_feed_progress(
        progress_callback,
        stage="signal_projection_started",
        started_at=feed_started_at,
        completed_steps=4,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
        operational_signal_count=len(operational_occurrences),
    )
    signal_atoms: list[dict[str, Any]] = []
    total_signal_occurrences = len(structure_occurrences)
    for index, occurrence in enumerate(structure_occurrences, start=1):
        signal_atoms.append(_structure_signal_atom(occurrence))
        if (
            progress_callback is not None
            and (
                index == 1
                or index == total_signal_occurrences
                or index % 2048 == 0
            )
        ):
            _emit_structural_feed_progress(
                progress_callback,
                stage="signal_projection_progress",
                started_at=feed_started_at,
                completed_steps=5,
                total_steps=total_steps,
                body_chars=body_chars,
                predicate_atom_count=len(predicate_atoms),
                legal_signal_count=len(legal_occurrences),
                operational_signal_count=len(operational_occurrences),
                signal_atom_count=len(signal_atoms),
                work_unit="signal_atoms",
                work_completed=index,
                work_total=total_signal_occurrences,
            )
    _emit_structural_feed_progress(
        progress_callback,
        stage="signal_projection",
        started_at=feed_started_at,
        completed_steps=5,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
        operational_signal_count=len(operational_occurrences),
        signal_atom_count=len(signal_atoms),
        work_unit="signal_atoms",
        work_completed=len(signal_atoms),
        work_total=total_signal_occurrences,
    )
    provenance_refs: list[str] = []
    expected_provenance_upper_bound = sum(len(atom.provenance) for atom in predicate_atoms) + len(signal_atoms)
    provenance_seen = 0
    for atom in predicate_atoms:
        for provenance_ref in atom.provenance:
            ref = str(provenance_ref).strip()
            if ref and ref not in provenance_refs:
                provenance_refs.append(ref)
            provenance_seen += 1
            if (
                progress_callback is not None
                and expected_provenance_upper_bound > 0
                and (
                    provenance_seen == 1
                    or provenance_seen == expected_provenance_upper_bound
                    or provenance_seen % 2048 == 0
                )
            ):
                _emit_structural_feed_progress(
                    progress_callback,
                    stage="provenance_progress",
                    started_at=feed_started_at,
                    completed_steps=5,
                    total_steps=total_steps,
                    body_chars=body_chars,
                    predicate_atom_count=len(predicate_atoms),
                    legal_signal_count=len(legal_occurrences),
                    operational_signal_count=len(operational_occurrences),
                    signal_atom_count=len(signal_atoms),
                    provenance_ref_count=len(provenance_refs),
                    work_unit="provenance_refs",
                    work_completed=provenance_seen,
                    work_total=expected_provenance_upper_bound,
                )
    for signal in signal_atoms:
        ref = str(signal["provenance_ref"]).strip()
        if ref and ref not in provenance_refs:
            provenance_refs.append(ref)
        provenance_seen += 1
        if (
            progress_callback is not None
            and expected_provenance_upper_bound > 0
            and (
                provenance_seen == 1
                or provenance_seen == expected_provenance_upper_bound
                or provenance_seen % 2048 == 0
            )
        ):
            _emit_structural_feed_progress(
                progress_callback,
                stage="provenance_progress",
                started_at=feed_started_at,
                completed_steps=5,
                total_steps=total_steps,
                body_chars=body_chars,
                predicate_atom_count=len(predicate_atoms),
                legal_signal_count=len(legal_occurrences),
                operational_signal_count=len(operational_occurrences),
                signal_atom_count=len(signal_atoms),
                provenance_ref_count=len(provenance_refs),
                work_unit="provenance_refs",
                work_completed=provenance_seen,
                work_total=expected_provenance_upper_bound,
            )

    is_question = any(
        isinstance(relation, dict)
        and relation.get("type") == "composition"
        and any(
            isinstance(role, dict)
            and role.get("role") == "mode"
            and role.get("value") == "question"
            for role in relation.get("roles", ())
        )
        for relation in bundle.get("relations", ())
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="receipt_finalize_started",
        started_at=feed_started_at,
        completed_steps=5,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
        operational_signal_count=len(operational_occurrences),
        signal_atom_count=len(signal_atoms),
        provenance_ref_count=len(provenance_refs),
        work_unit="provenance_refs",
        work_completed=expected_provenance_upper_bound,
        work_total=expected_provenance_upper_bound,
    )
    _emit_structural_feed_progress(
        progress_callback,
        stage="receipt_finalize",
        started_at=feed_started_at,
        completed_steps=6,
        total_steps=total_steps,
        body_chars=body_chars,
        predicate_atom_count=len(predicate_atoms),
        legal_signal_count=len(legal_occurrences),
        operational_signal_count=len(operational_occurrences),
        signal_atom_count=len(signal_atoms),
        provenance_ref_count=len(provenance_refs),
        work_unit="provenance_refs",
        work_completed=expected_provenance_upper_bound,
        work_total=expected_provenance_upper_bound,
    )

    return {
        "source": "sensiblaw_shared_reducer",
        "predicate_atoms": [_predicate_atom_dict(atom) for atom in predicate_atoms],
        "signal_atoms": signal_atoms,
        "provenance_refs": provenance_refs,
        "constraint_receipt": {
            "canonical_mode": canonical_mode,
            "question_mode": is_question,
            "tokenizer_profile_id": tokenizer_receipt["profile_id"],
            "evidence_only": True,
        },
    }


def collect_canonical_structural_ir_feed_from_units(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
    *,
    canonical_mode: str = "deterministic_legal",
    progress_callback=None,
) -> dict[str, Any]:
    """Emit a structural IR feed only from body-qualified canonical units."""

    text = _body_qualified_unit_text(units)
    if not text:
        return {
            "source": "sensiblaw_shared_reducer",
            "predicate_atoms": [],
            "signal_atoms": [],
            "provenance_refs": [],
            "constraint_receipt": {
                "canonical_mode": canonical_mode,
                "question_mode": False,
                "tokenizer_profile_id": get_canonical_tokenizer_profile_receipt()["profile_id"],
                "evidence_only": True,
            },
        }
    return collect_canonical_structural_ir_feed(
        text,
        canonical_mode=canonical_mode,
        progress_callback=progress_callback,
    )


def get_canonical_tokenizer_profile() -> dict[str, str]:
    """Return the current SL canonical tokenizer profile for cross-product consumers."""

    return get_tokenizer_profile()


def get_canonical_tokenizer_profile_receipt() -> dict[str, str]:
    """Return a bounded receipt for the current tokenizer profile."""

    profile = get_tokenizer_profile()
    profile_items = sorted(profile.items())
    profile_seed = "|".join(f"{key}={value}" for key, value in profile_items)
    return {
        "profile_id": hashlib.sha256(profile_seed.encode("utf-8")).hexdigest()[:16],
        "canonical_tokenizer_id": profile["canonical_tokenizer_id"],
        "canonical_tokenizer_version": profile["canonical_tokenizer_version"],
        "canonical_mode": profile["canonical_mode"],
    }


def collect_canonical_lexeme_occurrences(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> list[LexemeOccurrence]:
    """Collect canonical lexeme occurrences using the SL-owned reducer contract."""

    return collect_lexeme_occurrences(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )


def collect_canonical_lexeme_occurrences_with_profile(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> tuple[list[LexemeOccurrence], LexemeTokenizerProfile]:
    """Collect canonical lexeme occurrences together with the tokenizer profile."""

    return collect_lexeme_occurrences_with_profile(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )


def collect_canonical_lexeme_refs(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> list[dict[str, int | str]]:
    """Collect bounded opaque refs for SL-owned lexeme occurrences."""

    occurrences = collect_canonical_lexeme_occurrences(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )
    refs: list[dict[str, int | str]] = []
    for occurrence in occurrences:
        occurrence_seed = "|".join(
            (
                occurrence.kind,
                occurrence.norm_text,
                str(occurrence.start_char),
                str(occurrence.end_char),
                str(occurrence.flags),
            )
        )
        refs.append(
            {
                "occurrence_id": hashlib.sha256(occurrence_seed.encode("utf-8")).hexdigest()[:16],
                "kind": occurrence.kind,
                "span_start": occurrence.start_char,
                "span_end": occurrence.end_char,
            }
    )
    return refs


def collect_canonical_lexeme_terms(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> tuple[str, ...]:
    """Collect stable canonical lexeme terms for bounded downstream ingress."""

    occurrences = collect_canonical_lexeme_occurrences(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )
    seen: set[str] = set()
    ordered_terms: list[str] = []
    for occurrence in occurrences:
        if str(occurrence.kind or "").strip() != "word":
            continue
        norm_text = str(occurrence.norm_text or "").strip()
        if not norm_text or norm_text in seen:
            continue
        seen.add(norm_text)
        ordered_terms.append(norm_text)
    return tuple(ordered_terms)


def collect_canonical_structure_occurrences(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    include_legal: bool = True,
    include_operational: bool = True,
) -> list[StructureOccurrence]:
    """Collect the combined SL legal + operational structure occurrence stream."""

    return collect_structure_occurrences(
        text,
        canonical_mode=canonical_mode,
        include_legal=include_legal,
        include_operational=include_operational,
    )


def tokenize_canonical_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Expose SL canonical span tokenization as a supported adapter call."""

    return tokenize_with_spans(text)


def tokenize_canonical_detailed(text: str) -> list[LexemeToken]:
    """Expose SL canonical detailed tokenization as a supported adapter call."""

    return tokenize_detailed(text)


__all__ = [
    "RelationalAtom",
    "PredicateIndex",
    "CandidateResidual",
    "PredicateAtom",
    "PredicatePNF",
    "Residual",
    "ResidualLevel",
    "RoleState",
    "LexemeOccurrence",
    "LexemeTokenizerProfile",
    "LexemeToken",
    "StructureOccurrence",
    "coerce_predicate_atom",
    "comparable",
    "build_predicate_index",
    "build_predicate_ref_map",
    "collect_candidate_predicate_refs",
    "collect_candidate_residuals",
    "collect_canonical_lexeme_refs",
    "collect_canonical_lexeme_occurrences",
    "collect_canonical_lexeme_occurrences_with_profile",
    "collect_canonical_lexeme_terms",
    "collect_canonical_predicate_atoms",
    "collect_canonical_predicate_atoms_from_units",
    "collect_canonical_relational_bundle",
    "collect_canonical_structural_ir_feed",
    "collect_canonical_structural_ir_feed_from_units",
    "collect_canonical_structure_occurrences",
    "compute_indexed_residual",
    "compute_residual",
    "get_canonical_tokenizer_profile",
    "get_canonical_tokenizer_profile_receipt",
    "join_role_states",
    "join_residual",
    "join_typed_args",
    "meet_atom",
    "tokenize_canonical_detailed",
    "tokenize_canonical_with_spans",
]
