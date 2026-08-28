"""Structural diagnostics for candidate-transition write amplification.

This module is deliberately semantic-authority neutral.  It turns cumulative or
per-run PostgreSQL churn counters into an explicit receipt describing how much
planner transition work was performed relative to the retained candidate state.
It does not infer wall-time speedups or parser-relative acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CandidateTransitionChurnReceipt:
    candidate_mutations: int
    execution_event_mutations: int
    observation_mutations: int
    current_state_mutations: int
    retained_current_candidates: int

    @property
    def authority_transition_rows_preserved(self) -> bool:
        """Every candidate transition has a corresponding event and observation."""

        return (
            self.execution_event_mutations == self.candidate_mutations
            and self.observation_mutations == self.candidate_mutations
        )

    @property
    def transition_to_retained_ratio(self) -> float | None:
        if self.retained_current_candidates <= 0:
            return None
        return self.candidate_mutations / self.retained_current_candidates

    @property
    def current_projection_write_ratio(self) -> float | None:
        if self.candidate_mutations <= 0:
            return None
        return self.current_state_mutations / self.candidate_mutations


def _table(audit: Mapping[str, object], name: str) -> Mapping[str, object]:
    tables = audit.get("tables")
    if not isinstance(tables, list):
        raise ValueError("audit.tables must be a list")
    for table in tables:
        if isinstance(table, Mapping) and table.get("table_name") == name:
            return table
    raise ValueError(f"missing churn table: {name}")


def _count(table: Mapping[str, object], key: str) -> int:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def assess_candidate_transition_churn(
    audit: Mapping[str, object],
) -> CandidateTransitionChurnReceipt:
    """Build an exact structural receipt from a churn-delta/audit mapping."""

    candidate = _table(audit, "semantic_pnf_demand_candidate")
    event = _table(audit, "semantic_pnf_candidate_execution_event")
    observation = _table(audit, "semantic_pnf_demand_candidate_observation")
    current = _table(audit, "semantic_pnf_candidate_current_execution")

    candidate_mutations = _count(candidate, "total_mutations")
    event_mutations = _count(event, "total_mutations")
    observation_mutations = _count(observation, "total_mutations")
    current_mutations = _count(current, "total_mutations")

    retained = current.get("live_rows_after", current.get("live_rows"))
    if isinstance(retained, bool) or not isinstance(retained, int) or retained < 0:
        raise ValueError("current candidate retained row count must be non-negative")

    return CandidateTransitionChurnReceipt(
        candidate_mutations=candidate_mutations,
        execution_event_mutations=event_mutations,
        observation_mutations=observation_mutations,
        current_state_mutations=current_mutations,
        retained_current_candidates=retained,
    )
