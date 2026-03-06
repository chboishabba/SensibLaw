from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


SCHEMA_VERSION = "wikidata_projection_v0_1"


@dataclass(frozen=True)
class StatementBundle:
    subject: str
    property: str
    value: Any
    rank: str
    qualifiers: tuple[tuple[str, tuple[str, ...]], ...]
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]


@dataclass(frozen=True)
class WindowSlice:
    window_id: str
    bundles: tuple[StatementBundle, ...]


def _stringify(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _extract_datavalue(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return raw
    value = raw.get("value")
    if isinstance(value, Mapping):
        if "id" in value:
            return value["id"]
        if "text" in value:
            return value["text"]
        if "time" in value:
            return value["time"]
        if "amount" in value:
            return value["amount"]
    return value


def _normalize_value_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, (list, tuple)):
        return tuple(sorted(_stringify(item) for item in value))
    return (_stringify(value),)


def _normalize_qualifiers(raw: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, Mapping):
        items = raw.items()
    elif isinstance(raw, list):
        pairs: list[tuple[str, Any]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("qualifier list entries must be objects")
            prop = item.get("property")
            if prop is None:
                raise ValueError("qualifier list entries require property")
            pairs.append((_stringify(prop), item.get("value")))
        items = pairs
    else:
        raise ValueError("qualifiers must be an object or list")
    return tuple(
        sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in items)
    )


def _normalize_references(raw: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if raw is None:
        return tuple()
    if not isinstance(raw, list):
        raise ValueError("references must be a list")
    blocks: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    for block in raw:
        if not isinstance(block, Mapping):
            raise ValueError("reference blocks must be objects")
        normalized = tuple(
            sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in block.items())
        )
        blocks.append(normalized)
    return tuple(sorted(blocks))


def _parse_bundle(raw: Mapping[str, Any]) -> StatementBundle:
    subject = raw.get("subject")
    prop = raw.get("property")
    if not subject or not prop:
        raise ValueError("statement bundles require subject and property")
    return StatementBundle(
        subject=_stringify(subject),
        property=_stringify(prop),
        value=raw.get("value"),
        rank=_stringify(raw.get("rank", "normal")),
        qualifiers=_normalize_qualifiers(raw.get("qualifiers")),
        references=_normalize_references(raw.get("references")),
    )


def _extract_references_from_wikidata(raw_refs: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if not isinstance(raw_refs, list):
        return tuple()
    blocks: list[dict[str, list[Any]]] = []
    for ref in raw_refs:
        if not isinstance(ref, Mapping):
            continue
        snaks = ref.get("snaks")
        if not isinstance(snaks, Mapping):
            continue
        block: dict[str, list[Any]] = {}
        for prop, snak_list in snaks.items():
            if not isinstance(snak_list, list):
                continue
            values: list[Any] = []
            for snak in snak_list:
                if not isinstance(snak, Mapping):
                    continue
                datavalue = snak.get("datavalue")
                extracted = _extract_datavalue(datavalue)
                if extracted is not None:
                    values.append(extracted)
            if values:
                block[_stringify(prop)] = values
        if block:
            blocks.append(block)
    return _normalize_references(blocks)


def _extract_qualifiers_from_wikidata(raw_quals: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(raw_quals, Mapping):
        return tuple()
    normalized: dict[str, list[Any]] = {}
    for prop, snak_list in raw_quals.items():
        if not isinstance(snak_list, list):
            continue
        values: list[Any] = []
        for snak in snak_list:
            if not isinstance(snak, Mapping):
                continue
            extracted = _extract_datavalue(snak.get("datavalue"))
            if extracted is not None:
                values.append(extracted)
        if values:
            normalized[_stringify(prop)] = values
    return _normalize_qualifiers(normalized)


def load_windows(payload: Mapping[str, Any]) -> tuple[WindowSlice, ...]:
    raw_windows = payload.get("windows")
    if not isinstance(raw_windows, list) or not raw_windows:
        raise ValueError("payload requires non-empty windows list")
    windows: list[WindowSlice] = []
    for index, raw_window in enumerate(raw_windows):
        if not isinstance(raw_window, Mapping):
            raise ValueError("window entries must be objects")
        window_id = raw_window.get("id") or f"window_{index + 1}"
        raw_bundles = raw_window.get("statement_bundles")
        if not isinstance(raw_bundles, list):
            raise ValueError("window entries require statement_bundles list")
        windows.append(
            WindowSlice(
                window_id=_stringify(window_id),
                bundles=tuple(_parse_bundle(bundle) for bundle in raw_bundles),
            )
        )
    return tuple(windows)


def build_slice_from_entity_exports(
    window_sources: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    property_filter: Iterable[str] | None = None,
) -> Dict[str, Any]:
    allowed = tuple(sorted(set(property_filter or ("P31", "P279"))))
    windows: list[dict[str, Any]] = []
    for window_id, sources in window_sources.items():
        bundles: list[dict[str, Any]] = []
        source_labels: list[str] = []
        for source in sources:
            source_name = _stringify(source.get("_source_path", "unknown"))
            source_labels.append(source_name)
            entities = source.get("entities")
            if not isinstance(entities, Mapping):
                raise ValueError("entity export payload requires top-level entities object")
            for entity_id, entity in sorted(entities.items()):
                if not isinstance(entity, Mapping):
                    continue
                claims = entity.get("claims")
                if not isinstance(claims, Mapping):
                    continue
                for prop in allowed:
                    claim_list = claims.get(prop)
                    if not isinstance(claim_list, list):
                        continue
                    for statement in claim_list:
                        if not isinstance(statement, Mapping):
                            continue
                        mainsnak = statement.get("mainsnak")
                        if not isinstance(mainsnak, Mapping):
                            continue
                        extracted = _extract_datavalue(mainsnak.get("datavalue"))
                        if extracted is None:
                            continue
                        bundles.append(
                            {
                                "subject": _stringify(entity_id),
                                "property": prop,
                                "value": extracted,
                                "rank": _stringify(statement.get("rank", "normal")),
                                "qualifiers": dict(_extract_qualifiers_from_wikidata(statement.get("qualifiers"))),
                                "references": [
                                    {key: list(values) for key, values in block}
                                    for block in _extract_references_from_wikidata(statement.get("references"))
                                ],
                            }
                        )
        windows.append(
            {
                "id": _stringify(window_id),
                "statement_bundles": bundles,
                "source_files": sorted(source_labels),
            }
        )
    return {
        "metadata": {
            "generated_by": "build_slice_from_entity_exports",
            "properties": list(allowed),
        },
        "windows": windows,
    }


def _qualifier_signature(qualifiers: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    return json.dumps(qualifiers, ensure_ascii=False, separators=(",", ":"))


def _reference_metrics(
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
) -> tuple[int, int, int]:
    n_blocks = len(references)
    distinct_sources = set()
    has_time = 0
    for block in references:
        for prop, values in block:
            if prop == "P248":
                distinct_sources.update(values)
            if prop in {"P577", "P813", "retrieved", "publication_date"} and values:
                has_time = 1
    return n_blocks, len(distinct_sources), has_time


def _project_bundle(bundle: StatementBundle, *, e0: int) -> Dict[str, Any]:
    n_refs, n_sources, has_time = _reference_metrics(bundle.references)
    evidence = min(n_refs + n_sources + has_time, 9)
    tau = 0
    if evidence >= e0:
        if bundle.rank == "preferred":
            tau = 1
        elif bundle.rank == "deprecated":
            tau = -1
    return {
        "tau": tau,
        "evidence": evidence,
        "conflict": 0,
        "audit": {
            "rule_ids": ["base", "quals", "refs", "rank"],
            "rank": bundle.rank,
            "qualifier_signature": _qualifier_signature(bundle.qualifiers),
            "reference_block_count": n_refs,
            "distinct_sources": n_sources,
            "has_time_reference": bool(has_time),
        },
    }


def _aggregate_window(window: WindowSlice, *, e0: int) -> Dict[str, Any]:
    slots: dict[tuple[str, str], dict[str, Any]] = {}
    for bundle in window.bundles:
        slot_key = (bundle.subject, bundle.property)
        projected = _project_bundle(bundle, e0=e0)
        slot = slots.setdefault(
            slot_key,
            {
                "subject_qid": bundle.subject,
                "property_pid": bundle.property,
                "bundle_count": 0,
                "taus": [],
                "sum_e": 0,
                "sum_c": 0,
                "audit": [],
                "qualifier_signatures": [],
                "qualifier_property_sets": [],
            },
        )
        qualifier_props = tuple(prop for prop, _ in bundle.qualifiers)
        slot["bundle_count"] += 1
        slot["taus"].append(projected["tau"])
        slot["sum_e"] += projected["evidence"]
        slot["sum_c"] += projected["conflict"]
        slot["audit"].append(projected["audit"])
        slot["qualifier_signatures"].append(projected["audit"]["qualifier_signature"])
        slot["qualifier_property_sets"].append(qualifier_props)

    result_slots: dict[str, dict[str, Any]] = {}
    for subject, prop in sorted(slots):
        slot = slots[(subject, prop)]
        signature_counts: dict[str, int] = {}
        for signature in slot["qualifier_signatures"]:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        total_signatures = len(slot["qualifier_signatures"]) or 1
        qualifier_entropy = 0.0
        for count in signature_counts.values():
            probability = count / total_signatures
            qualifier_entropy -= probability * math.log2(probability)
        qualifier_property_set = sorted(
            {
                prop_name
                for prop_tuple in slot["qualifier_property_sets"]
                for prop_name in prop_tuple
            }
        )
        taus = set(slot["taus"])
        if taus == {1}:
            tau_star = 1
        elif taus == {-1}:
            tau_star = -1
        elif 1 in taus and -1 in taus:
            tau_star = 0
            slot["sum_c"] += 1
        else:
            tau_star = 0
        result_slots[f"{subject}|{prop}"] = {
            "subject_qid": subject,
            "property_pid": prop,
            "tau": tau_star,
            "sum_e": slot["sum_e"],
            "sum_c": slot["sum_c"],
            "bundle_count": slot["bundle_count"],
            "audit": slot["audit"],
            "qualifier_signatures": sorted(signature_counts),
            "qualifier_property_set": qualifier_property_set,
            "qualifier_entropy": round(qualifier_entropy, 6),
        }
    return result_slots


def _build_edges(window: WindowSlice, prop: str) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for bundle in window.bundles:
        if bundle.property != prop:
            continue
        target = _stringify(bundle.value)
        edges.append((bundle.subject, target))
    return sorted(edges)


def _tarjan_scc(edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    nodes = set()
    for source, target in edges:
        nodes.add(source)
        nodes.add(target)
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])
    for neighbors in adjacency.values():
        neighbors.sort()

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while stack:
                current = stack.pop()
                on_stack.remove(current)
                component.append(current)
                if current == node:
                    break
            components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    return sorted((component for component in components if len(component) > 1), key=lambda c: (len(c), c))


def _find_mixed_order_nodes(window: WindowSlice) -> list[dict[str, Any]]:
    roles: dict[str, set[str]] = {}
    evidence: dict[str, list[dict[str, str]]] = {}
    for bundle in window.bundles:
        if bundle.property == "P31":
            roles.setdefault(bundle.subject, set()).add("subject_p31")
            value = _stringify(bundle.value)
            roles.setdefault(value, set()).add("value_p31")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P31", "role": "subject", "value_qid": value}
            )
            evidence.setdefault(value, []).append(
                {"property_pid": "P31", "role": "value", "subject_qid": bundle.subject}
            )
        elif bundle.property == "P279":
            target = _stringify(bundle.value)
            roles.setdefault(bundle.subject, set()).add("subject_p279")
            roles.setdefault(target, set()).add("value_p279")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P279", "role": "subject", "value_qid": target}
            )
            evidence.setdefault(target, []).append(
                {"property_pid": "P279", "role": "value", "subject_qid": bundle.subject}
            )

    findings: list[dict[str, Any]] = []
    for node in sorted(roles):
        node_roles = roles[node]
        if "subject_p31" in node_roles and ("subject_p279" in node_roles or "value_p279" in node_roles):
            findings.append(
                {
                    "qid": node,
                    "roles": sorted(node_roles),
                    "audit_trace": sorted(
                        evidence.get(node, []),
                        key=lambda item: (
                            item["property_pid"],
                            item["role"],
                            item.get("subject_qid", ""),
                            item.get("value_qid", ""),
                        ),
                    ),
                }
            )
    return findings


def _find_metaclass_candidates(window: WindowSlice) -> list[dict[str, Any]]:
    incoming_p31: dict[str, int] = {}
    higher_order_targets: set[str] = set()
    for bundle in window.bundles:
        if bundle.property == "P31":
            target = _stringify(bundle.value)
            incoming_p31[target] = incoming_p31.get(target, 0) + 1
        if bundle.property in {"P31", "P279"}:
            higher_order_targets.add(bundle.subject)

    findings: list[dict[str, Any]] = []
    for target in sorted(incoming_p31):
        if target not in higher_order_targets:
            continue
        incoming = incoming_p31[target]
        findings.append(
            {
                "qid": target,
                "p31_incoming_count": incoming,
                "metaclass_ratio": 1.0,
            }
        )
    return findings


def _build_qualifier_drift(
    slot_reports: Mapping[str, Mapping[str, Mapping[str, Any]]],
    windows: Sequence[WindowSlice],
) -> list[dict[str, Any]]:
    if len(windows) < 2:
        return []
    first = windows[0].window_id
    second = windows[1].window_id
    all_slot_ids = sorted(set(slot_reports[first]) | set(slot_reports[second]))
    findings: list[dict[str, Any]] = []
    for slot_id in all_slot_ids:
        left = slot_reports[first].get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        right = slot_reports[second].get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        signatures_changed = left["qualifier_signatures"] != right["qualifier_signatures"]
        property_set_changed = left["qualifier_property_set"] != right["qualifier_property_set"]
        entropy_delta = round(right["qualifier_entropy"] - left["qualifier_entropy"], 6)
        if not signatures_changed and not property_set_changed and entropy_delta == 0.0:
            continue
        severity = "low"
        if property_set_changed:
            severity = "high"
        elif signatures_changed:
            severity = "medium"
        findings.append(
            {
                "slot_id": slot_id,
                "subject_qid": slot_id.split("|", 1)[0],
                "property_pid": slot_id.split("|", 1)[1],
                "from_window": first,
                "to_window": second,
                "qualifier_signatures_t1": left["qualifier_signatures"],
                "qualifier_signatures_t2": right["qualifier_signatures"],
                "qualifier_property_set_t1": left["qualifier_property_set"],
                "qualifier_property_set_t2": right["qualifier_property_set"],
                "qualifier_entropy_t1": left["qualifier_entropy"],
                "qualifier_entropy_t2": right["qualifier_entropy"],
                "qualifier_entropy_delta": entropy_delta,
                "severity": severity,
            }
        )
    findings.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}[item["severity"]],
            item["slot_id"],
        )
    )
    return findings


