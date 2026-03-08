#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _slug(text: str) -> str:
    out: list[str] = []
    prev_sep = True
    for ch in text.casefold():
        if ch.isalnum():
            out.append(ch)
            prev_sep = False
        elif not prev_sep:
            out.append("_")
            prev_sep = True
    return "".join(out).strip("_")


def _norm(text: str) -> str:
    return " ".join(_slug(str(text or "")).split("_"))


def _activity_ref_id(row: dict[str, Any]) -> str:
    payload = {
        "ts": str(row.get("ts") or ""),
        "hour": row.get("hour"),
        "kind": str(row.get("kind") or ""),
        "detail": str(row.get("detail") or ""),
        "source_path": str(row.get("source_path") or ""),
        "meta": row.get("meta") if isinstance(row.get("meta"), dict) else {},
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"activity:{digest}"


def _mapping_action_id(run_id: str, activity_ref_id: str, suffix: str) -> str:
    return f"map:{_slug(run_id)}:{_slug(activity_ref_id)}:{suffix}:{time.time_ns()}"


def _timeline_activity_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = payload.get("timeline") if isinstance(payload.get("timeline"), list) else []
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(timeline):
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        item = {
            "activityRefId": _activity_ref_id(row),
            "timelineIndex": idx,
            "ts": str(row.get("ts") or ""),
            "hour": row.get("hour"),
            "kind": str(row.get("kind") or "unknown"),
            "detail": str(row.get("detail") or ""),
            "sourcePath": str(row.get("source_path") or ""),
            "meta": meta,
        }
        rows.append(item)
    return rows


def _dashboard_totals(payload: dict[str, Any]) -> dict[str, float]:
    freq = payload.get("frequency_by_hour") if isinstance(payload.get("frequency_by_hour"), dict) else {}
    totals: dict[str, float] = {}
    for lane, bins in freq.items():
        if isinstance(bins, list):
            totals[str(lane)] = float(sum(int(v) for v in bins if isinstance(v, (int, float))))
    if not totals:
        timeline = _timeline_activity_rows(payload)
        by_kind = Counter(str(row.get("kind") or "unknown") for row in timeline if isinstance(row, dict))
        totals = {kind: float(count) for kind, count in by_kind.items()}
    return totals


def _clip(value: str, limit: int = 80) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _lexical_candidates(row: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    field_texts = {
        "detail": str(row.get("detail") or ""),
        "sourcePath": str(row.get("sourcePath") or ""),
        "meta": json.dumps(row.get("meta", {}), sort_keys=True) if isinstance(row.get("meta"), dict) else "",
    }
    normalized_fields = {key: _norm(value) for key, value in field_texts.items()}
    candidates: list[dict[str, Any]] = []
    for node in plan.get("nodes", []):
        title = str(node.get("title") or "")
        matched_term = _norm(title)
        if not matched_term:
            continue
        matched_fields = [field for field, text in normalized_fields.items() if matched_term in text]
        if not matched_fields:
            continue
        snippets = [
            {
                "field": field,
                "snippet": _clip(field_texts[field]),
            }
            for field in matched_fields
            if field_texts[field]
        ]
        candidates.append(
            {
                "planNodeId": str(node["planNodeId"]),
                "matchedTitle": title,
                "matchedTerm": matched_term,
                "matchedFields": matched_fields,
                "snippets": snippets,
                "score": len(matched_fields),
            }
        )
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["matchedTitle"]), str(item["planNodeId"])))
    return candidates


