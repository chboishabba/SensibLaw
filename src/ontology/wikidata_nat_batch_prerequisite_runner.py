from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


BATCH_RESULT_SCHEMA_VERSION = "sl.nat_batch_prerequisite_result.v0_1"
BATCH_ROW_SCHEMA_VERSION = "sl.nat_batch_prerequisite_row.v0_1"
BATCH_GROUP_SCHEMA_VERSION = "sl.nat_batch_prerequisite_group.v0_1"

PREREQUISITE_ORDER = (
    "same_carrier",
    "source_support",
    "qualifier_transport",
    "rank_treatment",
    "provenance_support",
    "semantic_correspondence",
)

PRODUCER_BY_PREREQUISITE = {
    "same_carrier": "verify_same_carrier",
    "source_support": "acquire_source_support",
    "qualifier_transport": "prove_qualifier_transport",
    "rank_treatment": "review_rank_treatment",
    "provenance_support": "acquire_provenance_support",
    "semantic_correspondence": "prove_semantic_correspondence",
}

MECHANISM_BY_PRODUCER = {
    "verify_same_carrier": "look",
    "acquire_source_support": "look",
    "prove_qualifier_transport": "think",
    "review_rank_treatment": "review",
    "acquire_provenance_support": "look",
    "prove_semantic_correspondence": "think",
}

SELECTOR_CLASS_BY_MECHANISM = {
    "look": "zelph_hf_selector",
    "think": "theorem_search",
    "review": "human_review",
}

_SAFE_CLASSIFICATIONS = {"safe_equivalent", "safe_with_reference_transfer"}


