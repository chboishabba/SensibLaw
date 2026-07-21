"""Generic declarative reductions from relational annotations to PNF factors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.policy.algebra import Factor, FactorConstraint, TypedAlternative
from src.policy.carriers.canonical import canonical_refs, canonical_sha256, require_text


@dataclass(frozen=True)
class LocalTypeProjection:
    """One candidate-only local type licensed by an observed relation role."""

    role_name: str
    semantic_family: str
    local_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role_name": require_text(self.role_name, "role_name"),
            "semantic_family": require_text(self.semantic_family, "semantic_family"),
            "local_type": require_text(self.local_type, "local_type"),
        }


@dataclass(frozen=True)
class SemanticReductionDeclaration:
    """One immutable, corpus-neutral relation-to-factor declaration."""

    declaration_ref: str
    relation_type: str
    output_factor_type: str
    output_type_ref: str
    role_names: tuple[str, ...] = ()
    residuals: tuple[str, ...] = ()
    local_type_projections: tuple[LocalTypeProjection, ...] = ()
    constraint_types: tuple[tuple[str, str], ...] = ()
    feature_factor_types: tuple[tuple[str, str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "declaration_ref": require_text(self.declaration_ref, "declaration_ref"),
            "relation_type": require_text(self.relation_type, "relation_type"),
            "output_factor_type": require_text(
                self.output_factor_type, "output_factor_type"
            ),
            "output_type_ref": require_text(self.output_type_ref, "output_type_ref"),
            "role_names": list(canonical_refs(self.role_names)),
            "residuals": list(canonical_refs(self.residuals)),
            "local_type_projections": [
                row.to_dict()
                for row in sorted(
                    self.local_type_projections,
                    key=lambda value: (
                        value.role_name,
                        value.semantic_family,
                        value.local_type,
                    ),
                )
            ],
            "constraint_types": [
                {"role": role, "constraint_type": constraint_type}
                for role, constraint_type in sorted(self.constraint_types)
            ],
            "feature_factor_types": [
                {
                    "role": role,
                    "factor_type": factor_type,
                    "type_ref": type_ref,
                }
                for role, factor_type, type_ref in sorted(self.feature_factor_types)
            ],
            "authority": "grammar_only",
        }


@dataclass(frozen=True)
class SemanticReductionOutput:
    factors: tuple[Factor[Any], ...]
    constraints: tuple[FactorConstraint, ...]
    relation_refs: tuple[str, ...]
    declaration_refs: tuple[str, ...]


def derive_relational_type_hypotheses(
    *,
    bundle: Mapping[str, Any],
    atom_mention_refs: Mapping[str, Sequence[str]],
    declarations: Sequence[SemanticReductionDeclaration] | None = None,
) -> tuple[dict[str, object], ...]:
    """Project declared relation roles into candidate-only local type branches.

    This is a structural projection, not a lexical classifier or identity
    resolver.  One atom can preserve several compatible role interpretations;
    each projected row must later be consumed as an alternative.
    """

    declarations = declarations or default_semantic_reduction_declarations()
    projections_by_role: dict[tuple[str, str], tuple[LocalTypeProjection, ...]] = {}
    for declaration in declarations:
        for projection in declaration.local_type_projections:
            key = (declaration.relation_type, projection.role_name)
            projections_by_role[key] = tuple(
                sorted(
                    set(projections_by_role.get(key, ()) + (projection,)),
                    key=lambda value: (value.semantic_family, value.local_type),
                )
            )
    rows: list[dict[str, object]] = []
    for relation in sorted(
        bundle.get("relations") or (), key=lambda row: str(row["id"])
    ):
        relation_id = str(relation["id"])
        relation_type = str(relation.get("type") or "")
        for role in sorted(
            relation.get("roles") or (),
            key=lambda row: (str(row.get("role") or ""), str(row.get("atom") or "")),
        ):
            role_name = str(role.get("role") or "")
            projections = projections_by_role.get((relation_type, role_name))
            if not projections:
                continue
            atom_ref = str(role.get("atom") or "")
            for mention_ref in sorted(set(atom_mention_refs.get(atom_ref, ()))):
                for projection in projections:
                    rows.append(
                        {
                            "mention_ref": mention_ref,
                            "semantic_family": projection.semantic_family,
                            "local_type": projection.local_type,
                            "derivation_basis": "declared_relational_projection",
                            "evidence_refs": (
                                "grammar:semantic:role-typing:v0_3",
                                f"semantic-relation:{relation_id}",
                            ),
                        }
                    )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["mention_ref"]),
                str(row["semantic_family"]),
                str(row["local_type"]),
                tuple(row["evidence_refs"]),
            ),
        )
    )


def diagnose_untyped_mentions(
    *,
    mentions: Sequence[Mapping[str, Any]],
    local_typing: Mapping[str, Any],
    bundle: Mapping[str, Any],
    atom_mention_refs: Mapping[str, Sequence[str]],
    parser_observation_refs: Mapping[str, Sequence[str]] | None = None,
    parser_capabilities: Mapping[str, object] | None = None,
) -> tuple[dict[str, object], ...]:
    """Partition locally untyped mentions from public observations only.

    This diagnostic does not add a type, boundary, relation, or identity.  It
    records which declared reducer family *could* be evaluated next from
    existing public observations, keeping parser absence distinct from weak
    semantic content.
    """

    untyped_refs = {
        str(row["mention_ref"])
        for row in local_typing.get("coverage_pressure") or ()
        if str(row.get("coverage_state") or "") != "typed"
    }
    form_refs: dict[str, list[str]] = {mention_ref: [] for mention_ref in untyped_refs}
    for form in local_typing.get("forms") or ():
        mention_ref = str(form.get("mention_ref") or "")
        if mention_ref in form_refs:
            form_refs[mention_ref].append(str(form.get("form_ref") or ""))
    parser_observation_refs = parser_observation_refs or {}
    parser_capabilities = parser_capabilities or {}
    observations: dict[str, list[tuple[str, str, str]]] = {
        mention_ref: [] for mention_ref in untyped_refs
    }
    for relation in bundle.get("relations") or ():
        relation_id = str(relation.get("id") or "")
        relation_type = str(relation.get("type") or "")
        for role in relation.get("roles") or ():
            atom_ref = str(role.get("atom") or "")
            role_name = str(role.get("role") or "")
            for mention_ref in atom_mention_refs.get(atom_ref, ()):
                if mention_ref in observations:
                    observations[mention_ref].append(
                        (relation_type, role_name, relation_id)
                    )

    def classify(
        rows: Sequence[tuple[str, str, str]], parser_refs: Sequence[str]
    ) -> tuple[str, str, str]:
        pairs = {(relation_type, role_name) for relation_type, role_name, _ in rows}
        if ("modifier", "head") in pairs:
            return ("nominal_head_available", "nominal_description", "high")
        if ("modifier", "modifier") in pairs:
            return ("nominal_modifier_only", "nominal_description", "medium")
        if ("predicate", "head") in pairs:
            return ("verbal_or_predicative", "predication", "high")
        if any(kind == "predicate" for kind, _ in pairs):
            return ("syntactic_argument_role", "syntactic_argument", "high")
        if any(kind == "temporal" for kind, _ in pairs):
            return ("temporal_shape", "temporal_expression", "medium")
        if any(kind == "spatial" for kind, _ in pairs):
            return ("spatial_or_prepositional", "spatial_expression", "medium")
        if any(kind == "conjunction" for kind, _ in pairs):
            return ("coordination_fragment", "coordination", "medium")
        if any(kind == "composition" for kind, _ in pairs):
            return ("clausal_fragment", "embedded_proposition", "high")
        if rows:
            return ("function_or_discourse_structure", "no_declared_reducer", "low")
        if not bool(parser_capabilities.get("tokenization", True)):
            return ("parser_capability_unavailable", "tokenization", "low")
        if parser_refs:
            return (
                "parser_observation_unconsumed",
                "reduction_declaration_missing",
                "medium",
            )
        return ("parser_observation_absent", "observation_or_alignment", "low")

    def missing_annotation_reason(
        mention: Mapping[str, Any],
        observed: Sequence[tuple[str, str, str]],
        parser_refs: Sequence[str],
    ) -> tuple[str, str]:
        """Classify absent observations without inferring semantic content."""

        if mention.get("span_alignment") in {"mismatch", "unmapped"}:
            return ("tokenization_or_alignment_mismatch", "alignment")
        if mention.get("boundary_state") in {"overbroad", "inside_annotation"}:
            return ("mention_boundary_mismatch", "boundary")
        if observed:
            return ("relation_not_projected", "unprojected_relation")
        if parser_refs:
            return ("parser_observation_unconsumed", "reduction_declaration_missing")
        if not bool(parser_capabilities.get("tokenization", True)):
            return ("parser_capability_unavailable", "tokenization")
        return ("no_parser_observation", "semantically_weak_or_unobserved")

    rows: list[dict[str, object]] = []
    for mention in sorted(mentions, key=lambda row: str(row["mention_ref"])):
        mention_ref = str(mention["mention_ref"])
        if mention_ref not in untyped_refs:
            continue
        observed = tuple(sorted(observations[mention_ref]))
        parser_refs = tuple(sorted(set(parser_observation_refs.get(mention_ref, ()))))
        shape, missing_capability, pnf_impact = classify(observed, parser_refs)
        if not observed:
            suppression_reason, missing_capability = missing_annotation_reason(
                mention, observed, parser_refs
            )
        else:
            suppression_reason = "no_local_type_alternative"
        rows.append(
            {
                "mention_ref": mention_ref,
                "available_annotation_refs": tuple(
                    f"semantic-relation:{relation_id}"
                    for _relation_type, _role_name, relation_id in observed
                )
                + parser_refs,
                "parser_observation_refs": parser_refs,
                "projection_state": "projected" if parser_refs else "not_observed",
                "reduction_consumption_refs": tuple(
                    f"semantic-relation:{relation_id}"
                    for _relation_type, _role_name, relation_id in observed
                ),
                "syntactic_head_ref": next(
                    (
                        f"semantic-relation:{relation_id}"
                        for relation_type, role_name, relation_id in observed
                        if (relation_type, role_name)
                        in {("predicate", "head"), ("modifier", "head")}
                    ),
                    None,
                ),
                "dependency_role": observed[0][1] if len(observed) == 1 else None,
                "containing_clause_ref": None,
                "existing_form_alternatives": tuple(sorted(form_refs[mention_ref])),
                "annotation_shape": shape,
                "missing_reduction_capability": missing_capability,
                "pnf_impact": pnf_impact,
                "suppression_reason": suppression_reason,
                "authority": "diagnostic_only",
            }
        )
    return tuple(rows)


def summarize_untyped_diagnostics(
    diagnostics: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Return deterministic frequency rows for diagnostic prioritisation."""

    counts: dict[tuple[str, str, str], int] = {}
    for row in diagnostics:
        key = (
            str(row["annotation_shape"]),
            str(row["missing_reduction_capability"]),
            str(row["pnf_impact"]),
        )
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        {
            "annotation_shape": key[0],
            "missing_reduction_capability": key[1],
            "pnf_impact": key[2],
            "mention_count": count,
            "authority": "diagnostic_only",
        }
        for key, count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    )


