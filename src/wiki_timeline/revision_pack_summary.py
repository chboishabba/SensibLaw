from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def severity_rank(value: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1, "none": 0}.get(str(value or "none"), 0)


def build_pack_triage(article_results: list[dict[str, Any]], *, article_limit: int = 5, pair_limit: int = 8, section_limit: int = 10) -> dict[str, Any]:
    top_articles: list[dict[str, Any]] = []
    top_pairs: list[dict[str, Any]] = []
    top_sections: dict[str, dict[str, Any]] = {}
    top_graphs: list[dict[str, Any]] = []
    top_cycles: list[dict[str, Any]] = []
    top_regions: dict[str, dict[str, Any]] = {}

    for row in article_results:
        if not isinstance(row, Mapping):
            continue
        top_articles.append(
            {
                "article_id": row.get("article_id"),
                "title": row.get("title"),
                "status": row.get("status"),
                "top_severity": row.get("top_severity", "none"),
                "selected_primary_pair_kind": row.get("selected_primary_pair_kind"),
                "selected_primary_pair_id": row.get("selected_primary_pair_id"),
                "selected_primary_pair_score": row.get("selected_primary_pair_score"),
                "candidate_pairs_selected": row.get("candidate_pairs_selected", 0),
                "report_path": row.get("report_path"),
            }
        )
        graph_summary = row.get("contested_graph_summary") if isinstance(row.get("contested_graph_summary"), Mapping) else None
        if graph_summary:
            top_graphs.append(
                {
                    "article_id": row.get("article_id"),
                    "title": row.get("title"),
                    "top_severity": row.get("top_severity", "none"),
                    "contested_graph_path": row.get("contested_graph_path"),
                    "region_count": graph_summary.get("region_count", 0),
                    "cycle_count": graph_summary.get("cycle_count", 0),
                    "selected_pair_count": graph_summary.get("selected_pair_count", 0),
                    "graph_heat": graph_summary.get("graph_heat", 0.0),
                    "hottest_region": graph_summary.get("hottest_region"),
                }
            )
            for cycle in graph_summary.get("top_cycles") or []:
                if isinstance(cycle, Mapping):
                    top_cycles.append(
                        {
                            "article_id": row.get("article_id"),
                            "title": row.get("title"),
                            "cycle_id": cycle.get("cycle_id"),
                            "region_id": cycle.get("region_id"),
                            "region_title": cycle.get("region_title"),
                            "touch_count": cycle.get("touch_count", 0),
                            "highest_severity": cycle.get("highest_severity", "none"),
                            "pair_kinds": list(cycle.get("pair_kinds") or []),
                            "reason": cycle.get("reason"),
                            "contested_graph_path": row.get("contested_graph_path"),
                        }
                    )
            for region in graph_summary.get("top_regions") or []:
                if isinstance(region, Mapping):
                    key = str(region.get("region_id") or "")
                    candidate = {
                        "article_id": row.get("article_id"),
                        "title": row.get("title"),
                        "region_id": region.get("region_id"),
                        "region_title": region.get("title"),
                        "touch_count": region.get("touch_count", 0),
                        "total_touched_bytes": region.get("total_touched_bytes", 0),
                        "highest_severity": region.get("highest_severity", "none"),
                        "contested_graph_path": row.get("contested_graph_path"),
                    }
                    existing = top_regions.get(key)
                    if existing is None or int(candidate.get("total_touched_bytes") or 0) > int(existing.get("total_touched_bytes") or 0):
                        top_regions[key] = candidate
        for pair in row.get("pair_reports") or []:
            if not isinstance(pair, Mapping):
                continue
            top_pairs.append(
                {
                    "article_id": row.get("article_id"),
                    "title": row.get("title"),
                    "pair_id": pair.get("pair_id"),
                    "pair_kind": pair.get("pair_kind"),
                    "pair_kinds": list(pair.get("pair_kinds") or []),
                    "older_revid": pair.get("older_revid"),
                    "newer_revid": pair.get("newer_revid"),
                    "candidate_score": pair.get("candidate_score"),
                    "top_severity": pair.get("top_severity", "none"),
                    "pair_report_path": pair.get("pair_report_path"),
                }
            )
            for section in pair.get("top_changed_sections") or []:
                if not isinstance(section, Mapping):
                    continue
                name = str(section.get("section") or "").strip()
                if not name:
                    continue
                touched = int(section.get("touched_bytes") or 0)
                existing = top_sections.get(name)
                candidate = {
                    "section": name,
                    "max_touched_bytes": touched,
                    "article_id": row.get("article_id"),
                    "title": row.get("title"),
                    "pair_id": pair.get("pair_id"),
                    "pair_kind": pair.get("pair_kind"),
                    "top_severity": pair.get("top_severity", "none"),
                    "pair_report_path": pair.get("pair_report_path"),
                }
                if existing is None or touched > int(existing.get("max_touched_bytes") or 0):
                    top_sections[name] = candidate

    top_articles.sort(key=lambda item: (-severity_rank(item.get("top_severity")), -float(item.get("selected_primary_pair_score") or 0.0), -int(item.get("candidate_pairs_selected") or 0), str(item.get("article_id") or "")))
    top_pairs.sort(key=lambda item: (-severity_rank(item.get("top_severity")), -float(item.get("candidate_score") or 0.0), str(item.get("article_id") or ""), str(item.get("pair_id") or "")))
    ranked_sections = sorted(top_sections.values(), key=lambda item: (-int(item.get("max_touched_bytes") or 0), -severity_rank(item.get("top_severity")), str(item.get("section") or "")))
    top_graphs.sort(key=lambda item: (-severity_rank(item.get("top_severity")), -float(item.get("graph_heat") or 0.0), -int(item.get("cycle_count") or 0), str(item.get("article_id") or "")))
    top_cycles.sort(key=lambda item: (-severity_rank(item.get("highest_severity")), -int(item.get("touch_count") or 0), str(item.get("article_id") or ""), str(item.get("cycle_id") or "")))
    ranked_regions = sorted(top_regions.values(), key=lambda item: (-severity_rank(item.get("highest_severity")), -int(item.get("total_touched_bytes") or 0), -int(item.get("touch_count") or 0), str(item.get("region_title") or "")))
    return {
        "top_changed_articles": top_articles[:article_limit],
        "top_high_severity_pairs": top_pairs[:pair_limit],
        "top_sections_changed": ranked_sections[:section_limit],
        "top_contested_graphs": top_graphs[:article_limit],
        "top_contested_cycles": top_cycles[:pair_limit],
        "top_contested_regions": ranked_regions[:section_limit],
    }