@dataclass(frozen=True)
class PrerequisiteStatus:
    same_carrier: bool
    source_support: bool
    qualifier_transport: bool
    rank_treatment: bool
    provenance_support: bool
    semantic_correspondence: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "same_carrier": self.same_carrier,
            "source_support": self.source_support,
            "qualifier_transport": self.qualifier_transport,
            "rank_treatment": self.rank_treatment,
            "provenance_support": self.provenance_support,
            "semantic_correspondence": self.semantic_correspondence,
        }

    def first_missing(self) -> str | None:
        status = self.as_dict()
        for prerequisite in PREREQUISITE_ORDER:
            if not status[prerequisite]:
                return prerequisite
        return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _claim_bundle(candidate: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = candidate.get(key)
    return value if isinstance(value, Mapping) else {}


def _property_keys(mapping: Any) -> list[str]:
    if not isinstance(mapping, Mapping):
        return []
    return sorted({_text(key) for key in mapping if _text(key)})


def _reference_property_keys(references: Any) -> list[str]:
    if not isinstance(references, Sequence) or isinstance(
        references, (str, bytes, bytearray)
    ):
        return []
    result: set[str] = set()
    for reference in references:
        if not isinstance(reference, Mapping):
            continue
        result.update(_property_keys(reference))
    return sorted(result)


def _receipt_paid(candidate: Mapping[str, Any], prerequisite: str) -> bool:
    receipts = candidate.get("prerequisite_receipts")
    if not isinstance(receipts, Mapping):
        return False
    receipt = receipts.get(prerequisite)
    if isinstance(receipt, Mapping):
        return bool(receipt.get("paid", False))
    return receipt is True


def _same_carrier(candidate: Mapping[str, Any]) -> bool:
    before = _claim_bundle(candidate, "claim_bundle_before")
    after = _claim_bundle(candidate, "claim_bundle_after")
    if not before or not after:
        return False
    before_subject = _text(before.get("subject") or candidate.get("entity_qid"))
    after_subject = _text(after.get("subject") or candidate.get("entity_qid"))
    before_statement = _text(before.get("statement_id"))
    after_statement = _text(after.get("statement_id"))
    return bool(
        before_subject
        and before_subject == after_subject
        and before_statement
        and before_statement == after_statement
    )


def derive_prerequisite_status(candidate: Mapping[str, Any]) -> PrerequisiteStatus:
    """Derive only what the supplied artifact actually certifies.

    Same-carrier identity can be checked structurally from the before/after bundle.
    All semantic/evidential prerequisite payments require explicit receipt fields;
    the runner does not infer payment from classification labels, confidence, or the
    mere presence of P854/P248 references.
    """

    return PrerequisiteStatus(
        same_carrier=_same_carrier(candidate),
        source_support=_receipt_paid(candidate, "source_support"),
        qualifier_transport=_receipt_paid(candidate, "qualifier_transport"),
        rank_treatment=_receipt_paid(candidate, "rank_treatment"),
        provenance_support=_receipt_paid(candidate, "provenance_support"),
        semantic_correspondence=_receipt_paid(candidate, "semantic_correspondence"),
    )


def routing_family(candidate: Mapping[str, Any]) -> str:
    classification = _text(candidate.get("classification"))
    family_bucket = _text(candidate.get("family_bucket"))
    split_plan = candidate.get("split_plan")
    before = _claim_bundle(candidate, "claim_bundle_before")
    qualifiers = before.get("qualifiers") if isinstance(before, Mapping) else {}
    qualifier_keys = set(_property_keys(qualifiers))

    if classification in _SAFE_CLASSIFICATIONS:
        return "full_auto"
    if classification == "split_required" or isinstance(split_plan, Mapping):
        return "split_auto"
    if family_bucket == "C" or (qualifier_keys and "P459" not in qualifier_keys):
        return "repair_plus_migrate_review"
    if family_bucket == "E":
        return "manual_reconstruction"
    return "review_only_typed_hold"


def _first_missing_payload(status: PrerequisiteStatus) -> tuple[str, str, str, str]:
    prerequisite = status.first_missing()
    if prerequisite is None:
        return ("closed", "no_prerequisite_producer", "none", "no_selector")
    producer = PRODUCER_BY_PREREQUISITE[prerequisite]
    mechanism = MECHANISM_BY_PRODUCER[producer]
    selector_class = SELECTOR_CLASS_BY_MECHANISM[mechanism]
    return prerequisite, producer, mechanism, selector_class


def build_row_descriptor(
    candidate: Mapping[str, Any],
    *,
    source_cohort: str,
    source_revision_reference: str,
) -> dict[str, Any]:
    before = _claim_bundle(candidate, "claim_bundle_before")
    after = _claim_bundle(candidate, "claim_bundle_after")
    status = derive_prerequisite_status(candidate)
    first_missing, producer, mechanism, selector_class = _first_missing_payload(status)
    qid = _text(candidate.get("entity_qid") or before.get("subject"))
    candidate_id = _text(candidate.get("candidate_id"))
    statement_reference = _text(before.get("statement_id") or candidate_id)
    source_property = _text(before.get("property") or "P5991")
    target_property = _text(after.get("property") or "P14143")
    qualifiers = _property_keys(before.get("qualifiers"))
    references = _reference_property_keys(before.get("references"))

    descriptor_without_ref = {
        "schema_version": BATCH_ROW_SCHEMA_VERSION,
        "row_id": candidate_id or statement_reference,
        "qid": qid,
        "statement_reference": statement_reference,
        "source_cohort": source_cohort,
        "routing_family": routing_family(candidate),
        "source_property": source_property,
        "target_property": target_property,
        "qualifier_properties": qualifiers,
        "reference_properties": references,
        "source_revision_reference": source_revision_reference,
        "input_digest": canonical_sha256(candidate),
        "prerequisite_status": status.as_dict(),
        "first_missing_prerequisite": first_missing,
        "required_producer": producer,
        "mechanism": mechanism,
        "selector_class": selector_class,
        "source_classification": _text(candidate.get("classification")),
        "source_action": _text(candidate.get("action")),
    }
    descriptor = dict(descriptor_without_ref)
    descriptor["row_ref"] = "nat-prerequisite-row:" + canonical_sha256(
        descriptor_without_ref
    )
    return descriptor


def work_signature(row: Mapping[str, Any]) -> dict[str, Any]:
    signature_without_ref = {
        "schema_version": BATCH_GROUP_SCHEMA_VERSION,
        "source_cohort": _text(row.get("source_cohort")),
        "routing_family": _text(row.get("routing_family")),
        "first_missing_prerequisite": _text(row.get("first_missing_prerequisite")),
        "required_producer": _text(row.get("required_producer")),
        "mechanism": _text(row.get("mechanism")),
        "selector_class": _text(row.get("selector_class")),
        "source_property": _text(row.get("source_property")),
        "target_property": _text(row.get("target_property")),
        "qualifier_properties": _text_list(row.get("qualifier_properties")),
        "reference_properties": _text_list(row.get("reference_properties")),
    }
    signature = dict(signature_without_ref)
    signature["signature_ref"] = "nat-work-signature:" + canonical_sha256(
        signature_without_ref
    )
    return signature


def _manifest_cohort(
    manifest: Mapping[str, Any], cohort_id: str
) -> Mapping[str, Any] | None:
    cohorts = manifest.get("cohorts")
    if not isinstance(cohorts, Sequence) or isinstance(cohorts, (str, bytes, bytearray)):
        return None
    for cohort in cohorts:
        if isinstance(cohort, Mapping) and _text(cohort.get("cohort_id")) == cohort_id:
            return cohort
    return None


def _manifest_population(manifest: Mapping[str, Any], cohort_id: str) -> int | None:
    cohort = _manifest_cohort(manifest, cohort_id)
    if cohort is None or cohort.get("population") is None:
        return None
    try:
        return int(cohort.get("population"))
    except (TypeError, ValueError):
        return None


def _manifest_lane_id(manifest: Mapping[str, Any]) -> str:
    return _text(manifest.get("lane_id")) or "wikidata_nat_wdu_p5991_p14143"


def build_batch_dry_run(
    *,
    cohort_manifest: Mapping[str, Any],
    migration_packs: Sequence[Mapping[str, Any]],
    cohort_id: str = "business_family_reconciled",
    source_revision_reference: str = "",
) -> dict[str, Any]:
    """Build a no-I/O/no-edit content-addressed prerequisite classification artifact."""

    candidates: list[Mapping[str, Any]] = []
    input_pack_digests: list[str] = []
    for pack in migration_packs:
        input_pack_digests.append(canonical_sha256(pack))
        rows = pack.get("candidates")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            continue
        candidates.extend(row for row in rows if isinstance(row, Mapping))

    rows = [
        build_row_descriptor(
            candidate,
            source_cohort=cohort_id,
            source_revision_reference=source_revision_reference,
        )
        for candidate in candidates
    ]
    rows.sort(key=lambda row: (_text(row.get("qid")), _text(row.get("row_id"))))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    signatures_by_ref: dict[str, dict[str, Any]] = {}
    for row in rows:
        signature = work_signature(row)
        signature_ref = _text(signature["signature_ref"])
        signatures_by_ref[signature_ref] = signature
        grouped[signature_ref].append(row)

    groups: list[dict[str, Any]] = []
    for signature_ref in sorted(grouped):
        members = grouped[signature_ref]
        signature = signatures_by_ref[signature_ref]
        group_without_ref = {
            "signature": signature,
            "member_count": len(members),
            "member_row_refs": [_text(row.get("row_ref")) for row in members],
            "dispatch_status": "not_dispatched_dry_run",
        }
        group = dict(group_without_ref)
        group["group_ref"] = "nat-work-group:" + canonical_sha256(group_without_ref)
        groups.append(group)

    prerequisite_counts = Counter(
        _text(row.get("first_missing_prerequisite")) for row in rows
    )
    routing_counts = Counter(_text(row.get("routing_family")) for row in rows)
    selector_counts = Counter(_text(row.get("selector_class")) for row in rows)

    population = _manifest_population(cohort_manifest, cohort_id)
    payload_without_ref = {
        "schema_version": BATCH_RESULT_SCHEMA_VERSION,
        "mode": "dry_classification_only",
        "lane_id": _manifest_lane_id(cohort_manifest),
        "source_cohort": cohort_id,
        "source_population": population,
        "materialized_row_count": len(rows),
        "population_fully_materialized": population is not None and len(rows) == population,
        "source_revision_reference": source_revision_reference,
        "cohort_manifest_digest": canonical_sha256(cohort_manifest),
        "migration_pack_digests": sorted(input_pack_digests),
        "row_count": len(rows),
        "work_group_count": len(groups),
        "counts_by_first_missing_prerequisite": dict(sorted(prerequisite_counts.items())),
        "counts_by_routing_family": dict(sorted(routing_counts.items())),
        "counts_by_selector_class": dict(sorted(selector_counts.items())),
        "rows": rows,
        "work_groups": groups,
        "network_performed": False,
        "edits_performed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "formal_contract_reference": (
            "dashi_agda PR #814 DASHI.Wikimedia."
            "SensibLawNatBatchPrerequisiteRunnerContractExact"
        ),
    }
    payload = dict(payload_without_ref)
    payload["batch_ref"] = "nat-batch-prerequisite:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def iter_signature_histogram(batch: Mapping[str, Any]) -> Iterable[tuple[str, int]]:
    groups = batch.get("work_groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes, bytearray)):
        return ()
    values: list[tuple[str, int]] = []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        signature = group.get("signature")
        if not isinstance(signature, Mapping):
            continue
        ref = _text(signature.get("signature_ref"))
        try:
            count = int(group.get("member_count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        values.append((ref, count))
    return tuple(values)


__all__ = [
    "BATCH_GROUP_SCHEMA_VERSION",
    "BATCH_RESULT_SCHEMA_VERSION",
    "BATCH_ROW_SCHEMA_VERSION",
    "PrerequisiteStatus",
    "build_batch_dry_run",
    "build_row_descriptor",
    "derive_prerequisite_status",
    "iter_signature_histogram",
    "routing_family",
    "work_signature",
]
