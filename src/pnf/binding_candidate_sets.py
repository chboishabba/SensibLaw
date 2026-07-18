"""Set-valued document-local binding candidates for PartialPNF.

The local compiler may enumerate candidate antecedents while preserving ambiguity.
This module collapses pairwise evidence/alternative expansion into one immutable
candidate set per reference-factor revision and referential type.  Candidate
membership is not identity closure, and an empty set is never evidence that a
reference is expletive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_refs, canonical_sha256, require_text


ACCESSIBILITY_DECLARATION_REF = "binding-accessibility:document-structural:v0_2"
COMPATIBILITY_DECLARATION_REF = "binding-compatibility:pnf-kind-morphology:v0_2"
GENERATOR_OPERATION_REF = "operation:pnf-binding-candidate-set:v0_1"


@dataclass(frozen=True)
class BindingCandidateMember:
    candidate_factor_ref: str
    compatibility_state: str
    accessibility_path_ref: str
    compatibility_assessment_ref: str

    def to_dict(self) -> dict[str, str]:
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
    residuals: tuple[str, ...] = ("antecedent_unresolved",)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "sl.binding_candidate_set.v0_1",
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
            "exclusion_summaries": [
                row.to_dict() for row in self.exclusion_summaries
            ],
            "residuals": list(canonical_refs(self.residuals)),
            "authority": "candidate_only",
        }


def _factor_revision_ref(factor: Mapping[str, Any]) -> str:
    explicit = (factor.get("metadata") or {}).get("factor_revision_ref")
    if explicit:
        return str(explicit)
    return "factor-revision:" + canonical_sha256(factor)


def _accessibility_path(payload: Mapping[str, Any]) -> str:
    reference = payload.get("reference_position") or {}
    candidate = payload.get("candidate_position") or {}
    reference_sentence = reference.get("sentence_index")
    candidate_sentence = candidate.get("sentence_index")
    if reference_sentence == candidate_sentence:
        return "accessibility:same-sentence"
    if isinstance(reference_sentence, int) and isinstance(candidate_sentence, int):
        if candidate_sentence < reference_sentence:
            return "accessibility:preceding-discourse-unit"
    return "accessibility:parser-order"


def _candidate_ref(row: Mapping[str, Any], reference_factor_ref: str) -> str:
    return next(
        (
            str(subject_ref)
            for subject_ref in row.get("subject_refs") or ()
            if str(subject_ref) != reference_factor_ref
        ),
        "",
    )


def compact_binding_artifacts(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Return artifacts with pairwise binding expansion replaced by sets.

    Non-binding local evidence is retained byte-for-byte.  Typed meets and
    refinements reference candidate sets rather than removed pairwise evidence.
    The function is deterministic and idempotent.
    """

    if artifacts.get("binding_candidate_sets") is not None:
        return dict(artifacts)

    graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    factors = {
        str(row["factor_ref"]): row for row in graph.get("factors") or ()
    }
    binding_rows = tuple(
        row
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") == "typed_binding_candidate"
    )
    retained_evidence = tuple(
        row
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") != "typed_binding_candidate"
    )

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in binding_rows:
        subjects = tuple(str(ref) for ref in row.get("subject_refs") or ())
        if not subjects:
            continue
        reference_factor_ref = subjects[0]
        referential_type = str((row.get("payload") or {}).get("referential_type") or "")
        if reference_factor_ref and referential_type:
            grouped.setdefault((reference_factor_ref, referential_type), []).append(row)

    candidate_sets: list[BindingCandidateSet] = []
    evidence_to_set: dict[str, str] = {}
    pair_alternative_to_set: dict[str, str] = {}
    factor_to_sets: dict[str, list[str]] = {}

    for (reference_factor_ref, referential_type), rows in sorted(grouped.items()):
        factor = factors.get(reference_factor_ref) or {
            "factor_ref": reference_factor_ref,
            "factor_type": "semantic.reference",
            "closure_state": "open",
            "alternatives": (),
            "residuals": ("antecedent_unresolved",),
        }
        revision_ref = _factor_revision_ref(factor)
        build_payload = {
            "operation_ref": GENERATOR_OPERATION_REF,
            "reference_factor_revision_ref": revision_ref,
            "document_pnf_index_ref": str(graph.get("graph_ref") or ""),
            "accessibility_declaration_ref": ACCESSIBILITY_DECLARATION_REF,
            "compatibility_declaration_ref": COMPATIBILITY_DECLARATION_REF,
            "referential_type_ref": referential_type,
        }
        build_ref = "build:" + canonical_sha256(build_payload)
        set_ref = "binding-candidate-set:" + canonical_sha256(build_payload)
        members: dict[str, BindingCandidateMember] = {}
        exclusion_counts: dict[str, int] = {}
        for row in sorted(rows, key=lambda value: str(value.get("evidence_ref") or "")):
            evidence_ref = str(row.get("evidence_ref") or "")
            if evidence_ref:
                evidence_to_set[evidence_ref] = set_ref
            candidate_ref = _candidate_ref(row, reference_factor_ref)
            relation = str(row.get("relation") or "")
            pair_ref = (
                f"{reference_factor_ref}:binding:{referential_type}:{candidate_ref}"
            )
            pair_alternative_to_set[pair_ref] = set_ref
            if relation == "binding_incompatible_with" or not candidate_ref:
                reason = "inaccessible_or_incompatible"
                exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
                continue
            payload = row.get("payload") or {}
            assessment_ref = "binding-compatibility:" + canonical_sha256(
                {
                    "candidate_set_ref": set_ref,
                    "candidate_factor_ref": candidate_ref,
                    "relation": relation,
                    "payload": payload,
                }
            )
            members[candidate_ref] = BindingCandidateMember(
                candidate_factor_ref=candidate_ref,
                compatibility_state="compatible_candidate",
                accessibility_path_ref=_accessibility_path(payload),
                compatibility_assessment_ref=assessment_ref,
            )
        candidate_set = BindingCandidateSet(
            candidate_set_ref=set_ref,
            document_ref=str(next(iter(rows)).get("document_ref") or ""),
            reference_factor_ref=reference_factor_ref,
            reference_factor_revision_ref=revision_ref,
            referential_type_ref=referential_type,
            accessibility_declaration_ref=ACCESSIBILITY_DECLARATION_REF,
            compatibility_declaration_ref=COMPATIBILITY_DECLARATION_REF,
            generator_build_ref=build_ref,
            members=tuple(members[key] for key in sorted(members)),
            exclusion_summaries=tuple(
                BindingExclusionSummary(reason, count, build_ref)
                for reason, count in sorted(exclusion_counts.items())
            ),
        )
        candidate_sets.append(candidate_set)
        factor_to_sets.setdefault(reference_factor_ref, []).append(set_ref)

    compact_refinements: list[dict[str, Any]] = []
    for row in artifacts.get("factor_refinements") or ():
        compact = dict(row)
        prior = dict(compact.get("prior_factor") or {})
        resulting = dict(compact.get("resulting_factor") or {})
        factor_ref = str(prior.get("factor_ref") or resulting.get("factor_ref") or "")
        set_refs = tuple(sorted(set(factor_to_sets.get(factor_ref, ()))))
        if set_refs:
            alternatives = [
                alternative
                for alternative in resulting.get("alternatives") or ()
                if str(alternative.get("type_ref") or "") != "semantic.binding_candidate"
            ]
            existing_refs = {
                str(alternative.get("alternative_ref") or "") for alternative in alternatives
            }
            for set_ref in set_refs:
                alternative_ref = f"{factor_ref}:binding-set:{set_ref}"
                if alternative_ref not in existing_refs:
                    alternatives.append(
                        {
                            "alternative_ref": alternative_ref,
                            "type_ref": "semantic.binding_candidate_set",
                            "value": {"candidate_set_ref": set_ref},
                            "derivation_refs": [set_ref],
                            "authority_state": "candidate_only",
                        }
                    )
            resulting["alternatives"] = sorted(
                alternatives, key=lambda value: str(value.get("alternative_ref") or "")
            )
            compact["resulting_factor"] = resulting
            compact["candidate_set_refs"] = list(set_refs)
            compact["added_alternative_refs"] = sorted(
                {
                    ref
                    for ref in compact.get("added_alternative_refs") or ()
                    if ref not in pair_alternative_to_set
                }
                | {f"{factor_ref}:binding-set:{set_ref}" for set_ref in set_refs}
            )
            compact["rejected_candidate_refs"] = []
            compact["refinement_delta"] = {
                "prior_factor_revision_ref": _factor_revision_ref(prior),
                "resulting_factor_revision_ref": _factor_revision_ref(resulting),
                "candidate_set_refs": list(set_refs),
                "added_alternative_refs": compact["added_alternative_refs"],
                "retained_alternative_refs": list(
                    compact.get("retained_alternative_refs") or ()
                ),
                "rejected_alternative_refs": list(
                    compact.get("rejected_alternative_refs") or ()
                ),
                "residual_transitions": list(
                    compact.get("residual_transitions") or ()
                ),
            }
        compact_refinements.append(compact)

    compact_meets: list[dict[str, Any]] = []
    for row in artifacts.get("typed_meets") or ():
        compact = dict(row)
        refs = tuple(str(ref) for ref in compact.get("evidence_refs") or ())
        replacements = tuple(
            sorted({evidence_to_set[ref] for ref in refs if ref in evidence_to_set})
        )
        retained = tuple(ref for ref in refs if ref not in evidence_to_set)
        compact["evidence_refs"] = list(sorted(set(retained + replacements)))
        right_ref = str(compact.get("right_ref") or "")
        if right_ref in evidence_to_set:
            compact["right_ref"] = evidence_to_set[right_ref]
            compact["meet_type"] = "document_local_binding_candidate_set"
        compact_meets.append(compact)

    result = dict(artifacts)
    result["local_evidence"] = list(retained_evidence)
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
    result["typed_meets"] = compact_meets
    result["factor_refinements"] = compact_refinements
    result["binding_compaction_summary"] = {
        "pairwise_binding_evidence_removed": len(binding_rows),
        "candidate_set_count": len(candidate_sets),
        "candidate_member_count": sum(len(row.members) for row in candidate_sets),
        "exclusion_summary_count": sum(
            len(row.exclusion_summaries) for row in candidate_sets
        ),
        "accessibility_declaration_ref": ACCESSIBILITY_DECLARATION_REF,
        "compatibility_declaration_ref": COMPATIBILITY_DECLARATION_REF,
        "authority": "diagnostic_only",
    }
    return result


__all__ = [
    "ACCESSIBILITY_DECLARATION_REF",
    "BindingCandidateMember",
    "BindingCandidateSet",
    "BindingExclusionSummary",
    "COMPATIBILITY_DECLARATION_REF",
    "compact_binding_artifacts",
]
