from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .wikidata import build_wikidata_climate_review_demonstrator
from .wikidata_disjointness import load_disjointness_slice, project_wikidata_disjointness_payload
from .wikidata_linkage_depth import (
    build_climate_review_linkage_receipt,
    build_disjointness_report_linkage_receipt,
)
from .wikidata_superclass_linkage import (
    build_wikidata_q43229_superclass_pressure_linkage_receipt,
    build_wikidata_q43229_superclass_pressure_report,
)


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def load_climate_review_demonstrator_with_linkage_receipt() -> dict[str, Any]:
    sensiblaw_root = _sensiblaw_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"
    climate_root = (
        sensiblaw_root
        / "data"
        / "ontology"
        / "wikidata_migration_packs"
        / "p5991_p14143_climate_pilot_20260328"
    )

    demonstrator = build_wikidata_climate_review_demonstrator(
        _read_json(climate_root / "migration_pack.json"),
        climate_text_payload=_read_json(
            climate_root / "climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json"
        ),
        review_packet=_read_json(fixture_root / "wikidata_nat_review_packet_20260401.json"),
    )
    artifact = deepcopy(demonstrator)
    artifact["linkage_depth_receipt"] = build_climate_review_linkage_receipt(demonstrator)
    return artifact


def load_disjointness_report_with_linkage_receipt() -> dict[str, Any]:
    sensiblaw_root = _sensiblaw_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"
    report = project_wikidata_disjointness_payload(
        load_disjointness_slice(
            fixture_root / "disjointness_p2738_fixed_construction_real_pack_v1" / "slice.json"
        )
    )
    artifact = deepcopy(report)
    artifact["linkage_depth_receipt"] = build_disjointness_report_linkage_receipt(report)
    return artifact


def attach_wikidata_q43229_superclass_pressure_linkage_receipt(report: dict[str, Any]) -> dict[str, Any]:
    artifact = deepcopy(report)
    artifact["linkage_depth_receipt"] = build_wikidata_q43229_superclass_pressure_linkage_receipt(report)
    return artifact


def load_q43229_superclass_pressure_report_with_linkage_receipt() -> dict[str, Any]:
    sensiblaw_root = _sensiblaw_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"
    report = build_wikidata_q43229_superclass_pressure_report(
        review_bucket=_read_json(fixture_root / "wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )
    return attach_wikidata_q43229_superclass_pressure_linkage_receipt(report)


__all__ = [
    "attach_wikidata_q43229_superclass_pressure_linkage_receipt",
    "load_climate_review_demonstrator_with_linkage_receipt",
    "load_disjointness_report_with_linkage_receipt",
    "load_q43229_superclass_pressure_report_with_linkage_receipt",
]
