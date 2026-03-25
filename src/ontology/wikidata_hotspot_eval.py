from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


HOTSPOT_RESPONSE_SCHEMA_VERSION = "wikidata_hotspot_responses/v1"
HOTSPOT_EVAL_SCHEMA_VERSION = "wikidata_hotspot_eval/v1"
VALID_LABELS = {"yes", "no", "abstain"}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"required string field missing or empty: {key}")
    return value


def _as_question_lookup(cluster_pack: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    packs = cluster_pack.get("packs")
    if not isinstance(packs, list):
        raise ValueError("cluster pack requires packs[]")
    lookup: dict[str, dict[str, Any]] = {}
    for pack in packs:
        if not isinstance(pack, Mapping):
            continue
        pack_id = _require_string(pack, "pack_id")
        clusters = pack.get("clusters")
        if not isinstance(clusters, list):
            raise ValueError(f"cluster pack entry requires clusters[]: {pack_id}")
        for cluster in clusters:
            if not isinstance(cluster, Mapping):
                continue
            cluster_id = _require_string(cluster, "cluster_id")
            questions = cluster.get("questions")
            if not isinstance(questions, list) or not questions:
                raise ValueError(f"cluster requires questions[]: {cluster_id}")
            question_lookup: dict[str, dict[str, Any]] = {}
            for question in questions:
                if not isinstance(question, Mapping):
                    raise ValueError(f"cluster question entries must be objects: {cluster_id}")
                question_id = _require_string(question, "question_id")
                _require_string(question, "text")
                if question_id in question_lookup:
                    raise ValueError(f"duplicate question id in cluster pack: {question_id}")
                question_lookup[question_id] = dict(question)
            lookup[cluster_id] = {
                "pack_id": pack_id,
                "cluster_family": _require_string(cluster, "cluster_family"),
                "supporting_hotspot_family": _require_string(cluster, "supporting_hotspot_family"),
                "expected_polarity": _require_string(cluster, "expected_polarity"),
                "questions": question_lookup,
            }
    return lookup


def load_hotspot_response_bundle(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if payload.get("schema_version") != HOTSPOT_RESPONSE_SCHEMA_VERSION:
        raise ValueError(
            f"response bundle schema_version must be {HOTSPOT_RESPONSE_SCHEMA_VERSION}"
        )
    _require_string(payload, "model_run_id")
    _require_string(payload, "model_id")
    _require_string(payload, "prompt_profile")
    responses = payload.get("responses")
    if not isinstance(responses, list) or not responses:
        raise ValueError("response bundle requires non-empty responses[]")
    return payload


def evaluate_hotspot_cluster_pack(
    cluster_pack: Mapping[str, Any],
    response_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    question_lookup_by_cluster = _as_question_lookup(cluster_pack)
    bundle_responses = response_bundle.get("responses")
    if not isinstance(bundle_responses, list):
        raise ValueError("response bundle requires responses[]")

    response_index: dict[str, dict[str, dict[str, Any]]] = {}
    for row in bundle_responses:
        if not isinstance(row, Mapping):
            raise ValueError("response rows must be objects")
        cluster_id = _require_string(row, "cluster_id")
        question_id = _require_string(row, "question_id")
        label = _require_string(row, "label")
        if label not in VALID_LABELS:
            raise ValueError(f"invalid response label '{label}' for {question_id}")
        cluster = question_lookup_by_cluster.get(cluster_id)
        if cluster is None:
            raise ValueError(f"response references unknown cluster_id: {cluster_id}")
        if question_id not in cluster["questions"]:
            raise ValueError(
                f"response references unknown question_id '{question_id}' for cluster '{cluster_id}'"
            )
        cluster_rows = response_index.setdefault(cluster_id, {})
        if question_id in cluster_rows:
            raise ValueError(f"duplicate response for question_id: {question_id}")
        item = {
            "question_id": question_id,
            "label": label,
        }
        raw_text = row.get("raw_text")
        if raw_text is not None:
            item["raw_text"] = str(raw_text)
        cluster_rows[question_id] = item

    cluster_results: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "consistent": 0,
        "inconsistent": 0,
        "incomplete": 0,
        "abstained": 0,
    }
    by_hotspot_family: dict[str, dict[str, int]] = {}
    by_cluster_family: dict[str, dict[str, int]] = {}

    for cluster_id, cluster in question_lookup_by_cluster.items():
        responses = response_index.get(cluster_id)
        if responses is None:
            raise ValueError(f"missing responses for cluster_id: {cluster_id}")
        missing = sorted(set(cluster["questions"]) - set(responses))
        if missing:
            raise ValueError(
                f"missing responses for cluster_id '{cluster_id}': {', '.join(missing)}"
            )
        ordered_results = [responses[question_id] for question_id in cluster["questions"]]
        distribution = {"yes": 0, "no": 0, "abstain": 0}
        for item in ordered_results:
            distribution[item["label"]] += 1
        non_abstain = [item["label"] for item in ordered_results if item["label"] != "abstain"]
        expected = cluster["expected_polarity"]
        opposite = "no" if expected == "yes" else "yes"
        if not non_abstain:
            classification = "abstained"
        elif all(label == expected for label in non_abstain):
            classification = "consistent"
        elif all(label == opposite for label in non_abstain):
            classification = "incomplete"
        else:
            classification = "inconsistent"

        result = {
            "cluster_id": cluster_id,
            "pack_id": cluster["pack_id"],
            "cluster_family": cluster["cluster_family"],
            "supporting_hotspot_family": cluster["supporting_hotspot_family"],
            "expected_polarity": expected,
            "question_results": ordered_results,
            "answer_distribution": distribution,
            "classification": classification,
        }
        cluster_results.append(result)
        counts["total"] += 1
        counts[classification] += 1

        hotspot_bucket = by_hotspot_family.setdefault(
            cluster["supporting_hotspot_family"],
            {"total": 0, "consistent": 0, "inconsistent": 0, "incomplete": 0, "abstained": 0},
        )
        hotspot_bucket["total"] += 1
        hotspot_bucket[classification] += 1

        cluster_bucket = by_cluster_family.setdefault(
            cluster["cluster_family"],
            {"total": 0, "consistent": 0, "inconsistent": 0, "incomplete": 0, "abstained": 0},
        )
        cluster_bucket["total"] += 1
        cluster_bucket[classification] += 1

    total = counts["total"] or 1
    return {
        "schema_version": HOTSPOT_EVAL_SCHEMA_VERSION,
        "model_run_id": _require_string(response_bundle, "model_run_id"),
        "model_id": _require_string(response_bundle, "model_id"),
        "prompt_profile": _require_string(response_bundle, "prompt_profile"),
        "manifest_version": _require_string(cluster_pack, "manifest_version"),
        "selected_pack_ids": list(cluster_pack.get("selected_pack_ids") or []),
        "cluster_results": cluster_results,
        "summary": {
            "cluster_counts": counts,
            "inconsistency_rate": counts["inconsistent"] / total,
            "incompleteness_rate": counts["incomplete"] / total,
            "abstention_rate": counts["abstained"] / total,
            "by_hotspot_family": by_hotspot_family,
            "by_cluster_family": by_cluster_family,
        },
    }


__all__ = [
    "HOTSPOT_EVAL_SCHEMA_VERSION",
    "HOTSPOT_RESPONSE_SCHEMA_VERSION",
    "VALID_LABELS",
    "evaluate_hotspot_cluster_pack",
    "load_hotspot_response_bundle",
]
