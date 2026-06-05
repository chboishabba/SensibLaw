from __future__ import annotations

"""Corpus-derived latent fibres for utterance predicate atoms.

This module is deliberately read-only and artifact-driven. It does not encode
verb synonym tables or action families; every latent comparison must be backed
by a pinned local index candidate with evidence counts and provenance refs.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .residual_lattice import (
    PredicateAtom,
    Residual,
    ResidualLevel,
    RoleState,
    TypedArg,
    coerce_predicate_atom,
    join_role_states,
    meet_atom,
)


LATENT_FIBRE_INDEX_SCHEMA = "sl.utterance_latent_fibre_index.v0_1"
DEFAULT_MIN_CONFIDENCE = 0.80
DEFAULT_MIN_EVIDENCE_COUNT = 2
DEFAULT_MIN_SIGNAL_COUNT = 2


@dataclass(frozen=True, slots=True)
class LatentFibreCandidate:
    candidate_id: str
    source_predicate: str
    target_predicate: str
    relation: str = "same_family_candidate"
    confidence: float = 0.0
    evidence_count: int = 0
    signal_count: int = 0
    evidence_refs: tuple[str, ...] = ()
    role_context_signatures: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    high_precision: bool = False
    canonical: bool = True
    diagnostics_only: bool = False
    model_refs: tuple[str, ...] = ()

    def supports_canonical(
        self,
        *,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_evidence_count: int = DEFAULT_MIN_EVIDENCE_COUNT,
        min_signal_count: int = DEFAULT_MIN_SIGNAL_COUNT,
    ) -> bool:
        return (
            self.canonical
            and not self.diagnostics_only
            and self.confidence >= min_confidence
            and self.evidence_count >= min_evidence_count
            and self.signal_count >= min_signal_count
            and bool(self.evidence_refs or self.provenance_refs)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_predicate": self.source_predicate,
            "target_predicate": self.target_predicate,
            "relation": self.relation,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "signal_count": self.signal_count,
            "evidence_refs": list(self.evidence_refs),
            "role_context_signatures": list(self.role_context_signatures),
            "provenance_refs": list(self.provenance_refs),
            "high_precision": self.high_precision,
            "canonical": self.canonical,
            "diagnostics_only": self.diagnostics_only,
            "model_refs": list(self.model_refs),
        }


@dataclass(frozen=True, slots=True)
class UtteranceLatentIndex:
    artifact_id: str
    schema_version: str
    source_corpus: Mapping[str, Any]
    extraction_profile: Mapping[str, Any]
    model_assets: tuple[Mapping[str, Any], ...] = ()
    predicate_nodes: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    role_context_signatures: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    candidates: tuple[LatentFibreCandidate, ...] = ()
    artifact_sha256: str | None = None

    def canonical_candidates_for(self, predicate: str) -> tuple[LatentFibreCandidate, ...]:
        matches = (
            candidate
            for candidate in self.candidates
            if candidate.source_predicate == predicate and candidate.supports_canonical()
        )
        return tuple(sorted(matches, key=_candidate_sort_key))


def load_latent_index(path: str | Path) -> UtteranceLatentIndex:
    """Load and validate a pinned local utterance latent fibre artifact."""

    artifact_path = Path(path)
    raw_bytes = artifact_path.read_bytes()
    artifact_hash = hashlib.sha256(raw_bytes).hexdigest()
    payload = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Latent fibre index must be a JSON object")
    return parse_latent_index(payload, artifact_sha256=artifact_hash)


def parse_latent_index(
    payload: Mapping[str, Any],
    *,
    artifact_sha256: str | None = None,
) -> UtteranceLatentIndex:
    schema_version = _required_text(payload, "schema_version")
    if schema_version != LATENT_FIBRE_INDEX_SCHEMA:
        raise ValueError(f"Unsupported latent fibre index schema: {schema_version}")

    declared_hash = _optional_text(payload.get("artifact_sha256"))

    source_corpus = _required_mapping(payload, "source_corpus")
    extraction_profile = _required_mapping(payload, "extraction_profile")
    candidates = tuple(
        sorted(
            (_candidate_from_mapping(item) for item in _mapping_sequence(payload.get("derived_fibre_candidates"))),
            key=_candidate_sort_key,
        )
    )
    if not _optional_text(source_corpus.get("manifest_hash")):
        raise ValueError("Latent fibre index source_corpus.manifest_hash is required")
    if not _optional_text(extraction_profile.get("version")):
        raise ValueError("Latent fibre index extraction_profile.version is required")

    return UtteranceLatentIndex(
        artifact_id=_required_text(payload, "artifact_id"),
        schema_version=schema_version,
        source_corpus=dict(source_corpus),
        extraction_profile=dict(extraction_profile),
        model_assets=tuple(dict(item) for item in _mapping_sequence(payload.get("model_assets", []))),
        predicate_nodes={
            str(key): dict(value)
            for key, value in _required_mapping(payload, "predicate_nodes").items()
            if isinstance(value, Mapping)
        },
        role_context_signatures={
            str(key): dict(value)
            for key, value in _required_mapping(payload, "role_context_signatures").items()
            if isinstance(value, Mapping)
        },
        candidates=candidates,
        artifact_sha256=artifact_sha256 or declared_hash,
    )


def enrich_utterance_atoms(
    atoms: Iterable[PredicateAtom | Mapping[str, Any]],
    latent_index: UtteranceLatentIndex,
    *,
    include_diagnostics: bool = False,
) -> tuple[PredicateAtom, ...]:
    """Attach evidence-only latent support metadata to utterance atoms."""

    enriched: list[PredicateAtom] = []
    for raw_atom in atoms:
        atom = coerce_predicate_atom(raw_atom)
        if atom is None:
            continue
        candidates = _supported_candidates_for_atom(
            atom,
            latent_index,
            include_diagnostics=include_diagnostics,
        )
        if not candidates:
            enriched.append(
                replace(
                    atom,
                    support_fibres=(),
                    latent_grounding={
                        "artifact_id": latent_index.artifact_id,
                        "candidate_refs": [],
                        "confidence": 0.0,
                        "abstention_reason": "no_supported_latent_fibre",
                    },
                    semantic_comparison_mode="abstained",
                )
            )
            continue
        enriched.append(
            replace(
                atom,
                support_fibres=tuple(candidate.to_dict() for candidate in candidates),
                latent_grounding={
                    "artifact_id": latent_index.artifact_id,
                    "candidate_refs": [candidate.candidate_id for candidate in candidates],
                    "confidence": max(candidate.confidence for candidate in candidates),
                    "abstention_reason": None,
                },
                semantic_comparison_mode="latent_candidate",
            )
        )
    return tuple(enriched)


def meet_atom_with_latent_fibres(
    query_atom: PredicateAtom | Mapping[str, Any],
    candidate_atom: PredicateAtom | Mapping[str, Any],
    latent_index: UtteranceLatentIndex,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_evidence_count: int = DEFAULT_MIN_EVIDENCE_COUNT,
    min_signal_count: int = DEFAULT_MIN_SIGNAL_COUNT,
) -> Residual:
    """Compare atoms exactly first, then via bounded corpus-supported fibres."""

    exact = meet_atom(query_atom, candidate_atom)
    if exact.level is not ResidualLevel.NO_TYPED_MEET:
        return exact

    query = coerce_predicate_atom(query_atom)
    candidate = coerce_predicate_atom(candidate_atom)
    if query is None or candidate is None:
        return _abstained_residual(latent_index, "invalid_atom")
    if query.domain != "utterance_event" or candidate.domain != "utterance_event":
        return _abstained_residual(latent_index, "non_utterance_domain")

    fibre = _best_pair_candidate(
        query,
        candidate,
        latent_index,
        min_confidence=min_confidence,
        min_evidence_count=min_evidence_count,
        min_signal_count=min_signal_count,
    )
    if fibre is None:
        return _abstained_residual(latent_index, "no_supported_pair_fibre")

    role_state = _compatible_context_roles(query, candidate)
    grounding = {
        "artifact_id": latent_index.artifact_id,
        "candidate_refs": [fibre.candidate_id],
        "confidence": fibre.confidence,
        "evidence_count": fibre.evidence_count,
        "signal_count": fibre.signal_count,
        "provenance_refs": list(fibre.provenance_refs or fibre.evidence_refs),
        "abstention_reason": None,
    }
    if role_state is None:
        grounding["abstention_reason"] = "role_context_incompatible"
        return Residual(
            level=ResidualLevel.NO_TYPED_MEET,
            semantic_comparison_mode="abstained",
            semantic_relation=fibre.relation,
            latent_grounding=grounding,
            provenance=tuple(fibre.provenance_refs or fibre.evidence_refs),
        )

    if query.qualifiers.polarity != candidate.qualifiers.polarity:
        if fibre.high_precision:
            return Residual(
                level=ResidualLevel.CONTRADICTION,
                shared_roles=role_state.bindings,
                contradictions=("polarity conflict across supported latent fibre",),
                provenance=tuple(fibre.provenance_refs or fibre.evidence_refs),
                semantic_comparison_mode="latent_candidate",
                semantic_relation=fibre.relation,
                latent_grounding=grounding,
            )
        grounding["abstention_reason"] = "latent_fibre_not_high_precision_for_contradiction"
        return Residual(
            level=ResidualLevel.PARTIAL,
            shared_roles=role_state.bindings,
            provenance=tuple(fibre.provenance_refs or fibre.evidence_refs),
            semantic_comparison_mode="abstained",
            semantic_relation=fibre.relation,
            latent_grounding=grounding,
        )

    return Residual(
        level=ResidualLevel.PARTIAL,
        shared_roles=role_state.bindings,
        provenance=tuple(fibre.provenance_refs or fibre.evidence_refs),
        semantic_comparison_mode="latent_candidate",
        semantic_relation=fibre.relation,
        latent_grounding=grounding,
    )


def _candidate_from_mapping(raw: Mapping[str, Any]) -> LatentFibreCandidate:
    return LatentFibreCandidate(
        candidate_id=_required_text(raw, "candidate_id"),
        source_predicate=_required_text(raw, "source_predicate"),
        target_predicate=_required_text(raw, "target_predicate"),
        relation=str(raw.get("relation") or "same_family_candidate"),
        confidence=float(raw.get("confidence") or 0.0),
        evidence_count=int(raw.get("evidence_count") or 0),
        signal_count=int(raw.get("signal_count") or 0),
        evidence_refs=_text_tuple(raw.get("evidence_refs")),
        role_context_signatures=_text_tuple(raw.get("role_context_signatures")),
        provenance_refs=_text_tuple(raw.get("provenance_refs")),
        high_precision=bool(raw.get("high_precision")),
        canonical=bool(raw.get("canonical", True)),
        diagnostics_only=bool(raw.get("diagnostics_only")),
        model_refs=_text_tuple(raw.get("model_refs")),
    )


def _supported_candidates_for_atom(
    atom: PredicateAtom,
    latent_index: UtteranceLatentIndex,
    *,
    include_diagnostics: bool,
) -> tuple[LatentFibreCandidate, ...]:
    matches: list[LatentFibreCandidate] = []
    for candidate in latent_index.candidates:
        if candidate.source_predicate != atom.predicate:
            continue
        if candidate.diagnostics_only and not include_diagnostics:
            continue
        if not include_diagnostics and not candidate.supports_canonical():
            continue
        if candidate.role_context_signatures and not _atom_matches_any_signature(atom, candidate.role_context_signatures):
            continue
        matches.append(candidate)
    return tuple(sorted(matches, key=_candidate_sort_key))


def _best_pair_candidate(
    query: PredicateAtom,
    candidate_atom: PredicateAtom,
    latent_index: UtteranceLatentIndex,
    *,
    min_confidence: float,
    min_evidence_count: int,
    min_signal_count: int,
) -> LatentFibreCandidate | None:
    matches = [
        candidate
        for candidate in latent_index.candidates
        if candidate.source_predicate == query.predicate
        and candidate.target_predicate == candidate_atom.predicate
        and candidate.supports_canonical(
            min_confidence=min_confidence,
            min_evidence_count=min_evidence_count,
            min_signal_count=min_signal_count,
        )
        and (
            not candidate.role_context_signatures
            or _atom_matches_any_signature(query, candidate.role_context_signatures)
            or _atom_matches_any_signature(candidate_atom, candidate.role_context_signatures)
        )
    ]
    if not matches:
        return None
    return sorted(matches, key=_candidate_sort_key)[0]


def _compatible_context_roles(left: PredicateAtom, right: PredicateAtom) -> RoleState | None:
    shared_roles = sorted((set(left.roles).intersection(right.roles)) - {"action"})
    if not shared_roles:
        return None
    left_state = RoleState(bindings={role: left.roles[role] for role in shared_roles})
    right_state = RoleState(bindings={role: _with_fallback_provenance(right.roles[role], right.provenance) for role in shared_roles})
    joined = join_role_states(left_state, right_state)
    if joined.contradictions:
        return None
    return joined


def _with_fallback_provenance(arg: TypedArg, provenance: tuple[str, ...]) -> TypedArg:
    if arg.provenance or not provenance:
        return arg
    return TypedArg(
        value=arg.value,
        entity_type=arg.entity_type,
        provenance=provenance,
        status=arg.status,
        cardinality=arg.cardinality,
        members=arg.members,
    )


def _atom_matches_any_signature(atom: PredicateAtom, signatures: tuple[str, ...]) -> bool:
    atom_signatures = set(_atom_role_context_signatures(atom))
    return any(signature in atom_signatures for signature in signatures)


def _atom_role_context_signatures(atom: PredicateAtom) -> tuple[str, ...]:
    typed = tuple(
        f"{role}:{arg.entity_type or '*'}"
        for role, arg in sorted(atom.roles.items())
        if role != "action"
    )
    valued = tuple(
        f"{role}:{arg.entity_type or '*'}={arg.value}"
        for role, arg in sorted(atom.roles.items())
        if role != "action"
    )
    return ("|".join(typed), "|".join(valued))


def _abstained_residual(latent_index: UtteranceLatentIndex, reason: str) -> Residual:
    return Residual(
        level=ResidualLevel.NO_TYPED_MEET,
        semantic_comparison_mode="abstained",
        latent_grounding={
            "artifact_id": latent_index.artifact_id,
            "candidate_refs": [],
            "confidence": 0.0,
            "abstention_reason": reason,
        },
    )


def _candidate_sort_key(candidate: LatentFibreCandidate) -> tuple[Any, ...]:
    return (
        -candidate.confidence,
        -candidate.evidence_count,
        -candidate.signal_count,
        candidate.candidate_id,
    )


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Latent fibre index requires object field: {key}")
    return value


def _mapping_sequence(raw: Any) -> tuple[Mapping[str, Any], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, bytearray)):
        raise ValueError("Expected an array of objects in latent fibre index")
    values = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("Expected object entries in latent fibre index array")
        values.append(item)
    return tuple(values)


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_text(payload.get(key))
    if not value:
        raise ValueError(f"Latent fibre index requires non-empty string field: {key}")
    return value


def _optional_text(raw: Any) -> str:
    return str(raw or "").strip()


def _text_tuple(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,) if raw else ()
    if isinstance(raw, Iterable):
        return tuple(str(item) for item in raw if str(item or "").strip())
    return (str(raw),)


__all__ = [
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_MIN_EVIDENCE_COUNT",
    "DEFAULT_MIN_SIGNAL_COUNT",
    "LATENT_FIBRE_INDEX_SCHEMA",
    "LatentFibreCandidate",
    "UtteranceLatentIndex",
    "enrich_utterance_atoms",
    "load_latent_index",
    "meet_atom_with_latent_fibres",
    "parse_latent_index",
]
