from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.policy.semantic_promotion import (
    build_hotspot_pack_candidate,
    promote_hotspot_pack_candidate,
)

from .wikidata import project_wikidata_payload


HOTSPOT_CLUSTER_SCHEMA_VERSION = "wikidata_hotspot_cluster_pack/v1"
VALID_PACK_STATUSES = {
    "fixture_backed",
    "report_backed",
    "page_locked_candidate",
    "planned_only",
}
VALID_PROMOTION_STATUSES = {
    "candidate",
    "anchored",
    "promotable",
    "promoted",
}


def _derive_hotspot_semantic_basis(entry: Mapping[str, Any]) -> str:
    status = str(entry.get("status") or "").strip()
    if status in {"fixture_backed", "report_backed"}:
        return "structural"
    if status == "page_locked_candidate":
        return "mixed"
    return "heuristic"


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        out.append(str(value))
    return out


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _required_nonempty_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"required non-empty string field missing: {key}")
    return value


def _resolve_path(path_str: str, *, repo_root: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return repo_root / path


def load_hotspot_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("hotspot manifest requires entries[]")
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"hotspot manifest entry must be an object: {index}")
        pack_id = _required_nonempty_string(entry, "pack_id")
        status = _required_nonempty_string(entry, "status")
        if status not in VALID_PACK_STATUSES:
            raise ValueError(f"invalid hotspot pack status for {pack_id}: {status}")
        promotion_status = _required_nonempty_string(entry, "promotion_status")
        if promotion_status not in VALID_PROMOTION_STATUSES:
            raise ValueError(
                f"invalid hotspot pack promotion_status for {pack_id}: {promotion_status}"
            )
        hold_reason = entry.get("hold_reason")
        if promotion_status == "promoted":
            if hold_reason not in (None, ""):
                raise ValueError(
                    f"hold_reason must be omitted for promoted hotspot pack: {pack_id}"
                )
        else:
            if not isinstance(hold_reason, str) or not hold_reason.strip():
                raise ValueError(
                    f"hold_reason is required for non-promoted hotspot pack: {pack_id}"
                )
    return payload


def _label(qid: str, labels: Mapping[str, str]) -> str:
    value = labels.get(qid)
    if isinstance(value, str) and value.strip():
        return value
    return qid


def _question_block(
    *,
    subject_qid: str,
    subject_label: str,
    object_qid: str,
    object_label: str,
    relation_label: str,
    relation_variant: str,
) -> list[str]:
    if relation_variant == "instance_of":
        return [
            f"Is '{subject_label}' an instance of '{object_label}'?",
            f"Is '{subject_label}' a kind of '{object_label}'?",
            f"Would it be accurate to classify '{subject_label}' under '{object_label}'?",
        ]
    if relation_variant == "subclass_of":
        return [
            f"Is '{subject_label}' a subtype of '{object_label}'?",
            f"Is '{subject_label}' a subcategory of '{object_label}'?",
            f"Is every kind of '{subject_label}' also a kind of '{object_label}'?",
        ]
    if relation_variant == "has_part":
        return [
            f"Does '{subject_label}' have part '{object_label}'?",
            f"Is '{object_label}' listed as a part of '{subject_label}'?",
        ]
    if relation_variant == "temporalized_statement":
        return [
            f"In the older window, is '{subject_label}' linked by '{relation_label}' to '{object_label}'?",
            f"In the newer window, is '{subject_label}' linked by '{relation_label}' to '{object_label}'?",
        ]
    return [
        f"Is '{subject_label}' related to '{object_label}' by '{relation_label}'?",
        f"Would '{relation_label}' apply between '{subject_label}' and '{object_label}'?",
    ]


def _question_objects(cluster_id: str, questions: list[str]) -> list[dict[str, str]]:
    return [
        {
            "question_id": f"{cluster_id}:q{index}",
            "text": question,
        }
        for index, question in enumerate(questions)
    ]


