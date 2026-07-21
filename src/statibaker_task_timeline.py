from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "sl.statibaker_bidirectional_task_timeline.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _event_type(event: Mapping[str, Any]) -> str:
    return _text(event.get("lifecycle_event_type") or event.get("event_type") or event.get("type")).casefold()


def _event_status(event: Mapping[str, Any]) -> str:
    return _text(event.get("status_after") or event.get("inferred_status")).casefold()


def _event_residual(event: Mapping[str, Any]) -> str:
    return _text(event.get("residual") or "partial").casefold()


def _event_timestamp(event: Mapping[str, Any]) -> str:
    return _text(event.get("timestamp"))


@dataclass
class FoldState:
    status: str = "unresolved"
    observed_slots: set[str] = field(default_factory=set)
    task_graph_effects: set[str] = field(default_factory=set)
    successor_tasks: list[dict[str, Any]] = field(default_factory=list)
    identity_evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "observed_slots": sorted(self.observed_slots),
            "task_graph_effects": sorted(self.task_graph_effects),
            "successor_tasks": self.successor_tasks,
            "identity_evidence": self.identity_evidence,
            "contradictions": self.contradictions,
            "event_ids": self.event_ids,
        }


def _normalized_event(raw_event: Mapping[str, Any], phase: str, position: int) -> dict[str, Any]:
    event = dict(raw_event)
    event.setdefault("event_id", f"{phase}:{position + 1}")
    event["phase"] = phase
    event["event_type"] = _event_type(event)
    event["residual"] = _event_residual(event)
    event.setdefault("expected_slot_matched", bool(event.get("expected_slot")))
    return event


def _apply_event(state: FoldState, event: Mapping[str, Any]) -> FoldState:
    event_id = _text(event.get("event_id"))
    if event_id:
        state.event_ids.append(event_id)

    event_type = _event_type(event)
    residual = _event_residual(event)
    status = _event_status(event)
    if status:
        state.status = status

    for slot in _list(event.get("expected_slot")) + _list(event.get("matched_expected_slots")):
        slot_text = _text(slot)
        if slot_text and event.get("expected_slot_matched") is not False:
            state.observed_slots.add(slot_text)

    for effect in _list(event.get("task_graph_effect")) + _list(event.get("task_graph_effects")):
        effect_text = _text(effect)
        if effect_text:
            state.task_graph_effects.add(effect_text)

    if event_type in {
        "blocked",
        "closed",
        "completed",
        "implemented",
        "reframed",
        "spawned_successor",
        "split_into",
        "merged_with",
        "superseded",
        "held_missing_evidence",
    }:
        state.task_graph_effects.add(event_type)

    for successor in _list(event.get("successor_tasks")):
        if isinstance(successor, Mapping):
            state.successor_tasks.append(dict(successor))

    identity = _text(event.get("task_identity_evidence") or event.get("identity_evidence"))
    if identity:
        state.identity_evidence.append(identity)

    if residual == "contradiction":
        state.contradictions.append(event_id or event_type or "contradiction")

    return state


def _fold(events: Iterable[Mapping[str, Any]], initial: FoldState | None = None) -> FoldState:
    state = initial or FoldState()
    for event in events:
        _apply_event(state, event)
    return state


def _task_identity_residual(
    *,
    prior_state: FoldState,
    seed_event: Mapping[str, Any],
    declared: str,
) -> str:
    if declared:
        return declared
    seed_residual = _event_residual(seed_event)
    if prior_state.contradictions or seed_residual == "contradiction":
        return "contradiction"
    if prior_state.identity_evidence and seed_residual == "exact":
        return "exact"
    if prior_state.event_ids:
        return "partial"
    return seed_residual or "partial"


def _lifecycle_residual(state: FoldState, missing_slots: list[str], declared: str) -> str:
    if declared:
        return declared
    if state.contradictions:
        return "contradiction"
    if missing_slots:
        return "incomplete"
    return "exact" if state.event_ids else "partial"


