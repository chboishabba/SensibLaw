from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.policy.world_model_runtime import (
    attach_receipt as _attach_receipt,
    build_world_model as _build_world_model_from_input,
    project_report as _project_report,
)


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def attach_receipt(artifact: Mapping[str, Any], *, profile: str) -> dict[str, Any]:
    return _attach_receipt(artifact)


def build_report(profile: str, **kwargs: Any) -> dict[str, Any]:
    return _project_report(build_world_model(profile, **kwargs))


def build_world_model(profile: str, **kwargs: Any) -> dict[str, Any]:
    # Inject a schema marker so the adapter registry discovers this as
    # a NAT profile from the data itself — no smuggled lane hints.
    payload = {
        "schema_version": "sl.nat_wikidata_profile.v0_1",
        "profile_id": profile,
        **kwargs,
    }
    return _build_world_model_from_input(payload)


def load_fixture(profile: str, *, with_receipt: bool = False) -> dict[str, Any]:
    sensiblaw_root = _sensiblaw_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"

    if profile == "q43229_superclass_pressure":
        kwargs = {
            "review_bucket": _read_json(fixture_root / "wikidata_nat_cohort_b_review_bucket_20260402.json"),
            "operator_packet": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_packet_20260402.json"),
            "operator_queue": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_queue_20260402.json"),
            "operator_report": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_report_20260402.json"),
            "batch_report": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
        }
    else:
        kwargs = {}
    artifact = build_report(profile, **kwargs)
    if not with_receipt:
        return dict(artifact)
    return _attach_receipt(artifact)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
    "load_fixture",
]
