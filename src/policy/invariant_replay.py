"""Immutable replay of residual profiles against a revised domain invariant.

The generic carrier does not infer domain pressure from cohort statistics. A
domain adapter supplies reassessments after a governed invariant revision; this
module checks candidate/revision continuity, retains the original profiles, and
projects the resulting graph plus explicit per-candidate transitions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .domain_pressure import DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION
from .residual_graph import build_typed_residual_graph
from .residual_profiles import (
    CONTEXT_GATE_NAMES,
    TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION,
    build_typed_residual_profile,
)


INVARIANT_REPLAY_SCHEMA_VERSION = "sl.invariant_replay.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _context_from_profile(profile: Mapping[str, Any]) -> dict[str, bool | None]:
    gates = profile.get("context_gates")
    if not isinstance(gates, Mapping):
        raise ValueError("invariant replay requires profile context gates")
    values: dict[str, bool | None] = {}
    for name in CONTEXT_GATE_NAMES:
        state = _text(gates.get(name))
        if state == "compatible":
            values[name] = True
        elif state == "incompatible":
            values[name] = False
        elif state == "unknown":
            values[name] = None
        else:
            raise ValueError("invariant replay requires known profile context gates")
    return values


def _residual_states(profile: Mapping[str, Any]) -> dict[str, str]:
    return {
        _text(row.get("residual_kind")): _text(row.get("state"))
        for row in profile.get("residuals", [])
        if isinstance(row, Mapping) and _text(row.get("residual_kind"))
    }


def _transition(
    original: Mapping[str, Any], replayed: Mapping[str, Any]
) -> dict[str, Any]:
    before = _residual_states(original)
    after = _residual_states(replayed)
    names = sorted(set(before) | set(after))
    return {
        "candidate_ref": _text(original.get("candidate_ref")),
        "source_revision_ref": _text(original.get("source_revision_ref")),
        "comparison_state_before": _text(original.get("comparison_state")),
        "comparison_state_after": _text(replayed.get("comparison_state")),
        "residual_transitions": [
            {
                "residual_kind": name,
                "state_before": before.get(name),
                "state_after": after.get(name),
                "changed": before.get(name) != after.get(name),
            }
            for name in names
        ],
    }


def build_invariant_replay(
    *,
    source_snapshot_ref: str,
    revised_snapshot: Mapping[str, Any],
    original_profiles: Sequence[Mapping[str, Any]],
    reassessments: Sequence[Mapping[str, Any]],
    source_graph_ref: str,
) -> dict[str, Any]:
    """Replay supplied assessments against a named later invariant snapshot.

    Every reassessment must preserve the candidate and revision of its original
    profile and identify the supplied revised snapshot. The function neither
    derives reassessments nor mutates the source profile/graph.
    """

    old_snapshot_ref = _text(source_snapshot_ref)
    graph_ref = _text(source_graph_ref)
    new_snapshot_ref = _text(revised_snapshot.get("snapshot_id"))
    if not old_snapshot_ref or not graph_ref or not new_snapshot_ref:
        raise ValueError(
            "invariant replay requires source snapshot, revised snapshot, and source graph refs"
        )

    originals = [deepcopy(dict(profile)) for profile in original_profiles]
    if not originals:
        raise ValueError("invariant replay requires original profiles")
    by_candidate: dict[str, dict[str, Any]] = {}
    for profile in originals:
        if (
            _text(profile.get("schema_version"))
            != TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION
        ):
            raise ValueError("invariant replay requires typed residual profiles")
        candidate_ref = _text(profile.get("candidate_ref"))
        if not candidate_ref or candidate_ref in by_candidate:
            raise ValueError("invariant replay requires unique original candidates")
        by_candidate[candidate_ref] = profile

    supplied: dict[str, Mapping[str, Any]] = {}
    for assessment in reassessments:
        if (
            _text(assessment.get("schema_version"))
            != DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION
        ):
            raise ValueError("invariant replay requires domain pressure reassessments")
        candidate_ref = _text(assessment.get("candidate_ref"))
        if candidate_ref not in by_candidate or candidate_ref in supplied:
            raise ValueError(
                "invariant replay reassessments must match original candidates"
            )
        if _text(assessment.get("domain_invariant_ref")) != new_snapshot_ref:
            raise ValueError("invariant replay reassessment must name revised snapshot")
        supplied[candidate_ref] = assessment
    if set(supplied) != set(by_candidate):
        raise ValueError(
            "invariant replay requires one reassessment per original profile"
        )

    replayed_profiles = []
    for candidate_ref in sorted(by_candidate):
        original = by_candidate[candidate_ref]
        replayed_profiles.append(
            build_typed_residual_profile(
                assessment=supplied[candidate_ref],
                context=_context_from_profile(original),
                source_revision_ref=_text(original.get("source_revision_ref")),
                source_anchor_refs=original.get("source_anchor_refs") or (),
            )
        )
    replayed_by_candidate = {
        _text(profile.get("candidate_ref")): profile for profile in replayed_profiles
    }
    transitions = [
        _transition(by_candidate[candidate_ref], replayed_by_candidate[candidate_ref])
        for candidate_ref in sorted(by_candidate)
    ]
    return {
        "schema_version": INVARIANT_REPLAY_SCHEMA_VERSION,
        "source_snapshot_ref": old_snapshot_ref,
        "revised_snapshot_ref": new_snapshot_ref,
        "source_graph_ref": graph_ref,
        "original_profiles": originals,
        "replayed_profiles": replayed_profiles,
        "transitions": transitions,
        "replayed_graph": build_typed_residual_graph(replayed_profiles),
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = ["INVARIANT_REPLAY_SCHEMA_VERSION", "build_invariant_replay"]