def _build_cluster(
    *,
    pack_id: str,
    cluster_index: int,
    cluster_family: str,
    expected_polarity: str,
    supporting_hotspot_family: str,
    subject_qid: str,
    object_qid: str,
    subject_label: str,
    object_label: str,
    relation_label: str,
    relation_variant: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    cluster_id = f"{pack_id}:{cluster_family}:{cluster_index}"
    return {
        "cluster_id": cluster_id,
        "cluster_family": cluster_family,
        "expected_polarity": expected_polarity,
        "supporting_hotspot_family": supporting_hotspot_family,
        "subject_qid": subject_qid,
        "subject_label": subject_label,
        "object_qid": object_qid,
        "object_label": object_label,
        "relation_label": relation_label,
        "relation_variant": relation_variant,
        "questions": _question_objects(
            cluster_id,
            _question_block(
                subject_qid=subject_qid,
                subject_label=subject_label,
                object_qid=object_qid,
                object_label=object_label,
                relation_label=relation_label,
                relation_variant=relation_variant,
            ),
        ),
        "evidence": dict(evidence),
    }


def _slice_labels(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return {}
    label_map = metadata.get("label_map")
    if not isinstance(label_map, Mapping):
        return {}
    out: dict[str, str] = {}
    for key, value in label_map.items():
        if key is None or value is None:
            continue
        out[str(key)] = str(value)
    return out


def _first_window_bundles(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    windows = payload.get("windows")
    if not isinstance(windows, list) or not windows:
        return []
    first = windows[0]
    if not isinstance(first, Mapping):
        return []
    bundles = first.get("statement_bundles")
    if not isinstance(bundles, list):
        return []
    return [item for item in bundles if isinstance(item, Mapping)]


def _report_for_payload(entry: Mapping[str, Any], payload: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    for path_str in _string_list(entry.get("source_artifacts")):
        if path_str.endswith("projection.json"):
            path = _resolve_path(path_str, repo_root=repo_root)
            if path.exists():
                return _load_json(path)
    return project_wikidata_payload(payload)


def _clusters_from_mixed_order(entry: Mapping[str, Any], payload: Mapping[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    report = _report_for_payload(entry, payload, repo_root=repo_root)
    labels = _slice_labels(payload)
    bundles = _first_window_bundles(payload)
    by_subject: dict[str, list[Mapping[str, Any]]] = {}
    for bundle in bundles:
        subject = bundle.get("subject")
        if subject is None:
            continue
        by_subject.setdefault(str(subject), []).append(bundle)
    clusters: list[dict[str, Any]] = []
    for node in report["windows"][0]["diagnostics"]["mixed_order_nodes"]:
        subject = str(node["qid"])
        subject_bundles = by_subject.get(subject, [])
        p31_targets = [str(row.get("value")) for row in subject_bundles if row.get("property") == "P31" and row.get("value") is not None]
        p279_targets = [str(row.get("value")) for row in subject_bundles if row.get("property") == "P279" and row.get("value") is not None]
        for target in p31_targets:
            clusters.append(
                _build_cluster(
                    pack_id=str(entry["pack_id"]),
                    cluster_index=len(clusters) + 1,
                    cluster_family="edge_yes",
                    expected_polarity="yes",
                    supporting_hotspot_family="mixed_order",
                    subject_qid=subject,
                    object_qid=target,
                    subject_label=_label(subject, labels),
                    object_label=_label(target, labels),
                    relation_label="instance of",
                    relation_variant="instance_of",
                    evidence={"window_id": report["windows"][0]["id"], "property_pid": "P31"},
                )
            )
        for target in p279_targets:
            clusters.append(
                _build_cluster(
                    pack_id=str(entry["pack_id"]),
                    cluster_index=len(clusters) + 1,
                    cluster_family="hierarchy",
                    expected_polarity="yes",
                    supporting_hotspot_family="mixed_order",
                    subject_qid=subject,
                    object_qid=target,
                    subject_label=_label(subject, labels),
                    object_label=_label(target, labels),
                    relation_label="subclass of",
                    relation_variant="subclass_of",
                    evidence={"window_id": report["windows"][0]["id"], "property_pid": "P279"},
                )
            )
    return clusters


def _clusters_from_scc(entry: Mapping[str, Any], payload: Mapping[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    report = _report_for_payload(entry, payload, repo_root=repo_root)
    labels = _slice_labels(payload)
    clusters: list[dict[str, Any]] = []
    for scc in report["windows"][0]["diagnostics"]["p279_sccs"]:
        members = _string_list(scc.get("members"))
        if len(members) < 2:
            continue
        for index, subject in enumerate(members):
            obj = members[(index + 1) % len(members)]
            clusters.append(
                _build_cluster(
                    pack_id=str(entry["pack_id"]),
                    cluster_index=len(clusters) + 1,
                    cluster_family="closure_conflict",
                    expected_polarity="yes",
                    supporting_hotspot_family="p279_scc",
                    subject_qid=subject,
                    object_qid=obj,
                    subject_label=_label(subject, labels),
                    object_label=_label(obj, labels),
                    relation_label="subclass of",
                    relation_variant="subclass_of",
                    evidence={"window_id": report["windows"][0]["id"], "scc_id": scc["scc_id"]},
                )
            )
    return clusters


def _clusters_from_qualifier_drift(entry: Mapping[str, Any], payload: Mapping[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    report = _report_for_payload(entry, payload, repo_root=repo_root)
    labels = _slice_labels(payload)
    clusters: list[dict[str, Any]] = []
    for row in report.get("qualifier_drift", []):
        subject = str(row["subject_qid"])
        prop = str(row["property_pid"])
        relation_label = f"{prop} qualifier pattern"
        clusters.append(
            _build_cluster(
                pack_id=str(entry["pack_id"]),
                cluster_index=len(clusters) + 1,
                cluster_family="temporalized_statement",
                expected_polarity="yes",
                supporting_hotspot_family="qualifier_drift",
                subject_qid=subject,
                object_qid=prop,
                subject_label=_label(subject, labels),
                object_label=prop,
                relation_label=relation_label,
                relation_variant="temporalized_statement",
                evidence={
                    "from_window": row["from_window"],
                    "to_window": row["to_window"],
                    "severity": row["severity"],
                    "qualifier_property_set_t1": row["qualifier_property_set_t1"],
                    "qualifier_property_set_t2": row["qualifier_property_set_t2"],
                },
            )
        )
    return clusters


def _clusters_from_entity_kind_collapse(entry: Mapping[str, Any], payload: Mapping[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    _ = repo_root
    labels = _slice_labels(payload)
    bundles = _first_window_bundles(payload)
    clusters: list[dict[str, Any]] = []
    for bundle in bundles:
        subject = bundle.get("subject")
        prop = bundle.get("property")
        value = bundle.get("value")
        if subject is None or value is None or prop not in {"P31", "P279", "P527"}:
            continue
        subject_qid = str(subject)
        object_qid = str(value)
        if prop == "P31":
            cluster_family = "kind_disambiguation"
            relation_label = "instance of"
            relation_variant = "instance_of"
        elif prop == "P279":
            cluster_family = "kind_disambiguation"
            relation_label = "subclass of"
            relation_variant = "subclass_of"
        else:
            cluster_family = "property_inheritance"
            relation_label = "has part"
            relation_variant = "has_part"
        clusters.append(
            _build_cluster(
                pack_id=str(entry["pack_id"]),
                cluster_index=len(clusters) + 1,
                cluster_family=cluster_family,
                expected_polarity="yes",
                supporting_hotspot_family="entity_kind_collapse",
                subject_qid=subject_qid,
                object_qid=object_qid,
                subject_label=_label(subject_qid, labels),
                object_label=_label(object_qid, labels),
                relation_label=relation_label,
                relation_variant=relation_variant,
                evidence={"window_id": payload["windows"][0]["id"], "property_pid": prop, "rank": bundle.get("rank", "normal")},
            )
        )
    return clusters


def _clusters_for_entry(entry: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    source_artifacts = _string_list(entry.get("source_artifacts"))
    json_artifacts = [path for path in source_artifacts if path.endswith(".json")]
    if not json_artifacts:
        raise ValueError(f"hotspot pack requires at least one JSON source artifact: {entry.get('pack_id')}")
    payload = _load_json(_resolve_path(json_artifacts[0], repo_root=repo_root))
    family = str(entry.get("hotspot_family") or "")
    if family == "mixed_order":
        clusters = _clusters_from_mixed_order(entry, payload, repo_root=repo_root)
    elif family == "p279_scc":
        clusters = _clusters_from_scc(entry, payload, repo_root=repo_root)
    elif family == "qualifier_drift":
        clusters = _clusters_from_qualifier_drift(entry, payload, repo_root=repo_root)
    elif family == "entity_kind_collapse":
        clusters = _clusters_from_entity_kind_collapse(entry, payload, repo_root=repo_root)
    else:
        raise ValueError(f"unsupported hotspot family for generation: {family}")
    semantic_basis = _derive_hotspot_semantic_basis(entry)
    semantic_candidate = build_hotspot_pack_candidate(
        basis=semantic_basis,
        pack_id=str(entry["pack_id"]),
        hotspot_family=family,
        lane_promotion_status=str(entry.get("promotion_status") or "candidate"),
        status=str(entry.get("status") or "planned_only"),
        cluster_count=len(clusters),
        hold_reason=str(entry["hold_reason"]) if entry.get("hold_reason") not in (None, "") else None,
        source_artifacts=source_artifacts,
        rule_ids=[family],
    )
    promotion = promote_hotspot_pack_candidate(semantic_candidate)
    return {
        "pack_id": str(entry["pack_id"]),
        "status": str(entry.get("status") or "planned_only"),
        "promotion_status": str(entry.get("promotion_status") or "candidate"),
        "hold_reason": (
            str(entry["hold_reason"])
            if entry.get("hold_reason") not in (None, "")
            else None
        ),
        "hotspot_family": family,
        "primary_story": str(entry.get("primary_story") or ""),
        "focus_qids": _string_list(entry.get("focus_qids")),
        "focus_pids": _string_list(entry.get("focus_pids")),
        "source_artifacts": source_artifacts,
        "candidate_cluster_families": _string_list(entry.get("candidate_cluster_families")),
        "cluster_count": len(clusters),
        "semantic_candidate": semantic_candidate,
        "semantic_basis": semantic_basis,
        "canonical_promotion_status": promotion["status"],
        "canonical_promotion_basis": promotion["basis"],
        "canonical_promotion_reason": promotion["reason"],
        "clusters": clusters,
    }


def generate_hotspot_cluster_pack(
    manifest_payload: Mapping[str, Any],
    *,
    repo_root: Path,
    pack_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    entries = manifest_payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("hotspot manifest requires entries[]")
    requested = {str(item) for item in pack_ids} if pack_ids else None
    selected_entries = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        pack_id = str(entry.get("pack_id") or "")
        if requested is not None and pack_id not in requested:
            continue
        selected_entries.append(entry)
    if requested is not None:
        missing = sorted(requested - {str(entry.get("pack_id") or "") for entry in selected_entries})
        if missing:
            raise ValueError(f"unknown hotspot pack ids: {', '.join(missing)}")
    packs = [_clusters_for_entry(entry, repo_root=repo_root) for entry in selected_entries]
    return {
        "schema_version": HOTSPOT_CLUSTER_SCHEMA_VERSION,
        "manifest_version": str(manifest_payload.get("version") or ""),
        "selection_policy": manifest_payload.get("selection_policy") or {},
        "selected_pack_ids": [pack["pack_id"] for pack in packs],
        "pack_count": len(packs),
        "cluster_count": sum(pack["cluster_count"] for pack in packs),
        "packs": packs,
    }


__all__ = [
    "HOTSPOT_CLUSTER_SCHEMA_VERSION",
    "generate_hotspot_cluster_pack",
    "load_hotspot_manifest",
]
