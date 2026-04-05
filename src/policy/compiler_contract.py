from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


COMPILER_CONTRACT_SCHEMA_VERSION = "sl.compiler_contract.v0_1"


@dataclass(frozen=True)
class EvidenceBundleContract:
    bundle_kind: str
    source_family: str
    source_count: int
    item_count: int
    item_label: str


@dataclass(frozen=True)
class PromotedOutcomeContract:
    outcome_family: str
    promoted_count: int
    review_count: int
    abstained_count: int
    outcome_labels: tuple[str, ...]


@dataclass(frozen=True)
class DerivedProductContract:
    product_kind: str
    role: str
    default_surface: bool


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _labels(values: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return tuple(seen)


def normalize_promoted_outcomes(
    value: Mapping[str, Any] | PromotedOutcomeContract | None,
) -> dict[str, Any]:
    if isinstance(value, PromotedOutcomeContract):
        return {
            **asdict(value),
            "outcome_labels": list(value.outcome_labels),
        }
    mapping = value if isinstance(value, Mapping) else {}
    return {
        "outcome_family": str(mapping.get("outcome_family") or "").strip(),
        "promoted_count": _int(mapping.get("promoted_count")),
        "review_count": _int(mapping.get("review_count")),
        "abstained_count": _int(mapping.get("abstained_count")),
        "outcome_labels": list(_labels(mapping.get("outcome_labels", []))),
    }


def build_compiler_contract_payload(
    *,
    lane: str,
    evidence_bundle: EvidenceBundleContract,
    promoted_outcomes: PromotedOutcomeContract,
    derived_products: Sequence[DerivedProductContract],
) -> dict[str, Any]:
    return {
        "schema_version": COMPILER_CONTRACT_SCHEMA_VERSION,
        "lane": str(lane),
        "evidence_bundle": asdict(evidence_bundle),
        "promoted_outcomes": normalize_promoted_outcomes(promoted_outcomes),
        "derived_products": [asdict(product) for product in derived_products],
    }


def build_au_public_handoff_contract(slice_payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = slice_payload.get("summary") if isinstance(slice_payload.get("summary"), Mapping) else {}
    selected_facts = slice_payload.get("selected_facts") if isinstance(slice_payload.get("selected_facts"), list) else []
    promoted_count = sum(
        1
        for row in selected_facts
        if str((row or {}).get("review_status") or "").strip() != "review_queue"
    )
    review_count = sum(
        1
        for row in selected_facts
        if str((row or {}).get("review_status") or "").strip() == "review_queue"
    )
    abstained_count = _int(summary.get("abstained_fact_count"))
    return build_compiler_contract_payload(
        lane="au",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="legal_hearing_bundle",
            source_family="au_fact_review_bundle",
            source_count=max(1, len(slice_payload.get("source_bundle_paths", []))),
            item_count=_int(summary.get("fact_count")) or len(selected_facts),
            item_label="fact",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="procedural_review_outcomes",
            promoted_count=promoted_count,
            review_count=review_count,
            abstained_count=abstained_count,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("captured", promoted_count),
                    ("review_queue", review_count),
                    ("abstained", abstained_count),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "operator_handoff", True),
            DerivedProductContract("report", "narrative_summary", True),
            DerivedProductContract("graph", "downstream_reasoning_projection", False),
        ),
    )


def build_au_fact_review_bundle_contract(
    *,
    fact_report: Mapping[str, Any],
    review_summary: Mapping[str, Any],
    source_documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    summary = fact_report.get("summary") if isinstance(fact_report.get("summary"), Mapping) else {}
    review_queue = review_summary.get("review_queue") if isinstance(review_summary.get("review_queue"), list) else []
    abstentions = fact_report.get("abstentions") if isinstance(fact_report.get("abstentions"), Mapping) else {}
    abstained_count = _int(abstentions.get("fact_abstentions"))
    total_fact_count = _int(summary.get("fact_count"))
    review_count = len(review_queue)
    promoted_count = max(0, total_fact_count - review_count - abstained_count)
    return build_compiler_contract_payload(
        lane="au",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="legal_hearing_bundle",
            source_family="au_fact_review_bundle",
            source_count=max(1, len(source_documents)),
            item_count=total_fact_count,
            item_label="fact",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="procedural_review_outcomes",
            promoted_count=promoted_count,
            review_count=review_count,
            abstained_count=abstained_count,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("captured", promoted_count),
                    ("review_queue", review_count),
                    ("abstained", abstained_count),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "fact_review_bundle", True),
            DerivedProductContract("report", "operator_review_summary", True),
            DerivedProductContract("graph", "legal_follow_graph", False),
            DerivedProductContract("graph", "downstream_reasoning_projection", False),
        ),
    )


