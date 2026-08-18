from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.ontology.wikidata_contradiction_attribution import (
    EvidenceSquare,
    LayerEvidence,
    build_cross_ontology_attribution,
    target_evidence_from_disjoint_union_report,
)


def _layer(raw: Mapping[str, Any]) -> LayerEvidence:
    return LayerEvidence(
        EvidenceSquare(bool(raw.get("supports")), bool(raw.get("refutes"))),
        evidence=tuple(str(item) for item in raw.get("evidence", [])),
        provenance=tuple(str(item) for item in raw.get("provenance", [])),
        obligations=tuple(str(item) for item in raw.get("obligations", [])),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build source/transcription/alignment/target support-square attribution"
    )
    parser.add_argument("--evidence", type=Path, required=True, help="Pinned attribution evidence JSON")
    parser.add_argument("--target-report", type=Path, help="Optional disjoint-union report JSON")
    parser.add_argument("--target-spec-id", help="Disjoint-union spec_id to use for target evidence")
    parser.add_argument("--output", type=Path, help="Optional attribution packet path")
    args = parser.parse_args(argv)

    raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    source = _layer(raw.get("source", {}))
    transcription = _layer(raw.get("transcription", {}))
    alignment = _layer(raw.get("alignment", {}))
    target = _layer(raw.get("target", {}))

    if args.target_report is not None:
        if not args.target_spec_id:
            raise SystemExit("--target-spec-id is required with --target-report")
        target_report = json.loads(args.target_report.read_text(encoding="utf-8"))
        target = target_evidence_from_disjoint_union_report(
            target_report, spec_id=args.target_spec_id
        )

    packet = build_cross_ontology_attribution(
        claim_id=str(raw.get("claim_id", "")),
        claim_surface=str(raw.get("claim_surface", "")),
        source=source,
        transcription=transcription,
        alignment=alignment,
        target=target,
        required_layers=tuple(raw.get("required_layers", ("source", "transcription", "alignment", "target"))),
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
