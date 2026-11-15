"""Source-preserving NORA candidate-review adapter (not a NORA API parser).

This is an internal, candidate-only handoff. A future pinned NORA export parser
must supply the source and review mappings. It does not grant Wikidata access,
semantic truth, SLR S29 review persistence, or Agda/Lean proof certification.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256, canonical_value, require_text


SCHEMA_VERSION = "sl.nora_review_handoff.v0_1"
CHOICE_KIND = {
    "valid": "review_judgement",
    "invalid": "review_judgement",
    "ambiguous": "unresolved_judgement",
    "manual_search": "acquisition_request",
    "modeling_gap": "model_residual",
}
CONSUMER_RESULTS = frozenset({"sufficient_claim", "non_descent_claim", "unresolved"})


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return canonical_value(value)


def _rows(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be a list")
    return [_mapping(row, name) for row in value]


def _source_guard(source: Mapping[str, Any]) -> None:
    for key in ("candidate_ref", "source_field_ref", "source_revision_ref", "target_property_ref"):
        require_text(source.get(key), key)
    refs = _rows(source.get("attribution"), "attribution")
    if not refs:
        raise ValueError("attribution must retain at least one source record")
    for entry in refs:
        for key in ("actor_ref", "role", "source_ref"):
            require_text(entry.get(key), f"attribution.{key}")
    if source.get("classification") == "split_required":
        plan = _mapping(source.get("split_plan"), "split_plan")
        guids = plan.get("source_statement_guids")
        targets = plan.get("target_statement_bundles")
        if not isinstance(guids, list) or not guids or not all(isinstance(g, str) and g for g in guids):
            raise ValueError("split_required needs source statement GUIDs")
        if not isinstance(targets, list) or len(targets) < 2:
            raise ValueError("split_required needs two or more target bundles")
        for target in targets:
            _mapping(target, "target_statement_bundle")


def _review_guard(review: Mapping[str, Any]) -> str:
    for key in ("review_ref", "reviewer_ref", "standpoint_ref", "source_revision_ref"):
        require_text(review.get(key), f"review.{key}")
    choice = require_text(review.get("choice"), "review.choice")
    if choice not in CHOICE_KIND:
        raise ValueError(f"unknown NORA reviewer choice: {choice}")
    if choice in {"invalid", "ambiguous", "modeling_gap"}:
        refs = review.get("reason_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) and r for r in refs):
            raise ValueError(f"{choice} needs at least one reason or residual reference")
    return choice


def _checks_guard(checks: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in checks:
        consumer = require_text(row.get("consumer_ref"), "consumer_ref")
        require_text(row.get("standpoint_ref"), "consumer.standpoint_ref")
        require_text(row.get("source_revision_ref"), "consumer.source_revision_ref")
        if consumer in seen:
            raise ValueError(f"duplicate consumer: {consumer}")
        seen.add(consumer)
        result = require_text(row.get("result"), "consumer.result")
        if result not in CONSUMER_RESULTS:
            raise ValueError(f"unknown consumer result: {result}")
        if result == "non_descent_claim":
            require_text(row.get("witness_ref"), "consumer.witness_ref")
        if result == "sufficient_claim":
            require_text(row.get("witness_ref"), "consumer.witness_ref")


def build_nora_review_handoff(
    *, source_candidate: Mapping[str, Any], review: Mapping[str, Any],
    consumer_checks: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Preserve the exact supplied carriers. Never pay truth or edit authority."""
    source = _mapping(source_candidate, "source_candidate")
    decision = _mapping(review, "review")
    checks = _rows(consumer_checks, "consumer_checks")
    _source_guard(source)
    choice = _review_guard(decision)
    if decision["source_revision_ref"] != source["source_revision_ref"]:
        raise ValueError("review/source revision mismatch")
    _checks_guard(checks)
    for row in checks:
        if row["source_revision_ref"] != source["source_revision_ref"]:
            raise ValueError("consumer/source revision mismatch")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_candidate": source,
        "source_candidate_digest": canonical_sha256(source),
        "review": decision,
        "review_digest": canonical_sha256(decision),
        "choice_kind": CHOICE_KIND[choice],
        "consumer_checks": checks,
        "consumer_checks_digest": canonical_sha256(checks),
        "reported_consumer_results_not_kernel_proofs": True,
        "semantic_truth_paid": False,
        "global_mapping_validity_paid": False,
        "promotion_authority_paid": False,
        "external_edit_authority_paid": False,
        "slr_s29_persistence_performed": False,
        "nora_native_export_verified": False,
        "source_adjudication_performed": False,
    }
    payload["handoff_ref"] = "nora-review:" + canonical_sha256(payload)
    return payload


