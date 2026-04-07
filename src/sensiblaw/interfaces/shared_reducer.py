from __future__ import annotations

"""Supported cross-product access to SL canonical lexer/reducer outputs."""

from dataclasses import dataclass
import hashlib
import re
from typing import Any

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
    from src.text.operational_structure import StructureOccurrence
    from src.text.structure_index import collect_structure_occurrences
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
    from text.operational_structure import StructureOccurrence
    from text.structure_index import collect_structure_occurrences
try:
    from src.nlp.spacy_adapter import parse as parse_with_spacy
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from nlp.spacy_adapter import parse as parse_with_spacy


_YEAR_RE = re.compile(r"^\d{4}$")


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


def collect_canonical_relational_bundle(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
) -> dict[str, Any]:
    """Emit a deterministic relation bundle over canonical text."""

    del canonical_mode  # reserved for future profile-routing parity
    parsed = parse_with_spacy(text)
    sent_tokens = [token for sentence in parsed.get("sents", ()) for token in sentence.get("tokens", ())]

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

    token_by_index = {token["index"]: token for token in sent_tokens}
    nounish = {"NOUN", "PROPN", "PRON", "NUM"}
    predicate_deps = {"ROOT", "acl", "xcomp", "ccomp", "advcl"}
    object_deps = {"dobj", "obj", "attr", "oprd"}
    modifier_deps = {"compound", "amod", "nmod", "appos", "conj"}

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
            role["span_start"], role["span_end"] = question_span
        append_relation("composition", [role])

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
    "LexemeOccurrence",
    "LexemeTokenizerProfile",
    "LexemeToken",
    "StructureOccurrence",
    "collect_canonical_lexeme_refs",
    "collect_canonical_lexeme_occurrences",
    "collect_canonical_lexeme_occurrences_with_profile",
    "collect_canonical_relational_bundle",
    "collect_canonical_structure_occurrences",
    "get_canonical_tokenizer_profile",
    "get_canonical_tokenizer_profile_receipt",
    "tokenize_canonical_detailed",
    "tokenize_canonical_with_spans",
]
