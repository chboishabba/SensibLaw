"""Set-valued document-local binding candidates for PartialPNF.

The operational compiler constructs one immutable candidate set per reference
factor revision and referential type directly from the preserved annotation and
PNF graphs. Pairwise binding evidence is accepted only as a compatibility input
for older explicit exports. Candidate membership never closes coreference,
identity, event occurrence, proposition truth, or expletive status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_refs, canonical_sha256, require_text


ACCESSIBILITY_DECLARATION_REF = "binding-accessibility:document-structural:v0_3"
COMPATIBILITY_DECLARATION_REF = "binding-compatibility:pnf-kind-morphology:v0_3"
GENERATOR_OPERATION_REF = "operation:pnf-binding-candidate-set:v0_2"

_NONREFERENTIAL_TYPES = {"expletive_realisation"}
_CANDIDATE_FACTOR_TYPES: Mapping[str, tuple[str, ...]] = {
    "entity_reference": ("semantic.mention_identity",),
    "eventuality_reference": ("semantic.eventuality",),
    "proposition_reference": (
        "semantic.embedded_proposition",
        "semantic.proposition",
    ),
}
_ALLOWED_ACCESSIBILITY_PATHS: Mapping[str, tuple[str, ...]] = {
    "entity_reference": (
        "same_clause",
        "governing_clause",
        "preceding_coordinated_clause",
        "same_sentence",
        "preceding_discourse_unit",
        "preceding_paragraph",
        "preceding_document_unit",
    ),
    "eventuality_reference": (
        "same_clause",
        "governing_clause",
        "preceding_coordinated_clause",
        "same_sentence",
        "preceding_discourse_unit",
        "reporting_content_boundary",
        "preceding_paragraph",
        "preceding_document_unit",
    ),
    "proposition_reference": (
        "same_clause",
        "governing_clause",
        "preceding_coordinated_clause",
        "same_sentence",
        "preceding_discourse_unit",
        "reporting_content_boundary",
        "preceding_paragraph",
        "preceding_document_unit",
    ),
}
_MORPHOLOGY_FEATURES = ("Number", "Gender", "Person")
_CANDIDATE_LIMIT = 64


@dataclass(frozen=True)
class BindingAccessibilityDeclaration:
    declaration_ref: str = ACCESSIBILITY_DECLARATION_REF
    candidate_limit: int = _CANDIDATE_LIMIT

    def to_dict(self) -> dict[str, object]:
        return {
            "declaration_ref": self.declaration_ref,
            "allowed_paths": {
                key: list(value)
                for key, value in sorted(_ALLOWED_ACCESSIBILITY_PATHS.items())
            },
            "candidate_limit": self.candidate_limit,
            "computational_bound_role": "post_structural_accessibility_cap",
            "authority": "configuration_only",
        }


@dataclass(frozen=True)
class BindingCompatibilityDeclaration:
    declaration_ref: str = COMPATIBILITY_DECLARATION_REF

    def to_dict(self) -> dict[str, object]:
        return {
            "declaration_ref": self.declaration_ref,
            "referential_factor_types": {
                key: list(value)
                for key, value in sorted(_CANDIDATE_FACTOR_TYPES.items())
            },
            "morphology_features": list(_MORPHOLOGY_FEATURES),
            "missing_feature_policy": "retain_candidate",
            "authority": "configuration_only",
        }


@dataclass(frozen=True)
class FactorAnchor:
    factor_ref: str
    factor_revision_ref: str
    document_ref: str
    pnf_kind_ref: str
    start_token: int
    end_token: int
    sentence_index: int | None
    clause_ref: str | None
    discourse_unit_ref: str | None
    paragraph_index: int | None
    quotation_depth: int | None
    reporting_scope_ref: str | None
    coordination_group_ref: str | None
    parser_pos: str | None
    parser_dependency: str | None
    morphology: Mapping[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_ref": require_text(self.factor_ref, "factor_ref"),
            "factor_revision_ref": require_text(
                self.factor_revision_ref, "factor_revision_ref"
            ),
            "document_ref": require_text(self.document_ref, "document_ref"),
            "pnf_kind_ref": require_text(self.pnf_kind_ref, "pnf_kind_ref"),
            "start_token": self.start_token,
            "end_token": self.end_token,
            "sentence_index": self.sentence_index,
            "clause_ref": self.clause_ref,
            "discourse_unit_ref": self.discourse_unit_ref,
            "paragraph_index": self.paragraph_index,
            "quotation_depth": self.quotation_depth,
            "reporting_scope_ref": self.reporting_scope_ref,
            "coordination_group_ref": self.coordination_group_ref,
            "parser_pos": self.parser_pos,
            "parser_dependency": self.parser_dependency,
            "morphology": {
                key: list(value) for key, value in sorted(self.morphology.items())
            },
            "morphology_sha256": canonical_sha256(self.morphology),
            "authority": "parser_anchor_only",
        }


@dataclass(frozen=True)
class BindingCandidateMember:
    candidate_factor_ref: str
    compatibility_state: str
    accessibility_path_ref: str
    compatibility_assessment_ref: str
    distance_tokens: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_factor_ref": require_text(
                self.candidate_factor_ref, "candidate_factor_ref"
            ),
            "compatibility_state": require_text(
                self.compatibility_state, "compatibility_state"
            ),
            "accessibility_path_ref": require_text(
                self.accessibility_path_ref, "accessibility_path_ref"
            ),
            "compatibility_assessment_ref": require_text(
                self.compatibility_assessment_ref,
                "compatibility_assessment_ref",
            ),
            "distance_tokens": self.distance_tokens,
        }


@dataclass(frozen=True)
class BindingExclusionSummary:
    reason_ref: str
    excluded_count: int
    generator_build_ref: str

    def to_dict(self) -> dict[str, object]:
        if self.excluded_count < 0:
            raise ValueError("excluded_count must be non-negative")
        return {
            "reason_ref": require_text(self.reason_ref, "reason_ref"),
            "excluded_count": self.excluded_count,
            "generator_build_ref": require_text(
                self.generator_build_ref, "generator_build_ref"
            ),
        }


@dataclass(frozen=True)
class BindingCandidateSet:
    candidate_set_ref: str
    document_ref: str
    reference_factor_ref: str
    reference_factor_revision_ref: str
    referential_type_ref: str
    accessibility_declaration_ref: str
    compatibility_declaration_ref: str
    generator_build_ref: str
    members: tuple[BindingCandidateMember, ...]
    exclusion_summaries: tuple[BindingExclusionSummary, ...] = ()
    residuals: tuple[str, ...] = (
        "antecedent_unresolved",
        "referential_type_unresolved",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "sl.binding_candidate_set.v0_2",
            "candidate_set_ref": require_text(
                self.candidate_set_ref, "candidate_set_ref"
            ),
            "document_ref": require_text(self.document_ref, "document_ref"),
            "reference_factor_ref": require_text(
                self.reference_factor_ref, "reference_factor_ref"
            ),
            "reference_factor_revision_ref": require_text(
                self.reference_factor_revision_ref,
                "reference_factor_revision_ref",
            ),
            "referential_type_ref": require_text(
                self.referential_type_ref, "referential_type_ref"
            ),
            "accessibility_declaration_ref": require_text(
                self.accessibility_declaration_ref,
                "accessibility_declaration_ref",
            ),
            "compatibility_declaration_ref": require_text(
                self.compatibility_declaration_ref,
                "compatibility_declaration_ref",
            ),
            "generator_build_ref": require_text(
                self.generator_build_ref, "generator_build_ref"
            ),
            "member_count": len(self.members),
            "compatibility_state": (
                "compatible_members_present" if self.members else "no_compatible_member"
            ),
            "members": [row.to_dict() for row in self.members],
            "exclusion_summaries": [row.to_dict() for row in self.exclusion_summaries],
            "residuals": list(canonical_refs(self.residuals)),
            "authority": "candidate_only",
        }


def _factor_revision_ref(factor: Mapping[str, Any]) -> str:
    explicit = (factor.get("metadata") or {}).get("factor_revision_ref")
    if explicit:
        return str(explicit)
    return "factor-revision:" + canonical_sha256(factor)


def _normalise_morphology(value: object) -> dict[str, tuple[str, ...]]:
    if isinstance(value, Mapping):
        result: dict[str, tuple[str, ...]] = {}
        for key, raw in value.items():
            if isinstance(raw, str):
                values = tuple(item for item in raw.split(",") if item)
            elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                values = tuple(str(item) for item in raw if str(item))
            elif raw is None:
                values = ()
            else:
                values = (str(raw),)
            if values:
                result[str(key)] = tuple(sorted(set(values)))
        return result
    if isinstance(value, str):
        result: dict[str, tuple[str, ...]] = {}
        for item in value.split("|"):
            if "=" not in item:
                continue
            key, raw = item.split("=", 1)
            values = tuple(sorted(set(part for part in raw.split(",") if part)))
            if key and values:
                result[key] = values
        return result
    return {}


def _paragraph_index(text: str, start_char: int | None) -> int | None:
    if start_char is None or start_char < 0:
        return None
    prefix = text[:start_char]
    return prefix.count("\n\n")


def _quotation_depth(text: str, start_char: int | None) -> int | None:
    if start_char is None or start_char < 0:
        return None
    prefix = text[:start_char]
    straight = prefix.count('"') % 2
    curly = max(0, prefix.count("“") - prefix.count("”"))
    return straight + curly


def _span_contexts(artifacts: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    layer = artifacts.get("semantic_annotation_layer") or {}
    token_values = {
        (int(row["token_index"]), str(row["annotation_type"])): row.get("value")
        for row in layer.get("token_annotations") or ()
    }
    text = str(artifacts.get("canonical_text") or "")
    parser_spans = [
        row
        for row in layer.get("span_annotations") or ()
        if row.get("annotation_type") == "parser_token"
    ]
    contexts: dict[str, dict[str, Any]] = {}
    for span in parser_spans:
        index = int(span["start_token"])
        value = span.get("value") or {}
        start_char = value.get("start_char") if isinstance(value, Mapping) else None
        contexts[str(span["span_ref"])] = {
            "start_token": int(span["start_token"]),
            "end_token": int(span["end_token"]),
            "sentence_index": token_values.get((index, "parser.sentence")),
            "pos": token_values.get((index, "parser.pos")),
            "dependency": token_values.get((index, "parser.dependency")),
            "lemma": token_values.get((index, "parser.lemma")),
            "morphology": _normalise_morphology(
                token_values.get((index, "parser.morphology")) or {}
            ),
            "paragraph_index": _paragraph_index(text, start_char),
            "quotation_depth": _quotation_depth(text, start_char),
        }
    for span in layer.get("span_annotations") or ():
        if span.get("annotation_type") != "semantic_atom":
            continue
        overlaps = [
            contexts[str(parser_span["span_ref"])]
            for parser_span in parser_spans
            if str(parser_span["span_ref"]) in contexts
            and int(span["start_token"]) < int(parser_span["end_token"])
            and int(span["end_token"]) > int(parser_span["start_token"])
        ]
        if overlaps:
            contexts[str(span["span_ref"])] = dict(
                min(overlaps, key=lambda row: int(row["start_token"]))
            )
    return contexts


def _mention_contexts(
    artifacts: Mapping[str, Any], span_contexts: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    layer = artifacts.get("semantic_annotation_layer") or {}
    parser_spans = [
        row
        for row in layer.get("span_annotations") or ()
        if row.get("annotation_type") == "parser_token"
    ]
    result: dict[str, dict[str, Any]] = {}
    for mention in (artifacts.get("licensing") or {}).get("mentions") or ():
        matched = [
            span_contexts[str(span["span_ref"])]
            for span in parser_spans
            if str(span["span_ref"]) in span_contexts
            and int(mention["start_token"]) < int(span["end_token"])
            and int(mention["end_token"]) > int(span["start_token"])
        ]
        if matched:
            result[str(mention["mention_ref"])] = dict(
                min(matched, key=lambda row: int(row["start_token"]))
            )
    return result


def _factor_anchor(
    factor: Mapping[str, Any],
    *,
    document_ref: str,
    span_contexts: Mapping[str, Mapping[str, Any]],
    mention_contexts: Mapping[str, Mapping[str, Any]],
) -> FactorAnchor | None:
    metadata = factor.get("metadata") or {}
    contexts: list[Mapping[str, Any]] = []
    direct = metadata.get("atom_span_ref")
    if isinstance(direct, str) and direct in span_contexts:
        contexts.append(span_contexts[direct])
    for binding in metadata.get("bindings") or ():
        if not isinstance(binding, Mapping):
            continue
        atom_ref = binding.get("atom_ref")
        if isinstance(atom_ref, str) and atom_ref in span_contexts:
            contexts.append(span_contexts[atom_ref])
    mention_ref = metadata.get("mention_ref")
    if isinstance(mention_ref, str) and mention_ref in mention_contexts:
        contexts.append(mention_contexts[mention_ref])
    if not contexts:
        return None
    context = min(contexts, key=lambda row: int(row["start_token"]))
    sentence_index = context.get("sentence_index")
    relation_ref = metadata.get("relation_ref")
    relation_type = str(metadata.get("relation_type") or "")
    clause_ref = None
    if relation_ref and relation_type in {"predicate", "composition"}:
        clause_ref = f"clause:{relation_ref}"
    elif isinstance(sentence_index, int):
        clause_ref = f"clause:sentence:{sentence_index}:unresolved"
    reporting_scope_ref = (
        str(relation_ref)
        if relation_ref and relation_type == "composition"
        else None
    )
    coordination_group_ref = (
        str(relation_ref)
        if relation_ref and relation_type == "conjunction"
        else None
    )
    paragraph_index = context.get("paragraph_index")
    return FactorAnchor(
        factor_ref=str(factor["factor_ref"]),
        factor_revision_ref=_factor_revision_ref(factor),
        document_ref=document_ref,
        pnf_kind_ref=str(factor["factor_type"]),
        start_token=int(context["start_token"]),
        end_token=int(context["end_token"]),
        sentence_index=sentence_index if isinstance(sentence_index, int) else None,
        clause_ref=clause_ref,
        discourse_unit_ref=(
            f"sentence:{sentence_index}"
            if isinstance(sentence_index, int)
            else None
        ),
        paragraph_index=(paragraph_index if isinstance(paragraph_index, int) else None),
        quotation_depth=(
            int(context["quotation_depth"])
            if isinstance(context.get("quotation_depth"), int)
            else None
        ),
        reporting_scope_ref=reporting_scope_ref,
        coordination_group_ref=coordination_group_ref,
        parser_pos=(str(context["pos"]) if context.get("pos") else None),
        parser_dependency=(
            str(context["dependency"]) if context.get("dependency") else None
        ),
        morphology=_normalise_morphology(context.get("morphology") or {}),
    )


def _reference_types(factor: Mapping[str, Any]) -> tuple[str, ...]:
    values = {
        str((alternative.get("value") or {}).get("referential_type") or "")
        for alternative in factor.get("alternatives") or ()
        if alternative.get("type_ref") == "semantic.reference_candidate"
        and isinstance(alternative.get("value"), Mapping)
    }
    return tuple(
        sorted(
            value
            for value in values
            if value and value not in _NONREFERENTIAL_TYPES
        )
    )


def _candidate_types(
    factor: Mapping[str, Any], anchor: FactorAnchor
) -> tuple[str, ...]:
    factor_type = str(factor.get("factor_type") or "")
    types = [
        referential_type
        for referential_type, factor_types in _CANDIDATE_FACTOR_TYPES.items()
        if factor_type in factor_types
    ]
    if "entity_reference" in types and anchor.parser_pos not in {"NOUN", "PROPN"}:
        types.remove("entity_reference")
    return tuple(types)


def _accessibility_path(
    reference: FactorAnchor, candidate: FactorAnchor
) -> str:
    if candidate.start_token >= reference.start_token:
        return "not_preceding_reference"
    if (
        reference.quotation_depth is not None
        and candidate.quotation_depth is not None
        and reference.quotation_depth != candidate.quotation_depth
    ):
        if reference.reporting_scope_ref or candidate.reporting_scope_ref:
            return "reporting_content_boundary"
        return "quotation_boundary_crossed"
    if reference.clause_ref and reference.clause_ref == candidate.clause_ref:
        return "same_clause"
    if (
        reference.reporting_scope_ref
        and candidate.reporting_scope_ref
        and reference.reporting_scope_ref == candidate.reporting_scope_ref
    ):
        return "governing_clause"
    if (
        reference.coordination_group_ref
        and reference.coordination_group_ref == candidate.coordination_group_ref
    ):
        return "preceding_coordinated_clause"
    if (
        reference.sentence_index is not None
        and reference.sentence_index == candidate.sentence_index
    ):
        return "same_sentence"
    if (
        reference.paragraph_index is not None
        and reference.paragraph_index == candidate.paragraph_index
    ):
        return "preceding_discourse_unit"
    if (
        reference.paragraph_index is not None
        and candidate.paragraph_index is not None
        and candidate.paragraph_index < reference.paragraph_index
    ):
        return "preceding_paragraph"
    return "preceding_document_unit"


def _morphology_compatibility(
    reference: FactorAnchor, candidate: FactorAnchor
) -> tuple[str, tuple[str, ...]]:
    mismatches: list[str] = []
    for feature in _MORPHOLOGY_FEATURES:
        reference_values = set(reference.morphology.get(feature, ()))
        candidate_values = set(candidate.morphology.get(feature, ()))
        if reference_values and candidate_values and reference_values.isdisjoint(
            candidate_values
        ):
            mismatches.append(feature)
    if mismatches:
        return "incompatible_morphology", tuple(sorted(mismatches))
    return "compatible_candidate", ()


def _candidate_set_identity(
    *,
    reference_factor_revision_ref: str,
    graph_ref: str,
    referential_type: str,
) -> dict[str, str]:
    return {
        "operation_ref": GENERATOR_OPERATION_REF,
        "reference_factor_revision_ref": reference_factor_revision_ref,
        "document_pnf_index_ref": graph_ref,
        "accessibility_declaration_ref": ACCESSIBILITY_DECLARATION_REF,
        "compatibility_declaration_ref": COMPATIBILITY_DECLARATION_REF,
        "referential_type_ref": referential_type,
    }


def _direct_candidate_sets(
    artifacts: Mapping[str, Any],
) -> tuple[
    tuple[BindingCandidateSet, ...],
    tuple[FactorAnchor, ...],
    dict[str, list[str]],
    dict[str, str],
]:
    graph = artifacts.get("pnf_graph") or {}
    document_ref = str(graph.get("document_ref") or "")
    factors = tuple(graph.get("factors") or ())
    span_contexts = _span_contexts(artifacts)
    mention_contexts = _mention_contexts(artifacts, span_contexts)
    anchors: dict[str, FactorAnchor] = {}
    factor_by_ref = {str(row["factor_ref"]): row for row in factors}
    for factor in factors:
        anchor = _factor_anchor(
            factor,
            document_ref=document_ref,
            span_contexts=span_contexts,
            mention_contexts=mention_contexts,
        )
        if anchor is not None:
            anchors[anchor.factor_ref] = anchor

    candidate_index: dict[str, list[tuple[Mapping[str, Any], FactorAnchor]]] = {
        key: [] for key in _CANDIDATE_FACTOR_TYPES
    }
    for factor_ref, anchor in anchors.items():
        factor = factor_by_ref[factor_ref]
        for referential_type in _candidate_types(factor, anchor):
            candidate_index[referential_type].append((factor, anchor))
    for rows in candidate_index.values():
        rows.sort(key=lambda row: (row[1].start_token, row[1].factor_ref))

    candidate_sets: list[BindingCandidateSet] = []
    factor_to_sets: dict[str, list[str]] = {}
    set_to_reference: dict[str, str] = {}
    for reference_factor in sorted(factors, key=lambda row: str(row["factor_ref"])):
        reference_factor_ref = str(reference_factor["factor_ref"])
        reference_anchor = anchors.get(reference_factor_ref)
        if reference_anchor is None:
            continue
        for referential_type in _reference_types(reference_factor):
            if referential_type not in candidate_index:
                continue
            identity = _candidate_set_identity(
                reference_factor_revision_ref=reference_anchor.factor_revision_ref,
                graph_ref=str(graph.get("graph_ref") or ""),
                referential_type=referential_type,
            )
            build_ref = "build:" + canonical_sha256(identity)
            candidate_set_ref = "binding-candidate-set:" + canonical_sha256(identity)
            allowed_paths = set(
                _ALLOWED_ACCESSIBILITY_PATHS.get(referential_type, ())
            )
            compatible: list[tuple[int, BindingCandidateMember]] = []
            exclusion_counts: dict[str, int] = {}
            for candidate_factor, candidate_anchor in candidate_index[referential_type]:
                if candidate_anchor.factor_ref == reference_factor_ref:
                    continue
                path = _accessibility_path(reference_anchor, candidate_anchor)
                if path not in allowed_paths:
                    exclusion_counts[path] = exclusion_counts.get(path, 0) + 1
                    continue
                state, mismatches = _morphology_compatibility(
                    reference_anchor, candidate_anchor
                )
                if state != "compatible_candidate":
                    reason = "incompatible_morphology:" + ",".join(mismatches)
                    exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
                    continue
                distance = reference_anchor.start_token - candidate_anchor.start_token
                assessment_ref = "binding-compatibility:" + canonical_sha256(
                    {
                        "candidate_set_ref": candidate_set_ref,
                        "candidate_factor_ref": candidate_anchor.factor_ref,
                        "accessibility_path_ref": path,
                        "morphology_features": _MORPHOLOGY_FEATURES,
                    }
                )
                compatible.append(
                    (
                        distance,
                        BindingCandidateMember(
                            candidate_factor_ref=candidate_anchor.factor_ref,
                            compatibility_state=state,
                            accessibility_path_ref=f"accessibility:{path}",
                            compatibility_assessment_ref=assessment_ref,
                            distance_tokens=distance,
                        ),
                    )
                )
            compatible.sort(key=lambda row: (row[0], row[1].candidate_factor_ref))
            if len(compatible) > _CANDIDATE_LIMIT:
                exclusion_counts["candidate_limit_truncation"] = (
                    len(compatible) - _CANDIDATE_LIMIT
                )
                compatible = compatible[:_CANDIDATE_LIMIT]
            candidate_set = BindingCandidateSet(
                candidate_set_ref=candidate_set_ref,
                document_ref=document_ref,
                reference_factor_ref=reference_factor_ref,
                reference_factor_revision_ref=reference_anchor.factor_revision_ref,
                referential_type_ref=referential_type,
                accessibility_declaration_ref=ACCESSIBILITY_DECLARATION_REF,
                compatibility_declaration_ref=COMPATIBILITY_DECLARATION_REF,
                generator_build_ref=build_ref,
                members=tuple(row[1] for row in compatible),
                exclusion_summaries=tuple(
                    BindingExclusionSummary(reason, count, build_ref)
                    for reason, count in sorted(exclusion_counts.items())
                ),
            )
            candidate_sets.append(candidate_set)
            factor_to_sets.setdefault(reference_factor_ref, []).append(
                candidate_set_ref
            )
            set_to_reference[candidate_set_ref] = reference_factor_ref
    return (
        tuple(candidate_sets),
        tuple(sorted(anchors.values(), key=lambda row: row.factor_ref)),
        factor_to_sets,
        set_to_reference,
    )


def _pairwise_candidate_sets(
    artifacts: Mapping[str, Any],
) -> tuple[
    tuple[BindingCandidateSet, ...],
    tuple[FactorAnchor, ...],
    dict[str, list[str]],
    dict[str, str],
]:
    graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    factors = {str(row["factor_ref"]): row for row in graph.get("factors") or ()}
    rows = tuple(
        row
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") == "typed_binding_candidate"
    )
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        subjects = tuple(str(ref) for ref in row.get("subject_refs") or ())
        if not subjects:
            continue
        referential_type = str(
            (row.get("payload") or {}).get("referential_type") or ""
        )
        if referential_type:
            grouped.setdefault((subjects[0], referential_type), []).append(row)
    candidate_sets: list[BindingCandidateSet] = []
    factor_to_sets: dict[str, list[str]] = {}
    set_to_reference: dict[str, str] = {}
    for (reference_factor_ref, referential_type), grouped_rows in sorted(
        grouped.items()
    ):
        factor = factors.get(reference_factor_ref) or {
            "factor_ref": reference_factor_ref,
            "factor_type": "semantic.reference",
            "closure_state": "open",
            "alternatives": (),
            "residuals": ("antecedent_unresolved",),
        }
        identity = _candidate_set_identity(
            reference_factor_revision_ref=_factor_revision_ref(factor),
            graph_ref=str(graph.get("graph_ref") or ""),
            referential_type=referential_type,
        )
        build_ref = "build:" + canonical_sha256(identity)
        candidate_set_ref = "binding-candidate-set:" + canonical_sha256(identity)
        members: dict[str, BindingCandidateMember] = {}
        exclusions: dict[str, int] = {}
        for row in grouped_rows:
            candidate_ref = next(
                (
                    str(ref)
                    for ref in row.get("subject_refs") or ()
                    if str(ref) != reference_factor_ref
                ),
                "",
            )
            if row.get("relation") == "binding_incompatible_with" or not candidate_ref:
                exclusions["legacy_inaccessible_or_incompatible"] = (
                    exclusions.get("legacy_inaccessible_or_incompatible", 0) + 1
                )
                continue
            payload = row.get("payload") or {}
            reference_position = payload.get("reference_position") or {}
            candidate_position = payload.get("candidate_position") or {}
            distance = None
            if isinstance(reference_position.get("start_token"), int) and isinstance(
                candidate_position.get("start_token"), int
            ):
                distance = int(reference_position["start_token"]) - int(
                    candidate_position["start_token"]
                )
            path = "preceding_discourse_unit"
            if reference_position.get("sentence_index") == candidate_position.get(
                "sentence_index"
            ):
                path = "same_sentence"
            assessment_ref = "binding-compatibility:" + canonical_sha256(
                {
                    "candidate_set_ref": candidate_set_ref,
                    "candidate_factor_ref": candidate_ref,
                    "legacy_evidence_ref": row.get("evidence_ref"),
                }
            )
            members[candidate_ref] = BindingCandidateMember(
                candidate_factor_ref=candidate_ref,
                compatibility_state="compatible_candidate",
                accessibility_path_ref=f"accessibility:{path}",
                compatibility_assessment_ref=assessment_ref,
                distance_tokens=distance,
            )
        candidate_set = BindingCandidateSet(
            candidate_set_ref=candidate_set_ref,
            document_ref=str(grouped_rows[0].get("document_ref") or ""),
            reference_factor_ref=reference_factor_ref,
            reference_factor_revision_ref=_factor_revision_ref(factor),
            referential_type_ref=referential_type,
            accessibility_declaration_ref=ACCESSIBILITY_DECLARATION_REF,
            compatibility_declaration_ref=COMPATIBILITY_DECLARATION_REF,
            generator_build_ref=build_ref,
            members=tuple(members[key] for key in sorted(members)),
            exclusion_summaries=tuple(
                BindingExclusionSummary(reason, count, build_ref)
                for reason, count in sorted(exclusions.items())
            ),
        )
        candidate_sets.append(candidate_set)
        factor_to_sets.setdefault(reference_factor_ref, []).append(candidate_set_ref)
        set_to_reference[candidate_set_ref] = reference_factor_ref
    return tuple(candidate_sets), (), factor_to_sets, set_to_reference


def _strip_pairwise_alternatives(
    alternatives: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    retained: list[dict[str, Any]] = []
    rejected: list[str] = []
    for alternative in alternatives:
        if alternative.get("type_ref") == "semantic.binding_candidate":
            rejected.append(str(alternative.get("alternative_ref") or ""))
        else:
            retained.append(dict(alternative))
    return retained, tuple(sorted(ref for ref in rejected if ref))


def _refine_factors(
    artifacts: Mapping[str, Any],
    candidate_sets: Sequence[BindingCandidateSet],
    factor_to_sets: Mapping[str, Sequence[str]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    base_graph = artifacts.get("pnf_graph") or {}
    refined_graph = artifacts.get("refined_pnf_graph") or base_graph
    base_factors = {
        str(row["factor_ref"]): dict(row) for row in base_graph.get("factors") or ()
    }
    refined_factors = {
        str(row["factor_ref"]): dict(row) for row in refined_graph.get("factors") or ()
    }
    existing_refinements = {
        str((row.get("prior_factor") or {}).get("factor_ref") or ""): dict(row)
        for row in artifacts.get("factor_refinements") or ()
    }
    set_by_ref = {row.candidate_set_ref: row for row in candidate_sets}
    resulting_revision_refs: dict[str, str] = {}
    for factor_ref, set_refs in sorted(factor_to_sets.items()):
        prior = base_factors.get(factor_ref)
        resulting = refined_factors.get(factor_ref)
        if prior is None or resulting is None:
            continue
        alternatives, rejected_pairwise = _strip_pairwise_alternatives(
            resulting.get("alternatives") or ()
        )
        existing_alternative_refs = {
            str(row.get("alternative_ref") or "") for row in alternatives
        }
        added: list[str] = []
        for candidate_set_ref in sorted(set(set_refs)):
            candidate_set = set_by_ref[candidate_set_ref]
            alternative_ref = f"{factor_ref}:binding-set:{candidate_set_ref}"
            if alternative_ref in existing_alternative_refs:
                continue
            alternatives.append(
                {
                    "alternative_ref": alternative_ref,
                    "value": {
                        "candidate_set_ref": candidate_set_ref,
                        "referential_type": candidate_set.referential_type_ref,
                    },
                    "type_ref": "semantic.binding_candidate_set",
                    "derivation_refs": [candidate_set_ref],
                    "authority_state": "candidate_only",
                }
            )
            added.append(alternative_ref)
        metadata = dict(resulting.get("metadata") or {})
        metadata.pop("factor_revision_ref", None)
        metadata["binding_candidate_set_refs"] = sorted(set(set_refs))
        metadata["binding_accessibility_declaration_ref"] = (
            ACCESSIBILITY_DECLARATION_REF
        )
        metadata["binding_compatibility_declaration_ref"] = (
            COMPATIBILITY_DECLARATION_REF
        )
        dependency = str(metadata.get("parser_dependency") or "")
        if dependency == "expl":
            metadata["expletive_observation_ref"] = (
                "parser-structural-evidence:dependency-expl"
            )
        resulting = {
            **resulting,
            "alternatives": sorted(
                alternatives, key=lambda row: str(row.get("alternative_ref") or "")
            ),
            "metadata": metadata,
        }
        revision_ref = "factor-revision:" + canonical_sha256(resulting)
        resulting["metadata"] = {
            **metadata,
            "factor_revision_ref": revision_ref,
        }
        resulting_revision_refs[factor_ref] = revision_ref
        refined_factors[factor_ref] = resulting
        existing = existing_refinements.get(factor_ref, {})
        retained_refs = tuple(
            sorted(
                str(row.get("alternative_ref") or "")
                for row in prior.get("alternatives") or ()
                if row.get("alternative_ref")
            )
        )
        refinement_identity = {
            "factor_ref": factor_ref,
            "prior_factor_revision_ref": _factor_revision_ref(prior),
            "resulting_factor_revision_ref": revision_ref,
            "candidate_set_refs": sorted(set(set_refs)),
        }
        existing_refinements[factor_ref] = {
            "refinement_ref": "factor-refinement:"
            + canonical_sha256(refinement_identity),
            "prior_factor": prior,
            "resulting_factor": resulting,
            "added_alternative_refs": sorted(
                set(existing.get("added_alternative_refs") or ()) | set(added)
            ),
            "retained_alternative_refs": list(retained_refs),
            "rejected_alternative_refs": sorted(
                set(existing.get("rejected_alternative_refs") or ())
                | set(rejected_pairwise)
            ),
            "rejected_candidate_refs": [],
            "residual_transitions": list(
                existing.get("residual_transitions") or ()
            ),
            "evidence_refs": [
                ref
                for ref in existing.get("evidence_refs") or ()
                if not str(ref).startswith("local-evidence:")
            ],
            "candidate_set_refs": sorted(set(set_refs)),
            "refinement_delta": {
                **refinement_identity,
                "added_alternative_refs": sorted(added),
                "retained_alternative_refs": list(retained_refs),
                "rejected_alternative_refs": list(rejected_pairwise),
                "residual_transitions": list(
                    existing.get("residual_transitions") or ()
                ),
            },
            "authority": "pnf_refinement_only",
        }
    return (
        [
            existing_refinements[key]
            for key in sorted(existing_refinements)
            if key
        ],
        refined_factors,
        resulting_revision_refs,
    )


def _binding_meets(
    artifacts: Mapping[str, Any],
    candidate_sets: Sequence[BindingCandidateSet],
) -> list[dict[str, Any]]:
    pairwise_evidence_refs = {
        str(row.get("evidence_ref") or "")
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") == "typed_binding_candidate"
    }
    retained = []
    for row in artifacts.get("typed_meets") or ():
        refs = {str(ref) for ref in row.get("evidence_refs") or ()}
        if str(row.get("right_ref") or "") in pairwise_evidence_refs:
            continue
        if refs.intersection(pairwise_evidence_refs):
            item = dict(row)
            item["evidence_refs"] = sorted(refs.difference(pairwise_evidence_refs))
            retained.append(item)
        else:
            retained.append(dict(row))
    for candidate_set in candidate_sets:
        state = (
            "compatible_with_refinement"
            if candidate_set.members
            else "unresolved"
        )
        meet_identity = {
            "left_ref": candidate_set.reference_factor_ref,
            "right_ref": candidate_set.candidate_set_ref,
            "state": state,
        }
        retained.append(
            {
                "meet_ref": "typed-meet:" + canonical_sha256(meet_identity),
                "left_ref": candidate_set.reference_factor_ref,
                "right_ref": candidate_set.candidate_set_ref,
                "meet_type": "document_local_binding_candidate_set",
                "state": state,
                "result_alternatives": [
                    row.candidate_factor_ref for row in candidate_set.members
                ],
                "candidate_set_refs": [candidate_set.candidate_set_ref],
                "evidence_refs": [],
                "residual_refs": list(candidate_set.residuals),
                "authority": "assessment_only",
            }
        )
    return sorted(retained, key=lambda row: str(row.get("meet_ref") or ""))


def _relink_demands(
    artifacts: Mapping[str, Any],
    refined_factors: Mapping[str, Mapping[str, Any]],
    factor_to_sets: Mapping[str, Sequence[str]],
    revision_refs: Mapping[str, str],
) -> list[dict[str, Any]]:
    demands: list[dict[str, Any]] = []
    for row in artifacts.get("resolution_demands") or ():
        factor_ref = str(row.get("factor_ref") or "")
        if factor_ref not in factor_to_sets:
            demands.append(dict(row))
            continue
        factor = refined_factors[factor_ref]
        revision_ref = revision_refs.get(factor_ref) or _factor_revision_ref(factor)
        item = dict(row)
        item["factor_revision_ref"] = revision_ref
        item["expected_type_alternatives"] = sorted(
            str(alternative.get("type_ref") or "")
            for alternative in factor.get("alternatives") or ()
        )
        item["candidate_set_refs"] = sorted(set(factor_to_sets[factor_ref]))
        semantic_key = dict(item.get("semantic_key") or {})
        semantic_key["factor_revision_ref"] = revision_ref
        semantic_key["expected_type_alternatives"] = item[
            "expected_type_alternatives"
        ]
        semantic_key["candidate_set_refs"] = item["candidate_set_refs"]
        item["semantic_key"] = semantic_key
        item["demand_ref"] = "demand:" + canonical_sha256(semantic_key)
        item["closure_impact"] = "document_local_binding_set_refinement"
        demands.append(item)
    return sorted(demands, key=lambda row: str(row.get("demand_ref") or ""))


def compact_binding_artifacts(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the set-valued operational PNF binding representation.

    When the preserved semantic annotation graph is available, candidate sets
    are generated directly from graph indexes. Pairwise evidence is ignored for
    membership and removed from the result. Older synthetic/export carriers can
    still be compacted through the compatibility fallback.
    """

    if artifacts.get("binding_candidate_sets") is not None:
        return dict(artifacts)
    has_observation_graph = bool(
        (artifacts.get("semantic_annotation_layer") or {}).get("span_annotations")
    )
    if has_observation_graph:
        candidate_sets, anchors, factor_to_sets, set_to_reference = (
            _direct_candidate_sets(artifacts)
        )
        generation_mode = "direct_observation_graph_index"
    else:
        candidate_sets, anchors, factor_to_sets, set_to_reference = (
            _pairwise_candidate_sets(artifacts)
        )
        generation_mode = "legacy_pairwise_compatibility"
    refinements, refined_factors, revision_refs = _refine_factors(
        artifacts, candidate_sets, factor_to_sets
    )
    base_refined_graph = artifacts.get("refined_pnf_graph") or artifacts.get(
        "pnf_graph"
    ) or {}
    refined_graph = {
        **base_refined_graph,
        "factors": [refined_factors[key] for key in sorted(refined_factors)],
    }
    refined_graph["graph_ref"] = "pnf-graph:" + canonical_sha256(
        {
            "document_ref": refined_graph.get("document_ref"),
            "factors": refined_graph["factors"],
            "constraints": refined_graph.get("constraints") or (),
        }
    )
    local_evidence = [
        dict(row)
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") != "typed_binding_candidate"
    ]
    zero_sets = sum(not row.members for row in candidate_sets)
    one_sets = sum(len(row.members) == 1 for row in candidate_sets)
    many_sets = sum(len(row.members) > 1 for row in candidate_sets)
    reference_factors = {
        row.reference_factor_ref for row in candidate_sets
    }
    expletive_observed = sum(
        1
        for factor_ref in reference_factors
        if str((refined_factors.get(factor_ref) or {}).get("metadata", {}).get(
            "parser_dependency"
        ) or "")
        == "expl"
    )
    result = dict(artifacts)
    result["local_evidence"] = local_evidence
    result["binding_accessibility_declaration"] = (
        BindingAccessibilityDeclaration().to_dict()
    )
    result["binding_compatibility_declaration"] = (
        BindingCompatibilityDeclaration().to_dict()
    )
    result["binding_candidate_sets"] = [row.to_dict() for row in candidate_sets]
    result["binding_candidate_members"] = [
        {
            "candidate_set_ref": candidate_set.candidate_set_ref,
            **member.to_dict(),
        }
        for candidate_set in candidate_sets
        for member in candidate_set.members
    ]
    result["binding_exclusion_summaries"] = [
        {
            "candidate_set_ref": candidate_set.candidate_set_ref,
            **summary.to_dict(),
        }
        for candidate_set in candidate_sets
        for summary in candidate_set.exclusion_summaries
    ]
    result["binding_candidate_set_builds"] = [
        {
            "generator_build_ref": row.generator_build_ref,
            "candidate_set_ref": row.candidate_set_ref,
            "reference_factor_revision_ref": row.reference_factor_revision_ref,
            "document_pnf_index_ref": str(
                (artifacts.get("pnf_graph") or {}).get("graph_ref") or ""
            ),
            "accessibility_declaration_ref": row.accessibility_declaration_ref,
            "compatibility_declaration_ref": row.compatibility_declaration_ref,
            "referential_type_ref": row.referential_type_ref,
            "authority": "build_identity_only",
        }
        for row in candidate_sets
    ]
    result["factor_anchors"] = [row.to_dict() for row in anchors]
    result["typed_meets"] = _binding_meets(artifacts, candidate_sets)
    result["factor_refinements"] = refinements
    result["refined_pnf_graph"] = refined_graph
    result["resolution_demands"] = _relink_demands(
        artifacts,
        refined_factors,
        factor_to_sets,
        revision_refs,
    )
    result["binding_compaction_summary"] = {
        "generation_mode": generation_mode,
        "pairwise_binding_evidence_removed": sum(
            row.get("evidence_type") == "typed_binding_candidate"
            for row in artifacts.get("local_evidence") or ()
        ),
        "reference_factor_count": len(reference_factors),
        "candidate_set_count": len(candidate_sets),
        "candidate_member_count": sum(len(row.members) for row in candidate_sets),
        "zero_member_set_count": zero_sets,
        "one_member_set_count": one_sets,
        "many_member_set_count": many_sets,
        "exclusion_summary_count": sum(
            len(row.exclusion_summaries) for row in candidate_sets
        ),
        "expletive_parser_observation_count": expletive_observed,
        "set_to_reference": dict(sorted(set_to_reference.items())),
        "accessibility_declaration_ref": ACCESSIBILITY_DECLARATION_REF,
        "compatibility_declaration_ref": COMPATIBILITY_DECLARATION_REF,
        "authority": "diagnostic_only",
    }
    return result


__all__ = [
    "ACCESSIBILITY_DECLARATION_REF",
    "BindingAccessibilityDeclaration",
    "BindingCandidateMember",
    "BindingCandidateSet",
    "BindingCompatibilityDeclaration",
    "BindingExclusionSummary",
    "COMPATIBILITY_DECLARATION_REF",
    "FactorAnchor",
    "compact_binding_artifacts",
]
