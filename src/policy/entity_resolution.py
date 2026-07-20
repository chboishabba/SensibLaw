"""Generic, receipt-free carriers for span-anchored entity resolution.

The module records candidates and document-local coreference only. It does not
resolve identity, alter PNF, query an external registry, promote a claim, or
join identities across documents.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.sensiblaw.interfaces import (
    parse_canonical_text,
    tokenize_canonical_with_spans,
)


ENTITY_RESOLUTION_SCHEMA_VERSION = "sl.entity_resolution.v0_1"
ENTITY_RESOLUTION_AUTHORITY = "candidate_only"
MENTION_LICENSING_SCHEMA_VERSION = "sl.mention_licensing.v0_1"
MENTION_RECURRENCE_SCHEMA_VERSION = "sl.mention_recurrence.v0_1"
MENTION_EXPANSION_SCHEMA_VERSION = "sl.mention_expansion.v0_1"
ALIAS_EXPANSION_SCHEMA_VERSION = "sl.alias_expansion_requests.v0_1"
GRAMMAR_EXPANSION_SCHEMA_VERSION = "sl.grammar_expansion_requests.v0_1"
CANDIDATE_RETRIEVAL_SCHEMA_VERSION = "sl.candidate_retrieval.v0_1"
FORM_DERIVATION_SCHEMA_VERSION = "sl.form_derivation.v0_1"
LOCAL_TYPING_SCHEMA_VERSION = "sl.local_typing.v0_1"
PARTIAL_PNF_SCHEMA_VERSION = "sl.partial_pnf.v0_1"
RESOLUTION_DEMAND_SCHEMA_VERSION = "sl.resolution_demand.v0_1"
RESOLUTION_SUBJECT_SCHEMA_VERSION = "sl.resolution_subject.v0_1"
RESOLUTION_SCHEDULER_SCHEMA_VERSION = "sl.resolution_scheduler.v0_1"
_CANDIDATE_KINDS = frozenset(
    {
        "instance",
        "class",
        "property",
        "role",
        "event_type",
        "literal",
        "document_local",
    }
)
_STRUCTURAL_LEXEMES = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)
_LICENSE_PRIORITY = {
    "named_entity_shape": 10,
    "eventuality_annotation": 20,
    "numeric_literal": 30,
    "alias_hint": 40,
    "grammar_phrase": 50,
    "pnf_demand": 60,
    "lexical_token": 90,
}
_NOMINAL_GRAMMAR_PROFILE = "nominal_phrase.v0_1"
_NOMINAL_PHRASE_POS = frozenset({"ADJ", "DET", "NOUN", "NUM", "PROPN"})
_NOMINAL_HEAD_POS = frozenset({"NOUN", "PROPN"})
_LOCAL_SEMANTIC_FAMILIES = frozenset(
    {
        "entity",
        "relation",
        "quantity",
        "role",
        "eventuality",
        "class",
        "property",
        "literal",
    }
)
_COVERAGE_STATES = frozenset({"typed", "weakly_typed", "untyped", "not_applicable"})
_PNF_SLOT_KINDS = frozenset(
    {
        "subject",
        "predicate",
        "object",
        "time",
        "location",
        "eventuality",
        "qualifier",
        "modality",
        "polarity",
    }
)
_CLOSURE_REQUIREMENTS = frozenset({"local_type", "external_identity"})
_CLOSURE_STATES = frozenset(
    {
        "locally_closed",
        "requires_external_resolution",
        "requires_local_typing",
        "not_required",
    }
)
_RESOLUTION_SUBJECT_KINDS = frozenset(
    {
        "entity",
        "event_type",
        "event_occurrence",
        "event_artifact",
        "document_local_cluster",
        "property_or_relation",
    }
)
_EVENT_FORMAL_ROLES = frozenset(
    {
        "occurrence",
        "observation",
        "cluster",
        "forecast",
        "report",
        "alert",
        "rolling_state",
    }
)
_EVENT_ARTIFACT_ROLES = _EVENT_FORMAL_ROLES.difference({"occurrence"})
_RESOLUTION_CONSTRAINT_KINDS = frozenset(
    {"temporal", "spatial", "relation", "source_scope"}
)
_RESOLUTION_SOURCE_SCOPES = frozenset({"document_local", "declared_tranche"})
_CACHE_STATES = frozenset({"fresh", "stale", "negative"})
_SCHEDULE_STATES = frozenset(
    {
        "fresh_cache_hit",
        "stale_cache_hit",
        "negative_cache_hit",
        "fetch_planned",
        "backend_unavailable",
        "budget_exhausted",
        "unsupported_demand",
    }
)


def _text(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"entity-resolution carrier requires {field}")
    return normalized


def _refs(values: Sequence[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "reference") for value in values or ()}))


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_mapping(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    """Return a canonical JSON-safe mapping without preserving caller aliases."""

    try:
        encoded = json.dumps(
            dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be JSON-serializable") from error
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError(f"{field} must be a mapping")
    return decoded


@dataclass(frozen=True)
class MentionSpan:
    """One source-addressable mention candidate over canonical text."""

    mention_ref: str
    source_ref: str
    document_ref: str
    start_char: int
    end_char: int
    canonical_surface: str
    generation_reason: str
    grammatical_role: str | None = None
    context_refs: tuple[str, ...] = ()
    start_token: int | None = None
    end_token: int | None = None

    def to_dict(self) -> dict[str, Any]:
        _validate_mention(self)
        payload: dict[str, Any] = {
            "mention_ref": self.mention_ref,
            "source_ref": self.source_ref,
            "document_ref": self.document_ref,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "canonical_surface": self.canonical_surface,
            "generation_reason": self.generation_reason,
            "context_refs": list(_refs(self.context_refs)),
        }
        if self.grammatical_role:
            payload["grammatical_role"] = self.grammatical_role
        if self.start_token is not None:
            payload["start_token"] = self.start_token
            payload["end_token"] = self.end_token
        return payload


@dataclass(frozen=True)
class EntityCandidate:
    """A possible local or external identity with evidence references only."""

    candidate_ref: str
    candidate_kind: str
    identity_ref: str
    label: str
    evidence_refs: tuple[str, ...] = ()
    registry_snapshot_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        _validate_candidate(self)
        payload: dict[str, Any] = {
            "candidate_ref": self.candidate_ref,
            "candidate_kind": self.candidate_kind,
            "identity_ref": self.identity_ref,
            "label": self.label,
            "evidence_refs": list(_refs(self.evidence_refs)),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if self.registry_snapshot_ref:
            payload["registry_snapshot_ref"] = self.registry_snapshot_ref
        return payload


@dataclass(frozen=True)
class FormCandidate:
    """One typed linguistic-form alternative anchored through a mention.

    A form is not an entity candidate. Its payload may describe a number,
    date-shaped structure, abbreviation, or another language-profile result,
    but cannot select an external identity or promote a claim.
    """

    form_ref: str
    mention_ref: str
    form_type: str
    normalized_payload: Mapping[str, Any]
    derivation_basis: str
    start_token: int
    end_token: int
    ambiguity_state: str = "alternative"

    def to_dict(self) -> dict[str, Any]:
        form_ref = _text(self.form_ref, "form_ref")
        mention_ref = _text(self.mention_ref, "form mention_ref")
        form_type = _text(self.form_type, "form_type")
        derivation_basis = _text(self.derivation_basis, "form derivation_basis")
        if self.start_token < 0 or self.end_token <= self.start_token:
            raise ValueError("form token range must be non-empty and non-negative")
        if self.ambiguity_state != "alternative":
            raise ValueError("form candidates must remain alternatives")
        if (
            not isinstance(self.normalized_payload, Mapping)
            or not self.normalized_payload
        ):
            raise ValueError("form candidates require a normalized payload")
        payload = _json_mapping(self.normalized_payload, "form normalized_payload")
        forbidden = {
            "candidate_ref",
            "identity_ref",
            "resolved_identity_ref",
            "selected_candidate_ref",
            "promotion_state",
        }
        if forbidden.intersection(payload):
            raise ValueError("form payload cannot carry entity resolution or promotion")
        return {
            "form_ref": form_ref,
            "mention_ref": mention_ref,
            "form_type": form_type,
            "normalized_payload": payload,
            "derivation_basis": derivation_basis,
            "start_token": self.start_token,
            "end_token": self.end_token,
            "ambiguity_state": self.ambiguity_state,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class FormRelation:
    """A declared non-resolving relation between two form alternatives."""

    relation_ref: str
    left_form_ref: str
    relation_kind: str
    right_form_ref: str
    derivation_basis: str

    def to_dict(self) -> dict[str, Any]:
        relation_ref = _text(self.relation_ref, "form relation_ref")
        left_form_ref = _text(self.left_form_ref, "form relation left_form_ref")
        right_form_ref = _text(self.right_form_ref, "form relation right_form_ref")
        relation_kind = _text(self.relation_kind, "form relation_kind")
        derivation_basis = _text(
            self.derivation_basis, "form relation derivation_basis"
        )
        if left_form_ref == right_form_ref:
            raise ValueError("form relations must connect distinct forms")
        return {
            "relation_ref": relation_ref,
            "left_form_ref": left_form_ref,
            "relation_kind": relation_kind,
            "right_form_ref": right_form_ref,
            "derivation_basis": derivation_basis,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class FormLexiconEntry:
    """One profile-supplied lexical form fact, not an entity alias."""

    entry_ref: str
    token_sequence: tuple[str, ...]
    form_type: str
    normalized_payload: Mapping[str, Any]
    relation_kind: str
    evidence_refs: tuple[str, ...]
    derivation_basis: str = "profile_lexicon"

    def to_dict(self) -> dict[str, Any]:
        entry_ref = _text(self.entry_ref, "form lexicon entry_ref")
        token_sequence = _normalized_alias_tokens(self.token_sequence)
        if not token_sequence:
            raise ValueError("form lexicon entries require a token sequence")
        evidence_refs = _refs(self.evidence_refs)
        if not evidence_refs:
            raise ValueError("form lexicon entries require evidence references")
        form = FormCandidate(
            form_ref=f"form-lexicon:{entry_ref}",
            mention_ref="form-lexicon",
            form_type=self.form_type,
            normalized_payload=self.normalized_payload,
            derivation_basis=self.derivation_basis,
            start_token=0,
            end_token=1,
        ).to_dict()
        return {
            "entry_ref": entry_ref,
            "token_sequence": list(token_sequence),
            "form_type": form["form_type"],
            "normalized_payload": form["normalized_payload"],
            "relation_kind": _text(self.relation_kind, "form lexicon relation_kind"),
            "evidence_refs": list(evidence_refs),
            "derivation_basis": form["derivation_basis"],
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class FormCompositionRule:
    """A declarative adjacent-form rule supplied by a language profile."""

    rule_ref: str
    component_form_types: tuple[str, ...]
    output_form_type: str
    payload_keys: tuple[str, ...]
    derivation_basis: str = "profile_composition"

    def to_dict(self) -> dict[str, Any]:
        component_types = tuple(
            _text(value, "form composition component type")
            for value in self.component_form_types
        )
        payload_keys = tuple(
            _text(value, "form composition payload key") for value in self.payload_keys
        )
        if len(component_types) < 2 or len(component_types) != len(payload_keys):
            raise ValueError(
                "form composition requires matching component types and keys"
            )
        if len(set(payload_keys)) != len(payload_keys):
            raise ValueError("form composition payload keys must be unique")
        return {
            "rule_ref": _text(self.rule_ref, "form composition rule_ref"),
            "component_form_types": list(component_types),
            "output_form_type": _text(
                self.output_form_type, "form composition output_form_type"
            ),
            "payload_keys": list(payload_keys),
            "derivation_basis": _text(
                self.derivation_basis, "form composition derivation_basis"
            ),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class LocalTypeAlternative:
    """One local semantic type alternative, never an external identity."""

    type_ref: str
    mention_ref: str
    semantic_family: str
    local_type: str
    derivation_basis: str
    evidence_refs: tuple[str, ...]
    form_ref: str | None = None
    ambiguity_state: str = "alternative"

    def to_dict(self) -> dict[str, Any]:
        semantic_family = _text(self.semantic_family, "local semantic_family")
        if semantic_family not in _LOCAL_SEMANTIC_FAMILIES:
            raise ValueError(f"unsupported local semantic family: {semantic_family}")
        if self.ambiguity_state != "alternative":
            raise ValueError("local types must remain alternatives")
        evidence_refs = _refs(self.evidence_refs)
        if not evidence_refs:
            raise ValueError("local type alternatives require evidence references")
        payload: dict[str, Any] = {
            "type_ref": _text(self.type_ref, "local type_ref"),
            "mention_ref": _text(self.mention_ref, "local type mention_ref"),
            "semantic_family": semantic_family,
            "local_type": _text(self.local_type, "local_type"),
            "derivation_basis": _text(
                self.derivation_basis, "local type derivation_basis"
            ),
            "evidence_refs": list(evidence_refs),
            "ambiguity_state": self.ambiguity_state,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if self.form_ref:
            payload["form_ref"] = _text(self.form_ref, "local type form_ref")
        return payload


@dataclass(frozen=True)
class LocalTypingRule:
    """A provenance-bearing local typing reduction over one form type."""

    rule_ref: str
    form_type: str
    semantic_family: str
    local_type: str
    evidence_refs: tuple[str, ...]
    derivation_basis: str = "profile_local_typing"

    def to_dict(self) -> dict[str, Any]:
        alternative = LocalTypeAlternative(
            type_ref=f"local-typing-rule:{self.rule_ref}",
            mention_ref="local-typing-rule",
            form_ref="form-type-rule",
            semantic_family=self.semantic_family,
            local_type=self.local_type,
            derivation_basis=self.derivation_basis,
            evidence_refs=self.evidence_refs,
        ).to_dict()
        return {
            "rule_ref": _text(self.rule_ref, "local typing rule_ref"),
            "form_type": _text(self.form_type, "local typing form_type"),
            "semantic_family": alternative["semantic_family"],
            "local_type": alternative["local_type"],
            "evidence_refs": alternative["evidence_refs"],
            "derivation_basis": alternative["derivation_basis"],
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class CoveragePressureAssessment:
    """Candidate-world typing coverage for one anchored mention."""

    mention_ref: str
    coverage_state: str
    reason_codes: tuple[str, ...]
    local_type_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        coverage_state = _text(self.coverage_state, "coverage_state")
        if coverage_state not in _COVERAGE_STATES:
            raise ValueError(f"unsupported coverage state: {coverage_state}")
        reasons = _refs(self.reason_codes)
        if not reasons:
            raise ValueError("coverage assessments require reason codes")
        type_refs = _refs(self.local_type_refs)
        if coverage_state == "typed" and not type_refs:
            raise ValueError("typed coverage requires local type references")
        if coverage_state != "typed" and type_refs:
            raise ValueError("non-typed coverage cannot carry local type references")
        return {
            "mention_ref": _text(self.mention_ref, "coverage mention_ref"),
            "coverage_state": coverage_state,
            "reason_codes": list(reasons),
            "local_type_refs": list(type_refs),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class PartialPNFSlot:
    """A declared local PNF slot, before identity or claim closure."""

    slot_ref: str
    slot_kind: str
    expected_semantic_families: tuple[str, ...]
    closure_requirement: str
    mention_ref: str | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        slot_kind = _text(self.slot_kind, "PNF slot_kind")
        if slot_kind not in _PNF_SLOT_KINDS:
            raise ValueError(f"unsupported PNF slot kind: {slot_kind}")
        expected_families = tuple(
            sorted(
                {
                    _text(value, "PNF expected semantic family")
                    for value in self.expected_semantic_families
                }
            )
        )
        if not expected_families:
            raise ValueError("PNF slots require expected semantic families")
        if any(family not in _LOCAL_SEMANTIC_FAMILIES for family in expected_families):
            raise ValueError("PNF slots contain unsupported semantic families")
        closure_requirement = _text(self.closure_requirement, "PNF closure_requirement")
        if closure_requirement not in _CLOSURE_REQUIREMENTS:
            raise ValueError(
                f"unsupported PNF closure requirement: {closure_requirement}"
            )
        if self.required and not self.mention_ref:
            raise ValueError("required PNF slots require a mention reference")
        payload: dict[str, Any] = {
            "slot_ref": _text(self.slot_ref, "PNF slot_ref"),
            "slot_kind": slot_kind,
            "expected_semantic_families": list(expected_families),
            "closure_requirement": closure_requirement,
            "required": self.required,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if self.mention_ref:
            payload["mention_ref"] = _text(self.mention_ref, "PNF slot mention_ref")
        return payload


@dataclass(frozen=True)
class PartialPNF:
    """One document-bounded factorized PNF skeleton."""

    pnf_ref: str
    document_ref: str
    slots: tuple[PartialPNFSlot, ...]

    def to_dict(self) -> dict[str, Any]:
        slots = sorted(
            (slot.to_dict() for slot in self.slots),
            key=lambda slot: slot["slot_ref"],
        )
        slot_refs = [slot["slot_ref"] for slot in slots]
        if not slots:
            raise ValueError("partial PNFs require slots")
        if len(slot_refs) != len(set(slot_refs)):
            raise ValueError("partial PNF slot references must be unique")
        return {
            "pnf_ref": _text(self.pnf_ref, "partial PNF ref"),
            "document_ref": _text(self.document_ref, "partial PNF document_ref"),
            "slots": slots,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class PNFSlotAlternative:
    """A factorized link from a PNF slot to one local type alternative."""

    alternative_ref: str
    pnf_ref: str
    slot_ref: str
    local_type_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "alternative_ref": _text(self.alternative_ref, "PNF alternative_ref"),
            "pnf_ref": _text(self.pnf_ref, "PNF alternative pnf_ref"),
            "slot_ref": _text(self.slot_ref, "PNF alternative slot_ref"),
            "local_type_ref": _text(
                self.local_type_ref, "PNF alternative local_type_ref"
            ),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class ClosurePressureAssessment:
    """One non-resolving closure obligation for a declared PNF slot."""

    pnf_ref: str
    slot_ref: str
    closure_state: str
    reason_codes: tuple[str, ...]
    slot_alternative_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        closure_state = _text(self.closure_state, "closure_state")
        if closure_state not in _CLOSURE_STATES:
            raise ValueError(f"unsupported closure state: {closure_state}")
        reasons = _refs(self.reason_codes)
        if not reasons:
            raise ValueError("closure assessments require reason codes")
        alternatives = _refs(self.slot_alternative_refs)
        if (
            closure_state in {"locally_closed", "requires_external_resolution"}
            and not alternatives
        ):
            raise ValueError("bound closure states require slot alternatives")
        if closure_state in {"requires_local_typing", "not_required"} and alternatives:
            raise ValueError("unbound closure states cannot carry slot alternatives")
        return {
            "pnf_ref": _text(self.pnf_ref, "closure PNF ref"),
            "slot_ref": _text(self.slot_ref, "closure slot_ref"),
            "closure_state": closure_state,
            "reason_codes": list(reasons),
            "slot_alternative_refs": list(alternatives),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class ResolutionDemand:
    """A bounded evidence request plan derived from one PNF closure obligation."""

    demand_ref: str
    pnf_ref: str
    slot_ref: str
    mention_ref: str
    expected_semantic_families: tuple[str, ...]
    requested_facets: tuple[str, ...]
    source_closure_state: str
    budget_class: str

    def to_dict(self) -> dict[str, Any]:
        closure_state = _text(self.source_closure_state, "demand closure state")
        if closure_state not in {
            "requires_external_resolution",
            "requires_local_typing",
        }:
            raise ValueError("resolution demands require an unresolved closure state")
        expected_families = tuple(
            sorted(
                {
                    _text(value, "demand expected semantic family")
                    for value in self.expected_semantic_families
                }
            )
        )
        if not expected_families or any(
            family not in _LOCAL_SEMANTIC_FAMILIES for family in expected_families
        ):
            raise ValueError("resolution demands require supported semantic families")
        requested_facets = _refs(self.requested_facets)
        if not requested_facets:
            raise ValueError("resolution demands require requested facets")
        return {
            "demand_ref": _text(self.demand_ref, "resolution demand_ref"),
            "pnf_ref": _text(self.pnf_ref, "resolution demand PNF ref"),
            "slot_ref": _text(self.slot_ref, "resolution demand slot ref"),
            "mention_ref": _text(self.mention_ref, "resolution demand mention ref"),
            "expected_semantic_families": list(expected_families),
            "requested_facets": list(requested_facets),
            "source_closure_state": closure_state,
            "budget_class": _text(self.budget_class, "resolution demand budget_class"),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class ResolutionConstraint:
    """One typed, candidate-only constraint on a resolution subject."""

    constraint_ref: str
    constraint_kind: str
    payload: Mapping[str, Any]
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        constraint_kind = _text(self.constraint_kind, "resolution constraint_kind")
        if constraint_kind not in _RESOLUTION_CONSTRAINT_KINDS:
            raise ValueError(
                f"unsupported resolution constraint kind: {constraint_kind}"
            )
        payload = _json_mapping(self.payload, "resolution constraint payload")
        if not payload:
            raise ValueError("resolution constraints require a payload")
        forbidden = {
            "backend",
            "identity_ref",
            "promotion_state",
            "resolved_identity_ref",
            "selected_candidate_ref",
        }
        if forbidden.intersection(payload):
            raise ValueError(
                "resolution constraints cannot carry backend, identity, or promotion"
            )
        evidence_refs = _refs(self.evidence_refs)
        if not evidence_refs:
            raise ValueError("resolution constraints require evidence references")
        return {
            "constraint_ref": _text(self.constraint_ref, "resolution constraint_ref"),
            "constraint_kind": constraint_kind,
            "payload": payload,
            "evidence_refs": list(evidence_refs),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class ResolutionSubjectDeclaration:
    """An explicit subject interpretation for one unresolved demand."""

    declaration_ref: str
    demand_ref: str
    target_ref: str
    subject_kind: str
    constraints: tuple[ResolutionConstraint, ...] = ()
    formal_role: str | None = None
    source_scope: str = "document_local"

    def to_dict(self) -> dict[str, Any]:
        subject_kind = _text(self.subject_kind, "resolution subject_kind")
        if subject_kind not in _RESOLUTION_SUBJECT_KINDS:
            raise ValueError(f"unsupported resolution subject kind: {subject_kind}")
        formal_role = (
            _text(self.formal_role, "resolution subject formal_role")
            if self.formal_role
            else None
        )
        if subject_kind == "event_occurrence" and formal_role != "occurrence":
            raise ValueError(
                "event occurrence subjects require the occurrence formal role"
            )
        if (
            subject_kind == "event_artifact"
            and formal_role not in _EVENT_ARTIFACT_ROLES
        ):
            raise ValueError("event artifact subjects require an artifact formal role")
        if subject_kind not in {"event_occurrence", "event_artifact"} and formal_role:
            raise ValueError("non-event subjects cannot carry an event formal role")
        source_scope = _text(self.source_scope, "resolution subject source_scope")
        if source_scope not in _RESOLUTION_SOURCE_SCOPES:
            raise ValueError(f"unsupported resolution source scope: {source_scope}")
        constraints = sorted(
            (constraint.to_dict() for constraint in self.constraints),
            key=lambda constraint: constraint["constraint_ref"],
        )
        constraint_refs = [constraint["constraint_ref"] for constraint in constraints]
        if len(constraint_refs) != len(set(constraint_refs)):
            raise ValueError("resolution constraint references must be unique")
        payload: dict[str, Any] = {
            "declaration_ref": _text(
                self.declaration_ref, "resolution subject declaration_ref"
            ),
            "demand_ref": _text(self.demand_ref, "resolution subject demand_ref"),
            "target_ref": _text(self.target_ref, "resolution subject target_ref"),
            "subject_kind": subject_kind,
            "source_scope": source_scope,
            "constraints": constraints,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if formal_role:
            payload["formal_role"] = formal_role
        return payload


@dataclass(frozen=True)
class ResolutionCacheEntry:
    """Immutable execution evidence metadata; never a resolved identity."""

    cache_key: str
    backend_ref: str
    cache_state: str
    evidence_ref: str | None = None
    snapshot_ref: str | None = None
    freshness_ref: str | None = None
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        state = _text(self.cache_state, "cache entry state")
        if state not in _CACHE_STATES:
            raise ValueError(f"unsupported cache entry state: {state}")
        if state == "negative" and (self.evidence_ref or self.snapshot_ref):
            raise ValueError("negative cache entries cannot carry evidence snapshots")
        if state != "negative" and not self.evidence_ref:
            raise ValueError("positive cache entries require evidence_ref")
        payload: dict[str, Any] = {
            "cache_key": _text(self.cache_key, "cache entry cache_key"),
            "backend_ref": _text(self.backend_ref, "cache entry backend_ref"),
            "cache_state": state,
            "provenance_refs": list(_refs(self.provenance_refs)),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if self.evidence_ref:
            payload["evidence_ref"] = _text(
                self.evidence_ref, "cache entry evidence_ref"
            )
        if self.snapshot_ref:
            payload["snapshot_ref"] = _text(
                self.snapshot_ref, "cache entry snapshot_ref"
            )
        if self.freshness_ref:
            payload["freshness_ref"] = _text(
                self.freshness_ref, "cache entry freshness_ref"
            )
        if state != "negative" and not payload["provenance_refs"]:
            raise ValueError("positive cache entries require provenance references")
        return payload


@dataclass(frozen=True)
class ResolutionBackendCapability:
    """A declarative backend capability used only for schedule planning."""

    backend_ref: str
    subject_kinds: tuple[str, ...]
    formal_roles: tuple[str, ...] = ()
    facets: tuple[str, ...] = ()
    available: bool = True
    accepts_stale: bool = False
    max_batch_size: int = 1
    rate_limit_class: str = "default"

    def to_dict(self) -> dict[str, Any]:
        kinds = tuple(
            sorted({_text(kind, "backend subject kind") for kind in self.subject_kinds})
        )
        if not kinds or any(kind not in _RESOLUTION_SUBJECT_KINDS for kind in kinds):
            raise ValueError("backend capabilities require supported subject kinds")
        roles = _refs(self.formal_roles)
        if any(role not in _EVENT_FORMAL_ROLES for role in roles):
            raise ValueError("backend capabilities contain unsupported event roles")
        facets = _refs(self.facets)
        if self.max_batch_size < 1:
            raise ValueError("backend max_batch_size must be positive")
        return {
            "backend_ref": _text(self.backend_ref, "backend_ref"),
            "subject_kinds": list(kinds),
            "formal_roles": list(roles),
            "facets": list(facets),
            "available": bool(self.available),
            "accepts_stale": bool(self.accepts_stale),
            "max_batch_size": int(self.max_batch_size),
            "rate_limit_class": _text(self.rate_limit_class, "rate_limit_class"),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class CandidateCatalogEntry:
    """One bounded, provenance-bearing candidate input for exact retrieval.

    The entry represents a possible candidate supplied by an already bounded
    catalog or pinned snapshot. ``match_token_sequences`` defines only lexical
    admission in the canonical tokenizer's space; it does not resolve a
    mention to this identity or rank it above another matching entry.
    """

    catalog_entry_ref: str
    candidate_kind: str
    identity_ref: str
    label: str
    match_token_sequences: tuple[tuple[str, ...], ...]
    evidence_refs: tuple[str, ...]
    registry_snapshot_ref: str | None = None
    normalization_profile: str = "casefold_token_sequence.v0_1"

    def to_dict(self) -> dict[str, Any]:
        catalog_entry_ref = _text(self.catalog_entry_ref, "catalog entry_ref")
        if self.normalization_profile != "casefold_token_sequence.v0_1":
            raise ValueError("unsupported catalog normalization profile")
        candidate = EntityCandidate(
            candidate_ref=f"catalog-candidate:{catalog_entry_ref}",
            candidate_kind=self.candidate_kind,
            identity_ref=self.identity_ref,
            label=self.label,
            evidence_refs=self.evidence_refs,
            registry_snapshot_ref=self.registry_snapshot_ref,
        ).to_dict()
        match_sequences = tuple(
            sorted(
                {
                    _normalized_alias_tokens(sequence)
                    for sequence in self.match_token_sequences
                }
            )
        )
        if not match_sequences or any(not sequence for sequence in match_sequences):
            raise ValueError("catalog entries require match token sequences")
        evidence_refs = _refs(self.evidence_refs)
        if not evidence_refs:
            raise ValueError("catalog entries require evidence references")
        payload: dict[str, Any] = {
            "catalog_entry_ref": catalog_entry_ref,
            "candidate_kind": candidate["candidate_kind"],
            "identity_ref": candidate["identity_ref"],
            "label": candidate["label"],
            "match_token_sequences": [list(sequence) for sequence in match_sequences],
            "evidence_refs": list(evidence_refs),
            "registry_snapshot_ref": candidate.get("registry_snapshot_ref"),
            "normalization_profile": self.normalization_profile,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if candidate.get("registry_snapshot_ref"):
            payload["registry_snapshot_ref"] = candidate["registry_snapshot_ref"]
        return payload


@dataclass(frozen=True)
class EntityCandidateSet:
    """Semantically unordered alternatives with deterministic serialization."""

    mention_ref: str
    candidates: tuple[EntityCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        mention_ref = _text(self.mention_ref, "candidate-set mention_ref")
        candidates = sorted(
            (candidate.to_dict() for candidate in self.candidates),
            key=lambda candidate: candidate["candidate_ref"],
        )
        candidate_refs = [candidate["candidate_ref"] for candidate in candidates]
        if len(candidate_refs) != len(set(candidate_refs)):
            raise ValueError("entity candidate references must be unique per mention")
        return {
            "mention_ref": mention_ref,
            "candidates": candidates,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class CoreferenceCluster:
    """A document-bounded cluster that preserves, rather than resolves, aliases."""

    cluster_ref: str
    document_ref: str
    member_mention_refs: tuple[str, ...]
    candidate_set_refs: tuple[str, ...] = ()
    context_ref: str | None = None
    scope: str = "document_local"

    def to_dict(self) -> dict[str, Any]:
        cluster_ref = _text(self.cluster_ref, "cluster_ref")
        document_ref = _text(self.document_ref, "cluster document_ref")
        if self.scope != "document_local":
            raise ValueError("coreference clusters must remain document_local")
        members = _refs(self.member_mention_refs)
        if not members:
            raise ValueError("coreference clusters require member mentions")
        payload: dict[str, Any] = {
            "cluster_ref": cluster_ref,
            "document_ref": document_ref,
            "member_mention_refs": list(members),
            "candidate_set_refs": list(_refs(self.candidate_set_refs)),
            "scope": self.scope,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if self.context_ref:
            payload["context_ref"] = self.context_ref
        return payload


@dataclass(frozen=True)
class MentionLicense:
    """A cheap admission record, not an accepted mention or identity decision."""

    license_ref: str
    mention_ref: str
    license_kind: str
    expected_candidate_kinds: tuple[str, ...]
    local_type_hypotheses: tuple[str, ...] = ()
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        license_ref = _text(self.license_ref, "license_ref")
        mention_ref = _text(self.mention_ref, "license mention_ref")
        license_kind = _text(self.license_kind, "license_kind")
        if license_kind not in _LICENSE_PRIORITY:
            raise ValueError(f"unsupported mention license kind: {license_kind}")
        kinds = tuple(sorted(set(self.expected_candidate_kinds)))
        if not kinds:
            raise ValueError("mention licenses require expected candidate kinds")
        if any(kind not in _CANDIDATE_KINDS for kind in kinds):
            raise ValueError("mention licenses contain unsupported candidate kinds")
        if self.priority != _LICENSE_PRIORITY[license_kind]:
            raise ValueError("mention license priority must match its license kind")
        return {
            "license_ref": license_ref,
            "mention_ref": mention_ref,
            "license_kind": license_kind,
            "expected_candidate_kinds": list(kinds),
            "local_type_hypotheses": list(
                sorted(
                    {
                        _text(value, "local type hypothesis")
                        for value in self.local_type_hypotheses
                    }
                )
            ),
            "priority": self.priority,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class SuppressedSpan:
    """A source-addressable lattice member deliberately not instantiated."""

    start_token: int
    end_token: int
    suppression_reason: str

    def to_dict(self) -> dict[str, Any]:
        reason = _text(self.suppression_reason, "suppression_reason")
        if self.start_token < 0 or self.end_token <= self.start_token:
            raise ValueError(
                "suppressed token range must be non-empty and non-negative"
            )
        return {
            "start_token": self.start_token,
            "end_token": self.end_token,
            "suppression_reason": reason,
        }


@dataclass(frozen=True)
class MentionRecurrenceGroup:
    """Repeated normalized surfaces within one document, without coreference."""

    group_ref: str
    document_ref: str
    normalized_surface: str
    member_mention_refs: tuple[str, ...]
    normalization_profile: str = "casefold_whitespace.v0_1"
    scope: str = "document_local"

    def to_dict(self) -> dict[str, Any]:
        group_ref = _text(self.group_ref, "recurrence group_ref")
        document_ref = _text(self.document_ref, "recurrence document_ref")
        normalized_surface = _text(
            self.normalized_surface,
            "recurrence normalized_surface",
        )
        if self.normalization_profile != "casefold_whitespace.v0_1":
            raise ValueError("unsupported recurrence normalization profile")
        if self.scope != "document_local":
            raise ValueError("mention recurrence groups must remain document_local")
        members = _refs(self.member_mention_refs)
        if len(members) < 2:
            raise ValueError("mention recurrence groups require at least two members")
        return {
            "group_ref": group_ref,
            "document_ref": document_ref,
            "normalized_surface": normalized_surface,
            "member_mention_refs": list(members),
            "normalization_profile": self.normalization_profile,
            "scope": self.scope,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class MentionExpansionRequest:
    """A bounded reason to license a recoverable token interval.

    The request does not assert that an alias, grammatical interpretation, or
    PNF slot is correct. It only supplies a reviewable reason to materialize or
    re-license a source-anchored span for later candidate work.
    """

    request_ref: str
    source_ref: str
    document_ref: str
    start_token: int
    end_token: int
    expansion_kind: str
    expected_candidate_kinds: tuple[str, ...]
    context_refs: tuple[str, ...]
    local_type_hypotheses: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        request_ref = _text(self.request_ref, "expansion request_ref")
        source_ref = _text(self.source_ref, "expansion source_ref")
        document_ref = _text(self.document_ref, "expansion document_ref")
        expansion_kind = _text(self.expansion_kind, "expansion_kind")
        if expansion_kind not in {"alias_hint", "grammar_phrase", "pnf_demand"}:
            raise ValueError(f"unsupported mention expansion kind: {expansion_kind}")
        if self.start_token < 0 or self.end_token <= self.start_token:
            raise ValueError(
                "mention expansion token range must be non-empty and non-negative"
            )
        expected_kinds = tuple(sorted(set(self.expected_candidate_kinds)))
        if not expected_kinds:
            raise ValueError(
                "mention expansion requests require expected candidate kinds"
            )
        if any(kind not in _CANDIDATE_KINDS for kind in expected_kinds):
            raise ValueError(
                "mention expansion requests contain unsupported candidate kinds"
            )
        context_refs = _refs(self.context_refs)
        if not context_refs:
            raise ValueError("mention expansion requests require context references")
        return {
            "request_ref": request_ref,
            "source_ref": source_ref,
            "document_ref": document_ref,
            "start_token": self.start_token,
            "end_token": self.end_token,
            "expansion_kind": expansion_kind,
            "expected_candidate_kinds": list(expected_kinds),
            "context_refs": list(context_refs),
            "local_type_hypotheses": list(
                sorted(
                    {
                        _text(value, "local type hypothesis")
                        for value in self.local_type_hypotheses
                    }
                )
            ),
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


@dataclass(frozen=True)
class MentionAliasEntry:
    """A provenance-bearing lexical hint, never an identity assertion.

    ``token_sequence`` is supplied in the canonical tokenizer's token space.
    Its entries may include symbols, so an alias such as ``9 / 11`` stays
    distinct from a different lexical sequence such as ``911``.
    """

    alias_ref: str
    token_sequence: tuple[str, ...]
    expected_candidate_kinds: tuple[str, ...]
    context_refs: tuple[str, ...]
    local_type_hypotheses: tuple[str, ...] = ()
    normalization_profile: str = "casefold_token_sequence.v0_1"

    def to_dict(self) -> dict[str, Any]:
        alias_ref = _text(self.alias_ref, "alias_ref")
        if self.normalization_profile != "casefold_token_sequence.v0_1":
            raise ValueError("unsupported alias normalization profile")
        token_sequence = tuple(
            _text(token, "alias token") for token in self.token_sequence
        )
        if not token_sequence:
            raise ValueError("alias entries require a token sequence")
        expected_kinds = tuple(sorted(set(self.expected_candidate_kinds)))
        if not expected_kinds:
            raise ValueError("alias entries require expected candidate kinds")
        if any(kind not in _CANDIDATE_KINDS for kind in expected_kinds):
            raise ValueError("alias entries contain unsupported candidate kinds")
        context_refs = _refs(self.context_refs)
        if not context_refs:
            raise ValueError("alias entries require context references")
        return {
            "alias_ref": alias_ref,
            "token_sequence": list(token_sequence),
            "expected_candidate_kinds": list(expected_kinds),
            "context_refs": list(context_refs),
            "local_type_hypotheses": list(
                sorted(
                    {
                        _text(value, "local type hypothesis")
                        for value in self.local_type_hypotheses
                    }
                )
            ),
            "normalization_profile": self.normalization_profile,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }


def _validate_mention(mention: MentionSpan) -> None:
    _text(mention.mention_ref, "mention_ref")
    _text(mention.source_ref, "mention source_ref")
    _text(mention.document_ref, "mention document_ref")
    _text(mention.canonical_surface, "mention canonical_surface")
    _text(mention.generation_reason, "mention generation_reason")
    if mention.start_char < 0 or mention.end_char <= mention.start_char:
        raise ValueError("mention character range must be non-empty and non-negative")
    if (mention.start_token is None) != (mention.end_token is None):
        raise ValueError(
            "mention token intervals require both start_token and end_token"
        )
    if mention.start_token is not None and (
        mention.start_token < 0
        or mention.end_token is None
        or mention.end_token <= mention.start_token
    ):
        raise ValueError("mention token range must be non-empty and non-negative")


def _validate_candidate(candidate: EntityCandidate) -> None:
    _text(candidate.candidate_ref, "candidate_ref")
    _text(candidate.identity_ref, "candidate identity_ref")
    _text(candidate.label, "candidate label")
    if candidate.candidate_kind not in _CANDIDATE_KINDS:
        raise ValueError(
            f"unsupported entity candidate kind: {candidate.candidate_kind}"
        )
    if candidate.candidate_kind == "document_local" and candidate.registry_snapshot_ref:
        raise ValueError("document-local candidates cannot require registry snapshots")


def _coerce_mention(value: MentionSpan | Mapping[str, Any]) -> MentionSpan:
    if isinstance(value, MentionSpan):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("mentions must be MentionSpan values or mappings")
    return MentionSpan(
        mention_ref=str(value.get("mention_ref") or ""),
        source_ref=str(value.get("source_ref") or ""),
        document_ref=str(value.get("document_ref") or ""),
        start_char=int(value.get("start_char", -1)),
        end_char=int(value.get("end_char", -1)),
        canonical_surface=str(value.get("canonical_surface") or ""),
        generation_reason=str(value.get("generation_reason") or ""),
        grammatical_role=(
            str(value["grammatical_role"]).strip()
            if value.get("grammatical_role") is not None
            else None
        ),
        context_refs=tuple(value.get("context_refs") or ()),
        start_token=value.get("start_token"),
        end_token=value.get("end_token"),
    )


def _coerce_candidate(value: EntityCandidate | Mapping[str, Any]) -> EntityCandidate:
    if isinstance(value, EntityCandidate):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("entity candidates must be EntityCandidate values or mappings")
    return EntityCandidate(
        candidate_ref=str(value.get("candidate_ref") or ""),
        candidate_kind=str(value.get("candidate_kind") or ""),
        identity_ref=str(value.get("identity_ref") or ""),
        label=str(value.get("label") or ""),
        evidence_refs=tuple(value.get("evidence_refs") or ()),
        registry_snapshot_ref=(
            str(value["registry_snapshot_ref"]).strip()
            if value.get("registry_snapshot_ref") is not None
            else None
        ),
    )


def _coerce_catalog_entry(
    value: CandidateCatalogEntry | Mapping[str, Any],
) -> CandidateCatalogEntry:
    if isinstance(value, CandidateCatalogEntry):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("candidate catalog entries must be values or mappings")
    forbidden_fields = {
        "resolution_state",
        "resolved_identity_ref",
        "selected_candidate_ref",
        "promotion_state",
    }
    if forbidden_fields.intersection(value):
        raise ValueError("catalog entries cannot carry resolution or promotion state")
    token_sequences: list[tuple[Any, ...]] = []
    for sequence in value.get("match_token_sequences") or ():
        if isinstance(sequence, (str, bytes)) or not isinstance(sequence, Sequence):
            raise ValueError("catalog match token sequences must be token sequences")
        token_sequences.append(tuple(sequence))
    return CandidateCatalogEntry(
        catalog_entry_ref=str(value.get("catalog_entry_ref") or ""),
        candidate_kind=str(value.get("candidate_kind") or ""),
        identity_ref=str(value.get("identity_ref") or ""),
        label=str(value.get("label") or ""),
        match_token_sequences=tuple(token_sequences),
        evidence_refs=tuple(value.get("evidence_refs") or ()),
        registry_snapshot_ref=(
            str(value["registry_snapshot_ref"]).strip()
            if value.get("registry_snapshot_ref") is not None
            else None
        ),
        normalization_profile=str(
            value.get("normalization_profile") or "casefold_token_sequence.v0_1"
        ),
    )


def _coerce_form_lexicon_entry(
    value: FormLexiconEntry | Mapping[str, Any],
) -> FormLexiconEntry:
    if isinstance(value, FormLexiconEntry):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("form lexicon entries must be values or mappings")
    forbidden = {
        "candidate_ref",
        "identity_ref",
        "resolved_identity_ref",
        "selected_candidate_ref",
        "promotion_state",
    }
    if forbidden.intersection(value):
        raise ValueError(
            "form lexicon entries cannot carry entity resolution or promotion"
        )
    token_sequence = value.get("token_sequence") or ()
    if isinstance(token_sequence, (str, bytes)) or not isinstance(
        token_sequence, Sequence
    ):
        raise ValueError("form lexicon token sequence must be a token sequence")
    payload = value.get("normalized_payload") or {}
    if not isinstance(payload, Mapping):
        raise ValueError("form lexicon normalized_payload must be a mapping")
    return FormLexiconEntry(
        entry_ref=str(value.get("entry_ref") or ""),
        token_sequence=tuple(token_sequence),
        form_type=str(value.get("form_type") or ""),
        normalized_payload=payload,
        relation_kind=str(value.get("relation_kind") or ""),
        evidence_refs=tuple(value.get("evidence_refs") or ()),
        derivation_basis=str(value.get("derivation_basis") or "profile_lexicon"),
    )


def _coerce_form_composition_rule(
    value: FormCompositionRule | Mapping[str, Any],
) -> FormCompositionRule:
    if isinstance(value, FormCompositionRule):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("form composition rules must be values or mappings")
    component_types = value.get("component_form_types") or ()
    payload_keys = value.get("payload_keys") or ()
    if (
        isinstance(component_types, (str, bytes))
        or not isinstance(component_types, Sequence)
        or isinstance(payload_keys, (str, bytes))
        or not isinstance(payload_keys, Sequence)
    ):
        raise ValueError("form composition fields must be sequences")
    return FormCompositionRule(
        rule_ref=str(value.get("rule_ref") or ""),
        component_form_types=tuple(component_types),
        output_form_type=str(value.get("output_form_type") or ""),
        payload_keys=tuple(payload_keys),
        derivation_basis=str(value.get("derivation_basis") or "profile_composition"),
    )


def _coerce_form_candidate(value: FormCandidate | Mapping[str, Any]) -> FormCandidate:
    if isinstance(value, FormCandidate):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("form candidates must be FormCandidate values or mappings")
    payload = value.get("normalized_payload") or {}
    if not isinstance(payload, Mapping):
        raise ValueError("form normalized_payload must be a mapping")
    return FormCandidate(
        form_ref=str(value.get("form_ref") or ""),
        mention_ref=str(value.get("mention_ref") or ""),
        form_type=str(value.get("form_type") or ""),
        normalized_payload=payload,
        derivation_basis=str(value.get("derivation_basis") or ""),
        start_token=int(value.get("start_token", -1)),
        end_token=int(value.get("end_token", -1)),
        ambiguity_state=str(value.get("ambiguity_state") or "alternative"),
    )


def _coerce_local_typing_rule(
    value: LocalTypingRule | Mapping[str, Any],
) -> LocalTypingRule:
    if isinstance(value, LocalTypingRule):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("local typing rules must be values or mappings")
    forbidden = {
        "candidate_ref",
        "identity_ref",
        "resolved_identity_ref",
        "selected_candidate_ref",
        "promotion_state",
    }
    if forbidden.intersection(value):
        raise ValueError(
            "local typing rules cannot carry entity resolution or promotion"
        )
    return LocalTypingRule(
        rule_ref=str(value.get("rule_ref") or ""),
        form_type=str(value.get("form_type") or ""),
        semantic_family=str(value.get("semantic_family") or ""),
        local_type=str(value.get("local_type") or ""),
        evidence_refs=tuple(value.get("evidence_refs") or ()),
        derivation_basis=str(value.get("derivation_basis") or "profile_local_typing"),
    )


def _coerce_local_type_alternative(
    value: LocalTypeAlternative | Mapping[str, Any],
) -> LocalTypeAlternative:
    if isinstance(value, LocalTypeAlternative):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("local type alternatives must be values or mappings")
    return LocalTypeAlternative(
        type_ref=str(value.get("type_ref") or ""),
        mention_ref=str(value.get("mention_ref") or ""),
        semantic_family=str(value.get("semantic_family") or ""),
        local_type=str(value.get("local_type") or ""),
        derivation_basis=str(value.get("derivation_basis") or ""),
        evidence_refs=tuple(value.get("evidence_refs") or ()),
        form_ref=(str(value["form_ref"]).strip() if value.get("form_ref") else None),
        ambiguity_state=str(value.get("ambiguity_state") or "alternative"),
    )


def _coerce_partial_pnf_slot(
    value: PartialPNFSlot | Mapping[str, Any],
) -> PartialPNFSlot:
    if isinstance(value, PartialPNFSlot):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("partial PNF slots must be values or mappings")
    expected_families = value.get("expected_semantic_families") or ()
    if isinstance(expected_families, (str, bytes)) or not isinstance(
        expected_families, Sequence
    ):
        raise ValueError("PNF expected semantic families must be a sequence")
    return PartialPNFSlot(
        slot_ref=str(value.get("slot_ref") or ""),
        slot_kind=str(value.get("slot_kind") or ""),
        expected_semantic_families=tuple(expected_families),
        closure_requirement=str(value.get("closure_requirement") or ""),
        mention_ref=(
            str(value["mention_ref"]).strip() if value.get("mention_ref") else None
        ),
        required=bool(value.get("required", True)),
    )


def _coerce_partial_pnf(value: PartialPNF | Mapping[str, Any]) -> PartialPNF:
    if isinstance(value, PartialPNF):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("partial PNFs must be values or mappings")
    slots = value.get("slots") or ()
    if isinstance(slots, (str, bytes)) or not isinstance(slots, Sequence):
        raise ValueError("partial PNF slots must be a sequence")
    return PartialPNF(
        pnf_ref=str(value.get("pnf_ref") or ""),
        document_ref=str(value.get("document_ref") or ""),
        slots=tuple(_coerce_partial_pnf_slot(slot) for slot in slots),
    )


def _coerce_resolution_constraint(
    value: ResolutionConstraint | Mapping[str, Any],
) -> ResolutionConstraint:
    if isinstance(value, ResolutionConstraint):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("resolution constraints must be values or mappings")
    payload = value.get("payload") or {}
    if not isinstance(payload, Mapping):
        raise ValueError("resolution constraint payload must be a mapping")
    return ResolutionConstraint(
        constraint_ref=str(value.get("constraint_ref") or ""),
        constraint_kind=str(value.get("constraint_kind") or ""),
        payload=payload,
        evidence_refs=tuple(value.get("evidence_refs") or ()),
    )


def _coerce_resolution_subject_declaration(
    value: ResolutionSubjectDeclaration | Mapping[str, Any],
) -> ResolutionSubjectDeclaration:
    if isinstance(value, ResolutionSubjectDeclaration):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("resolution subject declarations must be values or mappings")
    constraints = value.get("constraints") or ()
    if isinstance(constraints, (str, bytes)) or not isinstance(constraints, Sequence):
        raise ValueError("resolution subject constraints must be a sequence")
    return ResolutionSubjectDeclaration(
        declaration_ref=str(value.get("declaration_ref") or ""),
        demand_ref=str(value.get("demand_ref") or ""),
        target_ref=str(value.get("target_ref") or ""),
        subject_kind=str(value.get("subject_kind") or ""),
        constraints=tuple(
            _coerce_resolution_constraint(constraint) for constraint in constraints
        ),
        formal_role=(
            str(value["formal_role"]).strip() if value.get("formal_role") else None
        ),
        source_scope=str(value.get("source_scope") or "document_local"),
    )


def _coerce_cache_entry(
    value: ResolutionCacheEntry | Mapping[str, Any],
) -> ResolutionCacheEntry:
    if isinstance(value, ResolutionCacheEntry):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("cache entries must be values or mappings")
    return ResolutionCacheEntry(
        cache_key=str(value.get("cache_key") or ""),
        backend_ref=str(value.get("backend_ref") or ""),
        cache_state=str(value.get("cache_state") or ""),
        evidence_ref=(
            str(value["evidence_ref"]) if value.get("evidence_ref") else None
        ),
        snapshot_ref=(
            str(value["snapshot_ref"]) if value.get("snapshot_ref") else None
        ),
        freshness_ref=(
            str(value["freshness_ref"]) if value.get("freshness_ref") else None
        ),
        provenance_refs=tuple(value.get("provenance_refs") or ()),
    )


def _coerce_backend_capability(
    value: ResolutionBackendCapability | Mapping[str, Any],
) -> ResolutionBackendCapability:
    if isinstance(value, ResolutionBackendCapability):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("backend capabilities must be values or mappings")
    return ResolutionBackendCapability(
        backend_ref=str(value.get("backend_ref") or ""),
        subject_kinds=tuple(value.get("subject_kinds") or ()),
        formal_roles=tuple(value.get("formal_roles") or ()),
        facets=tuple(value.get("facets") or ()),
        available=bool(value.get("available", True)),
        accepts_stale=bool(value.get("accepts_stale", False)),
        max_batch_size=int(value.get("max_batch_size", 1)),
        rate_limit_class=str(value.get("rate_limit_class") or "default"),
    )


def _coerce_candidate_set(
    value: EntityCandidateSet | Mapping[str, Any],
) -> EntityCandidateSet:
    if isinstance(value, EntityCandidateSet):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("candidate sets must be EntityCandidateSet values or mappings")
    return EntityCandidateSet(
        mention_ref=str(value.get("mention_ref") or ""),
        candidates=tuple(
            _coerce_candidate(candidate) for candidate in value.get("candidates") or ()
        ),
    )


def _coerce_cluster(
    value: CoreferenceCluster | Mapping[str, Any],
) -> CoreferenceCluster:
    if isinstance(value, CoreferenceCluster):
        return value
    if not isinstance(value, Mapping):
        raise ValueError(
            "coreference clusters must be CoreferenceCluster values or mappings"
        )
    return CoreferenceCluster(
        cluster_ref=str(value.get("cluster_ref") or ""),
        document_ref=str(value.get("document_ref") or ""),
        member_mention_refs=tuple(value.get("member_mention_refs") or ()),
        candidate_set_refs=tuple(value.get("candidate_set_refs") or ()),
        context_ref=(
            str(value["context_ref"]).strip()
            if value.get("context_ref") is not None
            else None
        ),
        scope=str(value.get("scope") or "document_local"),
    )


def build_entity_resolution_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    candidate_sets: Sequence[EntityCandidateSet | Mapping[str, Any]],
    coreference_clusters: Sequence[CoreferenceCluster | Mapping[str, Any]] = (),
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Validate and build a deterministic candidate-only resolution carrier."""

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("entity-resolution carrier authority must be candidate_only")

    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("mention references must be unique")
    mention_documents = {
        mention["mention_ref"]: mention["document_ref"] for mention in mention_rows
    }

    candidate_set_rows = sorted(
        (
            _coerce_candidate_set(candidate_set).to_dict()
            for candidate_set in candidate_sets
        ),
        key=lambda candidate_set: candidate_set["mention_ref"],
    )
    candidate_set_mentions = [
        candidate_set["mention_ref"] for candidate_set in candidate_set_rows
    ]
    if len(candidate_set_mentions) != len(set(candidate_set_mentions)):
        raise ValueError("candidate sets must be unique per mention")
    if any(
        mention_ref not in mention_documents for mention_ref in candidate_set_mentions
    ):
        raise ValueError("candidate sets must reference known mentions")

    candidate_set_refs = {
        f"candidate-set:{candidate_set['mention_ref']}"
        for candidate_set in candidate_set_rows
    }
    cluster_rows = sorted(
        (_coerce_cluster(cluster).to_dict() for cluster in coreference_clusters),
        key=lambda cluster: cluster["cluster_ref"],
    )
    cluster_refs = [cluster["cluster_ref"] for cluster in cluster_rows]
    if len(cluster_refs) != len(set(cluster_refs)):
        raise ValueError("coreference cluster references must be unique")
    for cluster in cluster_rows:
        members = cluster["member_mention_refs"]
        if any(member not in mention_documents for member in members):
            raise ValueError("coreference clusters must reference known mentions")
        if any(
            mention_documents[member] != cluster["document_ref"] for member in members
        ):
            raise ValueError("coreference clusters cannot cross document boundaries")
        if any(ref not in candidate_set_refs for ref in cluster["candidate_set_refs"]):
            raise ValueError("coreference clusters must reference known candidate sets")

    identity = {
        "schema_version": ENTITY_RESOLUTION_SCHEMA_VERSION,
        "authority": authority,
        "mentions": mention_rows,
        "candidate_sets": candidate_set_rows,
        "coreference_clusters": cluster_rows,
    }
    return {
        **identity,
        "carrier_ref": f"entity-resolution:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "mention_count": len(mention_rows),
            "candidate_set_count": len(candidate_set_rows),
            "candidate_count": sum(
                len(candidate_set["candidates"]) for candidate_set in candidate_set_rows
            ),
            "coreference_cluster_count": len(cluster_rows),
        },
    }


