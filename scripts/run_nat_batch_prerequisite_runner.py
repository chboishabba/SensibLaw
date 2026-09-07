from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.ontology.wikidata_nat_batch_prerequisite_runner import build_batch_dry_run


DEFAULT_MANIFEST = Path(
    "tests/fixtures/wikidata/wikidata_nat_lane_review_manifests_20260401.json"
)
DEFAULT_PACK = Path(
    "data/ontology/wikidata_migration_packs/"
    "p5991_p14143_climate_pilot_20260328/migration_pack.json"
)


def _load_mapping(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-classify Nat Wikidata migration rows by first missing prerequisite. "
            "Performs no network requests, edits, selector dispatch, or semantic promotion."
        )
    )
    parser.add_argument("--cohort-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--migration-pack",
        type=Path,
        action="append",
        dest="migration_packs",
        help="repeat for multiple materialized pack/tranche artifacts",
    )
    parser.add_argument("--cohort-id", default="business_family_reconciled")
    parser.add_argument(
        "--source-revision-reference",
        default="Nat revision-locked sandbox/cohort-manifest lineage",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = _load_mapping(args.cohort_manifest)
    pack_paths = args.migration_packs or [DEFAULT_PACK]
    packs = [_load_mapping(path) for path in pack_paths]

    result = build_batch_dry_run(
        cohort_manifest=manifest,
        migration_packs=packs,
        cohort_id=args.cohort_id,
        source_revision_reference=args.source_revision_reference,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "batch_ref": result["batch_ref"],
                    "source_population": result["source_population"],
                    "materialized_row_count": result["materialized_row_count"],
                    "work_group_count": result["work_group_count"],
                    "network_performed": result["network_performed"],
                    "edits_performed": result["edits_performed"],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