def project_wikidata_payload(
    payload: Mapping[str, Any], *, e0: int = 1, property_filter: Iterable[str] | None = None
) -> Dict[str, Any]:
    windows = load_windows(payload)
    allowed = tuple(sorted(set(property_filter or ("P31", "P279"))))
    filtered_windows = tuple(
        WindowSlice(
            window_id=window.window_id,
            bundles=tuple(bundle for bundle in window.bundles if bundle.property in allowed),
        )
        for window in windows
    )

    window_reports: list[dict[str, Any]] = []
    slot_reports: dict[str, dict[str, Any]] = {}
    for window in filtered_windows:
        slots = _aggregate_window(window, e0=e0)
        slot_reports[window.window_id] = slots
        p279_edges = _build_edges(window, "P279")
        sccs = _tarjan_scc(p279_edges)
        mixed_order_nodes = _find_mixed_order_nodes(window)
        metaclass_candidates = _find_metaclass_candidates(window)
        window_reports.append(
            {
                "id": window.window_id,
                "bundle_count": len(window.bundles),
                "slot_count": len(slots),
                "slots": [slots[key] | {"slot_id": key} for key in sorted(slots)],
                "diagnostics": {
                    "p279_sccs": [
                        {"scc_id": f"{window.window_id}:scc:{idx + 1}", "members": members, "size": len(members)}
                        for idx, members in enumerate(sccs)
                    ],
                    "mixed_order_nodes": mixed_order_nodes,
                    "metaclass_candidates": metaclass_candidates,
                },
            }
        )

    unstable_slots: list[dict[str, Any]] = []
    if len(filtered_windows) >= 2:
        first = filtered_windows[0].window_id
        second = filtered_windows[1].window_id
        all_slot_ids = sorted(set(slot_reports[first]) | set(slot_reports[second]))
        for slot_id in all_slot_ids:
            left_present = slot_id in slot_reports[first]
            right_present = slot_id in slot_reports[second]
            left = slot_reports[first].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            right = slot_reports[second].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            delta_e = right["sum_e"] - left["sum_e"]
            delta_c = right["sum_c"] - left["sum_c"]
            indicator = 1 if left["tau"] != right["tau"] else 0
            if indicator or delta_e or delta_c:
                severity = "low"
                if indicator and left["tau"] != 0 and right["tau"] != 0:
                    severity = "high"
                elif indicator:
                    severity = "medium"
                unstable_slots.append(
                    {
                        "slot_id": slot_id,
                        "subject_qid": slot_id.split("|", 1)[0],
                        "property_pid": slot_id.split("|", 1)[1],
                        "from_window": first,
                        "to_window": second,
                        "tau_t1": left["tau"],
                        "tau_t2": right["tau"],
                        "delta_e": delta_e,
                        "delta_c": delta_c,
                        "eii": indicator,
                        "present_in_both": left_present and right_present,
                        "severity": severity,
                    }
                )
        unstable_slots.sort(
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}[item["severity"]],
                -item["eii"],
                -(1 if item["present_in_both"] else 0),
                item["slot_id"],
            )
        )

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in unstable_slots:
        severity_counts[item["severity"]] += 1
    qualifier_drift = _build_qualifier_drift(slot_reports, filtered_windows)
    qualifier_severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in qualifier_drift:
        qualifier_severity_counts[item["severity"]] += 1

    review_summary = {
        "next_bounded_slice_recommendation": "Qualifier drift is now active; expand qualifier-bearing slices and review property-set instability before wider ontology phases.",
        "unstable_slot_counts": severity_counts,
        "top_unstable_slot_ids": [item["slot_id"] for item in unstable_slots[:5]],
        "structural_focus": [
            "mixed_order_nodes",
            "p279_sccs",
            "metaclass_candidates",
        ],
        "qualifier_drift_counts": qualifier_severity_counts,
        "top_qualifier_drift_slot_ids": [item["slot_id"] for item in qualifier_drift[:5]],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "bounded_slice": {"properties": list(allowed), "window_ids": [window.window_id for window in filtered_windows]},
        "assumptions": {
            "rank_evidence_gate_e0": e0,
            "advisory_only": True,
            "tokenizer_lexeme_boundary_preserved": True,
        },
        "windows": window_reports,
        "unstable_slots": unstable_slots,
        "qualifier_drift": qualifier_drift,
        "review_summary": review_summary,
    }


__all__ = [
    "SCHEMA_VERSION",
    "build_slice_from_entity_exports",
    "load_windows",
    "project_wikidata_payload",
]