def _recommendation_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {
            "recommendedAction": "none",
            "recommendedPlanNodeId": None,
            "recommendationReason": "",
            "recommendationConfidence": "low",
            "recommendationKind": "none",
            "recommendationCandidates": [],
        }
    top = candidates[0]
    top_alt = candidates[1] if len(candidates) > 1 else None
    candidate_slice = [
        {
            "planNodeId": str(candidate["planNodeId"]),
            "matchedTitle": str(candidate["matchedTitle"]),
            "matchedFields": list(candidate["matchedFields"]),
            "score": int(candidate["score"]),
        }
        for candidate in candidates[:2]
    ]
    if top_alt is None:
        return {
            "recommendedAction": "auto_link_safe",
            "recommendedPlanNodeId": str(top["planNodeId"]),
            "recommendationReason": f"single lexical title match in {', '.join(top['matchedFields'])}",
            "recommendationConfidence": "high",
            "recommendationKind": "auto_link_safe",
            "recommendationCandidates": candidate_slice,
        }
    if int(top["score"]) > int(top_alt["score"]):
        return {
            "recommendedAction": "auto_link_safe",
            "recommendedPlanNodeId": str(top["planNodeId"]),
            "recommendationReason": f"dominant lexical match in {', '.join(top['matchedFields'])}; top alternative weaker",
            "recommendationConfidence": "high",
            "recommendationKind": "auto_link_safe",
            "recommendationCandidates": candidate_slice,
        }
    return {
        "recommendedAction": "review_primary_vs_alternative",
        "recommendedPlanNodeId": str(top["planNodeId"]),
        "recommendationReason": "multiple lexical candidates without dominant winner",
        "recommendationConfidence": "medium",
        "recommendationKind": "review_primary_vs_alternative",
        "recommendationCandidates": candidate_slice,
    }


