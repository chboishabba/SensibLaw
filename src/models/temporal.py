from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


TEMPORAL_SCHEMA_VERSION = "sl.world_model_temporal.v0_1"

_RUN_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _extract_run_date(run_id: str) -> str:
    match = _RUN_DATE_PATTERN.search(_as_text(run_id))
    if not match:
        return ""
    return match.group(1)


@dataclass(frozen=True)
class TemporalEnvelope:
    claim_id: str
    valid_from: str
    valid_to: str
    observed_at: str
    supersedes: list[str]
    revision_basis: dict[str, Any]
    schema_version: str = TEMPORAL_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "observed_at": self.observed_at,
            "supersedes": list(self.supersedes),
            "revision_basis": dict(self.revision_basis),
        }


def build_temporal_envelope(
    *,
    claim_id: str,
    evidence_paths: Sequence[Mapping[str, Any]],
    independent_root_artifact_ids: Sequence[str],
) -> dict[str, Any]:
    ordered_paths: list[dict[str, str]] = []
    for path in evidence_paths:
        if not isinstance(path, Mapping):
            continue
        run_id = _as_text(path.get("run_id"))
        root_artifact_id = _as_text(path.get("root_artifact_id"))
        if not run_id and not root_artifact_id:
            continue
        ordered_paths.append(
            {
                "run_id": run_id,
                "root_artifact_id": root_artifact_id,
                "observed_at": _extract_run_date(run_id),
            }
        )

    ordered_paths.sort(
        key=lambda path: (
            path.get("observed_at", ""),
            path.get("run_id", ""),
            path.get("root_artifact_id", ""),
        )
    )
    observed_dates = [path["observed_at"] for path in ordered_paths if path.get("observed_at")]
    latest_path = ordered_paths[-1] if ordered_paths else {}
    latest_root_artifact_id = _as_text(latest_path.get("root_artifact_id"))

    envelope = TemporalEnvelope(
        claim_id=_as_text(claim_id),
        valid_from=observed_dates[0] if observed_dates else "",
        valid_to="",
        observed_at=observed_dates[-1] if observed_dates else "",
        supersedes=[
            value
            for value in independent_root_artifact_ids
            if _as_text(value) and _as_text(value) != latest_root_artifact_id
        ],
        revision_basis={
            "observation_count": len(ordered_paths),
            "run_ids": [_as_text(path.get("run_id")) for path in ordered_paths if _as_text(path.get("run_id"))],
            "independent_root_artifact_ids": [
                _as_text(value) for value in independent_root_artifact_ids if _as_text(value)
            ],
            "latest_root_artifact_id": latest_root_artifact_id,
        },
    )
    return envelope.as_dict()
