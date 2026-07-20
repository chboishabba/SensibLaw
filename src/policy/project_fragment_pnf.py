from __future__ import annotations

from typing import Any

from src.policy.fragment_pnf import (
    FragmentPNF,
    FragmentPNFProjectionReceipt,
    GrammarMatchStrength,
    ProjectionBasisLevel,
    residual_level_to_compatibility,
)
from src.text.residual_lattice import (
    PredicateAtom,
    PredicatePNF,
    QualifierState,
    ResidualLevel,
    TypedArg,
    WrapperState,
)


def _infer_entity_type(role_key: str, canonical_key: str | None) -> str:
    if role_key == "subject":
        return "actor"
    if role_key == "object":
        if canonical_key and canonical_key.startswith("office:"):
            return "office"
        if canonical_key and canonical_key.startswith("org:"):
            return "organization"
        if canonical_key and canonical_key.startswith("edu:"):
            return "education"
        if canonical_key and canonical_key.startswith("event:"):
            return "event"
        if canonical_key and canonical_key.startswith("actor:"):
            return "actor"
        return "object"
    return "unknown"


def _projection_basis(fragment: FragmentPNF) -> ProjectionBasisLevel:
    if fragment.grammar_match_strength == GrammarMatchStrength.fallback_bundle:
        return ProjectionBasisLevel.fallback_projected
    return ProjectionBasisLevel.grammar_projected


def project_fragment_pnf(
    fragment: FragmentPNF,
) -> tuple[PredicateAtom | None, FragmentPNFProjectionReceipt]:
    """Project a single FragmentPNF candidate to a PredicateAtom.

    Returns (atom, receipt) where atom is None when the fragment cannot
    produce a valid PredicateAtom (missing predicate or object role).
    """
    if not fragment.predicate_spine:
        receipt = FragmentPNFProjectionReceipt(
            fragment_id=fragment.fragment_id,
            projection_status=ProjectionBasisLevel.unprojectable,
            projection_basis=(),
            blocked_reasons=("missing_predicate_spine",),
        )
        return None, receipt

    subject_role = fragment.subject_role
    object_role = fragment.object_role
    roles: dict[str, TypedArg] = {}

    has_subject = subject_role is not None and bool(subject_role.canonical_key)
    has_object = object_role is not None and bool(object_role.canonical_key)

    if has_subject:
        roles["subject"] = TypedArg(
            value=subject_role.canonical_key,
            entity_type=_infer_entity_type("subject", subject_role.canonical_key),
            provenance=(f"fragment:{fragment.fragment_id}",),
            status="bound",
        )
    if has_object:
        roles["object"] = TypedArg(
            value=object_role.canonical_key,
            entity_type=_infer_entity_type("object", object_role.canonical_key),
            provenance=(f"fragment:{fragment.fragment_id}",),
            status="bound",
        )

    roles["action"] = TypedArg(
        value=fragment.predicate_spine,
        entity_type="action",
        provenance=(f"fragment:{fragment.fragment_id}",),
        status="bound",
    )
    roles["argument"] = roles.get("object") or roles.get("subject") or roles["action"]

    if not has_object and not has_subject:
        receipt = FragmentPNFProjectionReceipt(
            fragment_id=fragment.fragment_id,
            projection_status=ProjectionBasisLevel.partial_projected,
            projection_basis=(),
            blocked_reasons=("missing_roles",),
        )
        return None, receipt

    projection_basis_level = _projection_basis(fragment)
    provenance: tuple[str, ...] = (
        f"grammar:{fragment.grammar_id}",
        f"fragment:{fragment.fragment_id}",
        *fragment.pnf_basis,
    )

    structural_signature = f"fragment_pnf:{fragment.predicate_spine}"

    qualifiers = QualifierState()

    wrapper = WrapperState(status="fragment_projection", evidence_only=True)

    atom_id = fragment.fragment_id

    predicate = fragment.predicate_spine

    atom = PredicateAtom(
        predicate=predicate,
        structural_signature=structural_signature,
        roles=roles,
        qualifiers=qualifiers,
        wrapper=wrapper,
        provenance=provenance,
        atom_id=atom_id,
        domain="fragment_pnf_projection",
    )

    receipt = FragmentPNFProjectionReceipt(
        fragment_id=fragment.fragment_id,
        projection_status=projection_basis_level,
        predicate_atom_ref=atom_id,
        projection_basis=fragment.pnf_basis,
    )

    return atom, receipt


def project_fragment_pnfs(
    fragments: list[FragmentPNF],
) -> tuple[list[PredicateAtom], list[FragmentPNFProjectionReceipt]]:
    """Project a list of FragmentPNF candidates into PredicateAtoms.

    Returns (atoms, receipts).  Only fragments that produce a valid atom
    are included in the atoms list; all fragments receive a receipt.
    """
    atoms: list[PredicateAtom] = []
    receipts: list[FragmentPNFProjectionReceipt] = []
    for fragment in fragments:
        atom, receipt = project_fragment_pnf(fragment)
        receipts.append(receipt)
        if atom is not None:
            atoms.append(atom)
    return atoms, receipts


def project_row_fragment_pnfs(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Project all FragmentPNFs in a row to PredicateAtoms in-place.

    Sets row[\"projected_predicate_atoms\"] and
    row[\"fragment_projection_receipts\"].
    """
    fragments: list[FragmentPNF] = row.get("fragment_pnfs") or []
    if not fragments:
        row["projected_predicate_atoms"] = []
        row["fragment_projection_receipts"] = []
        return row

    atoms, receipts = project_fragment_pnfs(fragments)
    row["projected_predicate_atoms"] = [a.to_dict() for a in atoms]
    row["fragment_projection_receipts"] = [r.to_dict() for r in receipts]
    return row


__all__ = [
    "project_fragment_pnf",
    "project_fragment_pnfs",
    "project_row_fragment_pnfs",
]