def reconcile_task_timeline_case(raw_case: Mapping[str, Any], position: int = 0) -> dict[str, Any]:
    """Fold the canonical thread prefix, reinterpret the seed, then fold the suffix.

    The seed is an anchor rather than an assumed task origin. Prior receipts may
    establish an already-active task, alter the seed role, or expose that the
    seed is a refinement/reopen/blocker query. Later receipts update lifecycle
    state and may create successors, splits, merges, blockers, or completion.
    """

    case = dict(raw_case)
    prior_events = [
        _normalized_event(_dict(event), "prior", index)
        for index, event in enumerate(_list(case.get("prior_event_receipts")))
        if isinstance(event, Mapping)
    ]
    seed_event = _normalized_event(_dict(case.get("seed_message_receipt")), "seed", 0)
    later_events = [
        _normalized_event(_dict(event), "later", index)
        for index, event in enumerate(_list(case.get("later_event_receipts")))
        if isinstance(event, Mapping)
    ]

    prior_state = _fold(prior_events)
    seed_state = _fold([seed_event], FoldState(**{
        "status": prior_state.status,
        "observed_slots": set(prior_state.observed_slots),
        "task_graph_effects": set(prior_state.task_graph_effects),
        "successor_tasks": list(prior_state.successor_tasks),
        "identity_evidence": list(prior_state.identity_evidence),
        "contradictions": list(prior_state.contradictions),
        "event_ids": list(prior_state.event_ids),
    }))
    final_state = _fold(later_events, seed_state)

    expected_slots = sorted({_text(slot) for slot in _list(case.get("expected_event_slots")) if _text(slot)})
    explicit_missing = sorted({_text(slot) for slot in _list(case.get("missing_expected_slots")) if _text(slot)})
    missing_slots = explicit_missing or [slot for slot in expected_slots if slot not in final_state.observed_slots]

    supplied_successors = [dict(task) for task in _list(case.get("successor_tasks")) if isinstance(task, Mapping)]
    successors = supplied_successors + [task for task in final_state.successor_tasks if task not in supplied_successors]
    final_status = final_state.status if final_state.status != "unresolved" else _text(case.get("final_task_status") or "observed")

    return {
        "timeline_id": _text(case.get("timeline_id")) or f"archive_timeline:{position + 1}",
        "task_id": _text(case.get("task_id")) or f"task:{position + 1}",
        "task_title": _text(case.get("task_title")),
        "canonical_thread_id": _text(case.get("canonical_thread_id")),
        "thread_title": _text(case.get("thread_title")),
        "seed_role": _text(case.get("seed_role")),
        "seed_task_pnf": _dict(case.get("seed_task_pnf")),
        "prior_event_receipts": prior_events,
        "seed_message_receipt": seed_event,
        "later_event_receipts": later_events,
        "observed_lifecycle_events": prior_events + [seed_event] + later_events,
        "folded_prior_state": prior_state.as_dict(),
        "seed_interpretation_state": seed_state.as_dict(),
        "folded_final_state": final_state.as_dict(),
        "expected_event_slots": expected_slots,
        "matched_expected_slots": sorted(final_state.observed_slots),
        "missing_expected_slots": missing_slots,
        "successor_tasks": successors,
        "split_or_merge_events": [
            dict(event) for event in _list(case.get("split_or_merge_events")) if isinstance(event, Mapping)
        ],
        "task_graph_effects": sorted(final_state.task_graph_effects),
        "final_task_status": final_status,
        "task_identity_residual": _task_identity_residual(
            prior_state=prior_state,
            seed_event=seed_event,
            declared=_text(case.get("task_identity_residual")),
        ),
        "lifecycle_residual": _lifecycle_residual(
            final_state,
            missing_slots,
            _text(case.get("lifecycle_residual")),
        ),
        "authority_policy": "receipt_backed_reconciliation_only",
    }


def build_bidirectional_task_timeline_probe(
    *,
    timeline_cases: Iterable[Mapping[str, Any]],
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    timelines = [reconcile_task_timeline_case(case, index) for index, case in enumerate(timeline_cases)]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": dict(source or {}),
        "timeline_count": len(timelines),
        "timelines": timelines,
        "summary": {
            "with_prior_evidence": sum(bool(row["prior_event_receipts"]) for row in timelines),
            "with_later_evidence": sum(bool(row["later_event_receipts"]) for row in timelines),
            "with_successors": sum(bool(row["successor_tasks"]) for row in timelines),
            "with_missing_expected_slots": sum(bool(row["missing_expected_slots"]) for row in timelines),
            "seed_reinterpreted_with_prior_state": sum(bool(row["folded_prior_state"]["event_ids"]) for row in timelines),
        },
        "authority_boundary": {
            "archive_thread_reconciliation_only": True,
            "raw_keyword_tasking": False,
            "live_archive_query": False,
            "task_timeline_is_bidirectional": True,
            "seed_is_not_assumed_origin": True,
            "prior_prefix_is_folded_before_seed_interpretation": True,
            "later_suffix_is_folded_after_seed_interpretation": True,
            "completion_requires_receipt": True,
            "human_project_governance_required": True,
        },
    }
