"""Consumer-triggered H9 external planning after local numeric compilation.

The strict numeric document compiler intentionally ends with world resolution
deferred.  This coordinator is invoked only when an actual consumer/query/policy
needs external facts after H3/H6 have left an observable residual.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.policy.external_demand import ExternalNeedKind
from src.storage.postgres.external_demand_runtime_store import ExternalDemandRuntimeStore


@dataclass(frozen=True, slots=True)
class ExternalNeedSpec:
    demand_id: int
    need_kind: ExternalNeedKind
    provider_id: int = 1
    axis_kind: int | None = None
    provider_property_numeric_id: int | None = None
    priority: int = 100
    revision: int = 1


@dataclass(frozen=True, slots=True)
class LateExternalPlanReceipt:
    registered_need_count: int
    planned_request_members: int
    consumer_ref: str
    query_ref: str
    policy_ref: str


class LateExternalHorizonExecutor:
    """Compile consumer-observable external needs into provider cache misses."""

    def __init__(self, database_url: str) -> None:
        self.store = ExternalDemandRuntimeStore(database_url)

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
        """Register needs then plan only consumer-H9 residual cache misses.

        This method performs no provider/network I/O.  If H3/H6 already supplied
        a valid consumer sufficiency certificate, the SQL planner sees no eligible
        H9 residual and therefore emits no external request.
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
            planned_request_members=planned,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
