from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SEMANTIC_SEPARABILITY_ASSESSMENT_SCHEMA_VERSION = "sl.semantic_separability_assessment.v0_1"
_NORMALIZED_GWB_TARGET_SPLIT_KIND = {
    "matched_event": "event_split",
    "matched_source_family": "family_split",
}


@dataclass(frozen=True)
class GWBTargetingCandidate:
    seed_id: str
    review_item_id: str
    candidate_ref: str
    candidate_kind: str
    relation_kind: str
    selection_basis: str
    target_proposition_identity: dict[str, Any]
    anchor_refs: dict[str, Any]
    target_split_kind: str | None = None
    target_split_value: str | None = None
    target_text_or_label: str | None = None
    target_coverage_basis: str | None = None


@dataclass(frozen=True)
class GWBTargetingResult:
    claim_id: str
    seed_id: str
    candidate_targets: tuple[GWBTargetingCandidate, ...]
    selected_target: GWBTargetingCandidate | None
    selection_mode: str
    selection_basis: str
    candidate_count: int


@dataclass(frozen=True)
class SemanticSeparabilityAssessment:
    lane: str
    claim_id: str
    seed_id: str
    selection_mode: str
    candidate_count: int
    candidate_refs: tuple[str, ...]
    basis_kind: str
    assessment_status: str
    reason_codes: tuple[str, ...]
    descriptive_only: bool = True
    schema_version: str = SEMANTIC_SEPARABILITY_ASSESSMENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "lane": self.lane,
            "claim_id": self.claim_id,
            "seed_id": self.seed_id,
            "selection_mode": self.selection_mode,
            "candidate_count": self.candidate_count,
            "candidate_refs": [value for value in self.candidate_refs if value],
            "basis_kind": self.basis_kind,
            "assessment_status": self.assessment_status,
            "reason_codes": [value for value in self.reason_codes if value],
            "descriptive_only": self.descriptive_only,
        }


def build_gwb_targeting_result(
    *,
    claim_id: str,
    seed_id: str,
    candidate_targets: Sequence[GWBTargetingCandidate],
    selection_basis: str = "seed_linkage",
) -> GWBTargetingResult:
    candidates = tuple(candidate_targets)
    if not candidates:
        return GWBTargetingResult(
            claim_id=str(claim_id or "").strip(),
            seed_id=str(seed_id or "").strip(),
            candidate_targets=(),
            selected_target=None,
            selection_mode="no_target",
            selection_basis=selection_basis,
            candidate_count=0,
        )
    if len(candidates) == 1:
        return GWBTargetingResult(
            claim_id=str(claim_id or "").strip(),
            seed_id=str(seed_id or "").strip(),
            candidate_targets=candidates,
            selected_target=candidates[0],
            selection_mode="singleton_seed_linkage",
            selection_basis=selection_basis,
            candidate_count=1,
        )
    return GWBTargetingResult(
        claim_id=str(claim_id or "").strip(),
        seed_id=str(seed_id or "").strip(),
        candidate_targets=candidates,
        selected_target=None,
        selection_mode="multi_candidate_unresolved",
        selection_basis=selection_basis,
        candidate_count=len(candidates),
    )


def summarize_gwb_targeting_results(
    results: Sequence[GWBTargetingResult], *, top_n: int = 5
) -> dict[str, Any]:
    """Developer-only ambiguity inventory for deciding whether richer targeting is justified."""
    selection_mode_counts: dict[str, int] = {}
    selection_basis_counts: dict[str, int] = {}
    ambiguous_seeds: list[dict[str, Any]] = []
    for result in results:
        selection_mode_counts[result.selection_mode] = selection_mode_counts.get(result.selection_mode, 0) + 1
        selection_basis_counts[result.selection_basis] = selection_basis_counts.get(result.selection_basis, 0) + 1
        if result.selection_mode == "multi_candidate_unresolved":
            ambiguous_seeds.append(
                {
                    "seed_id": result.seed_id,
                    "claim_id": result.claim_id,
                    "candidate_count": result.candidate_count,
                    "candidate_refs": [candidate.candidate_ref for candidate in result.candidate_targets],
                }
            )
    ambiguous_seeds.sort(
        key=lambda item: (-int(item.get("candidate_count") or 0), str(item.get("seed_id") or ""))
    )
    return {
        "selection_mode_counts": selection_mode_counts,
        "selection_basis_counts": selection_basis_counts,
        "top_ambiguous_seeds": ambiguous_seeds[: max(int(top_n), 0)],
    }


def normalize_gwb_target_split_kind(value: Any) -> str:
    return _NORMALIZED_GWB_TARGET_SPLIT_KIND.get(str(value or "").strip(), "no_split")


