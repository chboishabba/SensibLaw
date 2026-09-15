#!/usr/bin/env python3
"""Render the bounded Mabo fixture as a Lee/SensibLaw proof-graph specimen.

The script consumes a real ``sl.evidential_pnf_bridge.v0_1`` JSON receipt from
SensibLaw numeric PNF and the repository Mabo fixture.  It does not run the
parser, infer semantic correspondence, or manufacture an adversarial account.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.pnf.evidential_pnf_receipt import EvidentialPNFBridgeReceipt
from src.pnf.mabo_legal_proof_graph_specimen import (
    MABO_FIXTURE_SOURCE_PATH,
    build_mabo_legal_proof_graph_specimen,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _bridge_from_json(value: dict[str, Any]) -> EvidentialPNFBridgeReceipt:
    if value.get("schema_version") != "sl.evidential_pnf_bridge.v0_1":
        raise ValueError("unsupported or missing evidential PNF bridge schema")
    residuals = value.get("residual_demand_refs", ())
    if not isinstance(residuals, list):
        raise ValueError("residual_demand_refs must be a JSON list")
    return EvidentialPNFBridgeReceipt(
        schema_version=str(value["schema_version"]),
        run_ref=str(value["run_ref"]),
        document_ref=str(value["document_ref"]),
        canonical_text_sha256=str(value["canonical_text_sha256"]),
        parser_contract_ref=str(value["parser_contract_ref"]),
        numeric_pnf_compiler_contract_ref=str(
            value["numeric_pnf_compiler_contract_ref"]
        ),
        graph_ref=str(value["graph_ref"]),
        residual_demand_refs=tuple(str(item) for item in residuals),
        representation=str(value["representation"]),
        world_resolution_deferred=bool(value["world_resolution_deferred"]),
        cross_document_identity_closed=bool(value["cross_document_identity_closed"]),
        legacy_document_materialisation=bool(value["legacy_document_materialisation"]),
        parser_observation_is_semantic_authority=bool(
            value["parser_observation_is_semantic_authority"]
        ),
        semantic_correspondence_required=bool(
            value["semantic_correspondence_required"]
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bridge-receipt",
        type=Path,
        required=True,
        help="JSON emitted from EvidentialPNFBridgeReceipt.to_dict()",
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        default=Path(MABO_FIXTURE_SOURCE_PATH),
        help="bounded Mabo repository fixture JSON",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    bridge = _bridge_from_json(_load_json(args.bridge_receipt))
    source = _load_json(args.source_json)
    body = source.get("body")
    if not isinstance(body, str) or not body:
        raise ValueError("Mabo source fixture requires a non-empty body")

    specimen = build_mabo_legal_proof_graph_specimen(
        bridge_receipt=bridge,
        source_text=body,
    )
    rendered = json.dumps(specimen.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
