from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.ontology.wikidata import build_wikidata_climate_review_demonstrator
from src.ontology.wikidata_disjointness import load_disjointness_slice, project_wikidata_disjointness_payload
from src.ontology.wikidata_linkage_depth import (
    build_climate_review_report,
    build_climate_review_linkage_receipt,
    build_climate_review_world_model,
    build_disjointness_report,
    build_disjointness_report_linkage_receipt,
    build_disjointness_world_model,
)
from src.ontology.wikidata_superclass_linkage import (
    build_receipt as build_superclass_receipt,
    build_report as build_superclass_report,
    build_world_model as build_superclass_world_model,
)
from src.policy.linkage_workflows import attach_receipt as _attach_receipt


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def attach_receipt(artifact: Mapping[str, Any], *, profile: str) -> dict[str, Any]:
    builders = {
        "climate_review_demonstrator": build_climate_review_linkage_receipt,
        "disjointness_report": build_disjointness_report_linkage_receipt,
        "q43229_superclass_pressure": build_superclass_receipt,
    }
    try:
        receipt_builder = builders[profile]
    except KeyError as exc:
        raise ValueError(f"unsupported nat receipt profile: {profile}") from exc
    return _attach_receipt(artifact, receipt_builder=receipt_builder)


def build_report(profile: str, **kwargs: Any) -> dict[str, Any]:
    if profile == "climate_review_demonstrator":
        return build_climate_review_report()
    if profile == "disjointness_report":
        return build_disjointness_report()
    if profile == "q43229_superclass_pressure":
        return build_superclass_report(**kwargs)
    raise ValueError(f"unsupported nat report profile: {profile}")


def build_world_model(profile: str, **kwargs: Any) -> dict[str, Any]:
    if profile == "climate_review_demonstrator":
        return build_climate_review_world_model()
    if profile == "disjointness_report":
        return build_disjointness_world_model()
    if profile == "q43229_superclass_pressure":
        return build_superclass_world_model(**kwargs)
    raise ValueError(f"unsupported nat world-model profile: {profile}")


def load_fixture(profile: str, *, with_receipt: bool = False) -> dict[str, Any]:
    sensiblaw_root = _sensiblaw_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"

    if profile == "climate_review_demonstrator":
        artifact = build_climate_review_report()
    elif profile == "disjointness_report":
        artifact = build_disjointness_report()
    elif profile == "q43229_superclass_pressure":
        artifact = build_superclass_report(
            review_bucket=_read_json(fixture_root / "wikidata_nat_cohort_b_review_bucket_20260402.json"),
            operator_packet=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_packet_20260402.json"),
            operator_queue=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_queue_20260402.json"),
            operator_report=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_report_20260402.json"),
            batch_report=_read_json(fixture_root / "wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
        )
    else:
        raise ValueError(f"unsupported nat fixture profile: {profile}")

    if not with_receipt:
        return dict(artifact)
    return attach_receipt(artifact, profile=profile)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
    "load_fixture",
]
