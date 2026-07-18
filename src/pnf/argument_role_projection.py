"""Canonical parser-supported syntactic roles for PNF argument factors.

The relational parser carrier may preserve a dependency argument under the
fallback role ``argument`` even when its public dependency label is more
specific. This projection narrows only the syntactic role licensed by that
label. It does not infer a semantic role, participant identity, antecedent,
event occurrence, or proposition truth.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


ARGUMENT_ROLE_DECLARATION_REF = "grammar:pnf:parser-argument-role:v0_1"

_DEPENDENCY_ROLES: Mapping[str, str] = {
    "nsubj": "subject",
    "nsubjpass": "subject",
    "csubj": "subject",
    "csubjpass": "subject",
    "obj": "object",
    "dobj": "object",
    "iobj": "object",
    "attr": "object",
    "acomp": "object",
    "obl": "oblique",
    "dative": "oblique",
    "prep": "oblique",
    "pobj": "oblique",
    "agent": "oblique",
    "ccomp": "complement",
    "xcomp": "complement",
}

_CONSTRAINT_TYPES: Mapping[str, str] = {
    "subject": "syntactic_subject_of",
    "object": "syntactic_object_of",
    "oblique": "syntactic_oblique_of",
    "complement": "syntactic_complement_of",
    "argument": "syntactic_argument_of",
}


def _is_argument_factor(factor: Mapping[str, Any]) -> bool:
    factor_type = str(factor.get("factor_type") or "")
    return factor_type.startswith("semantic.argument.") or factor_type == (
        "semantic.argument_reference"
    )


def _canonical_role(metadata: Mapping[str, Any]) -> str:
    role = str(metadata.get("role") or "argument")
    if role != "argument":
        return role
    dependency = str(metadata.get("parser_dependency") or "")
    return _DEPENDENCY_ROLES.get(dependency, role)


def _project_alternatives(
    alternatives: Sequence[Mapping[str, Any]], *, role: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in alternatives:
        row = dict(source)
        value = row.get("value")
        if row.get("type_ref") == "semantic.argument_candidate" and isinstance(
            value, Mapping
        ):
            row["value"] = {**dict(value), "role": role}
        result.append(row)
    return result


def _project_constraint(
    constraint: Mapping[str, Any], *, factor_ref: str, role: str
) -> dict[str, Any]:
    row = dict(constraint)
    source_refs = {str(ref) for ref in row.get("source_factor_refs") or ()}
    payload = dict(row.get("payload") or {})
    payload_source = str(payload.get("source_factor_ref") or "")
    if factor_ref not in source_refs and payload_source != factor_ref:
        return row
    row["constraint_type"] = _CONSTRAINT_TYPES.get(
        role, str(row.get("constraint_type") or "syntactic_argument_of")
    )
    payload["role"] = role
    payload["parser_role_projection_declaration_ref"] = (
        ARGUMENT_ROLE_DECLARATION_REF
    )
    row["payload"] = payload
    return row


def _project_factor(factor: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    row = dict(factor)
    if not _is_argument_factor(row):
        return row, False
    metadata = dict(row.get("metadata") or {})
    prior_role = str(metadata.get("role") or "argument")
    role = _canonical_role(metadata)
    if role == prior_role:
        return row, False
    factor_ref = str(row["factor_ref"])
    metadata.update(
        {
            "role": role,
            "parser_role_projection_declaration_ref": (
                ARGUMENT_ROLE_DECLARATION_REF
            ),
            "parser_role_projection_basis": str(
                metadata.get("parser_dependency") or ""
            ),
        }
    )
    row.update(
        {
            "factor_type": f"semantic.argument.{role}",
            "alternatives": _project_alternatives(
                row.get("alternatives") or (), role=role
            ),
            "constraints": [
                _project_constraint(
                    constraint,
                    factor_ref=factor_ref,
                    role=role,
                )
                for constraint in row.get("constraints") or ()
            ],
            "metadata": metadata,
        }
    )
    return row, True


def _project_graph(graph: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    factors: list[dict[str, Any]] = []
    role_by_factor: dict[str, str] = {}
    changed_count = 0
    for source in graph.get("factors") or ():
        factor, changed = _project_factor(source)
        factors.append(factor)
        changed_count += int(changed)
        if changed:
            role_by_factor[str(factor["factor_ref"])] = str(
                (factor.get("metadata") or {}).get("role") or "argument"
            )
    constraints: list[dict[str, Any]] = []
    for source in graph.get("constraints") or ():
        row = dict(source)
        source_refs = [str(ref) for ref in row.get("source_factor_refs") or ()]
        factor_ref = next((ref for ref in source_refs if ref in role_by_factor), "")
        if factor_ref:
            row = _project_constraint(
                row,
                factor_ref=factor_ref,
                role=role_by_factor[factor_ref],
            )
        constraints.append(row)
    result = dict(graph)
    result["factors"] = sorted(
        factors, key=lambda value: str(value.get("factor_ref") or "")
    )
    result["constraints"] = sorted(
        constraints, key=lambda value: str(value.get("constraint_ref") or "")
    )
    if changed_count:
        result["graph_ref"] = "pnf-graph:" + canonical_sha256(
            {
                "document_ref": result.get("document_ref"),
                "factors": result["factors"],
                "constraints": result["constraints"],
                "relation_refs": result.get("relation_refs") or (),
                "argument_role_declaration_ref": ARGUMENT_ROLE_DECLARATION_REF,
            }
        )
    return result, changed_count


def _project_refinement(refinement: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(refinement)
    prior, _prior_changed = _project_factor(row.get("prior_factor") or {})
    resulting, _resulting_changed = _project_factor(
        row.get("resulting_factor") or {}
    )
    row["prior_factor"] = prior
    row["resulting_factor"] = resulting
    return row


def _argument_morphology_by_span(
    *graphs: Mapping[str, Any],
) -> dict[str, object]:
    """Return parser morphology already preserved on argument factors."""

    morphology: dict[str, object] = {}
    for graph in graphs:
        for factor in graph.get("factors") or ():
            if not _is_argument_factor(factor):
                continue
            metadata = factor.get("metadata") or {}
            span_ref = metadata.get("atom_span_ref")
            observed = metadata.get("parser_morphology")
            if isinstance(span_ref, str) and observed:
                morphology[span_ref] = observed
    return morphology


def _align_annotation_morphology(
    layer: Mapping[str, Any], *, morphology_by_span: Mapping[str, object]
) -> dict[str, Any]:
    """Align factor-preserved morphology with its parser-token graph anchor.

    This copies an existing parser observation between two projections of the
    same parse. It never manufactures a feature or consults lexical knowledge.
    """

    if not morphology_by_span:
        return dict(layer)
    span_start = {
        str(row.get("span_ref") or ""): int(row["start_token"])
        for row in layer.get("span_annotations") or ()
        if row.get("span_ref") and row.get("start_token") is not None
    }
    morphology_by_token = {
        span_start[span_ref]: observed
        for span_ref, observed in morphology_by_span.items()
        if span_ref in span_start
    }
    if not morphology_by_token:
        return dict(layer)
    annotations: list[dict[str, Any]] = []
    seen_tokens: set[int] = set()
    for source in layer.get("token_annotations") or ():
        row = dict(source)
        token_index = int(row.get("token_index", -1))
        if (
            row.get("annotation_type") == "parser.morphology"
            and token_index in morphology_by_token
        ):
            row["value"] = morphology_by_token[token_index]
            provenance = {
                str(ref) for ref in row.get("provenance_refs") or ()
            }
            provenance.add(ARGUMENT_ROLE_DECLARATION_REF)
            row["provenance_refs"] = sorted(provenance)
            seen_tokens.add(token_index)
        annotations.append(row)
    for token_index, observed in sorted(morphology_by_token.items()):
        if token_index in seen_tokens:
            continue
        annotations.append(
            {
                "token_index": token_index,
                "annotation_type": "parser.morphology",
                "value": observed,
                "provenance_refs": [ARGUMENT_ROLE_DECLARATION_REF],
            }
        )
    result = dict(layer)
    result["token_annotations"] = sorted(
        annotations,
        key=lambda row: (
            int(row.get("token_index", -1)),
            str(row.get("annotation_type") or ""),
        ),
    )
    return result


def canonicalize_parser_argument_roles(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Narrow generic syntactic arguments using parser dependency evidence."""

    if artifacts.get("argument_role_projection_contract") == (
        ARGUMENT_ROLE_DECLARATION_REF
    ):
        return dict(artifacts)
    result = dict(artifacts)
    pnf_graph, base_changes = _project_graph(artifacts.get("pnf_graph") or {})
    refined_graph, refined_changes = _project_graph(
        artifacts.get("refined_pnf_graph") or pnf_graph
    )
    result["pnf_graph"] = pnf_graph
    result["refined_pnf_graph"] = refined_graph
    result["factor_refinements"] = [
        _project_refinement(row)
        for row in artifacts.get("factor_refinements") or ()
    ]
    morphology_by_span = _argument_morphology_by_span(
        pnf_graph, refined_graph
    )
    result["semantic_annotation_layer"] = _align_annotation_morphology(
        artifacts.get("semantic_annotation_layer") or {},
        morphology_by_span=morphology_by_span,
    )
    declarations = [
        dict(row) for row in artifacts.get("compiler_declarations") or ()
    ]
    if not any(
        row.get("declaration_ref") == ARGUMENT_ROLE_DECLARATION_REF
        for row in declarations
    ):
        declarations.append(
            {
                "declaration_ref": ARGUMENT_ROLE_DECLARATION_REF,
                "declaration_kind": "grammar",
                "input": "parser_dependency_on_generic_argument",
                "output": "canonical_syntactic_argument_role",
                "dependency_roles": dict(sorted(_DEPENDENCY_ROLES.items())),
                "prohibited": [
                    "semantic_role_selection",
                    "antecedent_selection",
                    "identity_closure",
                ],
                "authority": "configuration_only",
            }
        )
    result["compiler_declarations"] = sorted(
        declarations, key=lambda row: str(row.get("declaration_ref") or "")
    )
    result["argument_role_projection_contract"] = (
        ARGUMENT_ROLE_DECLARATION_REF
    )
    result["argument_role_projection_summary"] = {
        "base_factor_changes": base_changes,
        "refined_factor_changes": refined_changes,
        "aligned_morphology_span_count": len(morphology_by_span),
        "declaration_ref": ARGUMENT_ROLE_DECLARATION_REF,
        "authority": "syntactic_projection_only",
    }
    return result


__all__ = [
    "ARGUMENT_ROLE_DECLARATION_REF",
    "canonicalize_parser_argument_roles",
]
