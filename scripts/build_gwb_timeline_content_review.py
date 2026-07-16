#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR.parent))

from src.policy.gwb_timeline_content_review import build_content_review_payload

LOGGER = logging.getLogger(__name__)

def build_review_summary_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    relations = payload["reviewed_relations"]
    risky_events = payload["merge_risky_events"]
    conflict_packets = payload["conflict_packets"]
    
    lines = [
        "# GWB Timeline Content Corroboration Review Summary",
        "",
        "This report evaluates the GWB checkpoint extraction as evidence, classifying corroboration, date confidence, merge risk, and contradictions.",
        "",
        "## Merged Corroboration Summary",
        "",
        f"- **Total Reviewed Relations**: {summary['total_reviewed_relations']}",
        f"- **Risky Merged Event Clusters**: {summary['risky_merged_event_count']}",
        f"- **Conflict Packets**: {summary['conflict_packet_count']}",
        "",
        "### Status Counts:",
    ]
    for deg, count in sorted(summary["degree_counts"].items()):
        lines.append(f"- **{deg}**: {count}")
        
    lines.extend(["", "## 1. High-confidence cross-source events", ""])
    strong_items = [r for r in relations if r["corroboration_degree"] == "strong"]
    if strong_items:
        for item in strong_items[:10]:
            lines.append(
                f"- **{item['subject']['canonical_label']} {item['predicate_key'].replace('_', ' ')} {item['object']['canonical_label']}** "
                f"(resolved date: `{item['resolved_historical_date']}`, score: `{item['event_quality_score']}`)"
            )
    else:
        lines.append("- No strong cross-source corroborated relations found.")
        
    lines.extend(["", "## 2. Single-source events", ""])
    single_items = [r for r in relations if r["corroboration_degree"] == "single_source"]
    if single_items:
        for item in single_items[:10]:
            lines.append(
                f"- **{item['subject']['canonical_label']} {item['predicate_key'].replace('_', ' ')} {item['object']['canonical_label']}** "
                f"(source: {item['source_families'][0]})"
            )
    else:
        lines.append("- No single-source relations found.")
        
    lines.extend(["", "## 3. Date/order uncertainty", ""])
    uncertain_items = [
        r for r in relations 
        if r.get("date_confidence") in {"relative_order_only", "document_order_only", "ingest_order_only"}
    ]
    if uncertain_items:
        for item in uncertain_items[:10]:
            lines.append(
                f"- **{item['subject']['canonical_label']} {item['predicate_key'].replace('_', ' ')} {item['object']['canonical_label']}** "
                f"(confidence: `{item.get('date_confidence')}`)"
            )
    else:
        lines.append("- No date or order uncertainty flagged.")
        
    lines.extend(["", "## 4. Historical conflict residuals", ""])
    if conflict_packets:
        for item in conflict_packets[:10]:
            lines.append(
                f"- **Edge {item['ordering_edge_id']}**: Conflict between "
                f"`{item['source_event_id']}` (`{item['source_date']}`) and "
                f"`{item['target_event_id']}` (`{item['target_date']}`)."
            )
    else:
        lines.append("- No historical conflict residuals detected.")
        
    lines.extend(["", "## 5. Audit-block affected relations", ""])
    blocked_items = [r for r in relations if r["corroboration_degree"] == "blocked"]
    if blocked_items:
        for item in blocked_items[:10]:
            lines.append(
                f"- **{item['subject']['canonical_label']} {item['predicate_key'].replace('_', ' ')} {item['object']['canonical_label']}** (BLOCKED)"
            )
    else:
        lines.append("- No active relations affected by audit blocks.")
        
    lines.extend(["", "## 6. Over-merged or under-merged event clusters", ""])
    if risky_events:
        for item in risky_events[:10]:
            lines.append(
                f"- **{item['merged_event_id']}** ({item['event_label']}): risks: {', '.join(item['risks'])}"
            )
    else:
        lines.append("- No merge risk flags detected.")
        
    lines.extend(["", "## 7. Coverage gaps", ""])
    gap_counts: dict[str, int] = {}
    for r in relations:
        for gap in r.get("gaps", []):
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
    if gap_counts:
        for gap, count in sorted(gap_counts.items()):
            lines.append(f"- **{gap}**: {count} relations affected")
    else:
        lines.append("- No coverage gaps identified.")
        
    lines.extend(["", "## 8. Recommended next human review queue", ""])
    review_queue = [
        r for r in relations 
        if r["corroboration_degree"] in {"moderate", "weak", "conflicted"}
    ]
    if review_queue:
        for item in review_queue[:10]:
            lines.append(
                f"- **{item['subject']['canonical_label']} {item['predicate_key'].replace('_', ' ')} {item['object']['canonical_label']}** "
                f"(degree: `{item['corroboration_degree']}`, reasons: `{item['gaps']}`)"
            )
    else:
        lines.append("- Human review queue is empty.")
        
    return "\n".join(lines) + "\n"


def build_timeline_content_review(checkpoint_path: Path, output_dir: Path) -> dict[str, Any]:
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        checkpoint_payload = json.load(f)
        
    payload = build_content_review_payload(checkpoint_payload)
    markdown_text = build_review_summary_markdown(payload)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "gwb_content_corroboration_review.json"
    md_path = output_dir / "gwb_content_corroboration_review.md"
    
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_text, encoding="utf-8")
    
    LOGGER.info("Wrote GWB content corroboration review to %s", json_path)
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "summary": payload["summary"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the GWB timeline content corroboration review.")
    parser.add_argument("--checkpoint-path", required=True, help="Path to the broader GWB checkpoint JSON file.")
    parser.add_argument("--output-dir", required=True, help="Directory to write the review artifacts to.")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    result = build_timeline_content_review(Path(args.checkpoint_path), Path(args.output_dir))
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
