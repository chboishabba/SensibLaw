from __future__ import annotations

"""Deterministic residual lattice helpers for predicate-ready structural atoms.

This module does not parse text, infer semantics, or classify domains. It only
compares explicit predicate/role/modifier payloads that upstream parser and
reducer layers already emitted.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ResidualLevel(IntEnum):
    """Ordered residual severity.

    EXACT < PARTIAL < NO_TYPED_MEET < CONTRADICTION
    """

    EXACT = 0
    PARTIAL = 1
    NO_TYPED_MEET = 2
    CONTRADICTION = 3


@dataclass(frozen=True, slots=True)
class TypedArg:
    """Typed role binding used in predicate normal form."""

    value: str
    entity_type: str | None = None
    provenance: tuple[str, ...] = ()
    status: str = "bound"
    cardinality: str = "single"
    members: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "value": self.value,
            "provenance": list(self.provenance),
            "status": self.status,
            "cardinality": self.cardinality,
        }
        if self.entity_type is not None:
            payload["entity_type"] = self.entity_type
        if self.members:
            payload["members"] = list(self.members)
        return payload


@dataclass(frozen=True, slots=True)
class QualifierState:
    polarity: str = "positive"
    modality: str | None = None
    tense: str | None = None
    certainty: str | None = None
    condition: str | None = None
    temporal_scope: str | None = None
    jurisdiction_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"polarity": self.polarity}
        if self.modality is not None:
            payload["modality"] = self.modality
        if self.tense is not None:
            payload["tense"] = self.tense
        if self.certainty is not None:
            payload["certainty"] = self.certainty
        if self.condition is not None:
            payload["condition"] = self.condition
        if self.temporal_scope is not None:
            payload["temporal_scope"] = self.temporal_scope
        if self.jurisdiction_scope is not None:
            payload["jurisdiction_scope"] = self.jurisdiction_scope
        return payload


@dataclass(frozen=True, slots=True)
class WrapperState:
    status: str | None = None
    evidence_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = {"evidence_only": self.evidence_only}
        if self.status is not None:
            payload["status"] = self.status
        return payload


@dataclass(frozen=True, slots=True)
class PredicatePNF:
    """Canonical predicate carrier separating structure, qualifiers, and wrapper state."""

    predicate: str
    structural_signature: str
    roles: Mapping[str, TypedArg]
    qualifiers: QualifierState = field(default_factory=QualifierState)
    wrapper: WrapperState = field(default_factory=WrapperState)
    modifiers: Mapping[str, Any] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()
    atom_id: str | None = None
    domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "predicate": self.predicate,
            "structural_signature": self.structural_signature,
            "roles": {key: value.to_dict() for key, value in self.roles.items()},
            "qualifiers": self.qualifiers.to_dict(),
            "wrapper": self.wrapper.to_dict(),
            "modifiers": dict(self.modifiers),
            "provenance": list(self.provenance),
        }
        if self.atom_id is not None:
            payload["atom_id"] = self.atom_id
        if self.domain is not None:
            payload["domain"] = self.domain
        return payload


@dataclass(frozen=True, slots=True)
class PredicateAtom(PredicatePNF):
    """Compatibility subtype for bounded residual comparison."""


@dataclass(frozen=True, slots=True)
class RoleState:
    """Minimal algebraic carrier for slotwise role state."""

    bindings: Mapping[str, TypedArg] = field(default_factory=dict)
    contradictions: tuple[str, ...] = ()
    residuals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bindings": {key: value.to_dict() for key, value in self.bindings.items()},
            "contradictions": list(self.contradictions),
            "residuals": list(self.residuals),
        }


@dataclass(frozen=True, slots=True)
class Residual:
    """Join-stable residual facts for bounded downstream routing."""

    level: ResidualLevel
    shared_roles: Mapping[str, TypedArg] = field(default_factory=dict)
    missing_roles: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.name.lower(),
            "shared_roles": {
                key: value.to_dict() for key, value in self.shared_roles.items()
            },
            "missing_roles": list(self.missing_roles),
            "contradictions": list(self.contradictions),
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class PredicateIndex:
    """Bounded natural indexes over canonical predicate carriers."""

    by_structural_sig: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    by_role_slot: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    by_argval: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    by_role_arg: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_structural_sig": {key: list(value) for key, value in self.by_structural_sig.items()},
            "by_role_slot": {key: list(value) for key, value in self.by_role_slot.items()},
            "by_argval": {key: list(value) for key, value in self.by_argval.items()},
            "by_role_arg": {
                f"{role}|{arg}": list(value) for (role, arg), value in self.by_role_arg.items()
            },
        }


@dataclass(frozen=True, slots=True)
class CandidateResidual:
    """Ordered residual result for one shortlisted candidate."""

    ref: str
    residual: Residual

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "residual": self.residual.to_dict(),
        }


def _normalize_string_mapping(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if key is not None and value is not None
    }


def _normalize_typed_arg(value: Any, *, default_provenance: tuple[str, ...] = ()) -> TypedArg | None:
    if value is None:
        return None
    if isinstance(value, TypedArg):
        return value
    if isinstance(value, Mapping):
        raw_value = value.get("value")
        if raw_value is None:
            return None
        entity_type = value.get("entity_type")
        status = str(value.get("status") or "bound")
        cardinality = str(value.get("cardinality") or "single")
        provenance = _normalize_provenance(value.get("provenance")) or default_provenance
        raw_members = value.get("members")
        members = _normalize_provenance(raw_members)
        return TypedArg(
            value=str(raw_value),
            entity_type=str(entity_type) if entity_type is not None else None,
            provenance=provenance,
            status=status,
            cardinality=cardinality,
            members=members,
        )
    return TypedArg(value=str(value), provenance=default_provenance)


def _normalize_typed_role_mapping(
    raw: Any,
    *,
    default_provenance: tuple[str, ...] = (),
) -> dict[str, TypedArg]:
    if not isinstance(raw, Mapping):
        return {}
    normalized: dict[str, TypedArg] = {}
    for key, value in raw.items():
        if key is None:
            continue
        typed = _normalize_typed_arg(value, default_provenance=default_provenance)
        if typed is None:
            continue
        normalized[str(key)] = typed
    return normalized


def _normalize_generic_mapping(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if key is not None and value is not None
    }


def _normalize_provenance(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Iterable):
        return tuple(str(item) for item in raw if item is not None)
    return (str(raw),)


def _default_structural_signature(predicate: str, roles: Mapping[str, TypedArg]) -> str:
    return predicate


def _predicate_ref(atom: PredicatePNF, index: int) -> str:
    return atom.atom_id or f"pnf:{index}"


def _typed_arg_key(arg: TypedArg) -> str:
    member_key = "|".join(_typed_arg_members(arg))
    if arg.entity_type is None:
        return member_key
    return f"{arg.entity_type}:{member_key}"


def _is_bound_typed_arg(arg: TypedArg) -> bool:
    return arg.status == "bound"


def _typed_arg_members(arg: TypedArg) -> tuple[str, ...]:
    if arg.members:
        return tuple(sorted(set(arg.members)))
    return (arg.value,)


def _allows_multiple_occupants(arg: TypedArg) -> bool:
    return arg.cardinality == "multi"


def _normalize_qualifiers(raw: Any, *, modifiers: Mapping[str, Any]) -> QualifierState:
    if isinstance(raw, QualifierState):
        return raw
    if isinstance(raw, Mapping):
        polarity = str(raw.get("polarity") or "positive")
        return QualifierState(
            polarity=polarity,
            modality=str(raw.get("modality")) if raw.get("modality") is not None else None,
            tense=str(raw.get("tense")) if raw.get("tense") is not None else None,
            certainty=str(raw.get("certainty")) if raw.get("certainty") is not None else None,
            condition=str(raw.get("condition")) if raw.get("condition") is not None else None,
            temporal_scope=(
                str(raw.get("temporal_scope")) if raw.get("temporal_scope") is not None else None
            ),
            jurisdiction_scope=(
                str(raw.get("jurisdiction_scope"))
                if raw.get("jurisdiction_scope") is not None
                else None
            ),
        )
    negation = modifiers.get("negation")
    polarity = "negative" if negation is True else "positive"
    return QualifierState(polarity=polarity)


def _normalize_wrapper(raw: Any) -> WrapperState:
    if isinstance(raw, WrapperState):
        return raw
    if isinstance(raw, Mapping):
        status = raw.get("status")
        evidence_only = bool(raw.get("evidence_only", True))
        return WrapperState(
            status=str(status) if status is not None else None,
            evidence_only=evidence_only,
        )
    return WrapperState()


def coerce_predicate_atom(atom: PredicateAtom | Mapping[str, Any]) -> PredicateAtom | None:
    """Normalize an explicit predicate/role carrier into a stable atom."""

    if isinstance(atom, PredicateAtom):
        return atom
    if not isinstance(atom, Mapping):
        return None

    predicate_raw = atom.get("predicate")
    if predicate_raw is None:
        predicate_raw = atom.get("predicate_key")
    if predicate_raw is None:
        return None

    modifiers = _normalize_generic_mapping(atom.get("modifiers"))
    provenance = _normalize_provenance(atom.get("provenance"))
    roles = _normalize_typed_role_mapping(atom.get("roles"), default_provenance=provenance)
    if not roles:
        return None
    atom_id = atom.get("atom_id")
    if atom_id is None:
        atom_id = atom.get("id")
    domain = atom.get("domain")
    qualifiers = _normalize_qualifiers(atom.get("qualifiers"), modifiers=modifiers)
    wrapper = _normalize_wrapper(atom.get("wrapper"))
    structural_signature = atom.get("structural_signature")
    if structural_signature is None:
        structural_signature = _default_structural_signature(str(predicate_raw), roles)

    return PredicateAtom(
        predicate=str(predicate_raw),
        structural_signature=str(structural_signature),
        roles=roles,
        qualifiers=qualifiers,
        wrapper=wrapper,
        modifiers=modifiers,
        provenance=provenance,
        atom_id=str(atom_id) if atom_id is not None else None,
        domain=str(domain) if domain is not None else None,
    )


def comparable(
    query_atom: PredicateAtom | Mapping[str, Any],
    candidate_atom: PredicateAtom | Mapping[str, Any],
) -> bool:
    """Return whether two explicit atoms are directly comparable."""

    query = coerce_predicate_atom(query_atom)
    candidate = coerce_predicate_atom(candidate_atom)
    if query is None or candidate is None:
        return False
    if query.structural_signature != candidate.structural_signature:
        return False
    if query.domain is not None and candidate.domain is not None and query.domain != candidate.domain:
        return False
    return bool(set(query.roles).intersection(candidate.roles))


def _is_refinable_status(status: str) -> bool:
    return status in {"unresolved", "variable"}


def _status_rank(status: str) -> int:
    if status == "bound":
        return 2
    if status == "variable":
        return 1
    return 0


def join_typed_args(left: TypedArg, right: TypedArg) -> tuple[TypedArg | None, str | None]:
    """Join two typed role bindings when they are slotwise compatible."""

    if (
        left.entity_type is not None
        and right.entity_type is not None
        and left.entity_type != right.entity_type
    ):
        return None, "entity type conflict"

    left_members = _typed_arg_members(left)
    right_members = _typed_arg_members(right)

    if left_members == right_members:
        joined_members = left_members
    elif _is_refinable_status(left.status) and not _is_refinable_status(right.status):
        joined_members = right_members
    elif _is_refinable_status(right.status) and not _is_refinable_status(left.status):
        joined_members = left_members
    elif _allows_multiple_occupants(left) or _allows_multiple_occupants(right):
        joined_members = tuple(sorted(set(left_members).union(right_members)))
    else:
        return None, "value conflict"

    joined_entity_type = left.entity_type or right.entity_type
    joined_status = left.status if _status_rank(left.status) >= _status_rank(right.status) else right.status
    joined_provenance = tuple(sorted(set(left.provenance).union(right.provenance)))
    joined_cardinality = (
        "multi" if _allows_multiple_occupants(left) or _allows_multiple_occupants(right) else "single"
    )
    return (
        TypedArg(
            value=joined_members[0],
            entity_type=joined_entity_type,
            provenance=joined_provenance,
            status=joined_status,
            cardinality=joined_cardinality,
            members=joined_members if len(joined_members) > 1 else (),
        ),
        None,
    )


def join_role_states(left: RoleState, right: RoleState) -> RoleState:
    """Join two role states slotwise without widening beyond explicit contradictions/residuals."""

    bindings: dict[str, TypedArg] = dict(left.bindings)
    contradictions = set(left.contradictions).union(right.contradictions)
    residuals = set(left.residuals).union(right.residuals)

    for role, right_value in right.bindings.items():
        left_value = bindings.get(role)
        if left_value is None:
            bindings[role] = right_value
            continue
        joined_value, error = join_typed_args(left_value, right_value)
        if error is not None or joined_value is None:
            contradictions.add(f"role conflict: {role}")
            continue
        if joined_value != left_value or joined_value != right_value:
            residuals.add(f"role refined: {role}")
        bindings[role] = joined_value

    return RoleState(
        bindings=bindings,
        contradictions=tuple(sorted(contradictions)),
        residuals=tuple(sorted(residuals)),
    )


def join_residual(left: Residual, right: Residual) -> Residual:
    """Return the least upper bound of two residuals."""

    level = ResidualLevel(max(int(left.level), int(right.level)))
    role_state = join_role_states(
        RoleState(bindings=left.shared_roles, contradictions=left.contradictions),
        RoleState(bindings=right.shared_roles, contradictions=right.contradictions),
    )
    return Residual(
        level=level,
        shared_roles=role_state.bindings,
        missing_roles=tuple(sorted(set(left.missing_roles).union(right.missing_roles))),
        contradictions=role_state.contradictions,
        provenance=tuple(sorted(set(left.provenance).union(right.provenance))),
    )


def meet_atom(
    query_atom: PredicateAtom | Mapping[str, Any],
    candidate_atom: PredicateAtom | Mapping[str, Any],
) -> Residual:
    """Compare one explicit query atom against one explicit candidate atom."""

    query = coerce_predicate_atom(query_atom)
    candidate = coerce_predicate_atom(candidate_atom)
    if query is None or candidate is None or not comparable(query, candidate):
        return Residual(level=ResidualLevel.NO_TYPED_MEET)

    query_role_state = RoleState(bindings=query.roles)
    candidate_role_state = RoleState(
        bindings={
            role: (
                TypedArg(
                    value=value.value,
                    entity_type=value.entity_type,
                    provenance=candidate.provenance if not value.provenance and candidate.provenance else value.provenance,
                    status=value.status,
                )
                if not value.provenance and candidate.provenance
                else value
            )
            for role, value in candidate.roles.items()
        }
    )
    missing_roles = set(query.roles)

    for role in query.roles:
        candidate_value = candidate_role_state.bindings.get(role)
        if candidate_value is None:
            continue
        missing_roles.discard(role)

    compared_candidate_state = RoleState(
        bindings={
            role: value
            for role, value in candidate_role_state.bindings.items()
            if role in query.roles
        }
    )
    joined_role_state = join_role_states(query_role_state, compared_candidate_state)
    if joined_role_state.contradictions:
        return Residual(
            level=ResidualLevel.CONTRADICTION,
            contradictions=joined_role_state.contradictions,
            provenance=candidate.provenance,
        )

    if query.qualifiers.polarity != candidate.qualifiers.polarity:
        return Residual(
            level=ResidualLevel.CONTRADICTION,
            contradictions=("polarity conflict",),
            provenance=candidate.provenance,
        )

    if missing_roles:
        return Residual(
            level=ResidualLevel.PARTIAL,
            shared_roles={
                role: value
                for role, value in joined_role_state.bindings.items()
                if role in compared_candidate_state.bindings
            },
            missing_roles=tuple(sorted(missing_roles)),
            provenance=candidate.provenance,
        )

    return Residual(
        level=ResidualLevel.EXACT,
        shared_roles={
            role: value
            for role, value in joined_role_state.bindings.items()
            if role in compared_candidate_state.bindings
        },
        provenance=candidate.provenance,
    )


def compute_residual(
    query_atom: PredicateAtom | Mapping[str, Any],
    atoms: Iterable[PredicateAtom | Mapping[str, Any]],
) -> Residual:
    """Join residuals across all comparable atoms in a bounded set."""

    result = Residual(level=ResidualLevel.EXACT)
    saw_comparable = False

    for atom in atoms:
        if not comparable(query_atom, atom):
            continue
        saw_comparable = True
        result = join_residual(result, meet_atom(query_atom, atom))

    if not saw_comparable:
        return Residual(level=ResidualLevel.NO_TYPED_MEET)
    return result


def build_predicate_index(
    atoms: Iterable[PredicatePNF | PredicateAtom | Mapping[str, Any]],
) -> PredicateIndex:
    """Build bounded natural indexes over canonical predicate carriers."""

    by_structural_sig: dict[str, list[str]] = {}
    by_role_slot: dict[str, list[str]] = {}
    by_argval: dict[str, list[str]] = {}
    by_role_arg: dict[tuple[str, str], list[str]] = {}

    normalized_atoms: list[PredicateAtom] = []
    for atom in atoms:
        normalized = coerce_predicate_atom(atom)
        if normalized is None:
            continue
        normalized_atoms.append(normalized)

    for index, atom in enumerate(normalized_atoms):
        ref = _predicate_ref(atom, index)
        by_structural_sig.setdefault(atom.structural_signature, []).append(ref)
        for role, typed_arg in atom.roles.items():
            by_role_slot.setdefault(role, []).append(ref)
            arg_key = _typed_arg_key(typed_arg)
            by_argval.setdefault(arg_key, []).append(ref)
            by_role_arg.setdefault((role, arg_key), []).append(ref)

    return PredicateIndex(
        by_structural_sig={key: tuple(value) for key, value in by_structural_sig.items()},
        by_role_slot={key: tuple(value) for key, value in by_role_slot.items()},
        by_argval={key: tuple(value) for key, value in by_argval.items()},
        by_role_arg={key: tuple(value) for key, value in by_role_arg.items()},
    )


def build_predicate_ref_map(
    atoms: Iterable[PredicatePNF | PredicateAtom | Mapping[str, Any]],
) -> Mapping[str, PredicateAtom]:
    """Build a stable ref -> canonical atom map aligned with index fallback refs."""

    refs_to_atoms: dict[str, PredicateAtom] = {}
    normalized_atoms: list[PredicateAtom] = []
    for atom in atoms:
        normalized = coerce_predicate_atom(atom)
        if normalized is None:
            continue
        normalized_atoms.append(normalized)

    for index, atom in enumerate(normalized_atoms):
        refs_to_atoms[_predicate_ref(atom, index)] = atom
    return refs_to_atoms


def collect_candidate_predicate_refs(
    query_atom: PredicatePNF | PredicateAtom | Mapping[str, Any],
    predicate_index: PredicateIndex,
) -> tuple[str, ...]:
    """Return a bounded candidate superset for later algebraic comparison.

    This helper is a pure index pre-filter. It narrows by exact structural
    signature first, then required role-slot presence, then exact role-arg keys
    only for bound query arguments. It never decides admissibility or matching;
    residual algebra remains the authoritative comparison layer.
    """

    query = coerce_predicate_atom(query_atom)
    if query is None:
        return ()

    ordered_candidates = predicate_index.by_structural_sig.get(query.structural_signature, ())
    if not ordered_candidates:
        return ()

    allowed_refs = set(ordered_candidates)

    for role in query.roles:
        role_refs = predicate_index.by_role_slot.get(role)
        if not role_refs:
            return ()
        allowed_refs.intersection_update(role_refs)
        if not allowed_refs:
            return ()

    for role, typed_arg in query.roles.items():
        if not _is_bound_typed_arg(typed_arg):
            continue
        role_arg_refs = predicate_index.by_role_arg.get((role, _typed_arg_key(typed_arg)))
        if not role_arg_refs:
            return ()
        allowed_refs.intersection_update(role_arg_refs)
        if not allowed_refs:
            return ()

    return tuple(ref for ref in ordered_candidates if ref in allowed_refs)


def collect_candidate_residuals(
    query_atom: PredicatePNF | PredicateAtom | Mapping[str, Any],
    predicate_index: PredicateIndex,
    atoms_by_ref: Mapping[str, PredicatePNF | PredicateAtom | Mapping[str, Any]],
) -> tuple[CandidateResidual, ...]:
    """Run residual comparison only across the bounded shortlisted refs."""

    candidate_refs = collect_candidate_predicate_refs(query_atom, predicate_index)
    results: list[CandidateResidual] = []
    for ref in candidate_refs:
        atom = atoms_by_ref.get(ref)
        if atom is None:
            continue
        residual = meet_atom(query_atom, atom)
        if residual.level is ResidualLevel.NO_TYPED_MEET:
            continue
        results.append(CandidateResidual(ref=ref, residual=residual))
    return tuple(results)


def compute_indexed_residual(
    query_atom: PredicatePNF | PredicateAtom | Mapping[str, Any],
    predicate_index: PredicateIndex,
    atoms_by_ref: Mapping[str, PredicatePNF | PredicateAtom | Mapping[str, Any]],
) -> Residual:
    """Join residuals only across the bounded shortlisted refs."""

    candidate_residuals = collect_candidate_residuals(query_atom, predicate_index, atoms_by_ref)
    if not candidate_residuals:
        return Residual(level=ResidualLevel.NO_TYPED_MEET)

    result = Residual(level=ResidualLevel.EXACT)
    for candidate in candidate_residuals:
        result = join_residual(result, candidate.residual)
    return result


__all__ = [
    "PredicateIndex",
    "CandidateResidual",
    "PredicatePNF",
    "PredicateAtom",
    "RoleState",
    "TypedArg",
    "QualifierState",
    "WrapperState",
    "Residual",
    "ResidualLevel",
    "coerce_predicate_atom",
    "comparable",
    "compute_residual",
    "build_predicate_index",
    "build_predicate_ref_map",
    "collect_candidate_predicate_refs",
    "collect_candidate_residuals",
    "compute_indexed_residual",
    "join_role_states",
    "join_typed_args",
    "join_residual",
    "meet_atom",
]
