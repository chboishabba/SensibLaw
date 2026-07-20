from __future__ import annotations

"""DASHI carrier motif annotations for non-promoting PNF review metadata."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .residual_lattice import PredicateAtom, PredicatePNF


CARRIER_MOTIF_SCHEMA = "sl.dashi_carrier_motif_spine.v0_1"
CARRIER_MOTIF_MODIFIER_KEY = "dashi_carrier_motif_spine"


class CarrierMotif(str, Enum):
    MOTIF_369 = "motif369"
    MOTIF_CARRY = "motifCarry"
    MOTIF_DIALECTIC = "motifDialectic"
    MOTIF_BRAID = "motifBraid"
    MOTIF_BT_TREE = "motifBTTree"
    MOTIF_P_ADIC = "motifPAdic"
    MOTIF_SUPERVOXEL = "motifSupervoxel"
    MOTIF_FASCISTIC_CONTRACTION = "motifFascisticContraction"
    MOTIF_ANTIFASCIST_INVERTIBILITY = "motifAntifascistInvertibility"
    MOTIF_WAVE_TRANSPORT = "motifWaveTransport"
    MOTIF_WEAVE = "motifWeave"
    MOTIF_KNOT = "motifKnot"


class CarrierRole(str, Enum):
    LOCAL_STATE = "localState"
    ORIENTATION = "orientation"
    MEMORY = "memory"
    DEFECT = "defect"
    PRESSURE = "pressure"
    ADMISSIBILITY = "admissibility"
    TRANSPORT = "transport"
    BINDING = "binding"
    NON_PROMOTION_BOUNDARY = "nonPromotionBoundary"


class ProjectionTarget(str, Enum):
    PREDICATE = "predicateTarget"
    SUBJECT = "subjectTarget"
    ACTION = "actionTarget"
    OBJECT = "objectTarget"
    QUALIFIER = "qualifierTarget"
    MODIFIER_DIAGNOSTIC = "modifierDiagnosticTarget"
    PROVENANCE = "provenanceTarget"
    DROPPED = "droppedTarget"


_PROJECTION_TARGET_ALIASES = {
    "predicate": ProjectionTarget.PREDICATE,
    "predicate_target": ProjectionTarget.PREDICATE,
    "subject": ProjectionTarget.SUBJECT,
    "subject_target": ProjectionTarget.SUBJECT,
    "action": ProjectionTarget.ACTION,
    "action_target": ProjectionTarget.ACTION,
    "object": ProjectionTarget.OBJECT,
    "object_target": ProjectionTarget.OBJECT,
    "qualifier": ProjectionTarget.QUALIFIER,
    "qualifier_target": ProjectionTarget.QUALIFIER,
    "modifier_diagnostic": ProjectionTarget.MODIFIER_DIAGNOSTIC,
    "modifier_diagnostic_target": ProjectionTarget.MODIFIER_DIAGNOSTIC,
    "provenance": ProjectionTarget.PROVENANCE,
    "provenance_target": ProjectionTarget.PROVENANCE,
    "dropped": ProjectionTarget.DROPPED,
    "dropped_target": ProjectionTarget.DROPPED,
}


@dataclass(frozen=True, slots=True)
class CarrierMotifAnnotation:
    """Non-promoting DASHI motif metadata for PNF review artifacts."""

    motif: CarrierMotif
    roles: tuple[CarrierRole, ...] = (CarrierRole.NON_PROMOTION_BOUNDARY,)
    source_surface: Mapping[str, Any] | None = None
    projection_target: ProjectionTarget = ProjectionTarget.MODIFIER_DIAGNOSTIC
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CARRIER_MOTIF_SCHEMA,
            "motif": self.motif.value,
            "roles": [role.value for role in self.roles],
            "projection_target": self.projection_target.value,
            "authority_boundary": {
                "non_authoritative": True,
                "promotion_authority": False,
                "legal_authority": False,
                "wikidata_live_edit_authority": False,
            },
        }
        if self.source_surface is not None:
            payload["source_surface"] = dict(self.source_surface)
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        return payload


def coerce_carrier_motif_annotation(
    value: CarrierMotifAnnotation | Mapping[str, Any],
    *,
    strict: bool = True,
) -> CarrierMotifAnnotation:
    """Validate and normalize a carrier motif annotation.

    Strict mode rejects unknown motif and role labels. Non-strict mode keeps the
    annotation non-promoting by returning a diagnostic ``motifDialectic``
    placeholder for unknown motifs and dropping unknown roles.
    """

    if isinstance(value, CarrierMotifAnnotation):
        return _ensure_non_promoting_annotation(value)
    if not isinstance(value, Mapping):
        raise TypeError("carrier motif annotation must be a mapping or CarrierMotifAnnotation")

    schema = value.get("schema", CARRIER_MOTIF_SCHEMA)
    if schema != CARRIER_MOTIF_SCHEMA:
        raise ValueError(f"unsupported carrier motif schema: {schema!r}")

    diagnostics: list[str] = []
    motif = _coerce_motif(value.get("motif"), strict=strict, diagnostics=diagnostics)
    roles = _coerce_roles(value.get("roles"), strict=strict, diagnostics=diagnostics)
    projection_target = _coerce_projection_target(
        value.get("projection_target", ProjectionTarget.MODIFIER_DIAGNOSTIC.value),
        strict=strict,
        diagnostics=diagnostics,
    )
    source_surface = value.get("source_surface")
    if source_surface is not None and not isinstance(source_surface, Mapping):
        if strict:
            raise ValueError("source_surface must be a mapping when supplied")
        diagnostics.append("source_surface was not a mapping and was dropped")
        source_surface = None

    boundary = value.get("authority_boundary")
    _validate_non_promoting_boundary(boundary, strict=strict, diagnostics=diagnostics)

    annotation = CarrierMotifAnnotation(
        motif=motif,
        roles=roles,
        source_surface=source_surface,
        projection_target=projection_target,
        diagnostics=tuple(diagnostics),
    )
    return _ensure_non_promoting_annotation(annotation)


def attach_carrier_motif_modifier(
    atom: PredicatePNF,
    annotation: CarrierMotifAnnotation | Mapping[str, Any],
    *,
    strict: bool = True,
) -> PredicateAtom:
    """Return a copied atom with the motif annotation attached as a modifier."""

    normalized = coerce_carrier_motif_annotation(annotation, strict=strict)
    modifiers = dict(atom.modifiers)
    existing = modifiers.get(CARRIER_MOTIF_MODIFIER_KEY)
    annotation_payload = normalized.to_dict()
    if existing is None:
        modifiers[CARRIER_MOTIF_MODIFIER_KEY] = annotation_payload
    elif isinstance(existing, list):
        modifiers[CARRIER_MOTIF_MODIFIER_KEY] = [*existing, annotation_payload]
    else:
        modifiers[CARRIER_MOTIF_MODIFIER_KEY] = [existing, annotation_payload]

    return PredicateAtom(
        predicate=atom.predicate,
        structural_signature=atom.structural_signature,
        roles=atom.roles,
        qualifiers=atom.qualifiers,
        wrapper=replace(atom.wrapper, evidence_only=True),
        modifiers=modifiers,
        provenance=atom.provenance,
        atom_id=atom.atom_id,
        domain=atom.domain,
        support_fibres=atom.support_fibres,
        latent_grounding=atom.latent_grounding,
        semantic_comparison_mode=atom.semantic_comparison_mode,
    )


def _ensure_non_promoting_annotation(annotation: CarrierMotifAnnotation) -> CarrierMotifAnnotation:
    roles = annotation.roles or (CarrierRole.NON_PROMOTION_BOUNDARY,)
    if CarrierRole.NON_PROMOTION_BOUNDARY not in roles:
        roles = (*roles, CarrierRole.NON_PROMOTION_BOUNDARY)
    return replace(annotation, roles=tuple(dict.fromkeys(roles)))


def _coerce_motif(raw: Any, *, strict: bool, diagnostics: list[str]) -> CarrierMotif:
    if isinstance(raw, CarrierMotif):
        return raw
    try:
        return CarrierMotif(str(raw))
    except ValueError:
        if strict:
            raise ValueError(f"unknown carrier motif: {raw!r}") from None
        diagnostics.append(f"unknown motif {raw!r}; held as diagnostic")
        return CarrierMotif.MOTIF_DIALECTIC


def _coerce_roles(raw: Any, *, strict: bool, diagnostics: list[str]) -> tuple[CarrierRole, ...]:
    if raw is None:
        return (CarrierRole.NON_PROMOTION_BOUNDARY,)
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raw_roles = (raw,)
    else:
        raw_roles = tuple(raw)

    roles: list[CarrierRole] = []
    for item in raw_roles:
        if isinstance(item, CarrierRole):
            role = item
        else:
            try:
                role = CarrierRole(str(item))
            except ValueError:
                if strict:
                    raise ValueError(f"unknown carrier role: {item!r}") from None
                diagnostics.append(f"unknown role {item!r}; dropped")
                continue
        if role not in roles:
            roles.append(role)
    if not roles:
        roles.append(CarrierRole.NON_PROMOTION_BOUNDARY)
    return tuple(roles)


def _coerce_projection_target(
    raw: Any,
    *,
    strict: bool,
    diagnostics: list[str],
) -> ProjectionTarget:
    if isinstance(raw, ProjectionTarget):
        return raw
    raw_text = str(raw)
    try:
        return ProjectionTarget(raw_text)
    except ValueError:
        alias = _PROJECTION_TARGET_ALIASES.get(raw_text)
        if alias is not None:
            return alias
        if strict:
            raise ValueError(f"unknown projection target: {raw!r}") from None
        diagnostics.append(f"unknown projection target {raw!r}; defaulted to modifierDiagnosticTarget")
        return ProjectionTarget.MODIFIER_DIAGNOSTIC


def _validate_non_promoting_boundary(
    boundary: Any,
    *,
    strict: bool,
    diagnostics: list[str],
) -> None:
    if boundary is None:
        return
    if not isinstance(boundary, Mapping):
        if strict:
            raise ValueError("authority_boundary must be a mapping when supplied")
        diagnostics.append("authority_boundary was not a mapping and was ignored")
        return

    forbidden_truths = {
        "promotion_authority",
        "legal_authority",
        "wikidata_live_edit_authority",
    }
    for key in forbidden_truths:
        if boundary.get(key) is True:
            raise ValueError(f"carrier motif annotation cannot set {key}=true")
    if boundary.get("non_authoritative") is False:
        raise ValueError("carrier motif annotation cannot set non_authoritative=false")


__all__ = [
    "CARRIER_MOTIF_MODIFIER_KEY",
    "CARRIER_MOTIF_SCHEMA",
    "CarrierMotif",
    "CarrierMotifAnnotation",
    "CarrierRole",
    "ProjectionTarget",
    "attach_carrier_motif_modifier",
    "coerce_carrier_motif_annotation",
]
