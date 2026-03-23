#!/usr/bin/env python3
"""Score stored Wikipedia snapshot manifests for article-wide ingest coverage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts.report_wiki_random_lexer_coverage import score_snapshot_payload as score_reducer_payload  # noqa: E402
from scripts.report_wiki_random_timeline_readiness import score_snapshot_payload as score_timeline_payload  # noqa: E402
from src.wiki_timeline.article_state import build_article_sentence_surface, build_wiki_article_state  # noqa: E402


SCHEMA_VERSION = "wiki_random_article_ingest_coverage_report_v0_1"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _event_has_action(event: Mapping[str, Any]) -> bool:
    if str(event.get("action") or "").strip():
        return True
    for step in event.get("steps") or []:
        if isinstance(step, Mapping) and str(step.get("action") or "").strip():
            return True
    return False


def _event_has_object(event: Mapping[str, Any]) -> bool:
    object_lanes = (
        event.get("entity_objects"),
        event.get("numeric_objects"),
        event.get("modifier_objects"),
        event.get("objects"),
    )
    for lane in object_lanes:
        if isinstance(lane, list) and any(str(item).strip() for item in lane):
            return True
    for step in event.get("steps") or []:
        if not isinstance(step, Mapping):
            continue
        for lane_name in ("entity_objects", "numeric_objects", "modifier_objects", "objects"):
            lane = step.get(lane_name)
            if isinstance(lane, list) and any(str(item).strip() for item in lane):
                return True
    return False


def _page_row_from_outputs(
    payload: Mapping[str, Any],
    article_state: Mapping[str, Any],
    timeline_row: Mapping[str, Any],
    reducer_row: Mapping[str, Any],
    *,
    follow_rows: list[Mapping[str, Any]] | None,
    max_follow_links_per_page: int,
) -> dict[str, Any]:
    sentence_rows = article_state.get("sentence_units")
    article_events = article_state.get("event_candidates")
    observation_rows = article_state.get("observations")
    timeline_projection = article_state.get("timeline_projection")
    article_sentences = [row for row in sentence_rows if isinstance(row, Mapping)] if isinstance(sentence_rows, list) else []
    article_aao_rows = [row for row in article_events if isinstance(row, Mapping)] if isinstance(article_events, list) else []
    observations = [row for row in observation_rows if isinstance(row, Mapping)] if isinstance(observation_rows, list) else []
    timeline_rows = [row for row in timeline_projection if isinstance(row, Mapping)] if isinstance(timeline_projection, list) else []
    follow_rows = [row for row in (follow_rows or []) if isinstance(row, Mapping)]

    article_sentence_count = len(article_sentences)
    article_aao_event_count = len(article_aao_rows)
    observation_count = len(observations)
    actor_event_count = sum(
        1
        for row in article_aao_rows
        if isinstance(row.get("actors"), list) and any(isinstance(actor, Mapping) for actor in row.get("actors") or [])
    )
    action_event_count = sum(1 for row in article_aao_rows if _event_has_action(row))
    object_event_count = sum(1 for row in article_aao_rows if _event_has_object(row))
    step_count = sum(len(row.get("steps") or []) for row in article_aao_rows if isinstance(row.get("steps"), list))
    claim_event_count = sum(1 for row in article_aao_rows if bool(row.get("claim_bearing")))
    attribution_event_count = sum(
        1 for row in article_aao_rows if isinstance(row.get("attributions"), list) and bool(row.get("attributions"))
    )
    unresolved_sentence_count = max(0, article_sentence_count - article_aao_event_count)
    sentence_retention_score = _ratio(article_aao_event_count, article_sentence_count)
    observation_density_score = _ratio(observation_count, article_sentence_count)
    actor_surface_score = _ratio(actor_event_count, article_aao_event_count)
    action_surface_score = _ratio(action_event_count, article_aao_event_count)
    object_surface_score = _ratio(object_event_count, article_aao_event_count)
    article_ingest_score = round(
        (sentence_retention_score + actor_surface_score + action_surface_score + object_surface_score) / 4.0,
        6,
    )

    anchor_status_counts: dict[str, int] = {}
    for row in timeline_rows:
        key = str(row.get("anchor_status") or "none")
        anchor_status_counts[key] = anchor_status_counts.get(key, 0) + 1

    link_count = int(payload.get("links") and len(payload.get("links") or []) or 0)
    followed_snapshot_count = len(follow_rows)
    follow_budget_used_ratio = _ratio(followed_snapshot_count, max_follow_links_per_page) if max_follow_links_per_page else 0.0

    issues: list[str] = []
    if article_sentence_count == 0:
        issues.append("no_article_sentences")
    if article_sentence_count > 0 and article_aao_event_count == 0:
        issues.append("article_sentences_without_aao_events")
    if article_aao_event_count > 0 and actor_event_count == 0:
        issues.append("no_actor_surface")
    if article_aao_event_count > 0 and action_event_count == 0:
        issues.append("no_action_surface")
    if article_aao_event_count > 0 and object_event_count == 0:
        issues.append("no_object_surface")
    if max_follow_links_per_page > 0 and link_count > 0 and followed_snapshot_count == 0:
        issues.append("follow_budget_unused")

    return {
        "title": str(payload.get("title") or ""),
        "pageid": payload.get("pageid"),
        "revid": payload.get("revid"),
        "source_url": payload.get("source_url"),
        "article_sentence_count": article_sentence_count,
        "observation_count": observation_count,
        "article_aao_event_count": article_aao_event_count,
        "actor_event_count": actor_event_count,
        "action_event_count": action_event_count,
        "object_event_count": object_event_count,
        "step_count": step_count,
        "claim_event_count": claim_event_count,
        "attribution_event_count": attribution_event_count,
        "unresolved_sentence_count": unresolved_sentence_count,
        "link_count": link_count,
        "followed_snapshot_count": followed_snapshot_count,
        "followed_titles": [str(row.get("title") or "") for row in follow_rows[:10]],
        "scores": {
            "sentence_retention_score": sentence_retention_score,
            "observation_density_score": observation_density_score,
            "actor_surface_score": actor_surface_score,
            "action_surface_score": action_surface_score,
            "object_surface_score": object_surface_score,
            "article_ingest_score": article_ingest_score,
            "follow_budget_used_ratio": follow_budget_used_ratio,
        },
        "article_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "order_index": int(row.get("order_index") or 0),
                "section": str(row.get("section") or ""),
                "text": str(row.get("text") or "")[:180],
                "links": list(row.get("links") or [])[:5],
                "anchor_status": str(row.get("anchor_status") or "none"),
            }
            for row in article_sentences[:3]
        ],
        "aao_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "action": str(row.get("action") or ""),
                "actor_count": len(row.get("actors") or []) if isinstance(row.get("actors"), list) else 0,
                "step_count": len(row.get("steps") or []) if isinstance(row.get("steps"), list) else 0,
                "anchor_status": str(row.get("anchor_status") or "none"),
                "text": str(row.get("text") or "")[:180],
            }
            for row in article_aao_rows[:3]
        ],
        "canonical_state": {
            "sentence_unit_count": article_sentence_count,
            "observation_count": observation_count,
            "event_candidate_count": article_aao_event_count,
            "anchor_status_counts": anchor_status_counts,
        },
        "timeline_projection": {
            "event_count": len(timeline_rows),
            "anchor_status_counts": anchor_status_counts,
            "preview": [
                {
                    "event_id": str(row.get("event_id") or ""),
                    "order_index": int(row.get("order_index") or 0),
                    "anchor_status": str(row.get("anchor_status") or "none"),
                    "ordering_basis": str(row.get("ordering_basis") or "source_text_order"),
                    "text": str(row.get("text") or "")[:180],
                }
                for row in timeline_rows[:5]
            ],
        },
        "timeline_readiness": {
            "timeline_candidate_count": int(timeline_row.get("timeline_candidate_count") or 0),
            "dated_timeline_candidate_count": int(timeline_row.get("dated_timeline_candidate_count") or 0),
            "aao_event_count": int(timeline_row.get("aao_event_count") or 0),
            "scores": dict(timeline_row.get("scores") or {}),
            "issues": list(timeline_row.get("issues") or []),
        },
        "shared_reducer": {
            "structural_token_count": int(reducer_row.get("structural_token_count") or 0),
            "meaningful_lexeme_count": int(reducer_row.get("meaningful_lexeme_count") or 0),
            "meaningful_structure_count": int(reducer_row.get("meaningful_structure_count") or 0),
            "scores": dict(reducer_row.get("scores") or {}),
            "issues": list(reducer_row.get("issues") or []),
        },
        "issues": issues,
        "parser": article_state.get("parser"),
        "extraction_profile": article_state.get("extraction_profile"),
    }


def score_snapshot_payload(
    payload: Mapping[str, Any],
    *,
    follow_rows: list[Mapping[str, Any]] | None = None,
    max_sentences: int = 400,
    max_events: int = 64,
    max_follow_links_per_page: int = 0,
    no_spacy: bool = False,
) -> dict[str, Any]:
    article_state = build_wiki_article_state(
        payload,
        max_sentences=max_sentences,
        max_events=max_sentences,
        no_spacy=no_spacy,
    )
    timeline_row = score_timeline_payload(payload, max_events=max_events, no_spacy=no_spacy)
    reducer_row = score_reducer_payload(payload)
    return _page_row_from_outputs(
        payload,
        article_state,
        timeline_row,
        reducer_row,
        follow_rows=follow_rows,
        max_follow_links_per_page=max_follow_links_per_page,
    )


def build_article_ingest_report(
    manifest: Mapping[str, Any],
    *,
    sample_limit: int | None = None,
    emit_page_rows: bool = True,
    max_sentences: int = 400,
    max_events: int = 64,
    no_spacy: bool = False,
) -> dict[str, Any]:
    sample_rows = manifest.get("samples")
    if not isinstance(sample_rows, list):
        raise ValueError("manifest samples must be a list")
    if sample_limit is not None:
        sample_rows = sample_rows[: max(0, int(sample_limit))]

    page_rows: list[dict[str, Any]] = []
    issue_counts: dict[str, int] = {}
    total_counts: dict[str, int] = {}
    score_sums = {
        "sentence_retention_score": 0.0,
        "observation_density_score": 0.0,
        "actor_surface_score": 0.0,
        "action_surface_score": 0.0,
        "object_surface_score": 0.0,
        "article_ingest_score": 0.0,
        "follow_budget_used_ratio": 0.0,
    }
    max_follow_links_per_page = int(manifest.get("max_follow_links_per_page") or 0)

    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        snapshot_path = row.get("snapshot_path")
        if not isinstance(snapshot_path, str):
            continue
        payload = _load_json(Path(snapshot_path))
        page_row = score_snapshot_payload(
            payload,
            follow_rows=list(row.get("followed_samples") or []),
            max_sentences=max_sentences,
            max_events=max_events,
            max_follow_links_per_page=max_follow_links_per_page,
            no_spacy=no_spacy,
        )
        page_rows.append(page_row)
        for issue in page_row["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for key in (
            "article_sentence_count",
            "observation_count",
            "article_aao_event_count",
            "actor_event_count",
            "action_event_count",
            "object_event_count",
            "step_count",
            "claim_event_count",
            "attribution_event_count",
            "followed_snapshot_count",
        ):
            total_counts[key] = total_counts.get(key, 0) + int(page_row[key])
        for key in score_sums:
            score_sums[key] += float(page_row["scores"][key])

    page_count = len(page_rows)
    summary = {
        "page_count": page_count,
        "issue_counts": dict(sorted(issue_counts.items())),
        "total_counts": dict(sorted(total_counts.items())),
        "pages_with_article_sentences": sum(1 for row in page_rows if row["article_sentence_count"] > 0),
        "pages_with_article_aao_events": sum(1 for row in page_rows if row["article_aao_event_count"] > 0),
        "pages_with_actor_surface": sum(1 for row in page_rows if row["actor_event_count"] > 0),
        "pages_with_action_surface": sum(1 for row in page_rows if row["action_event_count"] > 0),
        "pages_with_followed_snapshots": sum(1 for row in page_rows if row["followed_snapshot_count"] > 0),
        "average_scores": {key: round((value / page_count), 6) if page_count else 0.0 for key, value in score_sums.items()},
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest.get("generated_at"),
        "manifest": {
            "wiki": manifest.get("wiki"),
            "requested_count": manifest.get("requested_count"),
            "sampled_count": manifest.get("sampled_count"),
            "namespace": manifest.get("namespace"),
            "follow_hops": int(manifest.get("follow_hops") or 0),
            "max_follow_links_per_page": max_follow_links_per_page,
        },
        "supported_surface": {
            "canonical_state_surface": "wiki_article_state_v0_1",
            "article_sentence_surface": "full_article_sentence_rows",
            "event_candidate_surface": "wiki_timeline_aoo_extract",
            "timeline_surface": "wiki_random_timeline_readiness_report_v0_1",
            "shared_reducer_surface": "diagnostic_companion",
            "spacy_enabled": not no_spacy,
            "max_sentences": int(max_sentences),
            "max_events": int(max_events),
        },
        "summary": summary,
        "pages": page_rows if emit_page_rows else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score stored random-page Wikipedia snapshots for article-wide ingest coverage."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--emit-page-rows", action="store_true")
    parser.add_argument("--fail-on-empty", action="store_true")
    parser.add_argument("--max-sentences", type=int, default=400)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--no-spacy", action="store_true")
    args = parser.parse_args(argv)

    manifest = _load_json(args.manifest)
    report = build_article_ingest_report(
        manifest,
        sample_limit=args.sample_limit,
        emit_page_rows=args.emit_page_rows,
        max_sentences=args.max_sentences,
        max_events=args.max_events,
        no_spacy=args.no_spacy,
    )
    if args.fail_on_empty and report["summary"]["page_count"] == 0:
        raise SystemExit("no pages scored")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
