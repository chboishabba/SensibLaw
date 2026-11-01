from __future__ import annotations

from typing import Any, Mapping, Sequence


WIKIDATA_SIGNAL_REVIEW_BUNDLE_SCHEMA_VERSION = "sl.wikidata_signal_review_bundle.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nonempty_strings(values: Sequence[Any] | None) -> list[str]:
    seen: list[str] = []
    for value in values or []:
        text = _text(value)
        if text and text not in seen:
            seen.append(text)
    return seen


def _entity_row(
    *, qid: Any, role: str, label: Any = "", status: str = "candidate"
) -> dict[str, Any]:
    return {
        "qid": _text(qid),
        "role": _text(role),
        "label": _text(label),
        "status": _text(status) or "candidate",
    }


def _property_row(*, pid: Any, role: str, status: str = "candidate") -> dict[str, Any]:
    return {
        "pid": _text(pid),
        "role": _text(role),
        "status": _text(status) or "candidate",
    }


def _residual_row(*, code: str, status: str, detail: Any = "") -> dict[str, Any]:
    return {
        "code": _text(code),
        "status": _text(status) or "open",
        "detail": _text(detail),
    }


def _receipt_row(*, kind: str, value: Any, status: str = "pinned") -> dict[str, Any]:
    return {
        "kind": _text(kind),
        "value": _text(value),
        "status": _text(status) or "pinned",
    }


