"""Consumer-triggered H9 external planning after local numeric compilation.

The strict numeric document compiler intentionally ends with world resolution
deferred. This coordinator is invoked only when an actual consumer/query/policy
needs external facts after H3/H6 have left an observable residual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.policy.external_demand import ExternalNeedKind
from src.storage.postgres.external_demand_runtime_store import (
    ConsumerWorldAxisContract,
    ExternalDemandRuntimeStore,
)


@dataclass(frozen=True, slots=True)
class ExternalNeedSpec:
    """One explicitly addressed H9 need.

    Retained for callers that already know the exact demand. New query/policy
    integrations should generally register a ConsumerWorldAxisContract instead,
    so the database intersects the contract with the current H9 residual.
    """

    demand_id: int
    need_kind: ExternalNeedKind
    provider_id: int = 1
    axis_kind: int | None = None
    provider_property_numeric_id: int | None = None
    priority: int = 100
    revision: int = 1
    minimum_source_epoch: int | None = None


@dataclass(frozen=True, slots=True)
class LateExternalPlanReceipt:
    registered_need_count: int
    planner_work_units: int
    consumer_ref: str
    query_ref: str
    policy_ref: str


@dataclass(frozen=True, slots=True)
class ContractExternalPlanReceipt:
    active_contract_need_count: int
    planner_work_units: int
    consumer_ref: str
    query_ref: str
    policy_ref: str


class LateExternalHorizonExecutor:
    """Compile consumer-observable external needs into provider cache misses."""

    def __init__(self, database_url: str) -> None:
        self.store = ExternalDemandRuntimeStore(database_url)

    def register_world_axis_contract(
        self,
        *,
        consumer_ref: str,
        query_ref: str,
        contract: ConsumerWorldAxisContract,
        policy_ref: str = "",
    ) -> int:
        """Persist one cold observation contract; this performs no H9/provider work."""
        return self.store.register_world_axis_contract(
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
            contract=contract,
        )

    def plan_h9_observed_world_axes(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> ContractExternalPlanReceipt:
        """Intersect current contracts with H9 residuals, then plan cache misses.

        No contract means no compiled need. A contract must carry at least one
        numeric demand selector, so this method cannot translate every H9-ready
        demand into provider work by default.
        """
        compiled, planned = self.store.compile_and_plan_world_axis_contracts(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
        return ContractExternalPlanReceipt(
            active_contract_need_count=compiled,
            planner_work_units=planned,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )

    def plan_h9_external_residual(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        needs: Iterable[ExternalNeedSpec],
        policy_ref: str = "",
    ) -> LateExternalPlanReceipt:
        """Register exact needs then plan only consumer-H9 residual cache misses.

        This remains the escape hatch for a caller that already possesses exact
        demand IDs. It performs no provider/network I/O. ``planner_work_units``
        is the SQL planner's demand/request work count and is deliberately not
        labelled as a count of newly-created requests: idempotent re-planning may
        revisit an already-deduplicated request/member.
        """

        need_tuple = tuple(needs)
        for need in need_tuple:
            self.store.register_external_need(
                demand_id=need.demand_id,
                consumer_ref=consumer_ref,
                query_ref=query_ref,
                policy_ref=policy_ref,
                need_kind=need.need_kind,
                provider_id=need.provider_id,
                axis_kind=need.axis_kind,
                provider_property_numeric_id=need.provider_property_numeric_id,
                priority=need.priority,
                revision=need.revision,
                minimum_source_epoch=need.minimum_source_epoch,
            )
        planned = self.store.plan_external_demands(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
        return LateExternalPlanReceipt(
            registered_need_count=len(need_tuple),
            planner_work_units=planned,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
