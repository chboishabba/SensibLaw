"""Supported cross-product access to SL canonical lexer/reducer outputs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import hashlib
import re
import time
from pathlib import Path
from typing import Any, Mapping

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
    from src.text.operational_structure import (
        StructureOccurrence,
        collect_operational_structure_occurrences,
    )
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
    from src.text.utterance_latent_fibres import (
        UtteranceLatentIndex,
        enrich_utterance_atoms,
        load_latent_index,
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
    from text.operational_structure import (
        StructureOccurrence,
        collect_operational_structure_occurrences,
    )
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
    from text.utterance_latent_fibres import (
        UtteranceLatentIndex,
        enrich_utterance_atoms,
        load_latent_index,
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
try:
    from src.nlp.ontology_mapping import (
        canonical_action_morphology,
        unknown_action_morphology,
    )
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from nlp.ontology_mapping import (
        canonical_action_morphology,
        unknown_action_morphology,
    )


_YEAR_RE = re.compile(r"^\d{4}$")
_RELATIONAL_BUNDLE_BATCH_MAX_SENTENCES = 32
_RELATIONAL_BUNDLE_BATCH_MAX_CHARS = 8192
_NEGATION_LEXEMES = {"not", "never", "no"}
_AUXILIARY_LEXEMES = {
    "am",
    "are",
    "is",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "has",
    "have",
    "had",
    "will",
    "would",
    "shall",
    "should",
    "can",
    "could",
    "may",
    "might",
    "must",
}
_DETERMINER_LEXEMES = {"a", "an", "the"}
_CONJUNCTION_LEXEMES = {"and", "or"}
_COPULAR_RECLASSIFICATION_PATTERNS = (
    re.compile(
        r"\b(?P<subject>[A-Za-z0-9][\w.-]*)\s+"
        r"(?P<verb>is|are|was|were|be|being|been|isn't|aren't|wasn't|weren't)\s+"
        r"(?P<neg>not\s+)?(?P<first>[^,.!?;]+?)\s*,\s*"
        r"(?:(?:it|they|he|she|this|that|[A-Za-z0-9][\w.-]*)\s+)?"
        r"(?:is|are|was|were|be|being|been|it's|they're|isn't|aren't|wasn't|weren't)?\s*"
        r"(?P<trailing_neg>not\s+)?(?P<second>[^,.!?;]+)",
        re.IGNORECASE,
    ),
)
_COPULAR_NOT_TAIL_RE = re.compile(
    r"\b(?P<subject>[A-Za-z0-9][\w.-]*)\s+"
    r"(?:is|are|was|were|be|being|been)\s+"
    r"(?P<first>[^,.!?;]+?)\s*,\s*not\s+(?P<second>[^,.!?;]+)",
    re.IGNORECASE,
)
UTTERANCE_LATENT_FIBRE_INDEX_SCHEMA = "sl.utterance_latent_fibre_index.v0_1"
DEFAULT_UTTERANCE_LATENT_FIBRE_INDEX_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "latent_fibres"
    / "utterance_latent_fibres.v0_1.json"
)
_UTTERANCE_LATENT_FIBRE_INDEX_PATH_ENV = "SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH"
_UTTERANCE_LATENT_FIBRES_DISABLED_ENV = "SENSIBLAW_UTTERANCE_LATENT_FIBRES_DISABLED"
_LEGACY_UTTERANCE_LATENT_FIBRE_INDEX_ENV = "SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX"
_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG_ENV = (
    "SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG"
)
_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG_KEYS = {
    "utterance_latent_fibre_index",
    "utterance_latent_fibre_index_path",
    "path",
    "index_path",
    "artifact_path",
}
_UTTERANCE_LATENT_FIBRE_INDEX_CACHE: tuple[str, UtteranceLatentIndex] | None = None


@dataclass(frozen=True, slots=True)
class RelationalAtom:
    atom_id: str
    text: str
    span_start: int
    span_end: int
    lemma: str | None = None
    morph: dict[str, Any] | None = None
    pos: str | None = None
    dependency: str | None = None


def _dedupe_relation_key(relation: dict[str, Any]) -> tuple[Any, ...]:
    parts: list[Any] = [relation["type"]]
    for role in relation["roles"]:
        value = role.get("value")
        if isinstance(value, dict):
            value = tuple(sorted((str(key), str(item)) for key, item in value.items()))
        parts.append((role["role"], role.get("atom"), value))
    return tuple(parts)


def _detect_question_span(
    parsed: dict[str, Any],
) -> tuple[bool, tuple[int, int] | None]:
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
                if (
                    head is not None
                    and head["pos"] in {"VERB", "AUX"}
                    and token["index"] < head["index"]
                ):
                    return True, (token["start"], token["end"])

    return False, None


def _iter_sentence_batches(text: str) -> list[dict[str, Any]]:
    sentences = _normalized_sentence_records(text)
    if not sentences:
        return []

    batches: list[dict[str, Any]] = []
    batch_start_index = 0
    while batch_start_index < len(sentences):
        batch_end_index = batch_start_index
        batch_start_char = int(sentences[batch_start_index]["start_char"])
        batch_end_char = int(sentences[batch_start_index]["end_char"])
        while batch_end_index + 1 < len(sentences):
            candidate = sentences[batch_end_index + 1]
            candidate_count = (batch_end_index + 1) - batch_start_index + 1
            candidate_end_char = int(candidate["end_char"])
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


def _normalized_sentence_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cursor = 0
    for sentence in segment_sentences(text):
        sentence_text = str(getattr(sentence, "text", "") or "").strip()
        if not sentence_text:
            continue
        found = text.find(sentence_text, cursor)
        if found < 0:
            raw_start = int(getattr(sentence, "start_char", cursor) or cursor)
            raw_end = int(
                getattr(sentence, "end_char", raw_start + len(sentence_text))
                or raw_start + len(sentence_text)
            )
            if (
                raw_start < cursor
                or raw_end <= raw_start
                or text[raw_start:raw_end].strip() != sentence_text
            ):
                raw_start = cursor
                raw_end = min(len(text), raw_start + len(sentence_text))
            start = raw_start
            end = raw_end
        else:
            start = found
            end = found + len(sentence_text)
        records.append({"text": sentence_text, "start_char": start, "end_char": end})
        cursor = end
    return records


def _collect_utterance_latent_fibre_index(
    override: str | UtteranceLatentIndex | os.PathLike[str] | None,
) -> UtteranceLatentIndex | None:
    global _UTTERANCE_LATENT_FIBRE_INDEX_CACHE
    if isinstance(override, UtteranceLatentIndex):
        return override

    artifact_path = _resolve_utterance_latent_fibre_index_path(override)
    if not artifact_path:
        return None

    if (
        _UTTERANCE_LATENT_FIBRE_INDEX_CACHE is not None
        and _UTTERANCE_LATENT_FIBRE_INDEX_CACHE[0] == artifact_path
    ):
        return _UTTERANCE_LATENT_FIBRE_INDEX_CACHE[1]

    try:
        index = load_latent_index(artifact_path)
    except (FileNotFoundError, OSError, ValueError):
        return None
    _UTTERANCE_LATENT_FIBRE_INDEX_CACHE = (artifact_path, index)
    return index


def _clear_utterance_latent_fibre_index_cache() -> None:
    global _UTTERANCE_LATENT_FIBRE_INDEX_CACHE
    _UTTERANCE_LATENT_FIBRE_INDEX_CACHE = None


def _resolve_utterance_latent_fibre_index_path(
    override: str | os.PathLike[str] | None,
) -> str:
    if override is not None:
        return str(override)
    env_path = os.getenv(_UTTERANCE_LATENT_FIBRE_INDEX_PATH_ENV, "").strip()
    if env_path:
        return env_path
    config_path = _resolve_utterance_latent_fibre_index_path_from_config()
    if config_path:
        return config_path
    legacy_env_path = os.getenv(_LEGACY_UTTERANCE_LATENT_FIBRE_INDEX_ENV, "").strip()
    if legacy_env_path:
        return legacy_env_path
    if DEFAULT_UTTERANCE_LATENT_FIBRE_INDEX_PATH.exists():
        return str(DEFAULT_UTTERANCE_LATENT_FIBRE_INDEX_PATH)
    return ""


def _resolve_utterance_latent_fibre_index_path_from_config() -> str:
    raw_config = os.getenv(_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG_ENV, "").strip()
    if not raw_config:
        return ""

    config_payload: Any
    config_path: Path | None = None
    raw_config_path = Path(raw_config)
    if raw_config_path.exists():
        config_path = raw_config_path.expanduser()
        config_payload = config_path.read_text(encoding="utf-8")
    else:
        config_payload = raw_config
    try:
        payload = json.loads(config_payload)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, Mapping):
        return ""

    candidate_path = _extract_path_from_latent_fibre_config(payload)
    if not candidate_path:
        return ""
    resolved_path = Path(candidate_path).expanduser()
    if config_path is not None and not resolved_path.is_absolute():
        resolved_path = config_path.parent / resolved_path
    if resolved_path.exists():
        return str(resolved_path)
    return ""


def _extract_path_from_latent_fibre_config(payload: Mapping[str, Any]) -> str:
    for key in _UTTERANCE_LATENT_FIBRE_INDEX_CONFIG_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    nested = payload.get("utterance_latent_fibres")
    if isinstance(nested, Mapping):
        for key in _UTTERANCE_LATENT_FIBRE_INDEX_CONFIG_KEYS:
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _utterance_latent_fibres_disabled() -> bool:
    raw = os.getenv(_UTTERANCE_LATENT_FIBRES_DISABLED_ENV, "").strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def _apply_utterance_latent_fibres(
    atoms: list[PredicateAtom],
    *,
    enable_utterance_latent_fibres: bool,
    utterance_latent_fibre_index: str | UtteranceLatentIndex | os.PathLike[str] | None,
) -> list[PredicateAtom]:
    if not enable_utterance_latent_fibres or _utterance_latent_fibres_disabled():
        return atoms
    index = _collect_utterance_latent_fibre_index(utterance_latent_fibre_index)
    if index is None:
        return atoms
    try:
        return list(enrich_utterance_atoms(atoms, index))
    except Exception:
        return atoms


def collect_canonical_relational_bundle(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    parsed_document: Mapping[str, Any] | None = None,
    progress_callback=None,
) -> dict[str, Any]:
    """Emit a deterministic relation bundle over canonical parser observations.

    ``parsed_document`` is the public parser payload returned by
    :func:`sensiblaw.interfaces.parse_canonical_text`.  Supplying it preserves
    a one-parse compiler path; omitting it keeps the historical convenience
    surface intact.  The bundle is a syntactic observation projection only.
    """

    del canonical_mode  # reserved for future profile-routing parity
    if parsed_document is not None and str(parsed_document.get("text") or "") != text:
        raise ValueError("parsed_document text must equal text")
    sentence_batches = (
        [
            {
                "text": text,
                "start_char": 0,
                "sentences": tuple(parsed_document.get("sents") or ()),
                "parsed": parsed_document,
            }
        ]
        if parsed_document is not None
        else _iter_sentence_batches(text)
    )
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
            lemma=str(token.get("lemma") or token.get("text") or ""),
            morph=token.get("morph") if isinstance(token.get("morph"), dict) else None,
            pos=str(token.get("pos") or "") or None,
            dependency=str(token.get("dep") or "") or None,
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
        parsed = batch.get("parsed") or _parse_with_spacy_or_fallback(batch_text)
        sent_tokens: list[dict[str, Any]] = []
        for sentence in parsed.get("sents", ()):
            for token in sentence.get("tokens", ()):
                adjusted = dict(token)
                if parsed_document is None:
                    adjusted["start"] = int(token["start"]) + batch_start_char
                    adjusted["end"] = int(token["end"]) + batch_start_char
                sent_tokens.append(adjusted)
        token_by_index = {token["index"]: token for token in sent_tokens}

        for token in sent_tokens:
            if token["dep"] in predicate_deps and token["pos"] in {"VERB", "AUX"}:
                auxiliary_children = {
                    child["index"]
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and child["dep"] in {"aux", "auxpass"}
                    and child["pos"] == "AUX"
                }
                subject_children = [
                    child
                    for child in sent_tokens
                    if (
                        child["head_index"] == token["index"]
                        or child["head_index"] in auxiliary_children
                    )
                    and child["dep"] in {"nsubj", "nsubjpass"}
                    and child["pos"] in nounish
                ]
                object_children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and child["dep"] in object_deps
                    and child["pos"] in nounish
                ]
                oblique_children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and child["dep"] in {"obl", "pobj", "iobj"}
                    and child["pos"] in nounish
                ]
                complement_children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and child["dep"] in {"attr", "acomp", "ccomp", "xcomp", "oprd"}
                ]
                clausal_complement_children = [
                    child
                    for child in complement_children
                    if child["dep"] in {"ccomp", "xcomp"}
                ]
                negation_children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and (
                        child["dep"] == "neg"
                        or child["lemma"].casefold() in _NEGATION_LEXEMES
                    )
                ]
                aux_children = [
                    child
                    for child in sent_tokens
                    if child["head_index"] == token["index"]
                    and child["dep"] in {"aux", "auxpass"}
                    and child["pos"] == "AUX"
                ]
                if object_children:
                    # Preserve the v1 object-centred projection for existing
                    # predicate-atom consumers.  The no-object branch below
                    # extends coverage without changing these legacy rows.
                    relation_subjects = subject_children or [None]
                    for child in object_children:
                        head_atom = ensure_atom(token)
                        argument_atom = ensure_atom(child)
                        roles = [{"role": "head", "atom": head_atom.atom_id}]
                        for subject in relation_subjects:
                            if subject is not None:
                                subject_atom = ensure_atom(subject)
                                roles.append(
                                    {"role": "subject", "atom": subject_atom.atom_id}
                                )
                        roles.append({"role": "object", "atom": argument_atom.atom_id})
                        roles.append(
                            {"role": "argument", "atom": argument_atom.atom_id}
                        )
                        for negation in negation_children:
                            negation_atom = ensure_atom(negation)
                            roles.append(
                                {"role": "negation", "atom": negation_atom.atom_id}
                            )
                        for aux in aux_children:
                            aux_atom = ensure_atom(aux)
                            roles.append(
                                {"role": "auxiliary", "atom": aux_atom.atom_id}
                            )
                        roles.append(
                            {
                                "role": "action_meta",
                                "value": _canonical_action_metadata(token),
                            }
                        )
                        append_relation("predicate", roles)
                else:
                    head_atom = ensure_atom(token)
                    roles = [{"role": "head", "atom": head_atom.atom_id}]
                    for subject in subject_children:
                        subject_atom = ensure_atom(subject)
                        roles.append({"role": "subject", "atom": subject_atom.atom_id})
                    for child in oblique_children:
                        argument_atom = ensure_atom(child)
                        roles.append({"role": "oblique", "atom": argument_atom.atom_id})
                        roles.append(
                            {"role": "argument", "atom": argument_atom.atom_id}
                        )
                    for child in complement_children:
                        argument_atom = ensure_atom(child)
                        roles.append(
                            {"role": "complement", "atom": argument_atom.atom_id}
                        )
                        roles.append(
                            {"role": "argument", "atom": argument_atom.atom_id}
                        )
                    for negation in negation_children:
                        negation_atom = ensure_atom(negation)
                        roles.append(
                            {"role": "negation", "atom": negation_atom.atom_id}
                        )
                    for aux in aux_children:
                        aux_atom = ensure_atom(aux)
                        roles.append({"role": "auxiliary", "atom": aux_atom.atom_id})
                    roles.append(
                        {
                            "role": "action_meta",
                            "value": _canonical_action_metadata(token),
                        }
                    )
                    append_relation("predicate", roles)

                for child in clausal_complement_children:
                    host_atom = ensure_atom(token)
                    content_atom = ensure_atom(child)
                    append_relation(
                        "composition",
                        [
                            {"role": "host", "atom": host_atom.atom_id},
                            {"role": "content", "atom": content_atom.atom_id},
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

            if token["dep"] in {"npadvmod", "tmod", "pobj"} and _YEAR_RE.match(
                token["text"]
            ):
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

    atoms = []
    for atom in sorted(
        atoms_by_key.values(),
        key=lambda value: (value.span_start, value.span_end, value.atom_id),
    ):
        payload = {
            "id": atom.atom_id,
            "text": atom.text,
            "span": [atom.span_start, atom.span_end],
        }
        if atom.lemma:
            payload["lemma"] = atom.lemma
        if atom.morph:
            payload["morph"] = dict(atom.morph)
        if atom.pos:
            payload["pos"] = atom.pos
        if atom.dependency:
            payload["dependency"] = atom.dependency
        atoms.append(payload)
    return {
        "version": "relational_bundle_v1",
        "canonical_text": text,
        "atoms": atoms,
        "relations": relations,
    }


def _parse_with_spacy_or_fallback(text: str) -> dict[str, Any]:
    try:
        parsed = parse_with_spacy(text)
    except ModuleNotFoundError:
        return _fallback_parse(text)
    if not _parsed_has_predicate_signal(parsed):
        return _fallback_parse(text)
    return parsed


def _parsed_has_predicate_signal(parsed: dict[str, Any]) -> bool:
    for sentence in parsed.get("sents", ()):
        for token in sentence.get("tokens", ()):
            if token.get("dep") and token.get("pos"):
                return True
    return False


def _fallback_parse(text: str) -> dict[str, Any]:
    sentence_spans = _fallback_sentence_spans(text)
    sentences = [
        {
            "text": text[start:end].strip(),
            "start_char": start,
            "end_char": end,
        }
        for start, end in sentence_spans
        if text[start:end].strip()
    ]
    if not sentences:
        return {"text": text, "sents": []}
    parsed_sentences: list[dict[str, Any]] = []
    token_index = 0
    for sentence in sentences:
        sentence_tokens = _fallback_tokens(
            text, int(sentence["start_char"]), int(sentence["end_char"]), token_index
        )
        token_index += len(sentence_tokens)
        _fallback_assign_dependencies(sentence_tokens)
        parsed_sentences.append(
            {
                "text": sentence["text"],
                "start": sentence["start_char"],
                "end": sentence["end_char"],
                "tokens": sentence_tokens,
            }
        )
    return {"text": text, "sents": parsed_sentences}


def _fallback_sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for index, char in enumerate(text):
        if char in ".!?\n":
            if text[start:index].strip():
                spans.append((start, index))
            start = index + 1
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _fallback_tokens(
    text: str, start: int, end: int, token_index_start: int
) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    token_start: int | None = None
    for index in range(start, end):
        char = text[index]
        if char.isalnum() or char in "_-":
            if token_start is None:
                token_start = index
            continue
        if token_start is not None:
            tokens.append(
                _fallback_token(
                    text[token_start:index],
                    token_start,
                    index,
                    token_index_start + len(tokens),
                )
            )
            token_start = None
        if char in "?!":
            tokens.append(
                _fallback_token(
                    char,
                    index,
                    index + 1,
                    token_index_start + len(tokens),
                    pos="PUNCT",
                    tag=".",
                )
            )
    if token_start is not None:
        tokens.append(
            _fallback_token(
                text[token_start:end], token_start, end, token_index_start + len(tokens)
            )
        )
    return tokens


def _fallback_token(
    text: str,
    start: int,
    end: int,
    index: int,
    *,
    pos: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    lower = text.casefold()
    inferred_pos = pos or _fallback_pos(lower)
    return {
        "index": index,
        "text": text,
        "lemma": lower,
        "pos": inferred_pos,
        "tag": tag or inferred_pos,
        "dep": "",
        "head_index": index,
        "head_text": text,
        "start": start,
        "end": end,
    }


def _fallback_pos(token: str) -> str:
    if _YEAR_RE.match(token):
        return "NUM"
    if token in _DETERMINER_LEXEMES:
        return "DET"
    if token in _CONJUNCTION_LEXEMES:
        return "CCONJ"
    if token in _NEGATION_LEXEMES:
        return "PART"
    if token in _AUXILIARY_LEXEMES:
        return "AUX"
    if token in {"i", "you", "we", "it", "they", "he", "she", "this", "that"}:
        return "PRON"
    if token in _FALLBACK_VERBS or token.endswith(("ed", "ing", "ize", "ise")):
        return "VERB"
    return "NOUN"


_FALLBACK_VERBS = {
    "add",
    "adds",
    "build",
    "builds",
    "call",
    "calls",
    "check",
    "checks",
    "compare",
    "compares",
    "define",
    "defines",
    "emit",
    "emits",
    "implement",
    "implements",
    "measure",
    "measures",
    "need",
    "needs",
    "observe",
    "observes",
    "publish",
    "publishes",
    "reduce",
    "reduces",
    "require",
    "requires",
    "run",
    "runs",
    "test",
    "tests",
    "write",
    "writes",
}


def _canonical_verb_lemma(token: dict[str, Any]) -> str:
    lemma = str(token.get("lemma") or token.get("text") or "").strip().casefold()
    text = str(token.get("text") or "").strip().casefold()
    if not lemma or lemma in {"-pron-"}:
        lemma = text
    return lemma


class _MorphAdapter:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, name: str) -> list[str]:
        raw = self._values.get(name)
        if isinstance(raw, list):
            return [str(value) for value in raw if str(value)]
        if isinstance(raw, tuple):
            return [str(value) for value in raw if str(value)]
        if raw is None:
            return []
        return [str(raw)]


class _TokenMorphAdapter:
    def __init__(self, token: dict[str, Any]) -> None:
        self.text = str(token.get("text") or "")
        self.lemma_ = str(token.get("lemma") or token.get("text") or "")
        self.dep_ = str(token.get("dep") or "")
        morph = token.get("morph")
        self.morph = _MorphAdapter(morph if isinstance(morph, dict) else {})
        self.children: list[Any] = []


def _canonical_action_metadata(token: dict[str, Any]) -> dict[str, str]:
    if not isinstance(token.get("morph"), dict):
        return unknown_action_morphology(
            surface=str(token.get("text") or ""), source="fallback"
        )
    return canonical_action_morphology(
        _TokenMorphAdapter(token),
        surface=str(token.get("text") or ""),
        source="spacy_morphology",
    )


def _fallback_assign_dependencies(tokens: list[dict[str, Any]]) -> None:
    verbs = [token for token in tokens if token["pos"] == "VERB"]
    verb = verbs[0] if verbs else None
    if not verbs:
        for index, token in enumerate(tokens[:-1]):
            if token["pos"] == "AUX":
                candidate = next(
                    (
                        item
                        for item in tokens[index + 1 :]
                        if item["pos"] in {"NOUN", "PROPN"}
                        and str(item.get("lemma") or item.get("text") or "").casefold()
                        not in _DETERMINER_LEXEMES
                    ),
                    None,
                )
                if candidate is not None:
                    candidate["pos"] = "VERB"
                    candidate["tag"] = "VERB"
                    verb = candidate
                    verbs = [candidate]
                    break
    if verb is None:
        verb = next((token for token in tokens if token["pos"] == "AUX"), None)
        verbs = [verb] if verb is not None else []
    if verb is None:
        for token in tokens:
            token["dep"] = "ROOT" if token is tokens[0] else "compound"
            token["head_index"] = tokens[0]["index"]
            token["head_text"] = tokens[0]["text"]
        return

    primary_verb = verbs[0]
    for token in tokens:
        token["dep"] = "compound"
        token["head_index"] = primary_verb["index"]
        token["head_text"] = primary_verb["text"]

    for index, current_verb in enumerate(verbs):
        current_verb["dep"] = "ROOT" if index == 0 else "conj"
        current_verb["head_index"] = (
            primary_verb["index"] if index else current_verb["index"]
        )
        current_verb["head_text"] = (
            primary_verb["text"] if index else current_verb["text"]
        )

        next_verb_index = verbs[index + 1]["index"] if index + 1 < len(verbs) else None
        previous_verb_index = verbs[index - 1]["index"] if index > 0 else None

        subject = _fallback_nearest_subject(tokens, current_verb, previous_verb_index)
        if subject is not None and subject["dep"] in {"", "compound", "nsubj"}:
            subject["dep"] = "nsubj"
            subject["head_index"] = current_verb["index"]
            subject["head_text"] = current_verb["text"]

        obj = _fallback_nearest_object(tokens, current_verb, next_verb_index)
        if obj is not None and obj["dep"] in {"", "compound", "obj"}:
            obj["dep"] = "obj"
            obj["head_index"] = current_verb["index"]
            obj["head_text"] = current_verb["text"]

    for token in tokens:
        if token in verbs:
            continue
        if token["pos"] == "PUNCT":
            token["dep"] = "punct"
            token["head_index"] = primary_verb["index"]
            token["head_text"] = primary_verb["text"]
        elif (
            token["pos"] == "PART"
            and str(token.get("lemma") or token.get("text") or "").casefold()
            in _NEGATION_LEXEMES
        ):
            head = _fallback_next_verb(tokens, token, verbs) or primary_verb
            token["dep"] = "neg"
            token["head_index"] = head["index"]
            token["head_text"] = head["text"]
        elif token["pos"] == "AUX":
            head = _fallback_next_verb(tokens, token, verbs) or primary_verb
            token["dep"] = "aux"
            token["head_index"] = head["index"]
            token["head_text"] = head["text"]


def _fallback_nearest_subject(
    tokens: list[dict[str, Any]],
    verb: dict[str, Any],
    previous_verb_index: int | None,
) -> dict[str, Any] | None:
    lower_bound = previous_verb_index if previous_verb_index is not None else -1
    candidates = [
        token
        for token in tokens
        if lower_bound < token["index"] < verb["index"]
        and token["pos"] in {"NOUN", "PROPN", "PRON", "NUM"}
        and str(token.get("lemma") or token.get("text") or "").casefold()
        not in _DETERMINER_LEXEMES
    ]
    return candidates[-1] if candidates else None


def _fallback_nearest_object(
    tokens: list[dict[str, Any]],
    verb: dict[str, Any],
    next_verb_index: int | None,
) -> dict[str, Any] | None:
    upper_bound = next_verb_index if next_verb_index is not None else 10**9
    for token in tokens:
        if token["index"] <= verb["index"] or token["index"] >= upper_bound:
            continue
        lemma = str(token.get("lemma") or token.get("text") or "").casefold()
        if (
            token["pos"] in {"NOUN", "PROPN", "PRON", "NUM"}
            and lemma not in _DETERMINER_LEXEMES
        ):
            return token
    return None


def _fallback_next_verb(
    tokens: list[dict[str, Any]],
    token: dict[str, Any],
    verbs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    del tokens
    return next((verb for verb in verbs if verb["index"] > token["index"]), None)


def collect_canonical_predicate_atoms(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
) -> list[PredicateAtom]:
    """Expose bounded predicate-ready atoms derived from the shared reducer.

    This stays parser-first and reducer-first. It does not infer domains or
    semantic classes. It only projects explicit predicate relations and their
    attached modifier relations into the residual carrier.

    When enabled, utterance atoms are enriched from a pinned local latent fibre
    index only if the index resolves and validates against
    ``sl.utterance_latent_fibre_index.v0_1`` with a
    ``source_corpus.manifest_hash`` and extraction profile version. Resolution
    order is explicit ``utterance_latent_fibre_index``,
    ``SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_PATH``,
    ``SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX_CONFIG``,
    legacy ``SENSIBLAW_UTTERANCE_LATENT_FIBRE_INDEX``, then the checked-in
    default artifact. Missing or invalid artifacts are exact-projection fallbacks,
    not hard failures. ``SENSIBLAW_UTTERANCE_LATENT_FIBRES_DISABLED`` disables this
    enrichment path.
    """

    bundle = collect_canonical_relational_bundle(text, canonical_mode=canonical_mode)
    atoms = _collect_canonical_predicate_atoms_from_bundle(bundle)
    atoms = [*atoms, *_collect_copular_reclassification_atoms(text)]
    return _apply_utterance_latent_fibres(
        atoms,
        enable_utterance_latent_fibres=bool(enable_utterance_latent_fibres),
        utterance_latent_fibre_index=utterance_latent_fibre_index,
    )


def collect_canonical_predicate_pnfs(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
) -> list[PredicatePNF]:
    """Expose canonical predicate normal forms derived from the shared reducer.

    Latent fibre enrichment follows ``collect_canonical_predicate_atoms``:
    schema-valid pinned indexes may add evidence-only ``support_fibres``,
    ``latent_grounding``, and ``semantic_comparison_mode`` fields; unresolved
    indexes preserve exact-first predicate projection unchanged.
    """

    return collect_canonical_predicate_atoms(
        text,
        canonical_mode=canonical_mode,
        enable_utterance_latent_fibres=enable_utterance_latent_fibres,
        utterance_latent_fibre_index=utterance_latent_fibre_index,
    )


def _body_qualified_unit_text(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
) -> str:
    body_units = [
        unit
        for unit in sorted(
            units, key=lambda item: (item.start_char, item.end_char, item.unit_id)
        )
        if isinstance(unit, CanonicalUnit)
        and unit.metadata.get("body_qualified") is True
        and unit.text.strip()
    ]
    return "\n\n".join(unit.text.strip() for unit in body_units)


def collect_canonical_predicate_atoms_from_units(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
    *,
    canonical_mode: str = "deterministic_legal",
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
) -> list[PredicateAtom]:
    """Project predicate atoms only from body-qualified canonical units."""

    text = _body_qualified_unit_text(units)
    if not text:
        return []
    return collect_canonical_predicate_atoms(
        text,
        canonical_mode=canonical_mode,
        enable_utterance_latent_fibres=enable_utterance_latent_fibres,
        utterance_latent_fibre_index=utterance_latent_fibre_index,
    )


def collect_canonical_predicate_pnfs_from_units(
    units: list[CanonicalUnit] | tuple[CanonicalUnit, ...],
    *,
    canonical_mode: str = "deterministic_legal",
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
) -> list[PredicatePNF]:
    """Project predicate normal forms only from body-qualified canonical units."""

    text = _body_qualified_unit_text(units)
    if not text:
        return []
    return collect_canonical_predicate_pnfs(
        text,
        canonical_mode=canonical_mode,
        enable_utterance_latent_fibres=enable_utterance_latent_fibres,
        utterance_latent_fibre_index=utterance_latent_fibre_index,
    )


def _collect_canonical_predicate_atoms_from_bundle(
    bundle: dict[str, Any],
) -> list[PredicateAtom]:
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
        subject_id = None
        object_id = None
        negation_ids: list[str] = []
        auxiliary_ids: list[str] = []
        action_meta: dict[str, str] = {}
        for role in relation.get("roles", ()):
            if not isinstance(role, dict):
                continue
            if role.get("role") == "head" and role.get("atom") is not None:
                head_id = str(role["atom"])
            if role.get("role") == "argument" and role.get("atom") is not None:
                argument_id = str(role["atom"])
            if role.get("role") == "subject" and role.get("atom") is not None:
                subject_id = str(role["atom"])
            if role.get("role") == "object" and role.get("atom") is not None:
                object_id = str(role["atom"])
            if role.get("role") == "negation" and role.get("atom") is not None:
                negation_ids.append(str(role["atom"]))
            if role.get("role") == "auxiliary" and role.get("atom") is not None:
                auxiliary_ids.append(str(role["atom"]))
            if role.get("role") == "action_meta" and isinstance(
                role.get("value"), dict
            ):
                action_meta = {
                    str(key): str(value)
                    for key, value in role["value"].items()
                    if value is not None
                }

        if head_id is None or argument_id is None:
            continue

        head_atom = atoms_by_id.get(head_id)
        argument_atom = atoms_by_id.get(object_id or argument_id)
        subject_atom = atoms_by_id.get(subject_id) if subject_id is not None else None
        if not isinstance(head_atom, dict) or not isinstance(argument_atom, dict):
            continue

        predicate = _canonical_verb_lemma(head_atom)
        argument = str(argument_atom.get("text", "")).strip().lower()
        if not predicate or not argument:
            continue

        head_span = head_atom.get("span") or ()
        argument_span = argument_atom.get("span") or ()
        subject_span = (
            subject_atom.get("span") if isinstance(subject_atom, dict) else ()
        )
        relation_id = str(relation.get("id", "")).strip() or None
        provenance_parts: list[str] = []
        if relation_id is not None:
            provenance_parts.append(relation_id)
        if len(head_span) == 2:
            provenance_parts.append(f"head:{head_span[0]}-{head_span[1]}")
        if len(argument_span) == 2:
            provenance_parts.append(f"arg:{argument_span[0]}-{argument_span[1]}")
        if len(subject_span) == 2:
            provenance_parts.append(f"subject:{subject_span[0]}-{subject_span[1]}")

        modifiers: dict[str, Any] = {}
        if head_id in head_modifier_evidence:
            modifier_evidence = head_modifier_evidence[head_id]
            modifiers["modifier_evidence"] = modifier_evidence
            for evidence_item in modifier_evidence:
                provenance_ref = str(evidence_item["provenance_ref"]).strip()
                if provenance_ref and provenance_ref not in provenance_parts:
                    provenance_parts.append(provenance_ref)

        negation_evidence = []
        for negation_id in negation_ids:
            negation_atom = atoms_by_id.get(negation_id)
            if not isinstance(negation_atom, dict):
                continue
            negation_span = negation_atom.get("span") or ()
            if len(negation_span) != 2:
                continue
            negation_ref = f"neg:{negation_span[0]}-{negation_span[1]}"
            negation_evidence.append(
                {
                    "text": str(negation_atom.get("text", "")).strip().lower(),
                    "span_start": int(negation_span[0]),
                    "span_end": int(negation_span[1]),
                    "provenance_ref": negation_ref,
                }
            )
            if negation_ref not in provenance_parts:
                provenance_parts.append(negation_ref)
        if negation_evidence:
            modifiers["negation_evidence"] = tuple(negation_evidence)

        auxiliary_evidence = []
        for auxiliary_id in auxiliary_ids:
            auxiliary_atom = atoms_by_id.get(auxiliary_id)
            if not isinstance(auxiliary_atom, dict):
                continue
            auxiliary_span = auxiliary_atom.get("span") or ()
            if len(auxiliary_span) != 2:
                continue
            auxiliary_ref = f"aux:{auxiliary_span[0]}-{auxiliary_span[1]}"
            auxiliary_evidence.append(
                {
                    "text": str(auxiliary_atom.get("text", "")).strip().lower(),
                    "span_start": int(auxiliary_span[0]),
                    "span_end": int(auxiliary_span[1]),
                    "provenance_ref": auxiliary_ref,
                }
            )
            if auxiliary_ref not in provenance_parts:
                provenance_parts.append(auxiliary_ref)
        if auxiliary_evidence:
            modifiers["auxiliary_evidence"] = tuple(auxiliary_evidence)
        if action_meta:
            modifiers["action_morphology"] = dict(action_meta)

        argument_provenance = ()
        if len(argument_span) == 2:
            argument_provenance = (f"arg:{argument_span[0]}-{argument_span[1]}",)
        action_provenance = ()
        if len(head_span) == 2:
            action_provenance = (f"head:{head_span[0]}-{head_span[1]}",)
        subject_provenance = ()
        subject_value = None
        if isinstance(subject_atom, dict):
            subject_value = str(subject_atom.get("text", "")).strip().lower()
            if len(subject_span) == 2:
                subject_provenance = (f"subject:{subject_span[0]}-{subject_span[1]}",)
        polarity = (
            "negative"
            if any(
                item["text"] in _NEGATION_LEXEMES
                for item in (
                    *modifiers.get("modifier_evidence", ()),
                    *modifiers.get("negation_evidence", ()),
                )
            )
            else "positive"
        )
        typed_roles = {
            "action": TypedArg(
                value=predicate,
                entity_type="action",
                provenance=action_provenance,
                status="bound",
            ),
            "object": TypedArg(
                value=argument,
                entity_type="object",
                provenance=argument_provenance,
                status="bound",
            ),
        }
        if subject_value:
            typed_roles["subject"] = TypedArg(
                value=subject_value,
                entity_type="actor",
                provenance=subject_provenance,
                status="bound",
            )
        typed_roles["argument"] = typed_roles["object"]
        predicate_atoms.append(
            PredicateAtom(
                predicate=predicate,
                structural_signature=f"utterance_event:{predicate}",
                roles=typed_roles,
                qualifiers=QualifierState(
                    polarity=polarity,
                    tense=action_meta.get("tense")
                    if action_meta.get("tense") != "unknown"
                    else None,
                    modality=action_meta.get("modality")
                    if action_meta.get("modality") != "unknown"
                    else None,
                ),
                wrapper=WrapperState(
                    status="structural_projection", evidence_only=True
                ),
                modifiers=modifiers,
                provenance=tuple(provenance_parts),
                atom_id=relation_id,
                domain="utterance_event",
            )
        )

    return predicate_atoms


def _collect_copular_reclassification_atoms(text: str) -> list[PredicateAtom]:
    atoms: list[PredicateAtom] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for match in _COPULAR_NOT_TAIL_RE.finditer(text):
        atoms.extend(
            _copular_classification_pair(
                text,
                subject=match.group("subject"),
                first=match.group("first"),
                first_polarity="positive",
                second=match.group("second"),
                second_polarity="negative",
                match_start=match.start(),
                match_end=match.end(),
                seen=seen,
            )
        )
    for match in _COPULAR_RECLASSIFICATION_PATTERNS:
        for found in match.finditer(text):
            first_negative = bool(found.groupdict().get("neg")) or str(
                found.groupdict().get("verb") or ""
            ).casefold() in {"isn't", "aren't", "wasn't", "weren't"}
            trailing_negative = bool(found.groupdict().get("trailing_neg"))
            if not first_negative and not trailing_negative:
                continue
            atoms.extend(
                _copular_classification_pair(
                    text,
                    subject=found.group("subject"),
                    first=found.group("first"),
                    first_polarity="negative" if first_negative else "positive",
                    second=found.group("second"),
                    second_polarity="negative" if trailing_negative else "positive",
                    match_start=found.start(),
                    match_end=found.end(),
                    seen=seen,
                )
            )
    return atoms


def _copular_classification_pair(
    text: str,
    *,
    subject: str,
    first: str,
    first_polarity: str,
    second: str,
    second_polarity: str,
    match_start: int,
    match_end: int,
    seen: set[tuple[str, str, str, int, int]],
) -> list[PredicateAtom]:
    subject_value = _normalize_classification_value(subject)
    first_value = _normalize_classification_value(first)
    second_value = _normalize_classification_value(second)
    if not subject_value or not first_value or not second_value:
        return []
    if first_value == second_value:
        return []
    return [
        _classification_atom(
            text,
            subject_value,
            first_value,
            first_polarity,
            match_start,
            match_end,
            seen,
        ),
        _classification_atom(
            text,
            subject_value,
            second_value,
            second_polarity,
            match_start,
            match_end,
            seen,
        ),
    ]


def _normalize_classification_value(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    normalized = re.sub(r"^(?:a|an|the)\s+(.+)$", r"\1", normalized)
    normalized = re.sub(r"\s+(?:it|they|he|she|this|that)$", "", normalized)
    return normalized.strip(" \t\r\n,.;:!?")


def _classification_atom(
    text: str,
    subject: str,
    class_value: str,
    polarity: str,
    span_start: int,
    span_end: int,
    seen: set[tuple[str, str, str, int, int]],
) -> PredicateAtom:
    key = (subject, class_value, polarity, span_start, span_end)
    provenance = (f"copular:{span_start}-{span_end}",)
    atom_id = (
        "copular:"
        + hashlib.sha256("|".join(map(str, key)).encode("utf-8")).hexdigest()[:16]
    )
    if key in seen:
        provenance = (*provenance, "deduped")
    seen.add(key)
    return PredicateAtom(
        predicate="be/classify",
        structural_signature="classification:agent-theme",
        roles={
            "agent": TypedArg(
                value=subject,
                entity_type="classified_entity",
                provenance=provenance,
                status="bound",
            ),
            "theme": TypedArg(
                value=class_value,
                entity_type="classification",
                provenance=provenance,
                status="bound",
            ),
            "subject": TypedArg(
                value=subject,
                entity_type="classified_entity",
                provenance=provenance,
                status="bound",
            ),
            "object": TypedArg(
                value=class_value,
                entity_type="classification",
                provenance=provenance,
                status="bound",
            ),
        },
        qualifiers=QualifierState(polarity=polarity),
        wrapper=WrapperState(status="directEvidence", evidence_only=True),
        modifiers={
            "classification_extractor": "copular_reclassification_v0_1",
            "source_text": text[span_start:span_end],
        },
        provenance=provenance,
        atom_id=atom_id,
        domain="classification",
    )


def _predicate_atom_dict(atom: PredicateAtom) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "predicate": atom.predicate,
        "structural_signature": atom.structural_signature,
        "roles": {key: value.to_dict() for key, value in atom.roles.items()},
        "qualifiers": atom.qualifiers.to_dict(),
        "wrapper": atom.wrapper.to_dict(),
        "provenance": list(atom.provenance),
    }
    if atom.support_fibres:
        payload["support_fibres"] = [dict(item) for item in atom.support_fibres]
    if atom.latent_grounding:
        payload["latent_grounding"] = dict(atom.latent_grounding)
    if atom.semantic_comparison_mode != "exact":
        payload["semantic_comparison_mode"] = atom.semantic_comparison_mode
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
    stage_fraction_complete = (
        0.0 if total_steps <= 0 else float(completed_steps) / float(total_steps)
    )
    work_fraction_complete = None
    eta_seconds = None
    if (
        work_unit is not None
        and work_completed is not None
        and work_total is not None
        and work_total > 0
    ):
        work_fraction_complete = float(work_completed) / float(work_total)
        if 0.0 < work_fraction_complete < 1.0 and elapsed_seconds > 0:
            eta_seconds = round(
                (elapsed_seconds / work_fraction_complete) - elapsed_seconds, 3
            )
    elif 0.0 < stage_fraction_complete < 1.0 and elapsed_seconds > 0:
        eta_seconds = round(
            (elapsed_seconds / stage_fraction_complete) - elapsed_seconds, 3
        )
    progress_callback(
        "structural_feed_progress",
        {
            "stage": stage,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "stage_fraction_complete": round(stage_fraction_complete, 4),
            "work_fraction_complete": round(work_fraction_complete, 4)
            if work_fraction_complete is not None
            else None,
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
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
) -> dict[str, Any]:
    """Emit a bounded structural IR feed for downstream consumer contracts.

    This stays reducer-first and provenance-aware. It exposes predicate atoms,
    structural signal atoms, and a small constraint receipt without assigning
    semantic authority to lexical overlap alone. Latent fibre enrichment uses
    the same pinned-index schema/hash validation and exact-fallback behavior as
    ``collect_canonical_predicate_atoms``.
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
        if (
            fraction_complete > 0.0
            and fraction_complete < 1.0
            and bundle_elapsed_seconds > 0
        ):
            bundle_eta_seconds = round(
                (bundle_elapsed_seconds / fraction_complete) - bundle_elapsed_seconds, 3
            )
        progress_callback(
            "structural_feed_progress",
            {
                "stage": "relational_bundle_progress",
                "completed_steps": round(fraction_complete, 4),
                "total_steps": 1.0,
                "stage_fraction_complete": round(
                    fraction_complete / float(total_steps), 4
                ),
                "work_fraction_complete": round(
                    (
                        float(details.get("words_done") or 0)
                        / float(details.get("total_words") or 1)
                    ),
                    4,
                )
                if int(details.get("total_words") or 0) > 0
                else None,
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
        progress_callback=bundle_progress_callback
        if progress_callback is not None
        else None,
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
    predicate_atoms = _apply_utterance_latent_fibres(
        predicate_atoms,
        enable_utterance_latent_fibres=bool(enable_utterance_latent_fibres),
        utterance_latent_fibre_index=utterance_latent_fibre_index,
    )
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
    legal_occurrences = tuple(
        collect_lexeme_occurrences(text, canonical_mode=canonical_mode)
    )
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
        if progress_callback is not None and (
            index == 1 or index == total_signal_occurrences or index % 2048 == 0
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
    expected_provenance_upper_bound = sum(
        len(atom.provenance) for atom in predicate_atoms
    ) + len(signal_atoms)
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
    enable_utterance_latent_fibres: bool = True,
    utterance_latent_fibre_index: str
    | UtteranceLatentIndex
    | os.PathLike[str]
    | None = None,
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
                "tokenizer_profile_id": get_canonical_tokenizer_profile_receipt()[
                    "profile_id"
                ],
                "evidence_only": True,
            },
        }
    return collect_canonical_structural_ir_feed(
        text,
        canonical_mode=canonical_mode,
        progress_callback=progress_callback,
        enable_utterance_latent_fibres=enable_utterance_latent_fibres,
        utterance_latent_fibre_index=utterance_latent_fibre_index,
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
                "occurrence_id": hashlib.sha256(
                    occurrence_seed.encode("utf-8")
                ).hexdigest()[:16],
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