def _match_actuals_to_plan(
    payload: dict[str, Any],
    plan: dict[str, Any],
    reviewed_mappings: list[dict[str, Any]],
    reviewed_current: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]], list[dict[str, Any]], dict[str, int]]:
    timeline = _timeline_activity_rows(payload)
    left_weights = _dashboard_totals(payload)
    node_matches: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    reviewed_by_activity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mapping in reviewed_mappings:
        reviewed_by_activity[str(mapping.get("activityRefId") or "")].append(mapping)
    current_by_activity = {
        str(mapping.get("activityRefId") or ""): mapping
        for mapping in reviewed_current
    }
    activity_rows: list[dict[str, Any]] = []
    counters = {
        "reviewed_linked": 0,
        "reviewed_reassigned": 0,
        "reviewed_unlinked": 0,
        "reviewed_abstained": 0,
        "reviewed_override_count": 0,
        "reviewed_unresolved_count": 0,
        "lexical_linked": 0,
        "lexical_ambiguous": 0,
        "recommended_safe": 0,
        "recommended_review": 0,
        "recommended_abstain": 0,
        "unmapped": 0,
    }
    for row in timeline:
        kind = str(row.get("kind") or "unknown")
        matched_plan_node_ids: list[str] = []
        mapping_source = "unmapped"
        mapping_receipts: list[dict[str, Any]] = []
        mapping_status = "unmapped"
        effective_plan_node_id: str | None = None
        lexical_explanation: dict[str, Any] | None = None
        recommendation = {
            "recommendedAction": "none",
            "recommendedPlanNodeId": None,
            "recommendationReason": "",
            "recommendationConfidence": "low",
            "recommendationKind": "none",
            "recommendationCandidates": [],
        }
        reviewed = reviewed_by_activity.get(str(row["activityRefId"]), [])
        current = current_by_activity.get(str(row["activityRefId"]))
        if current:
            mapping_source = "reviewed"
            mapping_status = str(current.get("status") or "linked")
            effective_plan_node_id = str(current.get("planNodeId") or "") or None
            mapping_receipts = [
                {"kind": "current_status", "value": mapping_status},
                {"kind": "effective_mapping_id", "value": str(current.get("mappingId") or "")},
            ]
            if current.get("note"):
                mapping_receipts.append({"kind": "review_note", "value": str(current.get("note"))})
            for mapping in reviewed[:3]:
                mapping_receipts.extend(mapping.get("receipts") or [])
            if mapping_status in {"linked", "reassigned"} and effective_plan_node_id:
                node_matches[effective_plan_node_id][kind] += 1.0
                matched_plan_node_ids.append(effective_plan_node_id)
                counters["reviewed_linked" if mapping_status == "linked" else "reviewed_reassigned"] += 1
                counters["reviewed_override_count"] += 1
            elif mapping_status == "unlinked":
                counters["reviewed_unlinked"] += 1
                counters["reviewed_unresolved_count"] += 1
            elif mapping_status == "abstained":
                counters["reviewed_abstained"] += 1
                counters["reviewed_unresolved_count"] += 1
            recommendation = {
                "recommendedAction": "none",
                "recommendedPlanNodeId": None,
                "recommendationReason": "reviewed state already exists",
                "recommendationConfidence": "low",
                "recommendationKind": "none",
                "recommendationCandidates": [],
            }
        if not matched_plan_node_ids:
            if mapping_source != "reviewed":
                candidates = _lexical_candidates(row, plan)
                if candidates:
                    mapping_source = "lexical"
                    mapping_status = "linked"
                    top_alternative = candidates[1] if len(candidates) > 1 else None
                    recommendation = _recommendation_from_candidates(candidates)
                    lexical_explanation = {
                        "planNodeId": str(candidates[0]["planNodeId"]),
                        "matchedTitle": str(candidates[0]["matchedTitle"]),
                        "matchedTerm": str(candidates[0]["matchedTerm"]),
                        "matchedFields": list(candidates[0]["matchedFields"]),
                        "snippets": list(candidates[0]["snippets"]),
                        "candidateCount": len(candidates),
                    }
                    if top_alternative is not None:
                        lexical_explanation["topAlternative"] = {
                            "planNodeId": str(top_alternative["planNodeId"]),
                            "matchedTitle": str(top_alternative["matchedTitle"]),
                            "matchedTerm": str(top_alternative["matchedTerm"]),
                            "matchedFields": list(top_alternative["matchedFields"]),
                        }
                    for candidate in candidates:
                        plan_node_id = str(candidate["planNodeId"])
                        node_matches[plan_node_id][kind] += 1.0
                        matched_plan_node_ids.append(plan_node_id)
                    mapping_receipts = [
                        {
                            "kind": "lexical_match",
                            "value": str(candidates[0]["matchedTerm"]),
                        },
                        {
                            "kind": "lexical_fields",
                            "value": ",".join(str(field) for field in candidates[0]["matchedFields"]),
                        },
                    ]
                    counters["lexical_linked"] += 1
                    if len(candidates) > 1:
                        counters["lexical_ambiguous"] = counters.get("lexical_ambiguous", 0) + 1
                    if recommendation["recommendedAction"] == "auto_link_safe":
                        counters["recommended_safe"] += 1
                    elif recommendation["recommendedAction"] == "review_primary_vs_alternative":
                        counters["recommended_review"] += 1
                else:
                    mapping_status = "unmapped"
                    node_matches["unmapped"]["unmapped"] += 1.0
                    counters["unmapped"] += 1
                    recommendation = {
                        "recommendedAction": "abstain_recommended",
                        "recommendedPlanNodeId": None,
                        "recommendationReason": "no lexical candidates were strong enough to map this row",
                        "recommendationConfidence": "low",
                        "recommendationKind": "abstain_recommended",
                        "recommendationCandidates": [],
                    }
                    counters["recommended_abstain"] += 1
        activity_rows.append(
            {
                **row,
                "mappingSource": mapping_source,
                "mappingStatus": mapping_status,
                "effectivePlanNodeId": effective_plan_node_id,
                "matchedPlanNodeIds": matched_plan_node_ids,
                "mappingReceipts": mapping_receipts,
                "mappingHistoryPreview": reviewed[:5],
                "lexicalExplanation": lexical_explanation,
                **recommendation,
            }
        )
    left = [
        {
            "id": f"actual:{kind}",
            "label": f"{kind} ({int(weight)})",
            "weight": float(weight),
            "color": "#dbeafe" if kind != "unmapped" else "#fde68a",
            "tooltip": f"Observed {kind} weight {weight:.0f}",
        }
        for kind, weight in sorted(left_weights.items(), key=lambda item: (-item[1], item[0]))
        if weight > 0
    ]
    if node_matches.get("unmapped", {}).get("unmapped"):
        left.append(
            {
                "id": "actual:unmapped",
                "label": f"unmapped ({int(node_matches['unmapped']['unmapped'])})",
                "weight": float(node_matches["unmapped"]["unmapped"]),
                "color": "#fde68a",
                "tooltip": "Observed activity not linked to any mission node",
            }
        )
    edges: list[dict[str, Any]] = []
    for plan_node_id, kinds in sorted(node_matches.items()):
        if plan_node_id == "unmapped":
            continue
        for kind, weight in sorted(kinds.items(), key=lambda item: (-item[1], item[0])):
            if weight <= 0:
                continue
            edges.append(
                {
                    "from": f"actual:{kind}",
                    "to": f"plan:{plan_node_id}",
                    "weight": float(weight),
                }
            )
    return left, edges, node_matches, activity_rows, counters