def _normalized_recurrence_surface(surface: str) -> str:
    return " ".join(_text(surface, "mention canonical_surface").split()).casefold()


def build_mention_recurrence_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Receipt repeated mention surfaces without asserting aliases or identity.

    The operation is document-bounded and backend-free. It is deliberately
    narrower than coreference: only exact case-folded, whitespace-normalized
    surface recurrence is preserved for later alias, grammar, or PNF-demand
    work. It does not create a candidate, resolve an identity, alter PNF, or
    produce any promotion or execution effect.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("mention recurrence carrier authority must be candidate_only")

    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("mention references must be unique")

    grouped_refs: dict[tuple[str, str], list[str]] = {}
    for mention in mention_rows:
        key = (
            mention["document_ref"],
            _normalized_recurrence_surface(mention["canonical_surface"]),
        )
        grouped_refs.setdefault(key, []).append(mention["mention_ref"])

    recurrence_rows: list[dict[str, Any]] = []
    for (document_ref, normalized_surface), members in sorted(grouped_refs.items()):
        if len(members) < 2:
            continue
        group_identity = {
            "document_ref": document_ref,
            "normalized_surface": normalized_surface,
        }
        recurrence_rows.append(
            MentionRecurrenceGroup(
                group_ref=f"mention-recurrence:{_canonical_digest(group_identity)}",
                document_ref=document_ref,
                normalized_surface=normalized_surface,
                member_mention_refs=tuple(members),
            ).to_dict()
        )

    recurrence_rows.sort(key=lambda group: group["group_ref"])
    identity = {
        "schema_version": MENTION_RECURRENCE_SCHEMA_VERSION,
        "authority": authority,
        "recurrence_groups": recurrence_rows,
    }
    return {
        **identity,
        "carrier_ref": f"mention-recurrence:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "input_mention_count": len(mention_rows),
            "recurrence_group_count": len(recurrence_rows),
            "recurrent_mention_count": sum(
                len(group["member_mention_refs"]) for group in recurrence_rows
            ),
        },
    }