def _bundle(
    *,
    lane_id: str,
    lane_family: str,
    surface_signal: str,
    signal_kind: str,
    authority_surface: str,
    soft_type_strength: str,
    domain_projection: str,
    promotion_status: str,
    candidate_entities: Sequence[Mapping[str, Any]],
    candidate_properties: Sequence[Mapping[str, Any]],
    residuals: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    source_revision_refs: Sequence[str],
    dependency_cone: Mapping[str, Any],
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    return {
        "schema_version": WIKIDATA_SIGNAL_REVIEW_BUNDLE_SCHEMA_VERSION,
        "lane_id": _text(lane_id),
        "lane_family": _text(lane_family),
        "surface_signal": _text(surface_signal),
        "signal_kind": _text(signal_kind),
        "authority_surface": _text(authority_surface),
        "soft_type_strength": _text(soft_type_strength),
        "domain_projection": _text(domain_projection),
        "promotion_status": _text(promotion_status),
        "candidate_entities": [dict(row) for row in candidate_entities],
        "candidate_properties": [dict(row) for row in candidate_properties],
        "residuals": [dict(row) for row in residuals],
        "receipts": [dict(row) for row in receipts],
        "source_revision_refs": _nonempty_strings(source_revision_refs),
        "dependency_cone": dict(dependency_cone),
        "authority_posture": _text(authority_posture),
        "evidence_mode": _text(evidence_mode),
        "execution_surface": _text(execution_surface),
        "summary": {
            "candidate_entity_count": len(candidate_entities),
            "candidate_property_count": len(candidate_properties),
            "residual_count": len(residuals),
            "receipt_count": len(receipts),
        },
    }


def build_climate_review_bundle(
    *,
    report: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    packet_context = (
        inputs.get("packet_context")
        if isinstance(inputs.get("packet_context"), Mapping)
        else {}
    )
    entity_qid = _text(inputs.get("entity_qid"))
    source_property = _text(inputs.get("source_property"))
    target_property = _text(inputs.get("target_property"))
    dispositions = (
        report.get("review_disposition", {}).get("candidate_dispositions", [])
        if isinstance(report.get("review_disposition"), Mapping)
        else []
    )
    held_count = sum(
        1 for row in dispositions if _text((row or {}).get("final_state")) == "held"
    )
    promotion_status = (
        "blocked"
        if held_count == len(dispositions) and dispositions
        else "candidate_only"
    )
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal=f"{source_property} -> {target_property} climate migration review",
        signal_kind="conditional",
        authority_surface="mixed",
        soft_type_strength="substantial",
        domain_projection="bounded climate-family migration packet",
        promotion_status=promotion_status,
        candidate_entities=[
            _entity_row(qid=entity_qid, role="review_entity", status="bounded")
        ],
        candidate_properties=[
            _property_row(
                pid=source_property, role="source_property", status="bounded"
            ),
            _property_row(
                pid=target_property, role="target_property", status="bounded"
            ),
        ],
        residuals=[
            _residual_row(
                code="split_pressure",
                status="open" if held_count else "closed",
                detail=f"held_candidate_count={held_count}",
            )
        ],
        receipts=[
            _receipt_row(kind="packet_id", value=packet_context.get("packet_id")),
            _receipt_row(
                kind="split_plan_id", value=packet_context.get("split_plan_id")
            ),
        ],
        source_revision_refs=[
            packet_context.get("packet_id"),
            packet_context.get("split_plan_id"),
        ],
        dependency_cone={
            "focus_qids": [entity_qid] if entity_qid else [],
            "focus_pids": [pid for pid in (source_property, target_property) if pid],
            "candidate_ids": _nonempty_strings(inputs.get("candidate_ids")),
        },
        authority_posture=authority_posture,
        evidence_mode=evidence_mode,
        execution_surface=execution_surface,
    )


def build_change_review_bundle(
    *,
    report: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    grounding = (
        report.get("wikidata_grounding")
        if isinstance(report.get("wikidata_grounding"), Mapping)
        else {}
    )
    components = (
        grounding.get("components")
        if isinstance(grounding.get("components"), Mapping)
        else {}
    )
    subject_candidates = [
        _entity_row(
            qid=row.get("qid"),
            role="subject_candidate",
            status="bounded",
        )
        for row in components.get("subject_qid_candidates", [])
        if isinstance(row, Mapping) and _text(row.get("qid"))
    ]
    object_candidates = [
        _entity_row(
            qid=row.get("qid"),
            role="object_candidate",
            status=_text(row.get("meet_status")) or "candidate",
        )
        for row in components.get("object_qid_candidates", [])
        if isinstance(row, Mapping) and _text(row.get("qid"))
    ]
    pid_candidates = [
        _property_row(
            pid=row.get("pid"),
            role="property_candidate",
            status="bounded",
        )
        for row in components.get("pid_candidates", [])
        if isinstance(row, Mapping) and _text(row.get("pid"))
    ]
    residuals = [
        _residual_row(
            code=_text(row.get("grounding_residual"))
            or _text(row.get("reason"))
            or "grounding_residual",
            status="open",
            detail=row.get("reason"),
        )
        for row in components.get("object_qid_candidates", [])
        if isinstance(row, Mapping)
        and (_text(row.get("grounding_residual")) or _text(row.get("reason")))
    ]
    if not residuals:
        residuals.append(
            _residual_row(
                code="review_only_candidate_comparison",
                status="open",
                detail="bounded in-memory candidate comparison",
            )
        )
    candidate_reports = (
        report.get("candidate_reports")
        if isinstance(report.get("candidate_reports"), list)
        else []
    )
    checked_safe = sum(
        1
        for row in candidate_reports
        if isinstance(row, Mapping)
        and _text(row.get("disposition")) == "checked_safe_reviewable"
    )
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal=f"bounded ontology repair review for {_text(report.get('focus_item'))}",
        signal_kind="structural",
        authority_surface="mixed",
        soft_type_strength="weak",
        domain_projection="bounded in-memory ontology repair comparison",
        promotion_status="candidate_only" if checked_safe else "blocked",
        candidate_entities=subject_candidates + object_candidates,
        candidate_properties=pid_candidates,
        residuals=residuals,
        receipts=[
            _receipt_row(kind="focus_item", value=report.get("focus_item")),
            _receipt_row(
                kind="packet_schema_version", value=report.get("packet_schema_version")
            ),
        ],
        source_revision_refs=[
            report.get("focus_item"),
            report.get("packet_schema_version"),
        ],
        dependency_cone={
            "focus_qids": _nonempty_strings([report.get("focus_item")]),
            "focus_pids": [
                row["pid"] for row in pid_candidates if _text(row.get("pid"))
            ],
            "candidate_report_ids": _nonempty_strings(
                (
                    row.get("candidate_id")
                    for row in candidate_reports
                    if isinstance(row, Mapping)
                )
            ),
        },
        authority_posture=authority_posture,
        evidence_mode=evidence_mode,
        execution_surface=execution_surface,
    )


def build_disjointness_bundle(
    *,
    report: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    pairs = (
        report.get("disjoint_pairs")
        if isinstance(report.get("disjoint_pairs"), list)
        else []
    )
    pair = pairs[0] if pairs and isinstance(pairs[0], Mapping) else {}
    culprit_classes = (
        report.get("culprit_classes")
        if isinstance(report.get("culprit_classes"), list)
        else []
    )
    culprit_items = (
        report.get("culprit_items")
        if isinstance(report.get("culprit_items"), list)
        else []
    )
    candidate_entities = []
    for role, qid_key, label_key in (
        ("holder_class", "holder_qid", "holder_label"),
        ("left_class", "left_qid", "left_label"),
        ("right_class", "right_qid", "right_label"),
    ):
        if _text(pair.get(qid_key)):
            candidate_entities.append(
                _entity_row(
                    qid=pair.get(qid_key),
                    role=role,
                    label=pair.get(label_key),
                    status="bounded",
                )
            )
    for row in culprit_classes:
        if isinstance(row, Mapping) and _text(row.get("qid")):
            candidate_entities.append(
                _entity_row(
                    qid=row.get("qid"),
                    role="culprit_class",
                    label=row.get("label"),
                    status="contradiction",
                )
            )
    for row in culprit_items:
        if isinstance(row, Mapping) and _text(row.get("qid")):
            candidate_entities.append(
                _entity_row(
                    qid=row.get("qid"),
                    role="culprit_item",
                    label=row.get("label"),
                    status="contradiction",
                )
            )
    candidate_properties = [
        _property_row(
            pid=pair.get("property_pid"), role="disjointness_property", status="bounded"
        ),
        _property_row(
            pid=pair.get("qualifier_pid"), role="qualifier_property", status="bounded"
        ),
        _property_row(pid="P279", role="subclass_context", status="bounded"),
        _property_row(pid="P31", role="instance_context", status="bounded"),
    ]
    residuals = [
        _residual_row(
            code="subclass_contradiction",
            status="open"
            if int(report.get("subclass_violation_count") or 0)
            else "closed",
            detail=f"count={int(report.get('subclass_violation_count') or 0)}",
        ),
        _residual_row(
            code="instance_contradiction",
            status="open"
            if int(report.get("instance_violation_count") or 0)
            else "closed",
            detail=f"count={int(report.get('instance_violation_count') or 0)}",
        ),
    ]
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal="P2738/P11260 disjointness contradiction scan",
        signal_kind="structural",
        authority_surface="wikidata",
        soft_type_strength="receipt_backed",
        domain_projection="bounded disjointness contradiction diagnostic",
        promotion_status="candidate_only",
        candidate_entities=candidate_entities,
        candidate_properties=candidate_properties,
        residuals=residuals,
        receipts=[
            _receipt_row(kind="source_window_id", value=report.get("source_window_id")),
            _receipt_row(kind="pair_id", value=pair.get("pair_id")),
        ],
        source_revision_refs=[
            report.get("source_window_id"),
            pair.get("pair_id"),
        ],
        dependency_cone={
            "focus_qids": _nonempty_strings(
                [
                    pair.get("holder_qid"),
                    pair.get("left_qid"),
                    pair.get("right_qid"),
                    *(
                        row.get("qid")
                        for row in culprit_classes + culprit_items
                        if isinstance(row, Mapping)
                    ),
                ]
            ),
            "focus_pids": _nonempty_strings(
                [pair.get("property_pid"), pair.get("qualifier_pid"), "P279", "P31"]
            ),
            "pair_ids": _nonempty_strings([pair.get("pair_id")]),
        },
        authority_posture=authority_posture,
        evidence_mode=evidence_mode,
        execution_surface=execution_surface,
    )


def build_hotspot_eval_bundle(
    *,
    report: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    cluster_results = (
        report.get("cluster_results")
        if isinstance(report.get("cluster_results"), list)
        else []
    )
    selected_pack_ids = _nonempty_strings(report.get("selected_pack_ids"))
    candidate_entities = [
        _entity_row(
            qid=row.get("cluster_id"),
            role="cluster_candidate",
            label=row.get("cluster_family"),
            status=row.get("classification") or "candidate",
        )
        for row in cluster_results
        if isinstance(row, Mapping) and _text(row.get("cluster_id"))
    ]
    candidate_properties = [
        _property_row(
            pid=row.get("supporting_hotspot_family"),
            role="hotspot_family",
            status="bounded",
        )
        for row in cluster_results
        if isinstance(row, Mapping) and _text(row.get("supporting_hotspot_family"))
    ]
    inconsistent = int(
        report.get("summary", {}).get("cluster_counts", {}).get("inconsistent") or 0
    )
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal="bounded structural hotspot cluster evaluation",
        signal_kind="structural",
        authority_surface="wikidata",
        soft_type_strength="weak",
        domain_projection="reviewer geometry over structural hotspot packs",
        promotion_status="candidate_only",
        candidate_entities=candidate_entities,
        candidate_properties=candidate_properties,
        residuals=[
            _residual_row(
                code="inconsistent_cluster_answers",
                status="open" if inconsistent else "closed",
                detail=f"count={inconsistent}",
            )
        ],
        receipts=[
            _receipt_row(kind="manifest_version", value=report.get("manifest_version")),
            *[
                _receipt_row(kind="pack_id", value=pack_id)
                for pack_id in selected_pack_ids
            ],
        ],
        source_revision_refs=[report.get("manifest_version"), *selected_pack_ids],
        dependency_cone={
            "focus_qids": [],
            "focus_pids": _nonempty_strings(
                row.get("supporting_hotspot_family")
                for row in cluster_results
                if isinstance(row, Mapping)
            ),
            "cluster_ids": _nonempty_strings(
                row.get("cluster_id")
                for row in cluster_results
                if isinstance(row, Mapping)
            ),
        },
        authority_posture=authority_posture,
        evidence_mode=evidence_mode,
        execution_surface=execution_surface,
    )


def build_live_follow_preflight_bundle(
    *,
    report: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    authority_posture: str,
    evidence_mode: str,
    execution_surface: str,
) -> dict[str, Any]:
    candidates = (
        report.get("candidates") if isinstance(report.get("candidates"), list) else []
    )
    candidate_entities = [
        _entity_row(
            qid=row.get("qid"),
            role="follow_candidate",
            status=row.get("coverage_status") or "candidate",
        )
        for row in candidates
        if isinstance(row, Mapping) and _text(row.get("qid"))
    ]
    residuals = [
        _residual_row(
            code="coverage_hold",
            status="open"
            if _text(row.get("coverage_status")) == "hold"
            else "candidate",
            detail=row.get("stop_condition"),
        )
        for row in candidates
        if isinstance(row, Mapping)
    ]
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal="bounded live-follow policy-risk population preview",
        signal_kind="conditional",
        authority_surface="mixed",
        soft_type_strength="substantial",
        domain_projection="bounded live follow routing and authority preview",
        promotion_status="candidate_only",
        candidate_entities=candidate_entities,
        candidate_properties=[],
        residuals=residuals,
        receipts=[
            _receipt_row(kind="campaign_id", value=report.get("campaign_id")),
            _receipt_row(
                kind="plan_schema_version", value=report.get("plan_schema_version")
            ),
        ],
        source_revision_refs=[
            report.get("campaign_id"),
            report.get("plan_schema_version"),
        ],
        dependency_cone={
            "focus_qids": _nonempty_strings(
                row.get("qid") for row in candidates if isinstance(row, Mapping)
            ),
            "focus_pids": [],
            "plan_ids": _nonempty_strings(
                row.get("plan_id") for row in candidates if isinstance(row, Mapping)
            ),
        },
        authority_posture=authority_posture,
        evidence_mode=evidence_mode,
        execution_surface=execution_surface,
    )