def _build_layered_graph(plan: dict[str, Any], drift_by_node: dict[str, dict[str, float]]) -> dict[str, Any]:
    layers_by_kind = {
        "mission": [],
        "phase": [],
        "task": [],
        "subtask": [],
        "set": [],
    }
    for node in plan.get("nodes", []):
        kind = str(node.get("nodeKind") or "task")
        drift = drift_by_node.get(str(node.get("planNodeId")), {})
        actual = drift.get("actual", 0.0)
        target = drift.get("target", float(node.get("targetWeight") or 0.0))
        label = f"{node.get('title')} · A {actual:.0f} / T {target:.0f}"
        item = {
            "id": f"plan:{node['planNodeId']}",
            "label": label,
            "color": "#dcfce7" if actual >= target and target > 0 else "#fee2e2" if target > 0 else "#e5e7eb",
            "tooltip": json.dumps(
                {
                    "status": node.get("status"),
                    "sourceKind": node.get("sourceKind"),
                    "deadline": node.get("deadline"),
                },
                sort_keys=True,
            ),
            "scale": max(0.8, min(2.0, 0.8 + (target / 4.0))),
        }
        layers_by_kind.setdefault(kind, []).append(item)
    order = ["mission", "phase", "task", "subtask", "set"]
    layers = [{"id": kind, "title": kind.title(), "nodes": layers_by_kind.get(kind, [])} for kind in order if layers_by_kind.get(kind)]
    edges = [
        {
            "from": f"plan:{row['fromPlanNodeId']}",
            "to": f"plan:{row['toPlanNodeId']}",
            "label": str(row.get("edgeKind") or ""),
            "kind": "sequence" if str(row.get("edgeKind")) == "depends_on" else "context",
        }
        for row in plan.get("edges", [])
    ]
    return {"layers": layers, "edges": edges}


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT run_id FROM mission_runs ORDER BY datetime(created_at) DESC, run_id DESC LIMIT 1").fetchone()
    return str(row["run_id"]) if row is not None else None


def build_mission_lens_report(
    *,
    itir_db_path: Path,
    sb_db_path: Path,
    date: str,
    run_id: str | None,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "SensibLaw") not in sys.path:
        sys.path.insert(0, str(repo_root / "SensibLaw"))
    if str(repo_root / "StatiBaker") not in sys.path:
        sys.path.insert(0, str(repo_root / "StatiBaker"))
    from src.gwb_us_law.semantic import (  # noqa: PLC0415
        ensure_gwb_semantic_schema,
        load_mission_actual_mapping_current,
        load_mission_actual_mappings,
        load_mission_observer,
        load_mission_plan,
    )
    from sb.dashboard_store_sqlite import DashboardKey, load_best_daily_payload_for_date, load_dashboard_payload  # noqa: PLC0415

    with sqlite3.connect(str(itir_db_path)) as itir_conn:
        itir_conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(itir_conn)
        active_run_id = run_id or _latest_run_id(itir_conn)
        if not active_run_id:
            return {
                "date": date,
                "run_id": None,
                "mission_observer": {"summary": {}, "missions": [], "followups": [], "sb_observer_overlays": [], "unavailableReason": "No mission runs exist yet."},
                "planning_graph": {"nodes": [], "edges": []},
                "actual_allocation": {"left": [], "right": [], "edges": []},
                "deadline_summary": [],
                "drift_summary": [],
                "sb_dashboard_source": None,
            }
        mission_observer = load_mission_observer(itir_conn, run_id=active_run_id)
        plan = load_mission_plan(itir_conn, run_id=active_run_id)
        reviewed_mappings = load_mission_actual_mappings(itir_conn, run_id=active_run_id)
        reviewed_current = load_mission_actual_mapping_current(itir_conn, run_id=active_run_id)

    dashboard = load_best_daily_payload_for_date(db_path=sb_db_path, date=date)
    if dashboard is None:
        dashboard = (load_dashboard_payload(db_path=sb_db_path, key=DashboardKey(date=date, view="daily", scope="scoped", window_days=0)), "scoped")
    payload = dashboard[0] if dashboard is not None else {}
    scope = dashboard[1] if dashboard is not None else None
    left, actual_edges, node_matches, activity_rows, mapping_summary = _match_actuals_to_plan(
        payload or {}, plan, reviewed_mappings, reviewed_current
    )
    right = [
        {
            "id": f"plan:{node['planNodeId']}",
            "label": f"{node['title']} ({int(node['targetWeight'])})",
            "weight": float(node["targetWeight"]),
            "color": "#dcfce7" if str(node.get("sourceKind")) == "manual" else "#ede9fe",
            "tooltip": json.dumps(
                {
                    "status": node.get("status"),
                    "deadline": node.get("deadline"),
                },
                sort_keys=True,
            ),
        }
        for node in plan.get("nodes", [])
    ]
    drift_summary = []
    drift_by_node: dict[str, dict[str, float]] = {}
    for node in plan.get("nodes", []):
        actual = float(sum(node_matches.get(str(node["planNodeId"]), {}).values()))
        target = float(node.get("targetWeight") or 0.0)
        drift = actual - target
        drift_by_node[str(node["planNodeId"])] = {"actual": actual, "target": target, "drift": drift}
        drift_summary.append(
            {
                "planNodeId": str(node["planNodeId"]),
                "title": str(node["title"]),
                "actualWeight": actual,
                "targetWeight": target,
                "drift": drift,
                "status": "over" if drift > 0 else "under" if drift < 0 else "matched",
            }
        )
    deadline_summary = [
        {
            "planNodeId": str(node["planNodeId"]),
            "title": str(node["title"]),
            **(node.get("deadline") or {}),
        }
        for node in plan.get("nodes", [])
        if isinstance(node.get("deadline"), dict) and ((node["deadline"] or {}).get("rawPhrase") or (node["deadline"] or {}).get("dueStart"))
    ]
    return {
        "date": date,
        "run_id": active_run_id,
        "sb_dashboard_source": {"dbPath": str(sb_db_path), "scope": scope},
        "mission_observer": mission_observer,
        "planning_graph": plan,
        "actual_allocation": {"left": left, "right": right, "edges": actual_edges},
        "deadline_summary": deadline_summary,
        "drift_summary": sorted(drift_summary, key=lambda row: (-abs(float(row["drift"])), str(row["title"]))),
        "layered_graph": _build_layered_graph(plan, drift_by_node),
        "activity_rows": activity_rows[:80],
        "actual_mapping_summary": mapping_summary,
        "effective_actual_mappings": reviewed_current,
        "reviewed_actual_mappings": reviewed_mappings,
        "summary": {
            "planning_node_count": len(plan.get("nodes", [])),
            "planning_edge_count": len(plan.get("edges", [])),
            "mapped_actual_edge_count": len(actual_edges),
            "deadline_count": len(deadline_summary),
            "mission_count": int((mission_observer.get("summary") or {}).get("mission_count", 0)),
            "reviewed_actual_mapping_count": len(reviewed_current),
        },
    }


