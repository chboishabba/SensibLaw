"""Factories keep tests focused on invariants rather than carrier boilerplate."""

from __future__ import annotations

from typing import Any

from src.policy.algebra import Factor, MeetState, TypedAlternative, TypedMeet
from src.resolution import ExternalSnapshotEnvelope


def typed_alternative(
    ref: str = "alternative:test",
    *,
    value: Any = "value",
    type_ref: str = "type:test",
) -> TypedAlternative[Any]:
    return TypedAlternative(
        alternative_ref=ref,
        value=value,
        type_ref=type_ref,
        derivation_refs=("fixture:semantic",),
    )


def factor(
    ref: str = "factor:test",
    *,
    factor_type: str = "pnf.subject",
    alternatives: tuple[TypedAlternative[Any], ...] | None = None,
    residuals: tuple[str, ...] = (),
    closure_state: str = "open",
) -> Factor[Any]:
    return Factor(
        factor_ref=ref,
        factor_type=factor_type,
        alternatives=alternatives or (),
        residuals=residuals,
        closure_state=closure_state,
    )


def typed_meet(
    ref: str = "meet:test",
    *,
    state: MeetState | str = MeetState.COMPATIBLE,
    meet_type: str = "type_lattice_meet",
    residual_refs: tuple[str, ...] = (),
) -> TypedMeet[Any]:
    return TypedMeet(
        meet_ref=ref,
        left_ref="left:test",
        right_ref="right:test",
        meet_type=meet_type,
        state=state,
        residual_refs=residual_refs,
    )


def worldmonitor_snapshot(
    *,
    role: str = "observation",
    payload: Any | None = None,
) -> ExternalSnapshotEnvelope[Any]:
    return ExternalSnapshotEnvelope(
        snapshot_ref=f"worldmonitor:test@v1:{role}",
        backend_ref="worldmonitor",
        external_ref="worldmonitor:test",
        version_ref="v1",
        formal_role=role,
        payload=payload or {"event_type": "event:test"},
        provenance_refs=("fixture:worldmonitor:v1",),
    )
