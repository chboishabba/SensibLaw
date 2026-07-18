"""Compare expanded binding artifacts with set-valued PNF candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.operational_reference_binding import (  # noqa: E402
    build_set_valued_binding_artifacts,
)


def _encoded_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "compilation_json",
        type=Path,
        help="Explicit legacy compilation.json used only as benchmark input.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(args.compilation_json.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts") or payload
    compact = build_set_valued_binding_artifacts(artifacts)
    expanded_binding_rows = [
        row
        for row in artifacts.get("local_evidence") or ()
        if row.get("evidence_type") == "typed_binding_candidate"
    ]
    expanded_binding_alternatives = [
        alternative
        for refinement in artifacts.get("factor_refinements") or ()
        for alternative in (refinement.get("resulting_factor") or {}).get(
            "alternatives", ()
        )
        if alternative.get("type_ref") == "semantic.binding_candidate"
    ]
    set_projection = {
        "accessibility_declaration": compact.get(
            "binding_accessibility_declaration"
        ),
        "compatibility_declaration": compact.get(
            "binding_compatibility_declaration"
        ),
        "candidate_sets": compact.get("binding_candidate_sets") or (),
        "members": compact.get("binding_candidate_members") or (),
        "exclusions": compact.get("binding_exclusion_summaries") or (),
        "builds": compact.get("binding_candidate_set_builds") or (),
        "refinement_deltas": [
            row.get("refinement_delta")
            for row in compact.get("factor_refinements") or ()
            if row.get("refinement_delta")
        ],
    }
    expanded_projection = {
        "binding_evidence": expanded_binding_rows,
        "binding_alternatives": expanded_binding_alternatives,
    }
    candidate_sets = compact.get("binding_candidate_sets") or ()
    result = {
        "generation_mode": compact.get("binding_compaction_summary", {}).get(
            "generation_mode"
        ),
        "expanded_pairwise_bytes": _encoded_size(expanded_projection),
        "set_valued_bytes": _encoded_size(set_projection),
        "reference_factors": compact.get("binding_compaction_summary", {}).get(
            "reference_factor_count", 0
        ),
        "pairwise_evidence_rows": len(expanded_binding_rows),
        "pairwise_binding_alternatives": len(expanded_binding_alternatives),
        "candidate_sets": len(candidate_sets),
        "candidate_members": len(compact.get("binding_candidate_members") or ()),
        "compatible_members": sum(
            row.get("compatibility_state") == "compatible_candidate"
            for row in compact.get("binding_candidate_members") or ()
        ),
        "exclusion_summaries": len(
            compact.get("binding_exclusion_summaries") or ()
        ),
        "zero_member_sets": sum(
            int(row.get("member_count", 0)) == 0 for row in candidate_sets
        ),
        "one_member_sets": sum(
            int(row.get("member_count", 0)) == 1 for row in candidate_sets
        ),
        "many_member_sets": sum(
            int(row.get("member_count", 0)) > 1 for row in candidate_sets
        ),
        "factor_revisions": len(compact.get("factor_refinements") or ()),
        "local_binding_demands": sum(
            row.get("budget") == "bounded_document_local_evidence"
            for row in compact.get("resolution_demands") or ()
        ),
        "external_demands": sum(
            row.get("budget") == "bounded_external_evidence"
            for row in compact.get("resolution_demands") or ()
        ),
    }
    expanded_size = result["expanded_pairwise_bytes"]
    compact_size = result["set_valued_bytes"]
    result["byte_reduction_ratio"] = (
        round(1 - compact_size / expanded_size, 6) if expanded_size else 0.0
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