def _coerce_expansion_request(
    value: MentionExpansionRequest | Mapping[str, Any],
) -> MentionExpansionRequest:
    if isinstance(value, MentionExpansionRequest):
        return value
    if not isinstance(value, Mapping):
        raise ValueError(
            "mention expansion requests must be MentionExpansionRequest values or mappings"
        )
    return MentionExpansionRequest(
        request_ref=str(value.get("request_ref") or ""),
        source_ref=str(value.get("source_ref") or ""),
        document_ref=str(value.get("document_ref") or ""),
        start_token=int(value.get("start_token", -1)),
        end_token=int(value.get("end_token", -1)),
        expansion_kind=str(value.get("expansion_kind") or ""),
        expected_candidate_kinds=tuple(value.get("expected_candidate_kinds") or ()),
        context_refs=tuple(value.get("context_refs") or ()),
        local_type_hypotheses=tuple(value.get("local_type_hypotheses") or ()),
    )


def build_mention_expansion_carrier(
    *,
    canonical_text: str,
    licensing_carrier: Mapping[str, Any],
    requests: Sequence[MentionExpansionRequest | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Materialize bounded, candidate-only expansions from explicit requests.

    Alias hints, grammar phrases, and PNF demands are intentionally inputs to
    this generic carrier rather than conclusions. The function verifies that
    every requested token interval belongs to the declared licensing carrier,
    then either reuses the already licensed span or emits one additional
    source-anchored mention and license. It performs no lookup, candidate
    generation, coreference, PNF mutation, resolution, promotion, or execution.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("mention expansion carrier authority must be candidate_only")
    if not isinstance(licensing_carrier, Mapping):
        raise ValueError("mention expansion requires a mention licensing carrier")
    if licensing_carrier.get("schema_version") != MENTION_LICENSING_SCHEMA_VERSION:
        raise ValueError("mention expansion requires a compatible licensing carrier")
    if licensing_carrier.get("authority") != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("mention expansion licensing carrier must be candidate_only")

    text = str(canonical_text)
    if not text:
        raise ValueError("mention expansion requires canonical_text")
    if licensing_carrier.get("canonical_text_sha256") != _canonical_digest(text):
        raise ValueError(
            "mention expansion canonical_text digest does not match carrier"
        )
    source = _text(licensing_carrier.get("source_ref"), "licensing source_ref")
    document = _text(licensing_carrier.get("document_ref"), "licensing document_ref")
    tokens = tokenize_canonical_with_spans(text)
    lattice = licensing_carrier.get("lattice")
    if not isinstance(lattice, Mapping) or lattice.get("token_count") != len(tokens):
        raise ValueError("mention expansion token count does not match carrier")

    existing_mentions = sorted(
        (
            _coerce_mention(mention).to_dict()
            for mention in licensing_carrier.get("mentions", ())
        ),
        key=lambda mention: mention["mention_ref"],
    )
    by_interval = {
        (mention["start_token"], mention["end_token"]): mention
        for mention in existing_mentions
        if "start_token" in mention and "end_token" in mention
    }

    request_rows = sorted(
        (_coerce_expansion_request(request).to_dict() for request in requests),
        key=lambda request: request["request_ref"],
    )
    request_refs = [request["request_ref"] for request in request_rows]
    if len(request_refs) != len(set(request_refs)):
        raise ValueError("mention expansion request references must be unique")

    created_mentions: dict[str, dict[str, Any]] = {}
    license_rows: list[dict[str, Any]] = []
    expansion_rows: list[dict[str, Any]] = []
    for request in request_rows:
        if request["source_ref"] != source or request["document_ref"] != document:
            raise ValueError(
                "mention expansion requests must match the licensing source"
            )
        start_token = request["start_token"]
        end_token = request["end_token"]
        if end_token > len(tokens):
            raise ValueError("mention expansion token range exceeds canonical text")
        mention = by_interval.get((start_token, end_token))
        materialization = "reused"
        if mention is None:
            start_char = tokens[start_token][1]
            end_char = tokens[end_token - 1][2]
            mention = MentionSpan(
                mention_ref=f"mention:{document}:{start_char}:{end_char}",
                source_ref=source,
                document_ref=document,
                start_char=start_char,
                end_char=end_char,
                canonical_surface=text[start_char:end_char],
                generation_reason=request["expansion_kind"],
                context_refs=tuple(request["context_refs"]),
                start_token=start_token,
                end_token=end_token,
            ).to_dict()
            by_interval[(start_token, end_token)] = mention
            created_mentions[mention["mention_ref"]] = mention
            materialization = "created"

        license_identity = {
            "request_ref": request["request_ref"],
            "mention_ref": mention["mention_ref"],
            "expansion_kind": request["expansion_kind"],
        }
        license_rows.append(
            MentionLicense(
                license_ref=f"license:mention-expansion:{_canonical_digest(license_identity)}",
                mention_ref=mention["mention_ref"],
                license_kind=request["expansion_kind"],
                expected_candidate_kinds=tuple(request["expected_candidate_kinds"]),
                local_type_hypotheses=tuple(request["local_type_hypotheses"]),
                priority=_LICENSE_PRIORITY[request["expansion_kind"]],
            ).to_dict()
        )
        expansion_rows.append(
            {
                "request_ref": request["request_ref"],
                "mention_ref": mention["mention_ref"],
                "materialization": materialization,
                "authority": ENTITY_RESOLUTION_AUTHORITY,
            }
        )

    created_rows = sorted(
        created_mentions.values(), key=lambda mention: mention["mention_ref"]
    )
    license_rows.sort(key=lambda license_row: license_row["license_ref"])
    expansion_rows.sort(key=lambda expansion: expansion["request_ref"])
    identity = {
        "schema_version": MENTION_EXPANSION_SCHEMA_VERSION,
        "authority": authority,
        "source_ref": source,
        "document_ref": document,
        "canonical_text_sha256": _canonical_digest(text),
        "licensing_carrier_ref": _text(
            licensing_carrier.get("carrier_ref"), "licensing carrier_ref"
        ),
        "requests": request_rows,
        "created_mentions": created_rows,
        "licenses": license_rows,
        "expansions": expansion_rows,
    }
    return {
        **identity,
        "carrier_ref": f"mention-expansion:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "request_count": len(request_rows),
            "created_mention_count": len(created_rows),
            "reused_mention_count": sum(
                row["materialization"] == "reused" for row in expansion_rows
            ),
            "license_count": len(license_rows),
        },
    }


def _coerce_alias_entry(
    value: MentionAliasEntry | Mapping[str, Any],
) -> MentionAliasEntry:
    if isinstance(value, MentionAliasEntry):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("alias entries must be MentionAliasEntry values or mappings")
    prohibited_fields = {
        "candidate_ref",
        "identity_ref",
        "registry_ref",
        "registry_snapshot_ref",
    }
    if prohibited_fields.intersection(value):
        raise ValueError("alias entries cannot carry candidate or registry identity")
    return MentionAliasEntry(
        alias_ref=str(value.get("alias_ref") or ""),
        token_sequence=tuple(value.get("token_sequence") or ()),
        expected_candidate_kinds=tuple(value.get("expected_candidate_kinds") or ()),
        context_refs=tuple(value.get("context_refs") or ()),
        local_type_hypotheses=tuple(value.get("local_type_hypotheses") or ()),
        normalization_profile=str(
            value.get("normalization_profile") or "casefold_token_sequence.v0_1"
        ),
    )


def _normalized_alias_tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    return tuple(_text(token, "alias token").casefold() for token in tokens)


def build_alias_expansion_requests(
    *,
    canonical_text: str,
    source_ref: str,
    document_ref: str,
    alias_entries: Sequence[MentionAliasEntry | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Produce exact alias-hint expansion requests from caller-supplied entries.

    This is a lexical index adapter, not a registry adapter or resolver. It
    searches only exact case-folded canonical-token sequences and returns
    bounded ``MentionExpansionRequest`` records for later validation and
    materialization. It neither interprets a matched surface nor creates a
    candidate, identity, coreference relation, PNF binding, or authority.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("alias expansion authority must be candidate_only")
    text = str(canonical_text)
    if not text:
        raise ValueError("alias expansion requires canonical_text")
    source = _text(source_ref, "source_ref")
    document = _text(document_ref, "document_ref")
    entry_rows = sorted(
        (_coerce_alias_entry(entry).to_dict() for entry in alias_entries),
        key=lambda entry: entry["alias_ref"],
    )
    alias_refs = [entry["alias_ref"] for entry in entry_rows]
    if len(alias_refs) != len(set(alias_refs)):
        raise ValueError("alias entry references must be unique")

    tokens = tokenize_canonical_with_spans(text)
    normalized_text_tokens = _normalized_alias_tokens(
        [token for token, _start, _end in tokens]
    )
    request_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    for entry in entry_rows:
        normalized_sequence = _normalized_alias_tokens(entry["token_sequence"])
        span_length = len(normalized_sequence)
        for start_token in range(len(tokens) - span_length + 1):
            end_token = start_token + span_length
            if normalized_text_tokens[start_token:end_token] != normalized_sequence:
                continue
            request_identity = {
                "alias_ref": entry["alias_ref"],
                "source_ref": source,
                "document_ref": document,
                "start_token": start_token,
                "end_token": end_token,
            }
            request = MentionExpansionRequest(
                request_ref=(
                    f"alias-expansion-request:{_canonical_digest(request_identity)}"
                ),
                source_ref=source,
                document_ref=document,
                start_token=start_token,
                end_token=end_token,
                expansion_kind="alias_hint",
                expected_candidate_kinds=tuple(entry["expected_candidate_kinds"]),
                context_refs=tuple(entry["context_refs"]),
                local_type_hypotheses=tuple(entry["local_type_hypotheses"]),
            ).to_dict()
            request_rows.append(request)
            match_rows.append(
                {
                    "alias_ref": entry["alias_ref"],
                    "request_ref": request["request_ref"],
                    "start_token": start_token,
                    "end_token": end_token,
                    "canonical_surface": text[
                        tokens[start_token][1] : tokens[end_token - 1][2]
                    ],
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )

    request_rows.sort(key=lambda request: request["request_ref"])
    match_rows.sort(
        key=lambda match: (
            match["alias_ref"],
            match["start_token"],
            match["request_ref"],
        )
    )
    identity = {
        "schema_version": ALIAS_EXPANSION_SCHEMA_VERSION,
        "authority": authority,
        "source_ref": source,
        "document_ref": document,
        "canonical_text_sha256": _canonical_digest(text),
        "alias_entries": entry_rows,
        "requests": request_rows,
        "matches": match_rows,
    }
    return {
        **identity,
        "carrier_ref": f"alias-expansion-requests:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "alias_entry_count": len(entry_rows),
            "request_count": len(request_rows),
            "matched_alias_entry_count": len(
                {match["alias_ref"] for match in match_rows}
            ),
        },
    }


def _nominal_phrase_intervals(
    tokens: Sequence[tuple[str, int, int]],
    parsed: Mapping[str, Any],
) -> list[tuple[int, int, tuple[str, ...]]]:
    annotations = _annotation_by_span(parsed)
    intervals: list[tuple[int, int, tuple[str, ...]]] = []
    start_token: int | None = None
    phrase_pos: list[str] = []

    def flush(end_token: int) -> None:
        nonlocal start_token, phrase_pos
        if (
            start_token is not None
            and end_token - start_token > 1
            and _NOMINAL_HEAD_POS.intersection(phrase_pos)
        ):
            intervals.append((start_token, end_token, tuple(phrase_pos)))
        start_token = None
        phrase_pos = []

    for token_index, (_token, start_char, end_char) in enumerate(tokens):
        annotation = annotations.get((start_char, end_char))
        pos = str((annotation or {}).get("pos") or "").strip()
        if pos in _NOMINAL_PHRASE_POS:
            if start_token is None:
                start_token = token_index
            phrase_pos.append(pos)
            continue
        flush(token_index)
    flush(len(tokens))
    return intervals


def _grammar_phrase_shape(
    pos_tags: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    local_types = ["nominal_phrase"]
    if "PROPN" in pos_tags:
        local_types.append("proper_name_phrase")
        return ("document_local", "instance", "role"), tuple(local_types)
    local_types.append("common_noun_phrase")
    return ("class", "instance", "property", "role"), tuple(local_types)


def build_grammar_expansion_requests(
    *,
    canonical_text: str,
    source_ref: str,
    document_ref: str,
    context_refs: Sequence[str],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Emit parser-licensed nominal phrase requests without semantic resolution.

    The initial generic grammar profile accepts maximal contiguous
    determiner/adjective/numeral/noun/proper-noun spans with a noun or proper
    noun head. It consumes only the public parser and canonical-token adapter;
    missing or incompatible annotations produce no request. Returned records
    are ``grammar_phrase`` inputs for bounded mention expansion, not candidates
    or assertions about identity, PNF role, or authority.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("grammar expansion authority must be candidate_only")
    text = str(canonical_text)
    if not text:
        raise ValueError("grammar expansion requires canonical_text")
    source = _text(source_ref, "source_ref")
    document = _text(document_ref, "document_ref")
    canonical_context_refs = _refs(context_refs)
    if not canonical_context_refs:
        raise ValueError("grammar expansion requires context references")
    tokens = tokenize_canonical_with_spans(text)
    parsed = parse_canonical_text(text)
    phrase_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    for start_token, end_token, pos_tags in _nominal_phrase_intervals(tokens, parsed):
        expected_kinds, local_types = _grammar_phrase_shape(pos_tags)
        request_identity = {
            "grammar_profile": _NOMINAL_GRAMMAR_PROFILE,
            "source_ref": source,
            "document_ref": document,
            "start_token": start_token,
            "end_token": end_token,
        }
        request = MentionExpansionRequest(
            request_ref=(
                f"grammar-expansion-request:{_canonical_digest(request_identity)}"
            ),
            source_ref=source,
            document_ref=document,
            start_token=start_token,
            end_token=end_token,
            expansion_kind="grammar_phrase",
            expected_candidate_kinds=expected_kinds,
            context_refs=canonical_context_refs,
            local_type_hypotheses=local_types,
        ).to_dict()
        request_rows.append(request)
        phrase_rows.append(
            {
                "request_ref": request["request_ref"],
                "start_token": start_token,
                "end_token": end_token,
                "canonical_surface": text[
                    tokens[start_token][1] : tokens[end_token - 1][2]
                ],
                "pos_tags": list(pos_tags),
                "authority": ENTITY_RESOLUTION_AUTHORITY,
            }
        )

    request_rows.sort(key=lambda request: request["request_ref"])
    phrase_rows.sort(key=lambda phrase: (phrase["start_token"], phrase["request_ref"]))
    identity = {
        "schema_version": GRAMMAR_EXPANSION_SCHEMA_VERSION,
        "authority": authority,
        "source_ref": source,
        "document_ref": document,
        "canonical_text_sha256": _canonical_digest(text),
        "grammar_profile": _NOMINAL_GRAMMAR_PROFILE,
        "context_refs": list(canonical_context_refs),
        "requests": request_rows,
        "phrases": phrase_rows,
    }
    return {
        **identity,
        "carrier_ref": f"grammar-expansion-requests:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "phrase_count": len(phrase_rows),
            "request_count": len(request_rows),
        },
    }


def _mention_token_sequence(surface: str) -> tuple[str, ...]:
    return _normalized_alias_tokens(
        tuple(token for token, _start, _end in tokenize_canonical_with_spans(surface))
    )


def _form_candidate(
    *,
    mention_ref: str,
    form_type: str,
    normalized_payload: Mapping[str, Any],
    derivation_basis: str,
    start_token: int,
    end_token: int,
) -> FormCandidate:
    identity = {
        "mention_ref": mention_ref,
        "form_type": form_type,
        "normalized_payload": _json_mapping(
            normalized_payload, "form normalized_payload"
        ),
        "derivation_basis": derivation_basis,
        "start_token": start_token,
        "end_token": end_token,
    }
    return FormCandidate(
        form_ref=f"form:{_canonical_digest(identity)}",
        mention_ref=mention_ref,
        form_type=form_type,
        normalized_payload=normalized_payload,
        derivation_basis=derivation_basis,
        start_token=start_token,
        end_token=end_token,
    )


def _form_relation(
    *,
    left_form_ref: str,
    relation_kind: str,
    right_form_ref: str,
    derivation_basis: str,
) -> FormRelation:
    identity = {
        "left_form_ref": left_form_ref,
        "relation_kind": relation_kind,
        "right_form_ref": right_form_ref,
        "derivation_basis": derivation_basis,
    }
    return FormRelation(
        relation_ref=f"form-relation:{_canonical_digest(identity)}",
        left_form_ref=left_form_ref,
        relation_kind=relation_kind,
        right_form_ref=right_form_ref,
        derivation_basis=derivation_basis,
    )


def _sequence_matches_at(
    tokens: Sequence[str], sequence: Sequence[str], start: int
) -> bool:
    return tuple(tokens[start : start + len(sequence)]) == tuple(sequence)


def _composed_form_candidates(
    *,
    mention_ref: str,
    forms: Sequence[FormCandidate],
    rules: Sequence[dict[str, Any]],
) -> tuple[list[FormCandidate], list[FormRelation]]:
    """Apply declared adjacent-form algebra without choosing an interpretation."""

    generated_forms: list[FormCandidate] = []
    generated_relations: list[FormRelation] = []
    available_forms = list(forms)
    for rule in rules:
        component_types = tuple(rule["component_form_types"])
        by_start: dict[int, list[FormCandidate]] = {}
        for form in available_forms:
            by_start.setdefault(form.start_token, []).append(form)
        for candidates in by_start.values():
            candidates.sort(key=lambda candidate: candidate.form_ref)

        def compatible_component_paths(
            components: tuple[FormCandidate, ...],
        ) -> list[tuple[FormCandidate, ...]]:
            next_index = len(components)
            if next_index == len(component_types):
                return [components]
            cursor = components[-1].end_token
            return [
                path
                for candidate in by_start.get(cursor, ())
                if candidate.form_type == component_types[next_index]
                for path in compatible_component_paths((*components, candidate))
            ]

        for first in tuple(available_forms):
            if first.form_type != component_types[0]:
                continue
            for components in compatible_component_paths((first,)):
                values: dict[str, Any] = {}
                for key, component in zip(
                    rule["payload_keys"], components, strict=True
                ):
                    if "value" not in component.normalized_payload:
                        break
                    values[key] = component.normalized_payload["value"]
                if len(values) != len(components):
                    continue
                output = _form_candidate(
                    mention_ref=mention_ref,
                    form_type=rule["output_form_type"],
                    normalized_payload=values,
                    derivation_basis=rule["derivation_basis"],
                    start_token=components[0].start_token,
                    end_token=components[-1].end_token,
                )
                if any(form.form_ref == output.form_ref for form in available_forms):
                    continue
                available_forms.append(output)
                generated_forms.append(output)
                for component in components:
                    generated_relations.append(
                        _form_relation(
                            left_form_ref=component.form_ref,
                            relation_kind="component_of",
                            right_form_ref=output.form_ref,
                            derivation_basis=rule["derivation_basis"],
                        )
                    )
    return generated_forms, generated_relations


def build_form_derivation_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    lexicon_entries: Sequence[FormLexiconEntry | Mapping[str, Any]] = (),
    composition_rules: Sequence[FormCompositionRule | Mapping[str, Any]] = (),
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Derive ambiguous linguistic forms before entity or PNF interpretation.

    The carrier emits source-anchored form alternatives and declared relations.
    Built-in structural derivations cover token sequences, integer literals,
    rational literals, and abbreviation-shaped forms. Language-specific forms
    such as month names or spoken numerals must arrive through the
    provenance-bearing lexical profile and declarative composition rules.
    Nothing in this stage names an entity, event, or legal provision.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("form derivation authority must be candidate_only")
    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("form derivation mention references must be unique")
    lexicon_rows = sorted(
        (_coerce_form_lexicon_entry(entry).to_dict() for entry in lexicon_entries),
        key=lambda entry: entry["entry_ref"],
    )
    lexicon_refs = [entry["entry_ref"] for entry in lexicon_rows]
    if len(lexicon_refs) != len(set(lexicon_refs)):
        raise ValueError("form lexicon entry references must be unique")
    rule_rows = sorted(
        (_coerce_form_composition_rule(rule).to_dict() for rule in composition_rules),
        key=lambda rule: rule["rule_ref"],
    )
    rule_refs = [rule["rule_ref"] for rule in rule_rows]
    if len(rule_refs) != len(set(rule_refs)):
        raise ValueError("form composition rule references must be unique")

    form_rows: list[dict[str, Any]] = []
    relation_rows: list[dict[str, Any]] = []
    for mention in mention_rows:
        raw_tokens = tuple(
            token
            for token, _start, _end in tokenize_canonical_with_spans(
                mention["canonical_surface"]
            )
        )
        tokens = _normalized_alias_tokens(raw_tokens)
        if not tokens:
            raise ValueError("form derivation mention requires canonical tokens")
        surface = _form_candidate(
            mention_ref=mention["mention_ref"],
            form_type="surface_text",
            normalized_payload={"text": mention["canonical_surface"]},
            derivation_basis="canonical_source_span",
            start_token=0,
            end_token=len(tokens),
        )
        token_sequence = _form_candidate(
            mention_ref=mention["mention_ref"],
            form_type="token_sequence",
            normalized_payload={"tokens": list(tokens)},
            derivation_basis="canonical_tokenizer",
            start_token=0,
            end_token=len(tokens),
        )
        forms = [surface, token_sequence]
        relations = [
            _form_relation(
                left_form_ref=surface.form_ref,
                relation_kind="orthographic_variant_of",
                right_form_ref=token_sequence.form_ref,
                derivation_basis="canonical_tokenizer",
            )
        ]
        if len(tokens) == 1 and tokens[0].isdigit():
            numeric = _form_candidate(
                mention_ref=mention["mention_ref"],
                form_type="integer",
                normalized_payload={"value": tokens[0]},
                derivation_basis="numeric_syntax",
                start_token=0,
                end_token=1,
            )
            forms.append(numeric)
            relations.append(
                _form_relation(
                    left_form_ref=surface.form_ref,
                    relation_kind="numeric_rendering_of",
                    right_form_ref=numeric.form_ref,
                    derivation_basis="numeric_syntax",
                )
            )
        if (
            len(tokens) == 3
            and tokens[0].isdigit()
            and tokens[1] == "/"
            and tokens[2].isdigit()
        ):
            rational = _form_candidate(
                mention_ref=mention["mention_ref"],
                form_type="rational",
                normalized_payload={"numerator": tokens[0], "denominator": tokens[2]},
                derivation_basis="numeric_syntax",
                start_token=0,
                end_token=3,
            )
            forms.append(rational)
            relations.append(
                _form_relation(
                    left_form_ref=surface.form_ref,
                    relation_kind="numeric_rendering_of",
                    right_form_ref=rational.form_ref,
                    derivation_basis="numeric_syntax",
                )
            )
        if (
            len(tokens) == 1
            and raw_tokens[0].upper() == raw_tokens[0]
            and any(character.isalpha() for character in raw_tokens[0])
            and any(character.isdigit() for character in raw_tokens[0])
        ):
            abbreviation = _form_candidate(
                mention_ref=mention["mention_ref"],
                form_type="abbreviation",
                normalized_payload={"value": raw_tokens[0]},
                derivation_basis="orthographic_shape",
                start_token=0,
                end_token=1,
            )
            forms.append(abbreviation)
            relations.append(
                _form_relation(
                    left_form_ref=surface.form_ref,
                    relation_kind="abbreviation_of",
                    right_form_ref=abbreviation.form_ref,
                    derivation_basis="orthographic_shape",
                )
            )
        for entry in lexicon_rows:
            entry_tokens = tuple(entry["token_sequence"])
            for start in range(len(tokens) - len(entry_tokens) + 1):
                if not _sequence_matches_at(tokens, entry_tokens, start):
                    continue
                lexical_form = _form_candidate(
                    mention_ref=mention["mention_ref"],
                    form_type=entry["form_type"],
                    normalized_payload=entry["normalized_payload"],
                    derivation_basis=entry["derivation_basis"],
                    start_token=start,
                    end_token=start + len(entry_tokens),
                )
                forms.append(lexical_form)
                relations.append(
                    _form_relation(
                        left_form_ref=surface.form_ref,
                        relation_kind=entry["relation_kind"],
                        right_form_ref=lexical_form.form_ref,
                        derivation_basis=entry["derivation_basis"],
                    )
                )
        derived_forms, derived_relations = _composed_form_candidates(
            mention_ref=mention["mention_ref"], forms=forms, rules=rule_rows
        )
        forms.extend(derived_forms)
        relations.extend(derived_relations)
        form_rows.extend(form.to_dict() for form in forms)
        relation_rows.extend(relation.to_dict() for relation in relations)

    form_rows.sort(key=lambda form: form["form_ref"])
    relation_rows.sort(key=lambda relation: relation["relation_ref"])
    if len({form["form_ref"] for form in form_rows}) != len(form_rows):
        raise ValueError("form derivation emitted duplicate form references")
    if len({relation["relation_ref"] for relation in relation_rows}) != len(
        relation_rows
    ):
        raise ValueError("form derivation emitted duplicate relation references")
    identity = {
        "schema_version": FORM_DERIVATION_SCHEMA_VERSION,
        "authority": authority,
        "mentions": mention_rows,
        "lexicon_entries": lexicon_rows,
        "composition_rules": rule_rows,
        "forms": form_rows,
        "relations": relation_rows,
        "serialization_order": "form_ref_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"form-derivation:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "pnf_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "mention_count": len(mention_rows),
            "form_count": len(form_rows),
            "relation_count": len(relation_rows),
            "lexicon_entry_count": len(lexicon_rows),
            "composition_rule_count": len(rule_rows),
        },
    }


def _local_type_alternative(
    *,
    mention_ref: str,
    semantic_family: str,
    local_type: str,
    derivation_basis: str,
    evidence_refs: Sequence[str],
    form_ref: str | None = None,
) -> LocalTypeAlternative:
    identity = {
        "mention_ref": mention_ref,
        "semantic_family": semantic_family,
        "local_type": local_type,
        "derivation_basis": derivation_basis,
        "evidence_refs": list(_refs(evidence_refs)),
        "form_ref": form_ref,
    }
    return LocalTypeAlternative(
        type_ref=f"local-type:{_canonical_digest(identity)}",
        mention_ref=mention_ref,
        semantic_family=semantic_family,
        local_type=local_type,
        derivation_basis=derivation_basis,
        evidence_refs=tuple(evidence_refs),
        form_ref=form_ref,
    )


def build_local_typing_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    forms: Sequence[FormCandidate | Mapping[str, Any]],
    typing_rules: Sequence[LocalTypingRule | Mapping[str, Any]] = (),
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Build candidate-only local types and independent coverage pressure.

    Built-in reductions type numeric forms as quantities, abbreviation-shaped
    forms as literals, and parser-annotated eventuality mentions as linguistic
    eventualities. Caller-supplied rules may reduce a form type to another
    local semantic family, but never name an external identity, resolve a
    candidate, construct PNF, or promote a fact.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("local typing authority must be candidate_only")
    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("local typing mention references must be unique")
    mention_by_ref = {mention["mention_ref"]: mention for mention in mention_rows}
    form_rows = sorted(
        (_coerce_form_candidate(form).to_dict() for form in forms),
        key=lambda form: form["form_ref"],
    )
    form_refs = [form["form_ref"] for form in form_rows]
    if len(form_refs) != len(set(form_refs)):
        raise ValueError("local typing form references must be unique")
    if unknown_mentions := {form["mention_ref"] for form in form_rows}.difference(
        mention_by_ref
    ):
        raise ValueError(
            f"local typing forms reference unknown mentions: {sorted(unknown_mentions)}"
        )
    rule_rows = sorted(
        (_coerce_local_typing_rule(rule).to_dict() for rule in typing_rules),
        key=lambda rule: rule["rule_ref"],
    )
    rule_refs = [rule["rule_ref"] for rule in rule_rows]
    if len(rule_refs) != len(set(rule_refs)):
        raise ValueError("local typing rule references must be unique")

    form_by_mention: dict[str, list[dict[str, Any]]] = {
        mention_ref: [] for mention_ref in mention_by_ref
    }
    for form in form_rows:
        form_by_mention[form["mention_ref"]].append(form)

    alternative_rows: list[dict[str, Any]] = []
    for mention_ref, mention in mention_by_ref.items():
        if (
            mention["generation_reason"] == "eventuality_annotation"
            or mention.get("grammatical_role") == "eventuality_predicate"
        ):
            alternative_rows.append(
                _local_type_alternative(
                    mention_ref=mention_ref,
                    semantic_family="eventuality",
                    local_type="linguistic_eventuality",
                    derivation_basis="public_parser_annotation",
                    evidence_refs=(f"source-anchor:{mention_ref}",),
                ).to_dict()
            )
        for form in form_by_mention[mention_ref]:
            builtin = {
                "integer": ("quantity", "numeric_quantity"),
                "rational": ("quantity", "numeric_quantity"),
                "abbreviation": ("literal", "abbreviation_form"),
                "month_day": ("literal", "calendar_expression"),
            }.get(form["form_type"])
            if builtin:
                alternative_rows.append(
                    _local_type_alternative(
                        mention_ref=mention_ref,
                        form_ref=form["form_ref"],
                        semantic_family=builtin[0],
                        local_type=builtin[1],
                        derivation_basis="generic_form_typing",
                        evidence_refs=(form["form_ref"],),
                    ).to_dict()
                )
            for rule in rule_rows:
                if rule["form_type"] != form["form_type"]:
                    continue
                alternative_rows.append(
                    _local_type_alternative(
                        mention_ref=mention_ref,
                        form_ref=form["form_ref"],
                        semantic_family=rule["semantic_family"],
                        local_type=rule["local_type"],
                        derivation_basis=rule["derivation_basis"],
                        evidence_refs=rule["evidence_refs"],
                    ).to_dict()
                )

    alternative_rows.sort(key=lambda alternative: alternative["type_ref"])
    if len({row["type_ref"] for row in alternative_rows}) != len(alternative_rows):
        raise ValueError("local typing emitted duplicate alternative references")
    alternatives_by_mention: dict[str, list[str]] = {
        mention_ref: [] for mention_ref in mention_by_ref
    }
    for alternative in alternative_rows:
        alternatives_by_mention[alternative["mention_ref"]].append(
            alternative["type_ref"]
        )
    coverage_rows: list[dict[str, Any]] = []
    for mention_ref in sorted(mention_by_ref):
        type_refs = alternatives_by_mention[mention_ref]
        if type_refs:
            assessment = CoveragePressureAssessment(
                mention_ref=mention_ref,
                coverage_state="typed",
                reason_codes=("local_type_alternatives",),
                local_type_refs=tuple(type_refs),
            )
        elif form_by_mention[mention_ref]:
            assessment = CoveragePressureAssessment(
                mention_ref=mention_ref,
                coverage_state="weakly_typed",
                reason_codes=("source_forms_without_semantic_type",),
            )
        else:
            assessment = CoveragePressureAssessment(
                mention_ref=mention_ref,
                coverage_state="untyped",
                reason_codes=("no_source_form",),
            )
        coverage_rows.append(assessment.to_dict())

    identity = {
        "schema_version": LOCAL_TYPING_SCHEMA_VERSION,
        "authority": authority,
        "mentions": mention_rows,
        "forms": form_rows,
        "typing_rules": rule_rows,
        "local_type_alternatives": alternative_rows,
        "coverage_pressure": coverage_rows,
        "serialization_order": "reference_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"local-typing:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "pnf_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "mention_count": len(mention_rows),
            "form_count": len(form_rows),
            "typing_rule_count": len(rule_rows),
            "local_type_alternative_count": len(alternative_rows),
            "coverage_state_counts": {
                state: sum(row["coverage_state"] == state for row in coverage_rows)
                for state in sorted(_COVERAGE_STATES)
            },
        },
    }


def build_partial_pnf_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    local_type_alternatives: Sequence[LocalTypeAlternative | Mapping[str, Any]],
    partial_pnfs: Sequence[PartialPNF | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Factorize local PNF slot alternatives and receipt closure obligations.

    Slots bind only to compatible local type alternatives. The carrier does not
    combine slot alternatives, resolve an external identity, issue a demand,
    decide a proposition, or promote a claim.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("partial PNF authority must be candidate_only")
    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("partial PNF mention references must be unique")
    mention_by_ref = {mention["mention_ref"]: mention for mention in mention_rows}
    type_rows = sorted(
        (
            _coerce_local_type_alternative(alternative).to_dict()
            for alternative in local_type_alternatives
        ),
        key=lambda alternative: alternative["type_ref"],
    )
    type_refs = [alternative["type_ref"] for alternative in type_rows]
    if len(type_refs) != len(set(type_refs)):
        raise ValueError("partial PNF local type references must be unique")
    if unknown_mentions := {
        alternative["mention_ref"] for alternative in type_rows
    }.difference(mention_by_ref):
        raise ValueError(
            "partial PNF local types reference unknown mentions: "
            f"{sorted(unknown_mentions)}"
        )
    pnf_rows = sorted(
        (_coerce_partial_pnf(pnf).to_dict() for pnf in partial_pnfs),
        key=lambda pnf: pnf["pnf_ref"],
    )
    pnf_refs = [pnf["pnf_ref"] for pnf in pnf_rows]
    if len(pnf_refs) != len(set(pnf_refs)):
        raise ValueError("partial PNF references must be unique")
    for pnf in pnf_rows:
        for slot in pnf["slots"]:
            mention_ref = slot.get("mention_ref")
            if mention_ref is None:
                continue
            if mention_ref not in mention_by_ref:
                raise ValueError(
                    f"partial PNF slots reference unknown mention: {mention_ref}"
                )
            if mention_by_ref[mention_ref]["document_ref"] != pnf["document_ref"]:
                raise ValueError("partial PNF slots must remain document-bounded")

    types_by_mention: dict[str, list[dict[str, Any]]] = {
        mention_ref: [] for mention_ref in mention_by_ref
    }
    for alternative in type_rows:
        types_by_mention[alternative["mention_ref"]].append(alternative)

    slot_alternative_rows: list[dict[str, Any]] = []
    closure_rows: list[dict[str, Any]] = []
    for pnf in pnf_rows:
        for slot in pnf["slots"]:
            mention_ref = slot.get("mention_ref")
            compatible_types = [
                alternative
                for alternative in types_by_mention.get(mention_ref, ())
                if alternative["semantic_family"] in slot["expected_semantic_families"]
            ]
            slot_alternatives = [
                PNFSlotAlternative(
                    alternative_ref=(
                        "pnf-slot-alternative:"
                        + _canonical_digest(
                            {
                                "pnf_ref": pnf["pnf_ref"],
                                "slot_ref": slot["slot_ref"],
                                "local_type_ref": alternative["type_ref"],
                            }
                        )
                    ),
                    pnf_ref=pnf["pnf_ref"],
                    slot_ref=slot["slot_ref"],
                    local_type_ref=alternative["type_ref"],
                ).to_dict()
                for alternative in compatible_types
            ]
            slot_alternative_rows.extend(slot_alternatives)
            slot_alternative_refs = tuple(
                alternative["alternative_ref"] for alternative in slot_alternatives
            )
            if not slot["required"]:
                closure = ClosurePressureAssessment(
                    pnf_ref=pnf["pnf_ref"],
                    slot_ref=slot["slot_ref"],
                    closure_state="not_required",
                    reason_codes=("optional_slot",),
                )
            elif not slot_alternative_refs:
                closure = ClosurePressureAssessment(
                    pnf_ref=pnf["pnf_ref"],
                    slot_ref=slot["slot_ref"],
                    closure_state="requires_local_typing",
                    reason_codes=("no_compatible_local_type",),
                )
            elif slot["closure_requirement"] == "external_identity":
                closure = ClosurePressureAssessment(
                    pnf_ref=pnf["pnf_ref"],
                    slot_ref=slot["slot_ref"],
                    closure_state="requires_external_resolution",
                    reason_codes=("external_identity_required",),
                    slot_alternative_refs=slot_alternative_refs,
                )
            else:
                closure = ClosurePressureAssessment(
                    pnf_ref=pnf["pnf_ref"],
                    slot_ref=slot["slot_ref"],
                    closure_state="locally_closed",
                    reason_codes=("local_type_requirement_satisfied",),
                    slot_alternative_refs=slot_alternative_refs,
                )
            closure_rows.append(closure.to_dict())

    slot_alternative_rows.sort(key=lambda row: row["alternative_ref"])
    closure_rows.sort(key=lambda row: (row["pnf_ref"], row["slot_ref"]))
    identity = {
        "schema_version": PARTIAL_PNF_SCHEMA_VERSION,
        "authority": authority,
        "mentions": mention_rows,
        "local_type_alternatives": type_rows,
        "partial_pnfs": pnf_rows,
        "slot_alternatives": slot_alternative_rows,
        "closure_pressure": closure_rows,
        "serialization_order": "reference_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"partial-pnf:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "demand_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "partial_pnf_count": len(pnf_rows),
            "slot_count": sum(len(pnf["slots"]) for pnf in pnf_rows),
            "slot_alternative_count": len(slot_alternative_rows),
            "closure_state_counts": {
                state: sum(row["closure_state"] == state for row in closure_rows)
                for state in sorted(_CLOSURE_STATES)
            },
        },
    }


def build_resolution_demand_carrier(
    *,
    partial_pnf_carrier: Mapping[str, Any],
    budget_class: str = "standard",
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Project unresolved PartialPNF closure obligations into bounded demands.

    The projection is registry-neutral and performs no I/O. It cannot modify
    the input skeleton, select a candidate, or report a resolution outcome.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("resolution demand authority must be candidate_only")
    if not isinstance(partial_pnf_carrier, Mapping):
        raise ValueError("resolution demand input must be a partial PNF carrier")
    if partial_pnf_carrier.get("schema_version") != PARTIAL_PNF_SCHEMA_VERSION:
        raise ValueError("resolution demand input must use the partial PNF schema")
    if partial_pnf_carrier.get("authority") != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("resolution demand input must remain candidate_only")
    input_carrier_ref = _text(
        partial_pnf_carrier.get("carrier_ref"), "partial PNF carrier_ref"
    )
    budget = _text(budget_class, "resolution demand budget_class")
    slot_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for pnf in partial_pnf_carrier.get("partial_pnfs") or ():
        if not isinstance(pnf, Mapping):
            raise ValueError("partial PNF carrier contains invalid PNF rows")
        pnf_ref = _text(pnf.get("pnf_ref"), "partial PNF ref")
        for slot in pnf.get("slots") or ():
            if not isinstance(slot, Mapping):
                raise ValueError("partial PNF carrier contains invalid slot rows")
            slot_ref = _text(slot.get("slot_ref"), "partial PNF slot_ref")
            if (pnf_ref, slot_ref) in slot_by_key:
                raise ValueError("partial PNF carrier repeats a slot reference")
            slot_by_key[(pnf_ref, slot_ref)] = dict(slot)

    demand_rows: list[dict[str, Any]] = []
    for closure in partial_pnf_carrier.get("closure_pressure") or ():
        if not isinstance(closure, Mapping):
            raise ValueError("partial PNF carrier contains invalid closure rows")
        closure_state = _text(closure.get("closure_state"), "closure_state")
        if closure_state not in {
            "requires_external_resolution",
            "requires_local_typing",
        }:
            continue
        pnf_ref = _text(closure.get("pnf_ref"), "closure PNF ref")
        slot_ref = _text(closure.get("slot_ref"), "closure slot_ref")
        slot = slot_by_key.get((pnf_ref, slot_ref))
        if slot is None:
            raise ValueError("closure pressure references an unknown PNF slot")
        mention_ref = slot.get("mention_ref")
        if not mention_ref:
            raise ValueError("unresolved closure pressure requires a mention anchor")
        requested_facets = (
            ("identity", "type_compatibility")
            if closure_state == "requires_external_resolution"
            else ("local_semantic_typing",)
        )
        identity = {
            "input_carrier_ref": input_carrier_ref,
            "pnf_ref": pnf_ref,
            "slot_ref": slot_ref,
            "mention_ref": mention_ref,
            "expected_semantic_families": slot["expected_semantic_families"],
            "requested_facets": requested_facets,
            "source_closure_state": closure_state,
            "budget_class": budget,
        }
        demand_rows.append(
            ResolutionDemand(
                demand_ref=f"resolution-demand:{_canonical_digest(identity)}",
                pnf_ref=pnf_ref,
                slot_ref=slot_ref,
                mention_ref=str(mention_ref),
                expected_semantic_families=tuple(slot["expected_semantic_families"]),
                requested_facets=requested_facets,
                source_closure_state=closure_state,
                budget_class=budget,
            ).to_dict()
        )
    demand_rows.sort(key=lambda demand: demand["demand_ref"])
    if len({demand["demand_ref"] for demand in demand_rows}) != len(demand_rows):
        raise ValueError("resolution demand projection emitted duplicate demands")
    identity = {
        "schema_version": RESOLUTION_DEMAND_SCHEMA_VERSION,
        "authority": authority,
        "input_partial_pnf_carrier_ref": input_carrier_ref,
        "budget_class": budget,
        "demands": demand_rows,
        "serialization_order": "demand_ref_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"resolution-demand:{_canonical_digest(identity)}",
        "backend_effect": "none",
        "resolution_effect": "none",
        "pnf_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "demand_count": len(demand_rows),
            "source_closure_state_counts": {
                state: sum(
                    demand["source_closure_state"] == state for demand in demand_rows
                )
                for state in (
                    "requires_external_resolution",
                    "requires_local_typing",
                )
            },
        },
    }


def build_resolution_subject_carrier(
    *,
    partial_pnf_carrier: Mapping[str, Any],
    resolution_demand_carrier: Mapping[str, Any],
    subject_declarations: Sequence[ResolutionSubjectDeclaration | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Attach typed resolution subjects and semantic demand equivalence.

    Subject kinds and event formal roles are caller-declared rather than
    inferred from surfaces or catalogs. Equivalence groups preserve all member
    demands and subjects; they perform no scheduling, retrieval, or resolution.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("resolution subject authority must be candidate_only")
    if not isinstance(partial_pnf_carrier, Mapping) or (
        partial_pnf_carrier.get("schema_version") != PARTIAL_PNF_SCHEMA_VERSION
    ):
        raise ValueError("resolution subjects require a partial PNF carrier")
    if not isinstance(resolution_demand_carrier, Mapping) or (
        resolution_demand_carrier.get("schema_version")
        != RESOLUTION_DEMAND_SCHEMA_VERSION
    ):
        raise ValueError("resolution subjects require a resolution demand carrier")
    if (
        partial_pnf_carrier.get("authority") != ENTITY_RESOLUTION_AUTHORITY
        or resolution_demand_carrier.get("authority") != ENTITY_RESOLUTION_AUTHORITY
    ):
        raise ValueError("resolution subject inputs must remain candidate_only")
    partial_carrier_ref = _text(
        partial_pnf_carrier.get("carrier_ref"), "partial PNF carrier_ref"
    )
    demand_carrier_ref = _text(
        resolution_demand_carrier.get("carrier_ref"),
        "resolution demand carrier_ref",
    )
    if (
        resolution_demand_carrier.get("input_partial_pnf_carrier_ref")
        != partial_carrier_ref
    ):
        raise ValueError("resolution demand carrier does not match partial PNF input")

    mention_document = {
        _text(mention.get("mention_ref"), "mention_ref"): _text(
            mention.get("document_ref"), "mention document_ref"
        )
        for mention in partial_pnf_carrier.get("mentions") or ()
        if isinstance(mention, Mapping)
    }
    slot_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for pnf in partial_pnf_carrier.get("partial_pnfs") or ():
        if not isinstance(pnf, Mapping):
            raise ValueError("partial PNF carrier contains invalid PNF rows")
        pnf_ref = _text(pnf.get("pnf_ref"), "partial PNF ref")
        for slot in pnf.get("slots") or ():
            if not isinstance(slot, Mapping):
                raise ValueError("partial PNF carrier contains invalid slot rows")
            slot_ref = _text(slot.get("slot_ref"), "partial PNF slot_ref")
            slot_by_key[(pnf_ref, slot_ref)] = dict(slot)
    local_types_by_slot: dict[tuple[str, str], list[str]] = {}
    for alternative in partial_pnf_carrier.get("slot_alternatives") or ():
        if not isinstance(alternative, Mapping):
            raise ValueError("partial PNF carrier contains invalid alternatives")
        key = (
            _text(alternative.get("pnf_ref"), "slot alternative PNF ref"),
            _text(alternative.get("slot_ref"), "slot alternative slot ref"),
        )
        local_types_by_slot.setdefault(key, []).append(
            _text(
                alternative.get("local_type_ref"),
                "slot alternative local type ref",
            )
        )

    demand_by_ref: dict[str, dict[str, Any]] = {}
    for demand in resolution_demand_carrier.get("demands") or ():
        if not isinstance(demand, Mapping):
            raise ValueError("resolution demand carrier contains invalid rows")
        demand_ref = _text(demand.get("demand_ref"), "resolution demand_ref")
        if demand_ref in demand_by_ref:
            raise ValueError("resolution demand references must be unique")
        demand_by_ref[demand_ref] = dict(demand)
    declaration_rows = sorted(
        (
            _coerce_resolution_subject_declaration(declaration).to_dict()
            for declaration in subject_declarations
        ),
        key=lambda declaration: declaration["declaration_ref"],
    )
    declaration_refs = [row["declaration_ref"] for row in declaration_rows]
    if len(declaration_refs) != len(set(declaration_refs)):
        raise ValueError("resolution subject declaration references must be unique")
    declared_demand_refs = [row["demand_ref"] for row in declaration_rows]
    if len(declared_demand_refs) != len(set(declared_demand_refs)):
        raise ValueError("each resolution demand requires one subject declaration")
    if set(declared_demand_refs) != set(demand_by_ref):
        raise ValueError(
            "resolution subject declarations must cover exactly the demand set"
        )

    subject_rows: list[dict[str, Any]] = []
    demand_subject_links: list[dict[str, Any]] = []
    equivalence_members: dict[str, dict[str, Any]] = {}
    for declaration in declaration_rows:
        demand = demand_by_ref[declaration["demand_ref"]]
        key = (
            _text(demand.get("pnf_ref"), "resolution demand PNF ref"),
            _text(demand.get("slot_ref"), "resolution demand slot ref"),
        )
        slot = slot_by_key.get(key)
        if slot is None:
            raise ValueError("resolution demand references an unknown PNF slot")
        mention_ref = _text(demand.get("mention_ref"), "resolution demand mention ref")
        document_ref = mention_document.get(mention_ref)
        if document_ref is None:
            raise ValueError("resolution demand references an unknown mention")
        constraints = declaration["constraints"]
        local_type_refs = sorted(set(local_types_by_slot.get(key, ())))
        subject_payload: dict[str, Any] = {
            "declaration_ref": declaration["declaration_ref"],
            "demand_ref": declaration["demand_ref"],
            "target_ref": declaration["target_ref"],
            "subject_kind": declaration["subject_kind"],
            "mention_ref": mention_ref,
            "document_ref": document_ref,
            "pnf_slot_role": slot["slot_kind"],
            "expected_semantic_families": sorted(
                set(demand["expected_semantic_families"])
            ),
            "local_type_refs": local_type_refs,
            "source_scope": declaration["source_scope"],
            "constraints": constraints,
            "authority": ENTITY_RESOLUTION_AUTHORITY,
        }
        if declaration.get("formal_role"):
            subject_payload["formal_role"] = declaration["formal_role"]
        subject_ref = f"resolution-subject:{_canonical_digest(subject_payload)}"
        subject = {"subject_ref": subject_ref, **subject_payload}
        subject_rows.append(subject)
        demand_subject_links.append(
            {
                "demand_ref": demand["demand_ref"],
                "resolution_subject_ref": subject_ref,
                "authority": ENTITY_RESOLUTION_AUTHORITY,
            }
        )

        constraint_semantics = sorted(
            (
                {
                    "constraint_kind": constraint["constraint_kind"],
                    "payload": constraint["payload"],
                }
                for constraint in constraints
            ),
            key=lambda constraint: (
                constraint["constraint_kind"],
                _canonical_digest(constraint["payload"]),
            ),
        )
        semantic_key: dict[str, Any] = {
            "target_ref": declaration["target_ref"],
            "subject_kind": declaration["subject_kind"],
            "document_ref": document_ref,
            "pnf_slot_role": slot["slot_kind"],
            "expected_semantic_families": subject_payload["expected_semantic_families"],
            "local_type_refs": local_type_refs,
            "source_scope": declaration["source_scope"],
            "constraints": constraint_semantics,
            "requested_facets": sorted(set(demand["requested_facets"])),
            "budget_classes": [
                _text(demand.get("budget_class"), "demand budget class")
            ],
        }
        if declaration.get("formal_role"):
            semantic_key["formal_role"] = declaration["formal_role"]
        semantic_key_sha256 = _canonical_digest(semantic_key)
        group = equivalence_members.setdefault(
            semantic_key_sha256,
            {
                "equivalence_ref": f"demand-equivalence:{semantic_key_sha256}",
                "semantic_key_sha256": semantic_key_sha256,
                "semantic_key": semantic_key,
                "member_demand_refs": [],
                "resolution_subject_refs": [],
                "authority": ENTITY_RESOLUTION_AUTHORITY,
            },
        )
        group["member_demand_refs"].append(demand["demand_ref"])
        group["resolution_subject_refs"].append(subject_ref)

    subject_rows.sort(key=lambda subject: subject["subject_ref"])
    demand_subject_links.sort(key=lambda link: link["demand_ref"])
    equivalence_groups = sorted(
        equivalence_members.values(), key=lambda group: group["equivalence_ref"]
    )
    for group in equivalence_groups:
        group["member_demand_refs"] = sorted(set(group["member_demand_refs"]))
        group["resolution_subject_refs"] = sorted(set(group["resolution_subject_refs"]))
        group["member_count"] = len(group["member_demand_refs"])

    identity = {
        "schema_version": RESOLUTION_SUBJECT_SCHEMA_VERSION,
        "authority": authority,
        "input_partial_pnf_carrier_ref": partial_carrier_ref,
        "input_resolution_demand_carrier_ref": demand_carrier_ref,
        "subject_declarations": declaration_rows,
        "resolution_subjects": subject_rows,
        "demand_subject_links": demand_subject_links,
        "equivalence_groups": equivalence_groups,
        "serialization_order": "reference_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"resolution-subject:{_canonical_digest(identity)}",
        "deduplication_effect": "receipt_only",
        "backend_effect": "none",
        "resolution_effect": "none",
        "pnf_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "demand_count": len(demand_by_ref),
            "resolution_subject_count": len(subject_rows),
            "equivalence_group_count": len(equivalence_groups),
            "coalescible_demand_count": len(demand_by_ref) - len(equivalence_groups),
            "grouped_equivalence_count": sum(
                group["member_count"] > 1 for group in equivalence_groups
            ),
        },
    }


def build_candidate_retrieval_carrier(
    *,
    mentions: Sequence[MentionSpan | Mapping[str, Any]],
    catalog_entries: Sequence[CandidateCatalogEntry | Mapping[str, Any]],
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Match anchored mentions against a bounded local candidate catalog.

    This is deliberately an offline exact-token matcher. It creates one
    candidate set for every supplied mention, including an explicit empty set
    when the bounded catalog offers no alternative. It neither ranks nor
    resolves the alternatives: deterministic output order is serialization
    only. It has no network, PNF, promotion, or execution effect.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("candidate retrieval authority must be candidate_only")

    mention_rows = sorted(
        (_coerce_mention(mention).to_dict() for mention in mentions),
        key=lambda mention: mention["mention_ref"],
    )
    mention_refs = [mention["mention_ref"] for mention in mention_rows]
    if len(mention_refs) != len(set(mention_refs)):
        raise ValueError("candidate retrieval mention references must be unique")

    catalog_rows = sorted(
        (_coerce_catalog_entry(entry).to_dict() for entry in catalog_entries),
        key=lambda entry: entry["catalog_entry_ref"],
    )
    catalog_refs = [entry["catalog_entry_ref"] for entry in catalog_rows]
    if len(catalog_refs) != len(set(catalog_refs)):
        raise ValueError("candidate catalog entry references must be unique")

    entries_by_sequence: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for entry in catalog_rows:
        for sequence in entry["match_token_sequences"]:
            entries_by_sequence.setdefault(tuple(sequence), []).append(entry)

    candidate_set_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    for mention in mention_rows:
        token_sequence = _mention_token_sequence(mention["canonical_surface"])
        matching_entries = entries_by_sequence.get(token_sequence, [])
        candidates: list[EntityCandidate] = []
        for entry in matching_entries:
            candidate_ref = (
                f"candidate-retrieval:{mention['mention_ref']}:"
                f"{entry['catalog_entry_ref']}"
            )
            candidates.append(
                EntityCandidate(
                    candidate_ref=candidate_ref,
                    candidate_kind=entry["candidate_kind"],
                    identity_ref=entry["identity_ref"],
                    label=entry["label"],
                    evidence_refs=tuple(entry["evidence_refs"]),
                    registry_snapshot_ref=entry.get("registry_snapshot_ref"),
                )
            )
            match_rows.append(
                {
                    "mention_ref": mention["mention_ref"],
                    "catalog_entry_ref": entry["catalog_entry_ref"],
                    "candidate_ref": candidate_ref,
                    "match_kind": "exact_canonical_token_sequence",
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )
        candidate_set_rows.append(
            EntityCandidateSet(
                mention_ref=mention["mention_ref"], candidates=tuple(candidates)
            ).to_dict()
        )

    candidate_set_rows.sort(key=lambda candidate_set: candidate_set["mention_ref"])
    match_rows.sort(
        key=lambda match: (match["mention_ref"], match["catalog_entry_ref"])
    )
    identity = {
        "schema_version": CANDIDATE_RETRIEVAL_SCHEMA_VERSION,
        "authority": authority,
        "mentions": mention_rows,
        "catalog_entries": catalog_rows,
        "candidate_sets": candidate_set_rows,
        "matches": match_rows,
    }
    return {
        **identity,
        "carrier_ref": f"candidate-retrieval:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "input_mention_count": len(mention_rows),
            "catalog_entry_count": len(catalog_rows),
            "candidate_set_count": len(candidate_set_rows),
            "candidate_count": sum(
                len(candidate_set["candidates"]) for candidate_set in candidate_set_rows
            ),
            "unmatched_mention_count": sum(
                not candidate_set["candidates"] for candidate_set in candidate_set_rows
            ),
        },
    }


def build_resolution_schedule_carrier(
    *,
    resolution_subject_carrier: Mapping[str, Any],
    cache_entries: Sequence[ResolutionCacheEntry | Mapping[str, Any]] = (),
    backend_capabilities: Sequence[
        ResolutionBackendCapability | Mapping[str, Any]
    ] = (),
    allowed_budget_classes: Sequence[str] = (),
    accept_stale: bool = False,
    authority: str = ENTITY_RESOLUTION_AUTHORITY,
) -> dict[str, Any]:
    """Plan cache-aware backend work without performing I/O or resolving identity.

    One plan is produced per semantic demand-equivalence group. Cache entries
    are immutable metadata supplied by the caller; backend capabilities are
    declarations only. The result records an execution state and any
    microbatch reference, but has no backend, resolution, PNF, or promotion
    effect.
    """

    if authority != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("resolution scheduling authority must be candidate_only")
    if (
        not isinstance(resolution_subject_carrier, Mapping)
        or resolution_subject_carrier.get("schema_version")
        != RESOLUTION_SUBJECT_SCHEMA_VERSION
    ):
        raise ValueError("scheduling requires a resolution subject carrier")
    if resolution_subject_carrier.get("authority") != ENTITY_RESOLUTION_AUTHORITY:
        raise ValueError("scheduling inputs must remain candidate_only")

    cache_rows = sorted(
        (_coerce_cache_entry(entry).to_dict() for entry in cache_entries),
        key=lambda row: (row["cache_key"], row["backend_ref"]),
    )
    cache_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in cache_rows:
        cache_by_key.setdefault(row["cache_key"], []).append(row)
    capability_rows = sorted(
        (
            _coerce_backend_capability(capability).to_dict()
            for capability in backend_capabilities
        ),
        key=lambda row: row["backend_ref"],
    )
    backend_refs = [row["backend_ref"] for row in capability_rows]
    if len(backend_refs) != len(set(backend_refs)):
        raise ValueError("backend capability references must be unique")
    allowed = {_text(value, "allowed budget class") for value in allowed_budget_classes}

    equivalence_groups = sorted(
        (
            dict(group)
            for group in resolution_subject_carrier.get("equivalence_groups") or ()
        ),
        key=lambda group: group["equivalence_ref"],
    )
    plans: list[dict[str, Any]] = []
    batch_members: dict[tuple[str, str, int], list[str]] = {}
    for group in equivalence_groups:
        group_ref = _text(group.get("equivalence_ref"), "equivalence_ref")
        member_demands = sorted(_refs(group.get("member_demand_refs")))
        if not member_demands:
            raise ValueError("equivalence groups require member demands")
        subject_refs = sorted(_refs(group.get("resolution_subject_refs")))
        subjects = [
            subject
            for subject in resolution_subject_carrier.get("resolution_subjects") or ()
            if subject.get("subject_ref") in set(subject_refs)
        ]
        if not subjects:
            raise ValueError("equivalence group references unknown subjects")
        semantic_key = group.get("semantic_key")
        if not isinstance(semantic_key, Mapping):
            raise ValueError("equivalence groups require semantic keys")
        subject_kind = _text(semantic_key.get("subject_kind"), "semantic subject kind")
        formal_role = semantic_key.get("formal_role")
        if formal_role:
            formal_role = _text(formal_role, "semantic formal role")
        facets = set(_refs(semantic_key.get("requested_facets")))
        budget_classes = set(_refs(semantic_key.get("budget_classes")))
        if allowed and not budget_classes.intersection(allowed):
            plans.append(
                {
                    "equivalence_ref": group_ref,
                    "member_demand_refs": member_demands,
                    "state": "budget_exhausted",
                    "reason": "budget_class_not_allowed",
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )
            continue
        cache_key = f"resolution:{group['semantic_key_sha256']}"
        cached = cache_by_key.get(cache_key, [])
        if cached:
            cache = cached[0]
            state = cache["cache_state"]
            if state == "fresh":
                plans.append(
                    {
                        "equivalence_ref": group_ref,
                        "member_demand_refs": member_demands,
                        "state": "fresh_cache_hit",
                        "cache_key": cache_key,
                        "backend_ref": cache["backend_ref"],
                        "evidence_ref": cache.get("evidence_ref"),
                        "authority": ENTITY_RESOLUTION_AUTHORITY,
                    }
                )
                continue
            if state == "negative":
                plans.append(
                    {
                        "equivalence_ref": group_ref,
                        "member_demand_refs": member_demands,
                        "state": "negative_cache_hit",
                        "cache_key": cache_key,
                        "backend_ref": cache["backend_ref"],
                        "authority": ENTITY_RESOLUTION_AUTHORITY,
                    }
                )
                continue
            if state == "stale" and accept_stale:
                plans.append(
                    {
                        "equivalence_ref": group_ref,
                        "member_demand_refs": member_demands,
                        "state": "stale_cache_hit",
                        "cache_key": cache_key,
                        "backend_ref": cache["backend_ref"],
                        "evidence_ref": cache.get("evidence_ref"),
                        "authority": ENTITY_RESOLUTION_AUTHORITY,
                    }
                )
                continue

        capable = []
        for backend in capability_rows:
            if subject_kind not in backend["subject_kinds"]:
                continue
            if (
                formal_role
                and backend["formal_roles"]
                and formal_role not in backend["formal_roles"]
            ):
                continue
            if not facets.issubset(set(backend["facets"])):
                continue
            capable.append(backend)
        if not capable:
            plans.append(
                {
                    "equivalence_ref": group_ref,
                    "member_demand_refs": member_demands,
                    "state": "unsupported_demand",
                    "reason": "no_capable_backend",
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )
            continue
        backend = capable[0]
        if not backend["available"]:
            plans.append(
                {
                    "equivalence_ref": group_ref,
                    "member_demand_refs": member_demands,
                    "state": "backend_unavailable",
                    "backend_ref": backend["backend_ref"],
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )
            continue
        batch_key = (
            backend["backend_ref"],
            backend["rate_limit_class"],
            backend["max_batch_size"],
        )
        batch_members.setdefault(batch_key, []).append(group_ref)
        plans.append(
            {
                "equivalence_ref": group_ref,
                "member_demand_refs": member_demands,
                "state": "fetch_planned",
                "backend_ref": backend["backend_ref"],
                "batch_key": ":".join(map(str, batch_key)),
                "cache_key": cache_key,
                "authority": ENTITY_RESOLUTION_AUTHORITY,
            }
        )

    batches: list[dict[str, Any]] = []
    for (backend_ref, rate_class, max_size), members in sorted(batch_members.items()):
        ordered = sorted(members)
        for index in range(0, len(ordered), max_size):
            chunk = ordered[index : index + max_size]
            batch_ref = f"resolution-batch:{_canonical_digest([backend_ref, rate_class, chunk])}"
            batches.append(
                {
                    "batch_ref": batch_ref,
                    "backend_ref": backend_ref,
                    "rate_limit_class": rate_class,
                    "member_equivalence_refs": chunk,
                    "authority": ENTITY_RESOLUTION_AUTHORITY,
                }
            )
            for plan in plans:
                if (
                    plan.get("equivalence_ref") in chunk
                    and plan["state"] == "fetch_planned"
                ):
                    plan["batch_ref"] = batch_ref
    identity = {
        "schema_version": RESOLUTION_SCHEDULER_SCHEMA_VERSION,
        "authority": authority,
        "input_resolution_subject_carrier_ref": _text(
            resolution_subject_carrier.get("carrier_ref"), "subject carrier_ref"
        ),
        "cache_entries": cache_rows,
        "backend_capabilities": capability_rows,
        "plans": sorted(plans, key=lambda row: row["equivalence_ref"]),
        "batches": batches,
        "serialization_order": "reference_nonsemantic",
    }
    return {
        **identity,
        "carrier_ref": f"resolution-schedule:{_canonical_digest(identity)}",
        "cache_effect": "none",
        "backend_effect": "plan_only",
        "resolution_effect": "none",
        "pnf_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "equivalence_group_count": len(equivalence_groups),
            "plan_count": len(plans),
            "batch_count": len(batches),
            "state_counts": {
                state: sum(plan["state"] == state for plan in plans)
                for state in sorted(_SCHEDULE_STATES)
            },
        },
    }


def _canonical_token_interval(
    tokens: Sequence[tuple[str, int, int]], start_char: int, end_char: int
) -> tuple[int, int] | None:
    indexes = [
        index
        for index, (_text_value, token_start, token_end) in enumerate(tokens)
        if token_start >= start_char and token_end <= end_char
    ]
    if not indexes:
        return None
    return indexes[0], indexes[-1] + 1


def _annotation_by_span(
    parsed: Mapping[str, Any],
) -> dict[tuple[int, int], dict[str, Any]]:
    annotations: dict[tuple[int, int], dict[str, Any]] = {}
    for sentence in parsed.get("sents", ()):
        for token in sentence.get("tokens", ()):
            start = token.get("start")
            end = token.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or end <= start:
                continue
            annotations[(start, end)] = dict(token)
    return annotations


def _local_types(annotation: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not annotation:
        return ("lexical_span",)
    pos = str(annotation.get("pos") or "").strip()
    if pos == "PROPN":
        return ("proper_name", "lexical_span")
    if pos == "NOUN":
        return ("common_noun", "lexical_span")
    if pos == "NUM":
        return ("numeric_expression", "lexical_span")
    if pos in {"VERB", "AUX"}:
        return ("linguistic_eventuality", "lexical_span")
    return ("lexical_span",)


def _lexical_expected_kinds(annotation: Mapping[str, Any] | None) -> tuple[str, ...]:
    pos = str((annotation or {}).get("pos") or "").strip()
    if pos == "NUM":
        return ("literal",)
    if pos == "PROPN":
        return ("document_local", "instance")
    if pos == "NOUN":
        return ("class", "instance", "property", "role")
    if pos in {"VERB", "AUX"}:
        return ("event_type", "property")
    return ("class", "document_local", "event_type", "instance", "property", "role")


def _is_lexical_token(token: str) -> bool:
    return any(character.isalnum() for character in token)


def _name_shaped_phrases(parsed: Mapping[str, Any]) -> list[tuple[int, int]]:
    phrases: list[tuple[int, int]] = []
    for sentence in parsed.get("sents", ()):
        run: list[Mapping[str, Any]] = []
        for token in sentence.get("tokens", ()):
            if str(token.get("pos") or "") == "PROPN":
                run.append(token)
                continue
            if run:
                phrases.append((int(run[0]["start"]), int(run[-1]["end"])))
                run = []
        if run:
            phrases.append((int(run[0]["start"]), int(run[-1]["end"])))
    return phrases


def build_mention_licensing_carrier(
    *,
    canonical_text: str,
    source_ref: str,
    document_ref: str,
    context_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build deterministic, backend-free licenses over a recoverable span lattice.

    This is a cheap structural admission stage. It does not query a registry,
    construct candidate identities, resolve a mention, alter PNF, or promote a
    claim. Every canonical token boundary remains recoverable through the
    lattice summary even where a span is deliberately not materialized.
    """

    text = str(canonical_text)
    if not text:
        raise ValueError("mention licensing requires canonical_text")
    source = _text(source_ref, "source_ref")
    document = _text(document_ref, "document_ref")
    canonical_context_refs = _refs(context_refs)
    tokens = tokenize_canonical_with_spans(text)
    parsed = parse_canonical_text(text)
    annotations = _annotation_by_span(parsed)

    proposed: dict[
        tuple[int, int], list[tuple[str, tuple[str, ...], tuple[str, ...]]]
    ] = {}
    suppressed: list[SuppressedSpan] = []
    for token_index, (token, start_char, end_char) in enumerate(tokens):
        normalized = token.strip().lower()
        if not _is_lexical_token(token):
            suppressed.append(
                SuppressedSpan(token_index, token_index + 1, "punctuation_or_symbol")
            )
            continue
        if normalized in _STRUCTURAL_LEXEMES:
            suppressed.append(
                SuppressedSpan(token_index, token_index + 1, "structural_lexeme")
            )
            continue
        annotation = annotations.get((start_char, end_char))
        proposed.setdefault((start_char, end_char), []).append(
            (
                "lexical_token",
                _lexical_expected_kinds(annotation),
                _local_types(annotation),
            )
        )

    for start_char, end_char in _name_shaped_phrases(parsed):
        proposed.setdefault((start_char, end_char), []).append(
            (
                "named_entity_shape",
                ("document_local", "instance"),
                ("proper_name_phrase",),
            )
        )

    for (start_char, end_char), annotation in annotations.items():
        pos = str(annotation.get("pos") or "")
        if pos == "NUM":
            proposed.setdefault((start_char, end_char), []).append(
                (
                    "numeric_literal",
                    ("event_type", "literal"),
                    ("numeric_expression",),
                )
            )
        if pos in {"VERB", "AUX"}:
            proposed.setdefault((start_char, end_char), []).append(
                (
                    "eventuality_annotation",
                    ("event_type", "property"),
                    ("linguistic_eventuality",),
                )
            )

    mention_rows: list[dict[str, Any]] = []
    license_rows: list[dict[str, Any]] = []
    for start_char, end_char in sorted(proposed):
        interval = _canonical_token_interval(tokens, start_char, end_char)
        if interval is None:
            continue
        start_token, end_token = interval
        mention_ref = f"mention:{document}:{start_char}:{end_char}"
        specifications = sorted(
            proposed[(start_char, end_char)],
            key=lambda specification: _LICENSE_PRIORITY[specification[0]],
        )
        primary_kind = specifications[0][0]
        mention_rows.append(
            MentionSpan(
                mention_ref=mention_ref,
                source_ref=source,
                document_ref=document,
                start_char=start_char,
                end_char=end_char,
                canonical_surface=text[start_char:end_char],
                generation_reason=primary_kind,
                grammatical_role=(
                    "eventuality_predicate"
                    if primary_kind == "eventuality_annotation"
                    else None
                ),
                context_refs=canonical_context_refs,
                start_token=start_token,
                end_token=end_token,
            ).to_dict()
        )
        for license_index, (license_kind, expected_kinds, local_types) in enumerate(
            specifications
        ):
            license_rows.append(
                MentionLicense(
                    license_ref=f"license:{mention_ref}:{license_kind}:{license_index}",
                    mention_ref=mention_ref,
                    license_kind=license_kind,
                    expected_candidate_kinds=expected_kinds,
                    local_type_hypotheses=local_types,
                    priority=_LICENSE_PRIORITY[license_kind],
                ).to_dict()
            )

    mention_rows.sort(key=lambda mention: mention["mention_ref"])
    license_rows.sort(key=lambda license_row: license_row["license_ref"])
    suppressed_rows = sorted(
        (span.to_dict() for span in suppressed),
        key=lambda span: (
            span["start_token"],
            span["end_token"],
            span["suppression_reason"],
        ),
    )
    identity = {
        "schema_version": MENTION_LICENSING_SCHEMA_VERSION,
        "authority": ENTITY_RESOLUTION_AUTHORITY,
        "source_ref": source,
        "document_ref": document,
        "canonical_text_sha256": _canonical_digest(text),
        "lattice": {
            "token_count": len(tokens),
            "token_boundary_count": len(tokens) + 1,
            "recoverable_contiguous_span_count": len(tokens) * (len(tokens) + 1) // 2,
        },
        "mentions": mention_rows,
        "licenses": license_rows,
        "suppressed_spans": suppressed_rows,
    }
    return {
        **identity,
        "carrier_ref": f"mention-licensing:{_canonical_digest(identity)}",
        "resolution_effect": "none",
        "promotion_effect": "none",
        "execution_effect": "none",
        "summary": {
            "materialized_mention_count": len(mention_rows),
            "license_count": len(license_rows),
            "suppressed_span_count": len(suppressed_rows),
            "eventuality_license_count": sum(
                row["license_kind"] == "eventuality_annotation" for row in license_rows
            ),
        },
    }


__all__ = [
    "ALIAS_EXPANSION_SCHEMA_VERSION",
    "CANDIDATE_RETRIEVAL_SCHEMA_VERSION",
    "ENTITY_RESOLUTION_AUTHORITY",
    "ENTITY_RESOLUTION_SCHEMA_VERSION",
    "FORM_DERIVATION_SCHEMA_VERSION",
    "GRAMMAR_EXPANSION_SCHEMA_VERSION",
    "LOCAL_TYPING_SCHEMA_VERSION",
    "PARTIAL_PNF_SCHEMA_VERSION",
    "RESOLUTION_DEMAND_SCHEMA_VERSION",
    "RESOLUTION_SCHEDULER_SCHEMA_VERSION",
    "RESOLUTION_SUBJECT_SCHEMA_VERSION",
    "MENTION_LICENSING_SCHEMA_VERSION",
    "MENTION_RECURRENCE_SCHEMA_VERSION",
    "MENTION_EXPANSION_SCHEMA_VERSION",
    "CoreferenceCluster",
    "CandidateCatalogEntry",
    "EntityCandidate",
    "EntityCandidateSet",
    "FormCandidate",
    "FormCompositionRule",
    "FormLexiconEntry",
    "FormRelation",
    "LocalTypeAlternative",
    "LocalTypingRule",
    "CoveragePressureAssessment",
    "ClosurePressureAssessment",
    "MentionLicense",
    "MentionAliasEntry",
    "MentionExpansionRequest",
    "MentionRecurrenceGroup",
    "MentionSpan",
    "PartialPNF",
    "PartialPNFSlot",
    "PNFSlotAlternative",
    "ResolutionDemand",
    "ResolutionCacheEntry",
    "ResolutionBackendCapability",
    "ResolutionConstraint",
    "ResolutionSubjectDeclaration",
    "SuppressedSpan",
    "build_mention_licensing_carrier",
    "build_candidate_retrieval_carrier",
    "build_alias_expansion_requests",
    "build_grammar_expansion_requests",
    "build_mention_expansion_carrier",
    "build_mention_recurrence_carrier",
    "build_entity_resolution_carrier",
    "build_form_derivation_carrier",
    "build_local_typing_carrier",
    "build_partial_pnf_carrier",
    "build_resolution_demand_carrier",
    "build_resolution_subject_carrier",
    "build_resolution_schedule_carrier",
]
