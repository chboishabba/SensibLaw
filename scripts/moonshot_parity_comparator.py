"""Produce a comparative parity snapshot across AU/GWB/Brexit/Wikidata lanes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LANE_SUMMARIES: dict[str, dict[str, Any]] = {
    "AU": {
        "strengths": [
            "Fact-review bundles capture clause-level authority references with `legal_follow_graph` and `authority_follow` views.",
            "Compiler contracts already surface evidence bundling + promotion guards."
        ],
        "weaknesses": [
            "Residual typing question pressure (e.g., missing `instance of` references) stays in `review_only` queue.",
            "Cross-jurisdictional comparisons still rely on manual AU/GWB adapter alignment."
        ],
        "context_resolves": "Local transcripts + AU fact-run chronology bring procedural anchors before bounded review.",
        "next_bounded_search": "Target AU transcripts lacking explicit `instance of` roles; enrich `authority_follow` queue with `typing_deficit_signals` derived from split-axis probes."
    },
    "GWB": {
        "strengths": [
            "Legal linkage graphs emit bounded followed-source receipts and node-level support metadata.",
            "GWB public/broader review slices already maintain `source_review_rows` with citation counts."
        ],
        "weaknesses": [
            "Semantic penetration beyond seeded public-bios remains linkage-heavy (coverage limited to `gwb_legal_follow`).",
            "Brexit/UK-EU queries still surface high residual uncertainty without direct provenance."
        ],
        "context_resolves": "Seeded U.S. law + Brexit timeline artifacts provide concrete anchors when matching to authority receipts.",
        "next_bounded_search": "Sweep GWB legal linkage rows missing `typing_deficit_signals` for their followed-source nodes to close unresolved citation gaps."
    },
    "Brexit": {
        "strengths": [
            "Dedicated Brexit/provincial nodes in GWB link graphs highlight EU/UK transitions.",
            "Brexit-focused lineages already surface via `legal_follow_graph` metadata."
        ],
        "weaknesses": [
            "Brexit-specific temporal semantics (Article 50 etc.) still rely on manual token filters — no calibrated evidence bundling.",
            "Action-level promotions tied to EU-specific follow targets remain challenge to unify with other lanes."
        ],
        "context_resolves": "Brexit tokens embedded in GWB/Brexit slices align with state-level authority receipts recorded in follow graphs.",
        "next_bounded_search": "Run a targeted search for Brexit-event rows lacking reference anchors to confirm `typing_deficit_signals` of connected legal sources."
    },
    "Wikidata/Nat": {
        "strengths": [
            "Nat lane already builds split-axis and typing-deficit probes (Cohort D/E) with live-follow plans.",
            "Schemas like `typing_deficit_signals` now propagate through normalized artifacts for cross-lane joins."
        ],
        "weaknesses": [
            "Limited migration execution due to `review_only` posture; unresolved split axes keep rows from promoting.",
            "Wikidata evidence still missing multi-step context beyond single revisions."
        ],
        "context_resolves": "Split-axis probes explicitly track axis-specific constraints and allow local context to flag insufficient qualifiers.",
        "next_bounded_search": "Perform live-follow scan for split-axis rows missing matching resolved axes to feed the normalized typing-deficit signal pool."
    },
}

DATAFILE = Path("/tmp/moonshot_parity_snapshot_worker.json")


def build_snapshot() -> dict[str, Any]:
    ranked = sorted(
        LANE_SUMMARIES.items(),
        key=lambda item: len(item[1]["weaknesses"]),
    )
    suggested_next_lane = "Wikidata/Nat"
    return {
        "constraints_invariants": {
            "AU": "Fail-closed review bundles; no unchecked promotions without contract.",
            "GWB": "Legal-linkage graph remains derived-only with follow control plane invariants.",
            "Brexit": "Node-level Brexit tags invoked only through documented follow receipts.",
            "Wikidata/Nat": "Split-axis + typing deficits emit guard flags before any migration."
        },
        "lane_status": {
            lane: summary for lane, summary in LANE_SUMMARIES.items()
        },
        "suggested_next_ranked_lane": suggested_next_lane,
        "ranked_weakness_positions": [
            {"lane": lane, "weakness_count": len(summary["weaknesses"])}
            for lane, summary in ranked
        ],
    }


def main() -> None:
    snapshot = build_snapshot()
    DATAFILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