__all__ = [
    "WIKIDATA_SIGNAL_REVIEW_BUNDLE_SCHEMA_VERSION",
    "build_change_review_bundle",
    "build_climate_review_bundle",
    "build_disjointness_bundle",
    "build_hotspot_eval_bundle",
    "build_live_follow_preflight_bundle",
]


# The existing signal bundle is the sole Wikidata lane review carrier. Proposal
# discussion history is an OPTIONAL source-side projection attached after the
# lane has already computed its candidate properties, structural diagnostics,
# pressure and dispositions. It does not replace any of those computations.
# Roszkowski (2024), DOI 10.1108/JD-01-2024-0008, motivates the distinction
# between proposal, knowledge work and closure; the adapter is SL-authored.
import re as _re

_PROPERTY_ID = _re.compile(r"P[1-9][0-9]*\Z")
_DELIBERATION_VERSION = "itir.governance.deliberation_assessment.v1"
_PROPOSAL_PROJECTION_VERSION = "sl.wikidata_proposal_review_projection.v0_1"


def attach_deliberation_context(
    bundle: Mapping[str, Any],
    assessment: Mapping[str, Any],
    *,
    consumer_ref: str,
    consumer_scope_ref: str,
    source_alignment_ref: str,
) -> dict[str, Any]:
    """Attach candidate proposal context *to a concrete existing review bundle*.

    A claimed equality of property IDs is navigational evidence only. The
    original lane's source/constraint review, Wikidata edit authority and
    community-governance assessment remain independent. This function is a
    pure overlay; it never edits a live Wiki or admits a cohort member.
    """
    if not isinstance(bundle, Mapping) or bundle.get("schema_version") != WIKIDATA_SIGNAL_REVIEW_BUNDLE_SCHEMA_VERSION:
        raise ValueError("expected a normalized existing Wikidata signal bundle")
    if not isinstance(assessment, Mapping) or assessment.get("version") != _DELIBERATION_VERSION:
        raise ValueError("expected source-native ITIR deliberation assessment v1")
    for field, value in (
        ("consumer_ref", consumer_ref),
        ("consumer_scope_ref", consumer_scope_ref),
        ("source_alignment_ref", source_alignment_ref),
        ("proposal_ref", assessment.get("proposal_ref")),
        ("proposal_source_revision_ref", assessment.get("source_revision_ref")),
        ("historical_policy_revision_ref", assessment.get("policy_revision_ref")),
        ("deliberation_packet_ref", assessment.get("packet_ref")),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > 512 or any(ord(c) < 32 for c in value):
            raise ValueError(f"invalid {field}")
    authority = assessment.get("authority")
    if not isinstance(authority, Mapping) or authority.get("candidate_only") is not True:
        raise ValueError("deliberation assessment must stay candidate-only")
    for forbidden in ("semantic_truth_promoted", "community_consensus_verified",
                      "actor_authority_verified", "wikidata_edit_authorised",
                      "ao_dispatch_allowed", "slr_s29_review_bypassed"):
        if authority.get(forbidden) is not False:
            raise ValueError(f"deliberation must not assert {forbidden}")
    if bundle.get("authority_posture") not in ("review_only", "diagnostic_only"):
        raise ValueError("candidate-only original report authority posture required")
    if bundle.get("promotion_status") not in ("blocked", "candidate_only"):
        raise ValueError("cannot attach governance context to a promoted bundle")
    candidates = bundle.get("candidate_properties")
    cone = bundle.get("dependency_cone")
    if not isinstance(candidates, list) or not isinstance(cone, Mapping):
        raise ValueError("invalid signal bundle candidate geometry")
    present = sorted({
        row["pid"] for row in candidates
        if isinstance(row, Mapping) and isinstance(row.get("pid"), str)
        and _PROPERTY_ID.fullmatch(row["pid"])
    })
    focus = cone.get("focus_pids")
    if not isinstance(focus, list):
        raise ValueError("missing source-derived focus PID cone")
    focus_pids = {
        pid for pid in focus if isinstance(pid, str) and _PROPERTY_ID.fullmatch(pid)
    }
    # Only a property ID observed BOTH in the emitted candidate-property
    # carrier AND in its current dependency cone may be navigated.
    reachable = sorted(set(present) & focus_pids)
    proposed = assessment.get("created_property_ref")
    if proposed is not None and (not isinstance(proposed, str) or not _PROPERTY_ID.fullmatch(proposed)):
        raise ValueError("invalid proposed property identifier")
    hits = [proposed] if proposed in reachable else []
    holds = assessment.get("holds")
    if not isinstance(holds, list) or any(not isinstance(v, str) for v in holds):
        raise ValueError("deliberation must carry explicit hold codes")
    source_events = assessment.get("event_source_revision_refs")
    if not isinstance(source_events, list) or not source_events or any(
        not isinstance(v, str) or not v.strip() for v in source_events
    ):
        raise ValueError("deliberation event provenance is required")
    projection = {
        "schema_version": _PROPOSAL_PROJECTION_VERSION,
        "consumer_ref": consumer_ref,
        "consumer_scope_ref": consumer_scope_ref,
        "source_alignment_ref": source_alignment_ref,
        "proposal_ref": assessment["proposal_ref"],
        "proposal_revision_ref": assessment["source_revision_ref"],
        "historical_policy_revision_ref": assessment["policy_revision_ref"],
        "deliberation_packet_ref": assessment["packet_ref"],
        "discussion_event_revision_refs": list(source_events),
        "recorded_judgement": assessment.get("recorded_judgement"),
        "record_completeness": assessment.get("record_completeness"),
        "deliberation_holds": list(holds),
        "source_consumer_pid_intersection": hits,
        "consumer_candidate_pid_count": len(reachable),
        "consumer_lane_id": bundle.get("lane_id"),
        # No bare scheme/version/packet ID is silently a revision-locked
        # source: existing source_revision_refs may hold *packet IDs*.
        "consumer_source_reopen_status": "not_attempted",
        "proposal_source_reopen_status": "not_attempted",
        "source_alignment_verification": "unverified",
        "community_creator_role_verification": "unverified",
        "community_consensus_verification": "unverified",
        "cross_lingual_abi_same_object": False,
        "independent_structural_diagnostics_retained": True,
        "candidate_only": True,
        "wikidata_edit_authorised": False,
        "ao_dispatch_allowed": False,
        "claim_truth_promoted": False,
    }
    # Do not alias nested source containers or reclassify even "checked safe"
    # predecessor dispositions. The new coordinate is a separate sidecar.
    from copy import deepcopy
    result = deepcopy(dict(bundle))
    if "deliberation_context" in result:
        raise ValueError("bundle already has a deliberation context")
    result["deliberation_context"] = projection
    return result

def project_historical_source_anchors(
    snapshot: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    """Project a *verified-by-fetcher revision match* into exact byte spans.

    Consumes existing `scripts/wiki_pull_api.py --wiki wikidata --revid ...`
    output, never performs its own network retrieval or changes Wikidata.
    Signatures are unique locator substrings in original canonical wikitext;
    they are NOT proof of users' permissions, statements' meanings or consensus.
    """
    import hashlib
    from datetime import datetime, timezone

    if not isinstance(snapshot, Mapping) or not isinstance(case, Mapping):
        raise ValueError("snapshot and case must be mappings")
    if case.get("schema_version") != "sl.wikimedia_history_locator.v0_1":
        raise ValueError("unsupported historical locator")
    if snapshot.get("wiki") != "wikidata":
        raise ValueError("historical witness must come from Wikidata")
    if snapshot.get("title", "").replace("_", " ") != case.get("proposal_title", "").replace("_", " "):
        raise ValueError("Wikidata proposal title differs from pinned manifest")
    if type(snapshot.get("revid")) is not int or snapshot["revid"] != case.get("observed_proposal_oldid"):
        raise ValueError("Wikidata source revision differs from pinned manifest")
    expected_minute = case.get("observed_proposal_revision_minute_utc")
    observed_ts = snapshot.get("rev_timestamp")
    if not isinstance(expected_minute, str) or not isinstance(observed_ts, str):
        raise ValueError("revision timestamp differs from observed archive minute")
    try:
        expected = datetime.strptime(expected_minute, "%Y-%m-%dT%H:%M").replace(
            tzinfo=timezone.utc
        )
        actual = datetime.fromisoformat(observed_ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("revision timestamp is not valid ISO-8601") from exc
    if actual.tzinfo is None or actual.utcoffset() is None or (
        actual.astimezone(timezone.utc).replace(second=0, microsecond=0)
        != expected
    ):
        raise ValueError("revision timestamp differs from observed archive minute")
    text = snapshot.get("wikitext")
    if not isinstance(text, str) or not text:
        raise ValueError("canonical wikitext is required for byte-anchored replay")
    raw = text.encode("utf-8")
    if len(raw) > 4_000_000:
        raise ValueError("proposal source exceeds the bounded capture policy")
    source_ref = f"wikidata:page:{snapshot['revid']}"
    events = case.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 128:
        raise ValueError("historical events must be bounded")
    seen = set()
    anchors = []
    normalized = []
    prior = None
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("event must be a mapping")
        event_ref = event.get("event_ref")
        needle = event.get("signature_needle")
        actor = event.get("actor_ref")
        if not isinstance(event_ref, str) or not event_ref or event_ref in seen:
            raise ValueError("duplicate or missing event ref")
        if not isinstance(actor, str) or not actor.startswith("wikidata:User:"):
            raise ValueError("event actor must be a Wikidata actor locator")
        if not isinstance(needle, str) or len(needle) < 12:
            raise ValueError("signature locator is missing")
        excerpt = needle.encode("utf-8")
        start = raw.find(excerpt)
        if start < 0 or raw.find(excerpt, start + 1) >= 0:
            raise ValueError(f"signature locator not uniquely found for {event_ref}")
        at = event.get("at")
        if not isinstance(at, str):
            raise ValueError("event timestamp required")
        try:
            dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("event timestamp is invalid") from exc
        if dt.tzinfo is None or dt.utcoffset() is None or dt.microsecond:
            raise ValueError("event timestamp must be timezone-qualified whole seconds")
        instant = dt.astimezone(timezone.utc)
        if prior is not None and instant < prior:
            raise ValueError("events are not chronologically ordered")
        prior = instant
        seen.add(event_ref)
        anchors.append({
            "event_ref": event_ref, "source_revision_ref": source_ref,
            "start_byte": start, "end_byte": start + len(excerpt),
            "excerpt_digest_ref": "sha256:" + hashlib.sha256(excerpt).hexdigest(),
        })
        normalized.append({
            "event_ref": event_ref,
            "actor_ref": actor,
            "kind": event.get("kind"),
            "at": instant.isoformat().replace("+00:00", "Z"),
            "source_revision_ref": source_ref,
            "source_interpretation_verified": False,
        })
    return {
        "schema_version": "sl.wikimedia_source_anchor_projection.v0_1",
        "source_revision_ref": source_ref,
        "original_revision_url": case.get("observed_source_url"),
        "source_content_digest_ref": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "canonical_text_byte_length": len(raw),
        "event_anchors": anchors,
        "observed_events": normalized,
        "historical_policy_revision_ref": case.get("historical_policy_oldid"),
        "historical_policy_source_authenticated": False,
        "creator_role_authenticated": False,
        "community_consensus_authenticated": False,
        "source_revision_reopened_in_slr": False,
        "event_actor_and_meaning_authenticated": False,
        "candidate_only": True,
        "wikidata_edit_authorised": False,
    }



def build_historical_source_handoff(
    proposal_snapshot: Mapping[str, Any],
    policy_snapshot: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    policy_minimum_age_seconds: int,
    closure_policy_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the native ITIR→SLR input shape over *two actual source snapshots*.

    This performs byte-level source grounding, never adjudicates what historical
    policy means or who has community authority. Its SHA/receipt coordinates
    become SLR evidence ONLY after independent canonical ingest/reopen.
    """
    from datetime import datetime, timezone
    import hashlib

    if type(policy_minimum_age_seconds) is not int or not 0 <= policy_minimum_age_seconds <= 366 * 86400:
        raise ValueError("policy minimum age must be a separate reviewed input")
    proposal = project_historical_source_anchors(proposal_snapshot,case)
    if not isinstance(policy_snapshot, Mapping) or policy_snapshot.get("wiki") != "wikidata":
        raise ValueError("historical policy must be a Wikidata source")
    if policy_snapshot.get("title", "").replace("_", " ") != case.get("historical_policy_title", "").replace("_", " "):
        raise ValueError("wrong historical policy page")
    revid=policy_snapshot.get("revid")
    content=policy_snapshot.get("wikitext")
    timestamp=policy_snapshot.get("rev_timestamp")
    if type(revid) is not int or revid < 1 or not isinstance(content,str) or not content:
        raise ValueError("historical policy must have a real revision and canonical text")
    if not isinstance(timestamp,str):
        raise ValueError("historical policy must include its revision time")
    try:
        selected=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
        proposed=datetime.fromisoformat(case["events"][0]["at"].replace("Z","+00:00"))
        closed=datetime.fromisoformat(case["events"][-1]["at"].replace("Z","+00:00"))
    except (ValueError,KeyError,TypeError) as exc:
        raise ValueError("policy/closure timestamps must be real UTC instants") from exc
    if (selected.tzinfo is None or selected.utcoffset() is None or
            proposed.tzinfo is None or proposed.utcoffset() is None or
            selected > proposed or selected > closed):
        raise ValueError("policy revision was not yet in force at proposal time")
    # SLR INGEST-1 is the ONLY canonical source-revision owner.
    # Exact same framed UTF-8 field sequence as
    # crates/sl-pg-source-store/src/generic_source_content_store.rs:
    # canonical_generic_source_revision_ref.
    provider_ref = "wikidata:mediawiki-api"
    media_type_ref = "text/x-wiki"
    def _canonical_source_revision(source: str, acquisition: str, sha: str) -> str:
        h = hashlib.sha256()
        for field in (
            "generic-source-revision:v1", source, provider_ref,
            acquisition, sha, media_type_ref,
        ):
            raw = field.encode("utf-8")
            h.update(len(raw).to_bytes(8, "big"))
            h.update(raw)
        return "source-revision:sha256:" + h.hexdigest()

    def source_input(snapshot: Mapping[str, Any], sha: str) -> dict[str, Any]:
        revid = snapshot.get("revid")
        if type(revid) is not int or revid < 1:
            raise ValueError("source must carry an exact positive MediaWiki oldid")
        text = snapshot.get("wikitext")
        if not isinstance(text, str) or not text:
            raise ValueError("source must have original UTF-8 text")
        if "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest() != sha:
            raise ValueError("source SHA cannot differ from canonical bytes")
        url = snapshot.get("api_url")
        if not isinstance(url, str) or not url.startswith(
            "https://www.wikidata.org/w/api.php?"
        ):
            raise ValueError("source must carry the actual Wikidata query origin")
        if len(text.encode("utf-8")) > 4_000_000:
            raise ValueError("source text exceeds 4MB capture bound")
        source = f"wikidata:page:{revid}"
        acquisition = "wiki-acquisition:sha256:" + hashlib.sha256(
            ("\\n".join([source, url, sha])).encode("utf-8")
        ).hexdigest()
        revision = _canonical_source_revision(source, acquisition, sha)
        envelope = {
            "source_ref": source,
            "source_revision_ref": revision,
            "provider_ref": provider_ref,
            "family": "wiki",
            "role_class": "content_source",
            "content_digest_ref": sha,
            "acquisition_receipt_ref": acquisition,
            "media_type_ref": media_type_ref,
            "candidate_only": True,
            "creates_semantic_authority": False,
            "applicability_promoted": False,
            "claim_truth_promoted": False,
        }
        return {"envelope": envelope, "canonical_text": text}

    policy_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    proposal_input = source_input(proposal_snapshot, proposal["source_content_digest_ref"])
    policy_input = source_input(policy_snapshot, policy_hash)
    source = proposal_input["envelope"]["source_revision_ref"]
    policy_source_ref = policy_input["envelope"]["source_revision_ref"]
    if source == policy_source_ref:
        raise ValueError("proposal and policy sources require independent revisions")
    native_events = []
    for row in case["events"]:
        record = {
            "event_ref": row["event_ref"], "source_revision_ref": source,
            "actor_ref": row["actor_ref"], "kind": row["kind"], "at": row["at"],
        }
        for field in ("supersedes_ref", "judgement"):
            if row.get(field) is not None:
                record[field] = row[field]
        native_events.append(record)
    result = {
        "deliberation": {
            "proposal_ref": f"wikidata:property-proposal:{case['property_ref']}",
            "source_revision_ref": source,
            "policy_revision_ref": policy_source_ref,
            "minimum_age_seconds": policy_minimum_age_seconds,
            "events": native_events,
            "created_property_ref": case["property_ref"],
        },
        "source_seals": [
            {key: input_["envelope"][key] for key in (
                "source_revision_ref", "content_digest_ref", "acquisition_receipt_ref"
            )} for input_ in (proposal_input, policy_input)
        ],
        "event_anchors": [
            {**anchor, "source_revision_ref": source}
            for anchor in proposal["event_anchors"]
        ],
    }
    # The native input is included separately from the untrusted ITIR claims.
    # The consumer MUST require SLR to ingest and reopen original bytes.
    source_inputs = [proposal_input, policy_input]
    policy_drift = "closure_policy_not_examined"
    closure_policy_oldid = None
    if closure_policy_snapshot is not None:
        closing = closure_policy_snapshot
        if not isinstance(closing, Mapping) or closing.get("wiki") != "wikidata":
            raise ValueError("closure policy must be a Wikidata source")
        if closing.get("title", "").replace("_", " ") != case["historical_policy_title"].replace("_", " "):
            raise ValueError("closure policy is not the same policy page")
        stamp = closing.get("rev_timestamp")
        if not isinstance(stamp, str):
            raise ValueError("closure policy source timestamp is missing")
        try:
            close_revision_time = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("closure policy revision time is malformed") from exc
        if (close_revision_time.tzinfo is None or
                close_revision_time.utcoffset() is None or
                close_revision_time > closed):
            raise ValueError("closure policy revision comes after the decision")
        revision = closing.get("revid")
        closure_text = closing.get("wikitext")
        if type(revision) is not int or revision < 1 or not isinstance(closure_text, str) or not closure_text:
            raise ValueError("closure policy revision lacks an exact oldid or wikitext")
        closure_policy_oldid = revision
        policy_drift = (
            "unchanged_across_proposal_window"
            if revision == revid and closure_text == content
            else "changed_during_proposal_requires_independent_rule_adjudication"
        )
        # A revision ID reused with altered source text is a contradiction,
        # not a historically stable policy.
        if revision == revid and closure_text != content:
            raise ValueError("identical policy oldid has different original bytes")

    return {
        "schema_version":"sl.wikidata_deliberation_slr_handoff_draft.v0_1",
        "itir_slr_input":result,
        "slr_source_inputs":source_inputs,
        "source_revision_refs":[source,policy_source_ref],
        "proposal_page_oldid":proposal_snapshot["revid"],
        "historical_policy_page_oldid":revid,
        "closure_policy_page_oldid":closure_policy_oldid,
        "historical_policy_drift_status":policy_drift,
        "producer_canonical_byte_digests_observed":True,
        "independent_source_provider_receipts_verified":False,
        "historical_policy_applicability_verified":False,
        "historical_policy_interpretation_verified":False,
        "creator_role_verified":False,
        "community_consensus_verified":False,
        "source_ingested_and_reopened_in_slr":False,
        "candidate_only":True,
        "wikidata_edit_authorised":False,
        "ao_dispatch_allowed":False,
    }