def default_semantic_reduction_declarations() -> tuple[
    SemanticReductionDeclaration, ...
]:
    """Return reductions over public relation categories, never corpus labels."""

    return (
        SemanticReductionDeclaration(
            "grammar:semantic:predicate:v0_4",
            "predicate",
            "semantic.eventuality",
            "semantic.eventuality_candidate",
            (
                "head",
                "subject",
                "object",
                "oblique",
                "complement",
                "argument",
                "negation",
                "auxiliary",
                "action_meta",
            ),
            ("event_identity_unresolved",),
            (
                LocalTypeProjection("head", "eventuality", "linguistic_predicate"),
                LocalTypeProjection("subject", "relation", "predicate_subject_role"),
                LocalTypeProjection("object", "relation", "predicate_object_role"),
                LocalTypeProjection("oblique", "relation", "predicate_oblique_role"),
                LocalTypeProjection(
                    "complement", "relation", "predicate_complement_role"
                ),
                LocalTypeProjection("argument", "relation", "predicate_argument_role"),
            ),
            (
                ("subject", "syntactic_subject_of"),
                ("object", "syntactic_object_of"),
                ("oblique", "syntactic_oblique_of"),
                ("complement", "syntactic_complement_of"),
                ("argument", "syntactic_argument_of"),
            ),
            (
                (
                    "action_meta",
                    "semantic.predicate_inflection",
                    "semantic.predicate_inflection_candidate",
                ),
            ),
        ),
        SemanticReductionDeclaration(
            "grammar:semantic:temporal:v0_3",
            "temporal",
            "semantic.temporal_expression",
            "semantic.temporal_candidate",
            ("anchor",),
            ("temporal_extent_unresolved",),
            (LocalTypeProjection("anchor", "time", "temporal_anchor"),),
            (("anchor", "temporal_anchor_of"),),
        ),
        SemanticReductionDeclaration(
            "grammar:semantic:spatial:v0_3",
            "spatial",
            "semantic.spatial_expression",
            "semantic.spatial_candidate",
            ("anchor",),
            ("spatial_extent_unresolved",),
            (LocalTypeProjection("anchor", "location", "spatial_anchor"),),
            (("anchor", "spatial_anchor_of"),),
        ),
        SemanticReductionDeclaration(
            "grammar:semantic:coordination:v0_3",
            "conjunction",
            "semantic.coordination",
            "semantic.coordination_candidate",
            ("item",),
            (),
            (LocalTypeProjection("item", "relation", "coordinated_item"),),
            (("item", "coordination_member_of"),),
        ),
        SemanticReductionDeclaration(
            "grammar:semantic:modification:v0_3",
            "modifier",
            "semantic.nominal_description",
            "semantic.nominal_description_candidate",
            ("head", "modifier"),
            ("nominal_denotation_unresolved", "modifier_scope_unresolved"),
            (
                LocalTypeProjection("head", "class", "modified_nominal_head"),
                LocalTypeProjection("modifier", "class", "nominal_modifier"),
            ),
            (
                ("head", "nominal_head_of"),
                ("modifier", "nominal_modifier_of"),
            ),
        ),
        SemanticReductionDeclaration(
            "grammar:semantic:composition:v0_4",
            "composition",
            "semantic.embedded_proposition",
            "semantic.composition_candidate",
            ("host", "content"),
            ("composition_scope_unresolved", "proposition_truth_not_evaluated"),
            (
                LocalTypeProjection("host", "relation", "composition_host"),
                LocalTypeProjection(
                    "content", "proposition", "embedded_proposition_content"
                ),
            ),
            (
                ("host", "host_of_embedded_proposition"),
                ("content", "content_of"),
            ),
        ),
    )