def build_run_summary(
    *,
    schema_version: str,
    pack_id: str,
    run_id: str,
    state_db_path: Path,
    out_dir: Path,
    counts: Mapping[str, Any],
    candidate_pair_counts: Mapping[str, Any],
    contested_graph_counts: Mapping[str, Any],
    article_results: list[dict[str, Any]],
) -> dict[str, Any]:
    highest_severity = "none"
    for candidate in ("high", "medium", "low"):
        if any(row.get("top_severity") == candidate for row in article_results):
            highest_severity = candidate
            break
    return {
        "schema_version": schema_version,
        "ok": True,
        "pack_id": pack_id,
        "run_id": run_id,
        "state_db_path": str(state_db_path),
        "out_dir": str(out_dir),
        "counts": dict(counts),
        "candidate_pair_counts": dict(candidate_pair_counts),
        "contested_graph_counts": dict(contested_graph_counts),
        "highest_severity": highest_severity,
        "pack_triage": build_pack_triage(article_results),
        "articles": article_results,
    }


def human_summary(payload: Mapping[str, Any]) -> str:
    counts = payload.get("counts") or {}
    pair_counts = payload.get("candidate_pair_counts") or {}
    graph_counts = payload.get("contested_graph_counts") or {}
    lines = [
        f"pack={payload.get('pack_id')} run={payload.get('run_id')}",
        (
            "counts: "
            f"baseline_initialized={counts.get('baseline_initialized', 0)} "
            f"unchanged={counts.get('unchanged', 0)} "
            f"changed={counts.get('changed', 0)} "
            f"no_candidate_delta={counts.get('no_candidate_delta', 0)} "
            f"error={counts.get('error', 0)}"
        ),
        (
            "pairs: "
            f"considered={pair_counts.get('considered', 0)} "
            f"selected={pair_counts.get('selected', 0)} "
            f"reported={pair_counts.get('reported', 0)}"
        ),
        (
            "graphs: "
            f"articles={graph_counts.get('articles_with_graphs', 0)} "
            f"built={graph_counts.get('graphs_built', 0)} "
            f"regions={graph_counts.get('regions_detected', 0)} "
            f"cycles={graph_counts.get('cycles_detected', 0)}"
        ),
        f"highest_severity={payload.get('highest_severity')}",
    ]
    triage = payload.get("pack_triage") or {}
    top_articles = triage.get("top_changed_articles") or []
    top_pairs = triage.get("top_high_severity_pairs") or []
    top_sections = triage.get("top_sections_changed") or []
    if top_articles:
        lines.append("top_articles=" + ", ".join(f"{row.get('article_id')}:{row.get('top_severity')}:{row.get('selected_primary_pair_kind')}" for row in top_articles[:3] if isinstance(row, Mapping)))
    if top_pairs:
        lines.append("top_pairs=" + ", ".join(f"{row.get('article_id')}:{row.get('pair_kind')}:{row.get('top_severity')}" for row in top_pairs[:3] if isinstance(row, Mapping)))
    if top_sections:
        lines.append("top_sections=" + ", ".join(f"{row.get('section')}:{row.get('max_touched_bytes')}" for row in top_sections[:3] if isinstance(row, Mapping)))
    for row in payload.get("articles") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"{row.get('article_id')}: status={row.get('status')} sev={row.get('top_severity', 'none')} prev={row.get('previous_revid')} curr={row.get('current_revid')} primary_pair={row.get('selected_primary_pair_kind')} pairs={row.get('candidate_pairs_selected', 0)} report={row.get('report_path')}"
        )
    return "\n".join(lines)