def replay_nora_review_handoff(handoff: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on altered source, review, consumer checks, or receipt digest."""
    record = _mapping(handoff, "handoff")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported NORA handoff version")
    original = build_nora_review_handoff(
        source_candidate=_mapping(record.get("source_candidate"), "source_candidate"),
        review=_mapping(record.get("review"), "review"),
        consumer_checks=_rows(record.get("consumer_checks"), "consumer_checks"),
    )
    if record != original:
        raise ValueError("NORA handoff replay mismatch")
    return original


def check_nora_revision(handoff: Mapping[str, Any], current_source_revision_ref: str) -> dict[str, Any]:
    """Return a review route. Do not claim to reopen SLR database records."""
    receipt = replay_nora_review_handoff(handoff)
    current = require_text(current_source_revision_ref, "current_source_revision_ref")
    pinned = receipt["source_candidate"]["source_revision_ref"]
    return {
        "handoff_ref": receipt["handoff_ref"],
        "pinned_source_revision_ref": pinned,
        "current_source_revision_ref": current,
        "review_recheck_required": current != pinned,
        "slr_reopening_performed": False,
    }


def nora_acquisition_route(handoff: Mapping[str, Any]) -> dict[str, Any]:
    """Plan a possible SLR/ITIR source job. Never dispatch a provider request."""
    receipt = replay_nora_review_handoff(handoff)
    decision = receipt["review"]
    return {
        "handoff_ref": receipt["handoff_ref"],
        "requested": decision["choice"] == "manual_search",
        "source_revision_ref": receipt["source_candidate"]["source_revision_ref"],
        "source_field_ref": receipt["source_candidate"]["source_field_ref"],
        "reason_refs": decision.get("reason_refs", []),
        "candidate_only": True,
        "provider_execution_performed": False,
    }


def plan_nora_zelph_scoped_review(
    handoff: Mapping[str, Any],
    *,
    subject_qid: str,
    name_lookup: Mapping[str, Any],
    query_closure: Mapping[str, Any],
) -> dict[str, Any]:
    """Candidate-only adapter for ITIR's byte-audited *scoped* route receipts.

    Keeps graph identity, source revision, and NORA standpoint as different
    axes.  Does not import an ITIR runtime or claim native NORA API support.
    An absent QID in the declared shards is always unresolved globally.
    """
    pinned = replay_nora_review_handoff(handoff)
    source = pinned["source_candidate"]
    if require_text(source.get("subject_qid"), "source.subject_qid") != subject_qid:
        raise ValueError("NORA source/route subject QID mismatch")
    route = _mapping(name_lookup, "name_lookup")
    closure = _mapping(query_closure, "query_closure")
    if route.get("version") != "itir.zelph.audited_name_lookup.v1":
        raise ValueError("ITIR byte-audited name lookup contract required")
    if closure.get("version") != "itir.zelph.query_family_closure_audit.v1":
        raise ValueError("ITIR query-family closure contract required")
    if route.get("qid") != subject_qid:
        raise ValueError("NORA source/route QID mismatch")
    graph_revision = require_text(route.get("graph_revision"), "name_lookup.graph_revision")
    if graph_revision != closure.get("graph_revision"):
        raise ValueError("ITIR name/closure revision mismatch")
    if route.get("complete_for_source_graph") is not False:
        raise ValueError("graph-source completeness cannot be inferred from name shards")
    if route.get("negative_query_authority") is not False:
        raise ValueError("scoped missing name may not create global negative authority")
    if closure.get("scoped_negative_answer_permitted") is not False:
        raise ValueError("unchecked closure may not create negative authority")
    if route.get("candidate_only") is not True or closure.get("candidate_only") is not True:
        raise ValueError("ITIR graph receipts must remain candidate-only")
    status = route.get("status")
    if status not in {"found-in-inspected-objects", "unresolved-in-original-graph"}:
        raise ValueError("unknown ITIR route status")
    if status == "found-in-inspected-objects" and not route.get("candidate_nodes"):
        raise ValueError("positive route must retain physical node witnesses")
    if status == "unresolved-in-original-graph" and route.get("candidate_nodes"):
        raise ValueError("unresolved route cannot silently retain positive witnesses")
    result = {
        "version": "sl.nora_zelph_scoped_review_plan.v1",
        "subject_qid": subject_qid,
        "source_revision_ref": source["source_revision_ref"],
        "graph_revision": graph_revision,
        "handoff_ref": pinned["handoff_ref"],
        "name_route_status": status,
        "physical_candidate_nodes": route.get("candidate_nodes", []),
        "candidate_collision": bool(route.get("collision", False)),
        "graph_family_coverage_status": closure.get("coverage_status"),
        "unresolved_dependencies": closure.get("missing_dependencies", {}),
        "review_choice": pinned["review"]["choice"],
        "review_standpoint": pinned["review"]["standpoint_ref"],
        "source_attribution": source["attribution"],
        "native_statement_evidence_required": True,
        "external_nora_export_verified": False,
        "slr_s29_persistence_performed": False,
        "source_support_paid": False,
        "global_absence_proved": False,
        "candidate_only": True,
        "external_edit_authority_paid": False,
    }
    result["receipt_ref"] = "nora-zelph:" + canonical_sha256(result)
    return result


def plan_nora_source_bound_persisted_review(
    handoff: Mapping[str, Any],
    *,
    original_cohort: Mapping[str, Any],
    s29_readback_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Strict read-only cross-owner join of actual source coordinates.

    Replays NORA's original choice/attribution first. ITIR's cohort remains
    a physical/native *candidate*, SLR's JSON readback is evidence of an
    operator-reported DB run but NOT cryptographic proof of a real DB query
    when processed by this I/O-free Python reference adapter.
    """
    from hashlib import sha256
    import json

    review = replay_nora_review_handoff(handoff)
    source = review["source_candidate"]
    cohort = _mapping(original_cohort, "original_cohort")
    s29 = _mapping(s29_readback_receipt, "s29_readback_receipt")
    if cohort.get("version") != "itir.zelph_wikibase_source_bound_candidate.v1":
        raise ValueError("ITIR same-run original cohort version required")
    if cohort.get("qid") != source.get("subject_qid"):
        raise ValueError("NORA subject QID and physically sourced QID mismatch")
    if cohort.get("property_id") != source.get("target_property_ref"):
        raise ValueError("NORA target property and actual native property mismatch")
    expected_revision = source.get("wikibase_native_revision_id")
    if (type(expected_revision) is not int or expected_revision <= 0
            or cohort.get("wikibase_native_entity_revision_id") != expected_revision):
        raise ValueError("NORA original native entity revision not independently pinned")
    if (source.get("classification") == "split_required"
            and cohort.get("statement_guid") not in
            source["split_plan"]["source_statement_guids"]):
        raise ValueError("ITIR source native GUID differs from NORA retained source split")
    for field in ("source_support_paid", "creates_world_truth", "edit_authority",
                  "p854_primary_documents_independently_verified",
                  "persisted_s29_review_verified",
                  "wikipedia_oldid_first_qualified_link_same_as_zelph_edge_proved"):
        if cohort.get(field) is not False:
            raise ValueError("source-bound cohort attempted authority/equivalence promotion")
    if (cohort.get("selected_root_bidirectional_source_adjacency_equal") is not True
            or cohort.get("declared_lr_query_family_complete") is not True):
        raise ValueError("incomplete original source-based graph query family")
    canonical = json.dumps(cohort, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    expected_digest = sha256(canonical).hexdigest()
    if s29.get("receipt_digest") != expected_digest:
        raise ValueError("SLR persisted candidate digest differs from source cohort")
    if (s29.get("db_readback_verified") is not True
            or s29.get("db_write_committed") is not True
            or s29.get("edit_authority") is not False
            or s29.get("source_support_paid") is not False):
        raise ValueError("SLR source-review readback receipt incomplete/unsafe")
    source_rows = s29.get("readback_sources")
    if not isinstance(source_rows, list):
        raise ValueError("actual DB readback source-coordinate rows required")
    qid, guid = cohort["qid"], cohort["statement_guid"]
    expected_rows = {
        ("zelph:acrion/zelph:" + qid,
         cohort["graph_dataset_revision"],
         cohort["original_bin_sha256_matched_supplied_pin"]),
        ("wikibase:" + qid + ":" + guid,
         str(expected_revision),
         cohort["wikibase_native_raw_entity_sha256"]),
    }
    if ({tuple(row) for row in source_rows if isinstance(row, list) and len(row) == 3}
            != expected_rows or len(source_rows) != 2):
        raise ValueError("SLR source DB rows mismatch physical/native original coordinates")
    result = {
        "version": "sl.nora_itir_s29_original_source_review.v1",
        "nora_handoff_ref": review["handoff_ref"],
        "subject_qid": qid, "statement_guid": guid,
        "native_entity_revision_id": expected_revision,
        "graph_dataset_revision": cohort["graph_dataset_revision"],
        "zelph_internal_node_id": cohort["zelph_internal_node_id"],
        "source_cohort_digest": expected_digest,
        "slr_readback_receipt_digest": s29["receipt_digest"],
        "slr_readback_coordinates_match": True,
        "readback_performed_independently_by_this_adapter": False,
        "review_choice": review["review"]["choice"],
        "review_standpoint_ref": review["review"]["standpoint_ref"],
        "source_attribution": source["attribution"],
        "reported_consumer_results_not_kernel_proofs": True,
        "source_support_paid": False, "semantic_truth_paid": False,
        "wikipedia_first_link_equivalence_paid": False,
        "nora_native_export_verified": False,
        "external_edit_authority_paid": False,
    }
    result["receipt_ref"] = "nora-s29:" + canonical_sha256(result)
    return result