def build_gwb_public_handoff_contract(slice_payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = slice_payload.get("summary") if isinstance(slice_payload.get("summary"), Mapping) else {}
    seed_rows = slice_payload.get("selected_seed_lanes") if isinstance(slice_payload.get("selected_seed_lanes"), list) else []
    unresolved_surfaces = slice_payload.get("unresolved_surfaces") if isinstance(slice_payload.get("unresolved_surfaces"), list) else []
    matched_seed_count = sum(
        1
        for row in seed_rows
        if str((row or {}).get("review_status") or "").strip() == "matched"
    )
    review_count = sum(
        1
        for row in seed_rows
        if str((row or {}).get("review_status") or "").strip() != "matched"
    ) + len(unresolved_surfaces)
    return build_compiler_contract_payload(
        lane="gwb",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="public_source_bundle",
            source_family="gwb_public_timeline",
            source_count=1,
            item_count=_int(slice_payload.get("timeline_event_count")),
            item_label="timeline_event",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="action_relation_review_outcomes",
            promoted_count=_int(summary.get("selected_promoted_relation_count")),
            review_count=review_count,
            abstained_count=0,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("promoted_relation", _int(summary.get("selected_promoted_relation_count"))),
                    ("matched_seed_lane", matched_seed_count),
                    ("review_lane", review_count),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "public_handoff", True),
            DerivedProductContract("report", "narrative_summary", True),
            DerivedProductContract("graph", "downstream_reasoning_projection", False),
        ),
    )


def build_gwb_public_review_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return build_compiler_contract_payload(
        lane="gwb",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="public_source_bundle",
            source_family="gwb_public_review",
            source_count=1,
            item_count=_int(summary.get("source_row_count")),
            item_label="source_row",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="action_relation_review_outcomes",
            promoted_count=_int(summary.get("covered_count")),
            review_count=_int(summary.get("missing_review_count")),
            abstained_count=0,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("covered", _int(summary.get("covered_count"))),
                    ("review_required", _int(summary.get("missing_review_count"))),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "public_review", True),
            DerivedProductContract("report", "normalized_review_summary", True),
            DerivedProductContract("graph", "legal_linkage_graph", False),
            DerivedProductContract("graph", "downstream_reasoning_projection", False),
        ),
    )


def build_gwb_broader_review_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    derived_products = [
        DerivedProductContract("packet", "broader_review", True),
        DerivedProductContract("report", "normalized_review_summary", True),
        DerivedProductContract("graph", "legal_linkage_graph", False),
        DerivedProductContract("graph", "downstream_reasoning_projection", False),
    ]
    if summary.get("broader_review_adjacent"):
        derived_products.append(
            DerivedProductContract("artifact", "parliamentary_reasoning", False)
        )
    return build_compiler_contract_payload(
        lane="gwb",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="public_source_bundle",
            source_family="gwb_broader_review",
            source_count=1,
            item_count=_int(summary.get("source_row_count")),
            item_label="source_row",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="action_relation_review_outcomes",
            promoted_count=_int(summary.get("covered_count")),
            review_count=_int(summary.get("missing_review_count")),
            abstained_count=0,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("covered", _int(summary.get("covered_count"))),
                    ("review_required", _int(summary.get("missing_review_count"))),
                )
                if count > 0
            ),
        ),
        derived_products=derived_products,
    )


