from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

EXPECTED_LAYER_CONTRACT_SCHEMA_VERSION = "sl.expected_layer_contract.v0_1"
LINKAGE_DEPTH_CASE_SCHEMA_VERSION = "sl.linkage_depth_case.v0_1"
LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION = "sl.linkage_depth_audit.v0_1"
LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION = "sl.linkage_depth_receipt.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bridge_key(source_layer: str, target_layer: str) -> str:
    return f"{source_layer}->{target_layer}"


def build_expected_layer_contract(
    *,
    contract_id: str,
    domain: str,
    anchor_kind: str,
    expected_layers: Sequence[str],
    required_bridges: Sequence[Sequence[str]],
    terminal_anchor: str,
    required_authority_boundaries: Sequence[str] = (),
    required_visibility_fields: Sequence[str] = (),
    notes: Sequence[str] = (),
    linkage_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_layers = [_text(layer) for layer in expected_layers if _text(layer)]
    normalized_bridges = [
        [_text(pair[0]), _text(pair[1])]
        for pair in required_bridges
        if isinstance(pair, Sequence) and len(pair) == 2 and _text(pair[0]) and _text(pair[1])
    ]
    return {
        "schema_version": EXPECTED_LAYER_CONTRACT_SCHEMA_VERSION,
        "contract_id": _text(contract_id),
        "domain": _text(domain),
        "anchor_kind": _text(anchor_kind),
        "expected_layers": normalized_layers,
        "required_bridges": normalized_bridges,
        "terminal_anchor": _text(terminal_anchor),
        "minimum_depth": len(normalized_bridges),
        "required_authority_boundaries": [_text(value) for value in required_authority_boundaries if _text(value)],
        "required_visibility_fields": [_text(value) for value in required_visibility_fields if _text(value)],
        "linkage_policy": dict(linkage_policy or {}),
        "notes": [_text(note) for note in notes if _text(note)],
    }


def normalize_expected_layer_contract(contract: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = contract if isinstance(contract, Mapping) else {}
    policy_payload = payload.get("linkage_policy")
    if not isinstance(policy_payload, Mapping):
        policy_payload = payload.get("wd_linkage_policy")
    return build_expected_layer_contract(
        contract_id=_text(payload.get("contract_id")),
        domain=_text(payload.get("domain")),
        anchor_kind=_text(payload.get("anchor_kind")),
        expected_layers=[
            _text(layer)
            for layer in payload.get("expected_layers", [])
            if _text(layer)
        ],
        required_bridges=[
            [_text(pair[0]), _text(pair[1])]
            for pair in payload.get("required_bridges", [])
            if isinstance(pair, Sequence) and len(pair) == 2
        ],
        terminal_anchor=_text(payload.get("terminal_anchor")),
        required_authority_boundaries=[
            _text(value)
            for value in payload.get("required_authority_boundaries", [])
            if _text(value)
        ],
        required_visibility_fields=[
            _text(value)
            for value in payload.get("required_visibility_fields", [])
            if _text(value)
        ],
        notes=[_text(note) for note in payload.get("notes", []) if _text(note)],
        linkage_policy=dict(policy_payload or {}),
    )


def build_linkage_depth_case(
    *,
    case_id: str,
    case_kind: str,
    contract_id: str,
    expected_anchor_ids: Sequence[str],
    expected_terminal_ids: Sequence[str],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    lane_id: str | None = None,
    case_source: str | None = None,
    notes: Sequence[str] = (),
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": LINKAGE_DEPTH_CASE_SCHEMA_VERSION,
        "case_id": _text(case_id),
        "case_kind": _text(case_kind),
        "lane_id": lane_id,
        "contract_id": _text(contract_id),
        "notes": [_text(note) for note in notes if _text(note)],
        "expected_anchor_ids": [_text(value) for value in expected_anchor_ids if _text(value)],
        "expected_terminal_ids": [_text(value) for value in expected_terminal_ids if _text(value)],
        "nodes": [deepcopy(dict(row)) for row in nodes if isinstance(row, Mapping)],
        "edges": [deepcopy(dict(row)) for row in edges if isinstance(row, Mapping)],
    }
    if case_source is not None:
        payload["case_source"] = _text(case_source)
    if isinstance(contract, Mapping):
        payload["contract"] = normalize_expected_layer_contract(contract)
    return payload


def normalize_linkage_depth_case(case: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = case if isinstance(case, Mapping) else {}
    return build_linkage_depth_case(
        case_id=_text(payload.get("case_id")),
        case_kind=_text(payload.get("case_kind")),
        contract_id=_text(payload.get("contract_id")) or _text((payload.get("contract") or {}).get("contract_id")),
        expected_anchor_ids=[
            _text(value) for value in payload.get("expected_anchor_ids", []) if _text(value)
        ],
        expected_terminal_ids=[
            _text(value) for value in payload.get("expected_terminal_ids", []) if _text(value)
        ],
        nodes=[row for row in payload.get("nodes", []) if isinstance(row, Mapping)],
        edges=[row for row in payload.get("edges", []) if isinstance(row, Mapping)],
        lane_id=_text(payload.get("lane_id")) or None,
        case_source=_text(payload.get("case_source")) or None,
        notes=[_text(note) for note in payload.get("notes", []) if _text(note)],
        contract=payload.get("contract") if isinstance(payload.get("contract"), Mapping) else None,
    )


def build_linkage_depth_receipt(
    *,
    case: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
    audited_case: Mapping[str, Any] | None = None,
    receipt_id: str | None = None,
    source_mode: str | None = None,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    case_payload = normalize_linkage_depth_case(case)
    contract_payload = (
        normalize_expected_layer_contract(contract)
        if isinstance(contract, Mapping)
        else normalize_expected_layer_contract(case_payload.get("contract"))
        if isinstance(case_payload.get("contract"), Mapping)
        else None
    )
    audited = (
        dict(audited_case)
        if isinstance(audited_case, Mapping)
        else audit_linkage_depth_case(case_payload, contract=contract_payload)
    )
    final_contract = (
        contract_payload
        if contract_payload is not None
        else normalize_expected_layer_contract(audited.get("contract"))
        if isinstance(audited.get("contract"), Mapping)
        else normalize_expected_layer_contract(case_payload.get("contract"))
        if isinstance(case_payload.get("contract"), Mapping)
        else {}
    )
    return {
        "schema_version": LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
        "receipt_id": _text(receipt_id) or f"linkage_depth:{_text(case_payload.get('case_id'))}",
        "artifact_type": "linkage_depth_receipt",
        "case_id": _text(case_payload.get("case_id")),
        "lane_id": case_payload.get("lane_id"),
        "contract": deepcopy(final_contract),
        "source_mode": _text(source_mode) or _text(case_payload.get("case_source")) or "reconstructed_case",
        "expected_anchor_ids": deepcopy(case_payload.get("expected_anchor_ids", [])),
        "expected_terminal_ids": deepcopy(case_payload.get("expected_terminal_ids", [])),
        "nodes": deepcopy(case_payload.get("nodes", [])),
        "edges": deepcopy(case_payload.get("edges", [])),
        "diagnostics": {
            "linkage_depth_status": audited["linkage_depth_status"],
            "layer_coverage": deepcopy(audited["layer_coverage"]),
            "typed_path_depth": audited["typed_path_depth"],
            "bridge_completeness": deepcopy(audited["bridge_completeness"]),
            "role_erasure_detected": audited["role_erasure_detected"],
            "wd_soft_stitch_present": audited["wd_soft_stitch_present"],
            "wd_promotion_blocked": audited["wd_promotion_blocked"],
            "anchor_to_tranche_reachability": deepcopy(audited["anchor_to_tranche_reachability"]),
            "collapse_points": deepcopy(audited["collapse_points"]),
            "collapse_origin": audited["collapse_origin"],
            "visibility_requirements": deepcopy(audited.get("visibility_requirements", {})),
            "authority_boundary_visibility": audited.get("authority_boundary_visibility", "not_applicable"),
            "instrument_or_jurisdiction_visible": bool(audited.get("instrument_or_jurisdiction_visible")),
            "candidate_vs_promoted_visibility": bool(audited.get("candidate_vs_promoted_visibility")),
        },
        "notes": [_text(note) for note in notes if _text(note)],
    }


def normalize_linkage_depth_receipt(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = receipt if isinstance(receipt, Mapping) else {}
    case_payload = build_linkage_depth_case(
        case_id=_text(payload.get("case_id")),
        case_kind="receipt_projected_case",
        contract_id=_text((payload.get("contract") or {}).get("contract_id")),
        expected_anchor_ids=[
            _text(value) for value in payload.get("expected_anchor_ids", []) if _text(value)
        ],
        expected_terminal_ids=[
            _text(value) for value in payload.get("expected_terminal_ids", []) if _text(value)
        ],
        nodes=[row for row in payload.get("nodes", []) if isinstance(row, Mapping)],
        edges=[row for row in payload.get("edges", []) if isinstance(row, Mapping)],
        lane_id=_text(payload.get("lane_id")) or None,
        case_source=_text(payload.get("source_mode")) or None,
        contract=payload.get("contract") if isinstance(payload.get("contract"), Mapping) else None,
    )
    return build_linkage_depth_receipt(
        case=case_payload,
        contract=payload.get("contract") if isinstance(payload.get("contract"), Mapping) else None,
        audited_case={"linkage_depth_status": "", "layer_coverage": {}, "typed_path_depth": 0, "bridge_completeness": [], "role_erasure_detected": False, "wd_soft_stitch_present": False, "wd_promotion_blocked": False, "anchor_to_tranche_reachability": {}, "collapse_points": [], "collapse_origin": "none"} if not isinstance(payload.get("diagnostics"), Mapping) else {
            "linkage_depth_status": _text(payload.get("diagnostics", {}).get("linkage_depth_status")),
            "layer_coverage": deepcopy(payload.get("diagnostics", {}).get("layer_coverage", {})),
            "typed_path_depth": int(payload.get("diagnostics", {}).get("typed_path_depth", 0) or 0),
            "bridge_completeness": deepcopy(payload.get("diagnostics", {}).get("bridge_completeness", [])),
            "role_erasure_detected": bool(payload.get("diagnostics", {}).get("role_erasure_detected")),
            "wd_soft_stitch_present": bool(payload.get("diagnostics", {}).get("wd_soft_stitch_present")),
            "wd_promotion_blocked": bool(payload.get("diagnostics", {}).get("wd_promotion_blocked")),
            "anchor_to_tranche_reachability": deepcopy(payload.get("diagnostics", {}).get("anchor_to_tranche_reachability", {})),
            "collapse_points": deepcopy(payload.get("diagnostics", {}).get("collapse_points", [])),
            "collapse_origin": _text(payload.get("diagnostics", {}).get("collapse_origin")) or "none",
            "visibility_requirements": deepcopy(payload.get("diagnostics", {}).get("visibility_requirements", {})),
            "authority_boundary_visibility": _text(payload.get("diagnostics", {}).get("authority_boundary_visibility")) or "not_applicable",
            "instrument_or_jurisdiction_visible": bool(payload.get("diagnostics", {}).get("instrument_or_jurisdiction_visible")),
            "candidate_vs_promoted_visibility": bool(payload.get("diagnostics", {}).get("candidate_vs_promoted_visibility")),
        },
        receipt_id=_text(payload.get("receipt_id")) or None,
        source_mode=_text(payload.get("source_mode")) or None,
        notes=[_text(note) for note in payload.get("notes", []) if _text(note)],
    )


def audit_linkage_depth_case(
    case: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_payload = normalize_linkage_depth_case(case)
    contract_payload = (
        normalize_expected_layer_contract(contract)
        if isinstance(contract, Mapping)
        else normalize_expected_layer_contract(case_payload.get("contract"))
        if isinstance(case_payload.get("contract"), Mapping)
        else {}
    )
    expected_layers = list(contract_payload.get("expected_layers", []))
    required_bridges = [
        [_text(pair[0]), _text(pair[1])]
        for pair in contract_payload.get("required_bridges", [])
        if isinstance(pair, Sequence) and len(pair) == 2
    ]
    required_visibility_fields = [
        _text(value)
        for value in contract_payload.get("required_visibility_fields", [])
        if _text(value)
    ]
    layer_index = {layer: index for index, layer in enumerate(expected_layers)}
    nodes = [dict(row) for row in case_payload.get("nodes", []) if isinstance(row, Mapping)]
    edges = [dict(row) for row in case_payload.get("edges", []) if isinstance(row, Mapping)]
    anchor_ids = [_text(value) for value in case_payload.get("expected_anchor_ids", []) if _text(value)]
    terminal_ids = {
        _text(value) for value in case_payload.get("expected_terminal_ids", []) if _text(value)
    }
    anchor_layer = _text(expected_layers[0]) if expected_layers else ""

    node_map = {_text(row.get("id")): row for row in nodes if _text(row.get("id"))}
    nodes_by_layer: dict[str, list[str]] = defaultdict(list)
    for node_id, row in node_map.items():
        layer = _text(row.get("layer"))
        if layer:
            nodes_by_layer[layer].append(node_id)

    edges_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bridge_matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    wd_soft_stitch_present = False
    wd_soft_stitch_nodes: list[str] = []
    wd_soft_stitch_blocked = True
    role_erasure_detected = False

    for row in nodes:
        layer = _text(row.get("layer"))
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        if layer == "sentence_pnf":
            role_bindings = metadata.get("carrier_roles")
            if not isinstance(role_bindings, list) or not [_text(value) for value in role_bindings if _text(value)]:
                role_erasure_detected = True

    for row in edges:
        source = _text(row.get("source"))
        target = _text(row.get("target"))
        if not source or not target or source not in node_map or target not in node_map:
            continue
        edges_by_source[source].append(row)
        source_layer = _text(node_map[source].get("layer"))
        target_layer = _text(node_map[target].get("layer"))
        bridge_matches[_bridge_key(source_layer, target_layer)].append(row)
        kind = _text(row.get("kind"))
        target_metadata = (
            node_map[target].get("metadata")
            if isinstance(node_map[target].get("metadata"), Mapping)
            else {}
        )
        if kind == "wd_soft_stitch" or _text(target_metadata.get("wd_stage")) == "soft_stitch":
            wd_soft_stitch_present = True
            wd_soft_stitch_nodes.append(target)
            if _text(target_metadata.get("promotion_status")) != "blocked":
                wd_soft_stitch_blocked = False

    def _collect_visibility_values(metadata: Mapping[str, Any], field: str) -> list[Any]:
        values: list[Any] = []
        if field in metadata:
            value = metadata.get(field)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                values.extend(item for item in value if item not in (None, "", [], {}))
            elif value not in (None, "", [], {}):
                values.append(value)
        visibility_flags = metadata.get("visibility_flags")
        if isinstance(visibility_flags, Sequence) and not isinstance(visibility_flags, (str, bytes, bytearray)):
            values.extend(item for item in visibility_flags if _text(item) == field)
        diagnostic_flags = metadata.get("diagnostic_flags")
        if isinstance(diagnostic_flags, Mapping) and field in diagnostic_flags:
            value = diagnostic_flags.get(field)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                values.extend(item for item in value if item not in (None, "", [], {}))
            elif value not in (None, "", [], {}):
                values.append(value)
        return values

    visibility_requirements: dict[str, dict[str, Any]] = {}
    for field in required_visibility_fields:
        raw_values: list[Any] = []
        node_ids: set[str] = set()
        edge_kinds: set[str] = set()
        for node_id, row in node_map.items():
            metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
            values = _collect_visibility_values(metadata, field)
            if values:
                raw_values.extend(values)
                node_ids.add(node_id)
        for row in edges:
            metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
            values = _collect_visibility_values(metadata, field)
            if values:
                raw_values.extend(values)
                edge_kinds.add(_text(row.get("kind")))
        normalized_values: list[Any] = []
        for value in raw_values:
            if isinstance(value, bool):
                normalized_values.append(value)
            else:
                text = _text(value)
                if text:
                    normalized_values.append(text)
        deduped_values: list[Any] = []
        seen_values: set[str] = set()
        for value in normalized_values:
            seen_key = repr(value)
            if seen_key in seen_values:
                continue
            seen_values.add(seen_key)
            deduped_values.append(value)
        visibility_requirements[field] = {
            "present": bool(deduped_values),
            "values": deduped_values,
            "node_count": len(node_ids),
            "node_ids": sorted(node_ids),
            "edge_kinds": sorted(kind for kind in edge_kinds if kind),
        }

    def _visibility_state(field: str) -> str:
        requirement = visibility_requirements.get(field)
        if requirement is None:
            return "not_applicable"
        values = requirement.get("values", [])
        if not values:
            return "missing"
        lowered = {str(value).strip().casefold() for value in values if not isinstance(value, bool)}
        if "missing" in lowered:
            return "missing"
        if "partial" in lowered:
            return "partial"
        if "complete" in lowered:
            return "complete"
        if any(value is True for value in values) or lowered:
            return "complete"
        return "missing"

    layer_coverage = {
        layer: {
            "present": bool(nodes_by_layer.get(layer)),
            "node_count": len(nodes_by_layer.get(layer, [])),
            "node_ids": sorted(nodes_by_layer.get(layer, [])),
        }
        for layer in expected_layers
    }

    bridge_completeness = []
    missing_bridges: list[str] = []
    for source_layer, target_layer in required_bridges:
        bridge_key = _bridge_key(source_layer, target_layer)
        matching = bridge_matches.get(bridge_key, [])
        if not matching:
            missing_bridges.append(bridge_key)
        bridge_completeness.append(
            {
                "source_layer": source_layer,
                "target_layer": target_layer,
                "present": bool(matching),
                "edge_count": len(matching),
                "edge_kinds": sorted({_text(row.get("kind")) for row in matching if _text(row.get("kind"))}),
            }
        )

    def _walk_anchor(anchor_id: str) -> dict[str, Any]:
        current_nodes = {anchor_id}
        max_layer_position = layer_index.get(anchor_layer, 0)
        typed_hops = 0
        path_layers = [anchor_layer] if anchor_layer else []
        for source_layer, target_layer in required_bridges:
            next_nodes = {
                _text(edge.get("target"))
                for node_id in current_nodes
                for edge in edges_by_source.get(node_id, [])
                if _text(node_map[_text(edge.get("target"))].get("layer")) == target_layer
                and _text(node_map[_text(edge.get("source"))].get("layer")) == source_layer
            }
            if not next_nodes:
                return {
                    "anchor_id": anchor_id,
                    "reachable": False,
                    "typed_hops": typed_hops,
                    "max_layer": source_layer,
                    "path_layers": list(path_layers),
                    "collapse_point": {
                        "anchor_id": anchor_id,
                        "after_layer": source_layer,
                        "missing_layer": target_layer,
                        "missing_bridge": _bridge_key(source_layer, target_layer),
                    },
                }
            current_nodes = next_nodes
            typed_hops += 1
            path_layers.append(target_layer)
            max_layer_position = max(max_layer_position, layer_index.get(target_layer, max_layer_position))
        reachable = bool(current_nodes & terminal_ids) if terminal_ids else True
        if not reachable:
            return {
                "anchor_id": anchor_id,
                "reachable": False,
                "typed_hops": typed_hops,
                "max_layer": expected_layers[max_layer_position],
                "path_layers": list(path_layers),
                "collapse_point": {
                    "anchor_id": anchor_id,
                    "after_layer": expected_layers[max_layer_position],
                    "missing_layer": contract_payload.get("terminal_anchor"),
                    "missing_bridge": "terminal_reachability",
                },
            }
        return {
            "anchor_id": anchor_id,
            "reachable": True,
            "typed_hops": typed_hops,
            "max_layer": expected_layers[max_layer_position],
            "path_layers": list(path_layers),
            "collapse_point": None,
        }

    anchor_walks = [_walk_anchor(anchor_id) for anchor_id in anchor_ids if anchor_id in node_map]
    reachable_anchor_ids = [row["anchor_id"] for row in anchor_walks if row["reachable"]]
    collapse_points = [row["collapse_point"] for row in anchor_walks if row.get("collapse_point")]
    typed_path_depth = max((int(row["typed_hops"]) for row in anchor_walks), default=0)

    if (
        all(layer_coverage[layer]["present"] for layer in expected_layers)
        and not missing_bridges
        and len(reachable_anchor_ids) == len(anchor_walks)
        and typed_path_depth >= int(contract_payload.get("minimum_depth", 0) or 0)
    ):
        linkage_depth_status = "complete"
    elif typed_path_depth == 0:
        linkage_depth_status = "absent"
    elif len(reachable_anchor_ids) == 0:
        linkage_depth_status = "shallow"
    else:
        linkage_depth_status = "partial"

    return {
        "case_id": _text(case_payload.get("case_id")),
        "case_kind": _text(case_payload.get("case_kind")),
        "lane_id": case_payload.get("lane_id"),
        "case_source": _text(case_payload.get("case_source")) or "reconstructed_case",
        "contract_id": _text(contract_payload.get("contract_id")),
        "contract": deepcopy(contract_payload),
        "linkage_depth_status": linkage_depth_status,
        "render_depth_status": "not_applicable",
        "layer_coverage": layer_coverage,
        "typed_path_depth": typed_path_depth,
        "minimum_depth": int(contract_payload.get("minimum_depth", 0) or 0),
        "bridge_completeness": bridge_completeness,
        "role_erasure_detected": role_erasure_detected,
        "wd_soft_stitch_present": wd_soft_stitch_present,
        "wd_soft_stitch_nodes": sorted(set(wd_soft_stitch_nodes)),
        "wd_promotion_blocked": wd_soft_stitch_present and wd_soft_stitch_blocked,
        "anchor_to_tranche_reachability": {
            "anchor_count": len(anchor_walks),
            "reachable_anchor_count": len(reachable_anchor_ids),
            "all_reachable": len(reachable_anchor_ids) == len(anchor_walks) and bool(anchor_walks),
            "reachable_anchor_ids": reachable_anchor_ids,
        },
        "collapse_points": collapse_points,
        "collapse_origin": "none" if not collapse_points else "projection",
        "visibility_requirements": visibility_requirements,
        "authority_boundary_visibility": _visibility_state("authority_boundary_visibility"),
        "instrument_or_jurisdiction_visible": bool(
            visibility_requirements.get("instrument_or_jurisdiction_visible", {}).get("present")
        ),
        "candidate_vs_promoted_visibility": bool(
            visibility_requirements.get("candidate_vs_promoted_visibility", {}).get("present")
        ),
        "anchor_walks": anchor_walks,
        "notes": deepcopy(case_payload.get("notes", [])),
    }


def build_linkage_depth_audit(
    *,
    cases: Sequence[Mapping[str, Any]],
    contracts: Sequence[Mapping[str, Any]] | None = None,
    audit_scope: str = "linkage_depth",
    schema_version: str = LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION,
    next_actions: Sequence[str] = (),
    primary_owner: str = "linkage_depth_projection_diagnostics",
) -> dict[str, Any]:
    audited_cases = [audit_linkage_depth_case(case) for case in cases]
    contract_payloads = [
        normalize_expected_layer_contract(contract)
        for contract in (contracts or [])
        if isinstance(contract, Mapping)
    ]
    if not contract_payloads:
        seen: set[str] = set()
        for row in audited_cases:
            contract = row.get("contract")
            contract_id = _text(row.get("contract_id"))
            if not contract_id or contract_id in seen or not isinstance(contract, Mapping):
                continue
            contract_payloads.append(normalize_expected_layer_contract(contract))
            seen.add(contract_id)
    contract_ids = sorted({_text(row.get("contract_id")) for row in audited_cases if _text(row.get("contract_id"))})
    complete_case_ids = [row["case_id"] for row in audited_cases if row["linkage_depth_status"] == "complete"]
    role_erasure_case_ids = [row["case_id"] for row in audited_cases if row["role_erasure_detected"]]
    anchor_failure_case_ids = [
        row["case_id"]
        for row in audited_cases
        if not row["anchor_to_tranche_reachability"]["all_reachable"]
    ]
    cases_with_wd_soft_stitch = [row["case_id"] for row in audited_cases if row["wd_soft_stitch_present"]]
    return {
        "schema_version": _text(schema_version) or LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION,
        "audit_scope": _text(audit_scope) or "linkage_depth",
        "contracts": contract_payloads,
        "summary": {
            "case_count": len(audited_cases),
            "complete_case_count": len(complete_case_ids),
            "complete_case_ids": complete_case_ids,
            "role_erasure_case_count": len(role_erasure_case_ids),
            "role_erasure_case_ids": role_erasure_case_ids,
            "anchor_failure_case_count": len(anchor_failure_case_ids),
            "anchor_failure_case_ids": anchor_failure_case_ids,
            "wd_soft_stitch_case_count": len(cases_with_wd_soft_stitch),
            "wd_soft_stitch_case_ids": cases_with_wd_soft_stitch,
            "emitted_artifact_case_count": sum(
                1 for row in audited_cases if row["case_source"] == "emitted_bridge_artifact"
            ),
            "contract_ids": contract_ids,
            "primary_owner": _text(primary_owner) or "linkage_depth_projection_diagnostics",
        },
        "cases": audited_cases,
        "next_actions": [_text(action) for action in next_actions if _text(action)],
    }


__all__ = [
    "EXPECTED_LAYER_CONTRACT_SCHEMA_VERSION",
    "LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION",
    "LINKAGE_DEPTH_CASE_SCHEMA_VERSION",
    "LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION",
    "audit_linkage_depth_case",
    "build_expected_layer_contract",
    "build_linkage_depth_audit",
    "build_linkage_depth_case",
    "build_linkage_depth_receipt",
    "normalize_expected_layer_contract",
    "normalize_linkage_depth_case",
    "normalize_linkage_depth_receipt",
]
