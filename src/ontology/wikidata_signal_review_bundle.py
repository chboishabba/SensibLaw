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


def _entity_row(*, qid: Any, role: str, label: Any = "", status: str = "candidate") -> dict[str, Any]:
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
    packet_context = inputs.get("packet_context") if isinstance(inputs.get("packet_context"), Mapping) else {}
    entity_qid = _text(inputs.get("entity_qid"))
    source_property = _text(inputs.get("source_property"))
    target_property = _text(inputs.get("target_property"))
    dispositions = (
        report.get("review_disposition", {}).get("candidate_dispositions", [])
        if isinstance(report.get("review_disposition"), Mapping)
        else []
    )
    held_count = sum(1 for row in dispositions if _text((row or {}).get("final_state")) == "held")
    promotion_status = "blocked" if held_count == len(dispositions) and dispositions else "candidate_only"
    return _bundle(
        lane_id=lane_id,
        lane_family=lane_family,
        surface_signal=f"{source_property} -> {target_property} climate migration review",
        signal_kind="conditional",
        authority_surface="mixed",
        soft_type_strength="substantial",
        domain_projection="bounded climate-family migration packet",
        promotion_status=promotion_status,
        candidate_entities=[_entity_row(qid=entity_qid, role="review_entity", status="bounded")],
        candidate_properties=[
            _property_row(pid=source_property, role="source_property", status="bounded"),
            _property_row(pid=target_property, role="target_property", status="bounded"),
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
            _receipt_row(kind="split_plan_id", value=packet_context.get("split_plan_id")),
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
    grounding = report.get("wikidata_grounding") if isinstance(report.get("wikidata_grounding"), Mapping) else {}
    components = grounding.get("components") if isinstance(grounding.get("components"), Mapping) else {}
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
            code=_text(row.get("grounding_residual")) or _text(row.get("reason")) or "grounding_residual",
            status="open",
            detail=row.get("reason"),
        )
        for row in components.get("object_qid_candidates", [])
        if isinstance(row, Mapping) and (
            _text(row.get("grounding_residual")) or _text(row.get("reason"))
        )
    ]
    if not residuals:
        residuals.append(
            _residual_row(
                code="review_only_candidate_comparison",
                status="open",
                detail="bounded in-memory candidate comparison",
            )
        )
    candidate_reports = report.get("candidate_reports") if isinstance(report.get("candidate_reports"), list) else []
    checked_safe = sum(
        1 for row in candidate_reports if isinstance(row, Mapping) and _text(row.get("disposition")) == "checked_safe_reviewable"
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
            _receipt_row(kind="packet_schema_version", value=report.get("packet_schema_version")),
        ],
        source_revision_refs=[
            report.get("focus_item"),
            report.get("packet_schema_version"),
        ],
        dependency_cone={
            "focus_qids": _nonempty_strings([report.get("focus_item")]),
            "focus_pids": [row["pid"] for row in pid_candidates if _text(row.get("pid"))],
            "candidate_report_ids": _nonempty_strings(
                (row.get("candidate_id") for row in candidate_reports if isinstance(row, Mapping))
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
    pairs = report.get("disjoint_pairs") if isinstance(report.get("disjoint_pairs"), list) else []
    pair = pairs[0] if pairs and isinstance(pairs[0], Mapping) else {}
    culprit_classes = report.get("culprit_classes") if isinstance(report.get("culprit_classes"), list) else []
    culprit_items = report.get("culprit_items") if isinstance(report.get("culprit_items"), list) else []
    candidate_entities = []
    for role, qid_key, label_key in (
        ("holder_class", "holder_qid", "holder_label"),
        ("left_class", "left_qid", "left_label"),
        ("right_class", "right_qid", "right_label"),
    ):
        if _text(pair.get(qid_key)):
            candidate_entities.append(
                _entity_row(qid=pair.get(qid_key), role=role, label=pair.get(label_key), status="bounded")
            )
    for row in culprit_classes:
        if isinstance(row, Mapping) and _text(row.get("qid")):
            candidate_entities.append(
                _entity_row(qid=row.get("qid"), role="culprit_class", label=row.get("label"), status="contradiction")
            )
    for row in culprit_items:
        if isinstance(row, Mapping) and _text(row.get("qid")):
            candidate_entities.append(
                _entity_row(qid=row.get("qid"), role="culprit_item", label=row.get("label"), status="contradiction")
            )
    candidate_properties = [
        _property_row(pid=pair.get("property_pid"), role="disjointness_property", status="bounded"),
        _property_row(pid=pair.get("qualifier_pid"), role="qualifier_property", status="bounded"),
        _property_row(pid="P279", role="subclass_context", status="bounded"),
        _property_row(pid="P31", role="instance_context", status="bounded"),
    ]
    residuals = [
        _residual_row(
            code="subclass_contradiction",
            status="open" if int(report.get("subclass_violation_count") or 0) else "closed",
            detail=f"count={int(report.get('subclass_violation_count') or 0)}",
        ),
        _residual_row(
            code="instance_contradiction",
            status="open" if int(report.get("instance_violation_count") or 0) else "closed",
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
    cluster_results = report.get("cluster_results") if isinstance(report.get("cluster_results"), list) else []
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
        _property_row(pid=row.get("supporting_hotspot_family"), role="hotspot_family", status="bounded")
        for row in cluster_results
        if isinstance(row, Mapping) and _text(row.get("supporting_hotspot_family"))
    ]
    inconsistent = int(report.get("summary", {}).get("cluster_counts", {}).get("inconsistent") or 0)
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
            *[_receipt_row(kind="pack_id", value=pack_id) for pack_id in selected_pack_ids],
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
                row.get("cluster_id") for row in cluster_results if isinstance(row, Mapping)
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
    candidates = report.get("candidates") if isinstance(report.get("candidates"), list) else []
    candidate_entities = [
        _entity_row(qid=row.get("qid"), role="follow_candidate", status=row.get("coverage_status") or "candidate")
        for row in candidates
        if isinstance(row, Mapping) and _text(row.get("qid"))
    ]
    residuals = [
        _residual_row(
            code="coverage_hold",
            status="open" if _text(row.get("coverage_status")) == "hold" else "candidate",
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
            _receipt_row(kind="plan_schema_version", value=report.get("plan_schema_version")),
        ],
        source_revision_refs=[report.get("campaign_id"), report.get("plan_schema_version")],
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