def reduce_relational_bundle(
    *,
    document_ref: str,
    bundle: Mapping[str, Any],
    atom_span_refs: Mapping[str, str],
    declarations: Sequence[SemanticReductionDeclaration],
) -> SemanticReductionOutput:
    """Reduce public relation observations without lexical or identity decisions."""

    by_relation = {row.relation_type: row for row in declarations}
    atoms_by_ref = {str(row.get("id") or ""): row for row in bundle.get("atoms") or ()}
    factors: list[Factor[Any]] = []
    constraints: list[FactorConstraint] = []
    relation_refs: list[str] = []
    used_declarations: set[str] = set()
    for relation in sorted(
        bundle.get("relations") or (), key=lambda row: str(row["id"])
    ):
        relation_type = str(relation.get("type") or "")
        declaration = by_relation.get(relation_type)
        if declaration is None:
            continue
        relation_id = str(relation["id"])
        relation_ref = "semantic-relation:" + canonical_sha256(
            {"document_ref": document_ref, "relation": relation}
        )
        relation_refs.append(relation_ref)
        used_declarations.add(declaration.declaration_ref)
        roles = tuple(
            row
            for row in relation.get("roles") or ()
            if str(row.get("role") or "") in set(declaration.role_names)
        )
        bindings = tuple(
            {
                "role": str(row["role"]),
                "atom_id": str(row.get("atom") or "") or None,
                "atom_ref": atom_span_refs.get(str(row.get("atom") or "")),
                "value": row.get("value"),
            }
            for row in roles
        )
        factor_ref = "factor:" + canonical_sha256(
            {
                "document_ref": document_ref,
                "declaration_ref": declaration.declaration_ref,
                "relation_id": relation_id,
            }
        )
        alternative = TypedAlternative(
            alternative_ref=f"{factor_ref}:candidate",
            value={"relation_ref": relation_ref, "bindings": bindings},
            type_ref=declaration.output_type_ref,
            derivation_refs=(declaration.declaration_ref, relation_ref),
        )
        constraint = FactorConstraint(
            constraint_ref=f"constraint:{factor_ref}",
            constraint_type="relation_observation",
            payload={"relation_type": relation_type, "bindings": bindings},
            provenance_refs=(declaration.declaration_ref, relation_ref),
        )
        factors.append(
            Factor(
                factor_ref=factor_ref,
                factor_type=declaration.output_factor_type,
                alternatives=(alternative,),
                constraints=(constraint,),
                residuals=declaration.residuals,
                closure_state="requires_external_resolution"
                if declaration.residuals
                else "locally_closed",
                metadata={
                    "declaration_ref": declaration.declaration_ref,
                    "relation_ref": relation_ref,
                    "relation_type": relation_type,
                    "bindings": bindings,
                },
            )
        )
        role_factor_refs: dict[str, str] = {}
        declared_constraints = dict(declaration.constraint_types)
        feature_factor_types = {
            role: (factor_type, type_ref)
            for role, factor_type, type_ref in declaration.feature_factor_types
        }
        for binding in bindings:
            role = str(binding["role"])
            feature_factor = feature_factor_types.get(role)
            if feature_factor is not None:
                feature_type, feature_alternative_type = feature_factor
                feature_factor_ref = "factor:" + canonical_sha256(
                    {
                        "document_ref": document_ref,
                        "relation_id": relation_id,
                        "feature_role": role,
                        "binding": binding,
                    }
                )
                factors.append(
                    Factor(
                        factor_ref=feature_factor_ref,
                        factor_type=feature_type,
                        alternatives=(
                            TypedAlternative(
                                alternative_ref=f"{feature_factor_ref}:candidate",
                                value={"role": role, "value": binding.get("value")},
                                type_ref=feature_alternative_type,
                                derivation_refs=(
                                    declaration.declaration_ref,
                                    relation_ref,
                                ),
                            ),
                        ),
                        constraints=(),
                        residuals=(),
                        closure_state="locally_closed",
                        metadata={"relation_ref": relation_ref, "role": role},
                    )
                )
            constraint_type = declared_constraints.get(role)
            if constraint_type is None:
                continue
            role_factor_ref = "factor:" + canonical_sha256(
                {
                    "document_ref": document_ref,
                    "relation_id": relation_id,
                    "role": role,
                    "binding": binding,
                }
            )
            role_factor_refs[role] = role_factor_ref
            role_factor_type = (
                f"semantic.argument.{role}"
                if relation_type == "predicate"
                else f"semantic.relation_role.{relation_type}.{role}"
            )
            role_residuals = (
                (
                    "syntactic_argument_structure_unchecked",
                    "argument_identity_unresolved",
                )
                if relation_type == "predicate"
                else ()
            )
            atom = atoms_by_ref.get(str(binding.get("atom_id") or ""), {})
            is_pronominal_subject = (
                relation_type == "predicate"
                and role == "subject"
                and str(atom.get("pos") or "") == "PRON"
            )
            alternatives = [
                TypedAlternative(
                    alternative_ref=f"{role_factor_ref}:candidate",
                    value={
                        "role": role,
                        "binding": binding,
                        "relation_ref": relation_ref,
                    },
                    type_ref="semantic.argument_candidate",
                    derivation_refs=(
                        declaration.declaration_ref,
                        relation_ref,
                    ),
                )
            ]
            if is_pronominal_subject:
                for referential_type in (
                    "entity_reference",
                    "eventuality_reference",
                    "proposition_reference",
                    "expletive_realisation",
                ):
                    alternatives.append(
                        TypedAlternative(
                            alternative_ref=f"{role_factor_ref}:{referential_type}",
                            value={
                                "role": role,
                                "referential_type": referential_type,
                                "parser_morphology": atom.get("morph") or {},
                                "relation_ref": relation_ref,
                            },
                            type_ref="semantic.reference_candidate",
                            derivation_refs=(
                                declaration.declaration_ref,
                                relation_ref,
                            ),
                        )
                    )
                role_residuals = (
                    "syntactic_argument_structure_unchecked",
                    "antecedent_unresolved",
                    "grammatical_subject_semantic_status_unresolved",
                    "referential_type_unresolved",
                )
            role_constraint = FactorConstraint(
                constraint_ref=f"constraint:{role_factor_ref}",
                constraint_type=constraint_type,
                payload={
                    "source_factor_ref": role_factor_ref,
                    "target_factor_ref": factor_ref,
                    "role": role,
                    "relation_type": relation_type,
                    "atom_span_ref": binding.get("atom_ref"),
                },
                provenance_refs=(declaration.declaration_ref, relation_ref),
                source_factor_refs=(role_factor_ref,),
                target_factor_refs=(factor_ref,),
                residual_on_failure=declaration.residuals[0]
                if declaration.residuals
                else None,
            )
            constraints.append(role_constraint)
            factors.append(
                Factor(
                    factor_ref=role_factor_ref,
                    factor_type=role_factor_type,
                    alternatives=tuple(alternatives),
                    constraints=(role_constraint,),
                    residuals=role_residuals,
                    closure_state=(
                        "requires_external_resolution"
                        if role_residuals
                        else "locally_closed"
                    ),
                    metadata={
                        "relation_ref": relation_ref,
                        "relation_type": relation_type,
                        "role": role,
                        "atom_id": binding.get("atom_id"),
                        "atom_span_ref": binding.get("atom_ref"),
                        "parser_pos": atom.get("pos"),
                        "parser_dependency": atom.get("dependency"),
                        "parser_morphology": atom.get("morph") or {},
                    },
                )
            )
        if role_factor_refs:
            for role, role_factor_ref in sorted(role_factor_refs.items()):
                constraint_type = declared_constraints[role]
                explicit = FactorConstraint(
                    constraint_ref=f"constraint:{factor_ref}:{role}",
                    constraint_type=constraint_type,
                    payload={
                        "source_factor_ref": role_factor_ref,
                        "target_factor_ref": factor_ref,
                        "role": role,
                        "relation_type": relation_type,
                    },
                    provenance_refs=(declaration.declaration_ref, relation_ref),
                    source_factor_refs=(role_factor_ref,),
                    target_factor_refs=(factor_ref,),
                    residual_on_failure=declaration.residuals[0]
                    if declaration.residuals
                    else None,
                )
                constraints.append(explicit)
    return SemanticReductionOutput(
        factors=tuple(sorted(factors, key=lambda row: row.factor_ref)),
        constraints=tuple(
            sorted(
                {row.constraint_ref: row for row in constraints}.values(),
                key=lambda row: row.constraint_ref,
            )
        ),
        relation_refs=tuple(sorted(set(relation_refs))),
        declaration_refs=tuple(sorted(used_declarations)),
    )


__all__ = [
    "LocalTypeProjection",
    "SemanticReductionDeclaration",
    "SemanticReductionOutput",
    "diagnose_untyped_mentions",
    "derive_relational_type_hypotheses",
    "default_semantic_reduction_declarations",
    "reduce_relational_bundle",
    "summarize_untyped_diagnostics",
]
