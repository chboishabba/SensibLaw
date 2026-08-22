"""Residual-only H3 -> H6 -> H9 consumer execution.

This is a thin orchestration layer over the existing numeric SQL/runtime
primitives.  It does not create a second horizon model.  Its purpose is to make
physical laziness the default API shape: H6 is invoked only for the H3 residual,
and optional H9 planning is invoked only for the H6 residual.

Provider I/O is deliberately outside this operation.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.storage.postgres.external_demand_runtime_store import ExternalDemandRuntimeStore


@dataclass(frozen=True, slots=True)
class ProgressiveHorizonReceipt:
    """Execution receipt, not semantic proof authority."""

    seeded_h3: int
    h6_residual_work: int
    inserted_h6_evidence: int
    h9_residual_work: int
    compiled_external_needs: int
    planned_external_work: int
    provider_io_performed: bool = False


class ProgressiveHorizonRuntimeStore(ExternalDemandRuntimeStore):
    """Execute the existing consumer queues in their residual-only order."""

    def process_progressive_horizons(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
        plan_h9: bool = False,
        reprocess_completed_h6: bool = False,
    ) -> ProgressiveHorizonReceipt:
        """Run one document/consumer horizon chain without speculative work.

        H3 proof/evidence already lives on the shared numeric fibre.  Seeding
        creates the consumer work projection.  Advancing H3 marks/evaluates that
        horizon and the SQL transition creates ready H6 work only for outcomes
        whose residual remains required.

        ``process_h6_for_consumer`` then consumes exactly that ready H6 set,
        produces typed numeric discourse/temporal evidence, completes H6 and
        exposes only its H9 residual.  H9 world-axis compilation/planning is
        optional and is skipped entirely when that residual is empty.

        This method never claims a provider lease and performs no provider I/O.
        """

        seeded_h3 = self.seed_h3_for_consumer(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
        h6_residual_work = self.advance_horizon_for_consumer(
            run_id=run_id,
            document_id=document_id,
            completed_horizon=3,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )

        inserted_h6_evidence = 0
        h9_residual_work = 0
        if h6_residual_work:
            inserted_h6_evidence, h9_residual_work = self.process_h6_for_consumer(
                run_id=run_id,
                document_id=document_id,
                consumer_ref=consumer_ref,
                query_ref=query_ref,
                policy_ref=policy_ref,
                reprocess_completed=reprocess_completed_h6,
            )

        compiled_external_needs = 0
        planned_external_work = 0
        if plan_h9 and h9_residual_work:
            compiled_external_needs, planned_external_work = (
                self.compile_and_plan_world_axis_contracts(
                    run_id=run_id,
                    document_id=document_id,
                    consumer_ref=consumer_ref,
                    query_ref=query_ref,
                    policy_ref=policy_ref,
                )
            )

        return ProgressiveHorizonReceipt(
            seeded_h3=seeded_h3,
            h6_residual_work=h6_residual_work,
            inserted_h6_evidence=inserted_h6_evidence,
            h9_residual_work=h9_residual_work,
            compiled_external_needs=compiled_external_needs,
            planned_external_work=planned_external_work,
        )


__all__ = ["ProgressiveHorizonReceipt", "ProgressiveHorizonRuntimeStore"]