def apply_safe_recommendations(
    *,
    itir_db_path: Path,
    sb_db_path: Path,
    date: str,
    run_id: str,
) -> dict[str, Any]:
    report = build_mission_lens_report(
        itir_db_path=itir_db_path,
        sb_db_path=sb_db_path,
        date=date,
        run_id=run_id,
    )
    safe_rows = [
        row
        for row in report.get("activity_rows", [])
        if str(row.get("recommendedAction") or "") == "auto_link_safe"
        and str(row.get("recommendationConfidence") or "") == "high"
        and not row.get("effectivePlanNodeId")
        and str(row.get("mappingSource") or "") != "reviewed"
        and str(row.get("recommendedPlanNodeId") or "")
    ]
    if not safe_rows:
        return {
            "run_id": run_id,
            "date": date,
            "appliedCount": 0,
            "appliedActivityRefIds": [],
            "note": "No safe recommendations were eligible for bulk apply.",
        }
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "SensibLaw") not in sys.path:
        sys.path.insert(0, str(repo_root / "SensibLaw"))
    from src.gwb_us_law.semantic import ensure_gwb_semantic_schema, upsert_mission_actual_mapping  # noqa: PLC0415

    applied_ids: list[str] = []
    with sqlite3.connect(str(itir_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        for row in safe_rows:
            activity_ref_id = str(row["activityRefId"])
            plan_node_id = str(row["recommendedPlanNodeId"])
            upsert_mission_actual_mapping(
                conn,
                run_id=run_id,
                mapping_id=_mapping_action_id(run_id, activity_ref_id, _slug(plan_node_id)),
                activity_ref_id=activity_ref_id,
                plan_node_id=plan_node_id,
                mapping_kind="reviewed_link",
                status="linked",
                confidence_tier="high",
                note=f"Bulk applied safe recommendation: {row.get('recommendationReason') or 'safe lexical match'}",
                receipts=[
                    ("authoring", "mission_lens_bulk_safe"),
                    ("recommendation_kind", str(row.get("recommendationKind") or "auto_link_safe")),
                    ("recommendation_reason", str(row.get("recommendationReason") or "")),
                    ("activity_ref_id", activity_ref_id),
                ],
            )
            applied_ids.append(activity_ref_id)
        conn.commit()
    return {
        "run_id": run_id,
        "date": date,
        "appliedCount": len(applied_ids),
        "appliedActivityRefIds": applied_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or mutate the fused mission lens artifact.")
    parser.add_argument("--itir-db-path", default=".cache_local/itir.sqlite")
    parser.add_argument("--sb-db-path", default="")
    sub = parser.add_subparsers(dest="cmd", required=True)

    report_p = sub.add_parser("report")
    report_p.add_argument("--date", required=True)
    report_p.add_argument("--run-id", default="")

    add_p = sub.add_parser("add-node")
    add_p.add_argument("--run-id", required=True)
    add_p.add_argument("--plan-node-id", default="")
    add_p.add_argument("--node-kind", default="task")
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--status", default="active")
    add_p.add_argument("--source-kind", default="manual")
    add_p.add_argument("--mission-id", default="")
    add_p.add_argument("--parent-plan-node-id", default="")
    add_p.add_argument("--target-weight", type=float, default=1.0)
    add_p.add_argument("--raw-deadline", default="")
    add_p.add_argument("--due-start", default="")
    add_p.add_argument("--due-end", default="")
    add_p.add_argument("--certainty-kind", default="")
    add_p.add_argument("--urgency-level", default="")
    add_p.add_argument("--flexibility-level", default="")

    map_p = sub.add_parser("add-mapping")
    map_p.add_argument("--run-id", required=True)
    map_p.add_argument("--activity-ref-id", required=True)
    map_p.add_argument("--plan-node-id", required=True)
    map_p.add_argument("--mapping-id", default="")
    map_p.add_argument("--mapping-kind", default="reviewed_link")
    map_p.add_argument("--status", default="linked")
    map_p.add_argument("--confidence-tier", default="high")
    map_p.add_argument("--note", default="")
    map_p.add_argument("--authoring", default="mission_lens_ui")
    map_p.add_argument("--recommendation-kind", default="")
    map_p.add_argument("--recommendation-reason", default="")

    reassign_p = sub.add_parser("reassign-mapping")
    reassign_p.add_argument("--run-id", required=True)
    reassign_p.add_argument("--activity-ref-id", required=True)
    reassign_p.add_argument("--plan-node-id", required=True)
    reassign_p.add_argument("--mapping-id", default="")
    reassign_p.add_argument("--confidence-tier", default="high")
    reassign_p.add_argument("--note", default="")

    unlink_p = sub.add_parser("unlink-mapping")
    unlink_p.add_argument("--run-id", required=True)
    unlink_p.add_argument("--activity-ref-id", required=True)
    unlink_p.add_argument("--mapping-id", default="")
    unlink_p.add_argument("--confidence-tier", default="high")
    unlink_p.add_argument("--note", default="")

    abstain_p = sub.add_parser("abstain-mapping")
    abstain_p.add_argument("--run-id", required=True)
    abstain_p.add_argument("--activity-ref-id", required=True)
    abstain_p.add_argument("--mapping-id", default="")
    abstain_p.add_argument("--confidence-tier", default="high")
    abstain_p.add_argument("--note", default="")

    bulk_p = sub.add_parser("apply-safe-recommendations")
    bulk_p.add_argument("--run-id", required=True)
    bulk_p.add_argument("--date", required=True)
    bulk_p.add_argument("--sb-db-path", default="")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "SensibLaw") not in sys.path:
        sys.path.insert(0, str(repo_root / "SensibLaw"))
    from src.gwb_us_law.semantic import ensure_gwb_semantic_schema, upsert_mission_actual_mapping, upsert_mission_plan_node  # noqa: PLC0415

    itir_db_path = Path(args.itir_db_path).expanduser().resolve()
    sb_db_path = Path(args.sb_db_path).expanduser().resolve() if getattr(args, "sb_db_path", "") else (repo_root / "StatiBaker" / "runs" / "dashboard.sqlite")
    if args.cmd == "report":
        payload = build_mission_lens_report(
            itir_db_path=itir_db_path,
            sb_db_path=sb_db_path,
            date=str(args.date),
            run_id=str(args.run_id or "") or None,
        )
    elif args.cmd == "apply-safe-recommendations":
        payload = apply_safe_recommendations(
            itir_db_path=itir_db_path,
            sb_db_path=sb_db_path,
            date=str(args.date),
            run_id=str(args.run_id),
        )
    elif args.cmd == "add-node":
        with sqlite3.connect(str(itir_db_path)) as conn:
            conn.row_factory = sqlite3.Row
            ensure_gwb_semantic_schema(conn)
            payload = upsert_mission_plan_node(
                conn,
                run_id=str(args.run_id),
                plan_node_id=str(args.plan_node_id or f"plan:manual:{_slug(args.title)}"),
                node_kind=str(args.node_kind),
                title=str(args.title),
                status=str(args.status),
                source_kind=str(args.source_kind),
                mission_id=str(args.mission_id or "") or None,
                parent_plan_node_id=str(args.parent_plan_node_id or "") or None,
                target_weight=float(args.target_weight),
                raw_phrase=str(args.raw_deadline or "") or None,
                due_start=str(args.due_start or "") or None,
                due_end=str(args.due_end or "") or None,
                certainty_kind=str(args.certainty_kind or "") or None,
                urgency_level=str(args.urgency_level or "") or None,
                flexibility_level=str(args.flexibility_level or "") or None,
                receipts=[("source_kind", str(args.source_kind)), ("authoring", "mission_lens_ui")],
            )
            conn.commit()
    else:
        with sqlite3.connect(str(itir_db_path)) as conn:
            conn.row_factory = sqlite3.Row
            ensure_gwb_semantic_schema(conn)
            if args.cmd == "add-mapping":
                mapping_id = str(args.mapping_id or _mapping_action_id(args.run_id, args.activity_ref_id, _slug(args.plan_node_id)))
                mapping_kind = str(args.mapping_kind)
                status = str(args.status)
                plan_node_id = str(args.plan_node_id)
                receipts = [
                    ("mapping_kind", str(args.mapping_kind)),
                    ("authoring", str(args.authoring or "mission_lens_ui")),
                    ("activity_ref_id", str(args.activity_ref_id)),
                ]
                if str(args.recommendation_kind or "").strip():
                    receipts.append(("recommendation_kind", str(args.recommendation_kind)))
                if str(args.recommendation_reason or "").strip():
                    receipts.append(("recommendation_reason", str(args.recommendation_reason)))
            elif args.cmd == "reassign-mapping":
                mapping_id = str(args.mapping_id or _mapping_action_id(args.run_id, args.activity_ref_id, _slug(args.plan_node_id)))
                mapping_kind = "reviewed_reassign"
                status = "reassigned"
                plan_node_id = str(args.plan_node_id)
                receipts = [
                    ("mapping_kind", "reviewed_reassign"),
                    ("authoring", "mission_lens_ui"),
                    ("activity_ref_id", str(args.activity_ref_id)),
                ]
            elif args.cmd == "unlink-mapping":
                mapping_id = str(args.mapping_id or _mapping_action_id(args.run_id, args.activity_ref_id, "unlinked"))
                mapping_kind = "reviewed_unlink"
                status = "unlinked"
                plan_node_id = None
                receipts = [
                    ("mapping_kind", "reviewed_unlink"),
                    ("authoring", "mission_lens_ui"),
                    ("activity_ref_id", str(args.activity_ref_id)),
                ]
            else:
                mapping_id = str(args.mapping_id or _mapping_action_id(args.run_id, args.activity_ref_id, "abstained"))
                mapping_kind = "reviewed_abstain"
                status = "abstained"
                plan_node_id = None
                receipts = [
                    ("mapping_kind", "reviewed_abstain"),
                    ("authoring", "mission_lens_ui"),
                    ("activity_ref_id", str(args.activity_ref_id)),
                ]
            payload = upsert_mission_actual_mapping(
                conn,
                run_id=str(args.run_id),
                mapping_id=mapping_id,
                activity_ref_id=str(args.activity_ref_id),
                plan_node_id=plan_node_id,
                mapping_kind=mapping_kind,
                status=status,
                confidence_tier=str(args.confidence_tier),
                note=str(args.note),
                receipts=receipts,
            )
            conn.commit()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