def build_wikidata_migration_pack_contract(migration_pack: Mapping[str, Any]) -> dict[str, Any]:
    summary = migration_pack.get("summary") if isinstance(migration_pack.get("summary"), Mapping) else {}
    source_slice = migration_pack.get("source_slice") if isinstance(migration_pack.get("source_slice"), Mapping) else {}
    checked_safe_subset = summary.get("checked_safe_subset") if isinstance(summary.get("checked_safe_subset"), list) else []
    abstained = summary.get("abstained") if isinstance(summary.get("abstained"), list) else []
    return build_compiler_contract_payload(
        lane="wikidata_nat",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="revision_text_evidence_bundle",
            source_family="wikidata_migration_pack",
            source_count=len(source_slice.get("window_ids", [])),
            item_count=_int(summary.get("candidate_count")),
            item_label="candidate",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="migration_review_outcomes",
            promoted_count=len(checked_safe_subset),
            review_count=_int(summary.get("requires_review_count")),
            abstained_count=len(abstained),
            outcome_labels=_labels(
                label
                for label, count in (
                    ("checked_safe", len(checked_safe_subset)),
                    ("requires_review", _int(summary.get("requires_review_count"))),
                    ("abstained", len(abstained)),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "migration_review_pack", True),
            DerivedProductContract("action", "checked_safe_export_surface", False),
            DerivedProductContract("report", "bucket_summary", True),
        ),
    )


def build_affidavit_coverage_review_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    source_input = payload.get("source_input") if isinstance(payload.get("source_input"), Mapping) else {}
    affidavit_rows = payload.get("affidavit_rows") if isinstance(payload.get("affidavit_rows"), list) else []
    promotion_statuses = [
        str((row or {}).get("promotion_status") or "").strip()
        for row in affidavit_rows
        if isinstance(row, Mapping)
    ]
    promoted_true_count = sum(1 for status in promotion_statuses if status == "promoted_true")
    promoted_false_count = sum(1 for status in promotion_statuses if status == "promoted_false")
    conflict_count = sum(1 for status in promotion_statuses if status == "candidate_conflict")
    abstained_count = sum(1 for status in promotion_statuses if status == "abstained")

    return build_compiler_contract_payload(
        lane="affidavit",
        evidence_bundle=EvidenceBundleContract(
            bundle_kind="contested_affidavit_bundle",
            source_family=str(source_input.get("source_kind") or "affidavit_review"),
            source_count=1,
            item_count=_int(summary.get("affidavit_proposition_count")) or len(affidavit_rows),
            item_label="affidavit_proposition",
        ),
        promoted_outcomes=PromotedOutcomeContract(
            outcome_family="contested_affidavit_claim_outcomes",
            promoted_count=promoted_true_count + promoted_false_count,
            review_count=conflict_count,
            abstained_count=abstained_count,
            outcome_labels=_labels(
                label
                for label, count in (
                    ("promoted_true", promoted_true_count),
                    ("promoted_false", promoted_false_count),
                    ("candidate_conflict", conflict_count),
                    ("abstained", abstained_count),
                )
                if count > 0
            ),
        ),
        derived_products=(
            DerivedProductContract("packet", "affidavit_coverage_review", True),
            DerivedProductContract("report", "coverage_summary", True),
            DerivedProductContract("artifact", "related_review_clusters", False),
            DerivedProductContract("artifact", "provisional_anchor_bundles", False),
            DerivedProductContract("artifact", "normalized_metrics_v1", False),
        ),
    )


__all__ = [
    "COMPILER_CONTRACT_SCHEMA_VERSION",
    "DerivedProductContract",
    "EvidenceBundleContract",
    "PromotedOutcomeContract",
    "build_affidavit_coverage_review_contract",
    "build_au_public_handoff_contract",
    "build_au_fact_review_bundle_contract",
    "build_compiler_contract_payload",
    "build_gwb_broader_review_contract",
    "build_gwb_public_handoff_contract",
    "build_gwb_public_review_contract",
    "build_wikidata_migration_pack_contract",
    "normalize_promoted_outcomes",
]