def build_gwb_ambiguous_seed_inventory(
    results: Sequence[GWBTargetingResult], *, top_n: int = 10
) -> list[dict[str, Any]]:
    """Developer-only view of unresolved GWB seeds for manual semantic inspection."""
    inventory: list[dict[str, Any]] = []
    for result in results:
        if result.selection_mode != "multi_candidate_unresolved":
            continue
        separability = assess_gwb_semantic_separability(result=result)
        relation_kinds = sorted(
            {
                str(candidate.relation_kind or "").strip()
                for candidate in result.candidate_targets
                if str(candidate.relation_kind or "").strip()
            }
        )
        anchor_ref_keys = sorted(
            {
                str(key).strip()
                for candidate in result.candidate_targets
                for key in candidate.anchor_refs.keys()
                if str(key).strip()
            }
        )
        candidate_kinds = sorted(
            {
                str(candidate.candidate_kind or "").strip()
                for candidate in result.candidate_targets
                if str(candidate.candidate_kind or "").strip()
            }
        )
        split_kinds = sorted(
            {
                normalize_gwb_target_split_kind(candidate.target_split_kind)
                for candidate in result.candidate_targets
            }
        )
        candidate_cards = []
        for candidate in result.candidate_targets:
            candidate_cards.append(
                {
                    "candidate_ref": candidate.candidate_ref,
                    "candidate_kind": candidate.candidate_kind,
                    "normalized_split_kind": normalize_gwb_target_split_kind(candidate.target_split_kind),
                    "split_value": str(candidate.target_split_value or "").strip() or None,
                    "text_or_label": str(candidate.target_text_or_label or "").strip() or None,
                    "coverage_basis": str(candidate.target_coverage_basis or "").strip() or None,
                    "target_proposition_id": str(
                        candidate.target_proposition_identity.get("proposition_id") or ""
                    ).strip()
                    or None,
                }
            )
        inventory.append(
            {
                "seed_id": result.seed_id,
                "claim_id": result.claim_id,
                "candidate_count": result.candidate_count,
                "candidate_refs": [candidate.candidate_ref for candidate in result.candidate_targets],
                "candidate_kinds": candidate_kinds,
                "relation_kinds": relation_kinds,
                "anchor_ref_keys": anchor_ref_keys,
                "selection_basis": result.selection_basis,
                "selection_mode": result.selection_mode,
                "normalized_split_kinds": split_kinds,
                "semantic_separability": str(separability.get("assessment_status") or "").strip(),
                "semantic_reason_codes": [
                    str(value).strip()
                    for value in separability.get("reason_codes", [])
                    if str(value).strip()
                ],
                "candidate_cards": candidate_cards,
            }
        )
    inventory.sort(key=lambda item: (-int(item.get("candidate_count") or 0), str(item.get("seed_id") or "")))
    return inventory[: max(int(top_n), 0)]


def assess_gwb_semantic_separability(*, result: GWBTargetingResult) -> dict[str, Any]:
    reason_codes: list[str] = []
    if result.candidate_count <= 0:
        return SemanticSeparabilityAssessment(
            lane="gwb",
            claim_id=result.claim_id,
            seed_id=result.seed_id,
            selection_mode=result.selection_mode,
            candidate_count=result.candidate_count,
            candidate_refs=tuple(),
            basis_kind=result.selection_basis,
            assessment_status="not_applicable",
            reason_codes=("no_target",),
        ).as_dict()

    candidate_refs = tuple(candidate.candidate_ref for candidate in result.candidate_targets if candidate.candidate_ref)
    if result.candidate_count == 1:
        return SemanticSeparabilityAssessment(
            lane="gwb",
            claim_id=result.claim_id,
            seed_id=result.seed_id,
            selection_mode=result.selection_mode,
            candidate_count=result.candidate_count,
            candidate_refs=candidate_refs,
            basis_kind=result.selection_basis,
            assessment_status="not_applicable",
            reason_codes=("singleton_target",),
        ).as_dict()

    semantic_keys: list[tuple[str, str, str]] = []
    for candidate in result.candidate_targets:
        split_kind = str(candidate.target_split_kind or "").strip()
        split_value = str(candidate.target_split_value or "").strip()
        coverage_basis = str(candidate.target_coverage_basis or "").strip()
        if not split_kind or not split_value or not coverage_basis:
            return SemanticSeparabilityAssessment(
                lane="gwb",
                claim_id=result.claim_id,
                seed_id=result.seed_id,
                selection_mode=result.selection_mode,
                candidate_count=result.candidate_count,
                candidate_refs=candidate_refs,
                basis_kind=result.selection_basis,
                assessment_status="insufficient_semantics",
                reason_codes=("missing_target_split_semantics",),
            ).as_dict()
        semantic_keys.append((split_kind, split_value, coverage_basis))

    if len(set(semantic_keys)) == len(semantic_keys):
        reason_codes.append("distinct_target_splits")
        status = "separable"
    else:
        reason_codes.append("duplicate_target_split_semantics")
        status = "nonseparable_unresolved"

    return SemanticSeparabilityAssessment(
        lane="gwb",
        claim_id=result.claim_id,
        seed_id=result.seed_id,
        selection_mode=result.selection_mode,
        candidate_count=result.candidate_count,
        candidate_refs=candidate_refs,
        basis_kind=result.selection_basis,
        assessment_status=status,
        reason_codes=tuple(reason_codes),
    ).as_dict()
