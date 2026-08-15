"""PostgreSQL gateway for late, deduplicated external-provider work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.pnf.numeric_hyperfabric import SymbolKind
from src.policy.external_demand import (
    DiscoveredWorldCandidate,
    ExternalBatchReceipt,
    ExternalEvidence,
    ExternalNeedKind,
    ExternalRequest,
    ExternalRequestKind,
    ExternalValueKind,
)
from src.storage.postgres.consumer_sufficient_runtime_store import (
    ConsumerSufficientRuntimeStore,
)
from src.storage.postgres.numeric_symbol_store import intern_symbols, symbol_id
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class ExternalCallEconomyRow:
    provider_id: int
    unique_external_requests: int
    cache_satisfied_requests: int
    provider_ready_requests: int
    leased_requests: int
    acquired_requests: int
    blocked_requests: int
    semantic_request_members: int
    fresh_provider_calls: int
    semantic_members_per_unique_request: float | None
    requests_per_provider_call: float | None


@dataclass(frozen=True, slots=True)
class ProgressiveHorizonReceipt:
    """Physical work receipt for one residual-only H3→H6→H9 pass.

    The receipt is execution evidence, not a semantic proof.  H9 planning is
    optional and never performs provider I/O here.
    """

    seeded_h3: int
    h6_residual_work: int
    inserted_h6_evidence: int
    h9_residual_work: int
    compiled_external_needs: int
    planned_external_work: int
    provider_io_performed: bool = False


@dataclass(frozen=True, slots=True)
class ConsumerWorldAxisContract:
    """Cold consumer contract selecting the H9 residual it can observe.

    All selectors are numeric PNF coordinates. At least one selector is required,
    so registering a contract can never silently mean "all H9-ready demands".
    """

    contract_ref: str
    need_kind: ExternalNeedKind
    provider_id: int = 1
    axis_kind: int | None = None
    provider_property_numeric_id: int | None = None
    contract_revision: int = 1
    need_revision: int = 1
    priority: int = 100
    minimum_source_epoch: int | None = None
    expected_target_kind: int | None = None
    expected_factor_type_symbol_id: int | None = None
    expected_object_kind_symbol_id: int | None = None
    lexical_symbol_id: int | None = None
    role_symbol_id: int | None = None
    residual_type_symbol_id: int | None = None
    active: bool = True

    def validate(self) -> None:
        if not self.contract_ref:
            raise ValueError("contract_ref must be non-empty")
        if self.contract_revision <= 0 or self.need_revision <= 0:
            raise ValueError("contract and need revisions must be positive")
        if self.priority <= 0:
            raise ValueError("priority must be positive")
        if self.minimum_source_epoch is not None and self.minimum_source_epoch <= 0:
            raise ValueError("minimum source epoch must be positive")
        if self.need_kind is ExternalNeedKind.PROPERTY_ENRICHMENT:
            if self.axis_kind is None or self.provider_property_numeric_id is None:
                raise ValueError(
                    "property contract requires axis and provider property ids"
                )
            if self.provider_property_numeric_id <= 0:
                raise ValueError("provider property id must be positive")
        elif (
            self.axis_kind is not None or self.provider_property_numeric_id is not None
        ):
            raise ValueError(
                "discovery/identity contracts do not accept property-axis coordinates"
            )
        selectors = (
            self.expected_target_kind,
            self.expected_factor_type_symbol_id,
            self.expected_object_kind_symbol_id,
            self.lexical_symbol_id,
            self.role_symbol_id,
            self.residual_type_symbol_id,
        )
        if all(selector is None for selector in selectors):
            raise ValueError(
                "consumer world-axis contract requires a numeric demand selector"
            )


class ExternalDemandRuntimeStore(ConsumerSufficientRuntimeStore):
    """H9 external-demand planning and cold provider-evidence cache."""

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
        """Execute only the semantic residual at each horizon.

        H3 evidence/proofs are already represented on the shared numeric fibre.
        This operation creates the consumer H3 work projection, marks/evaluates
        that horizon, and lets the SQL transition enqueue only rows whose rebuilt
        outcome retains a residual.  H6 then runs only over those ready rows and
        its own transition similarly exposes only the H9 residual.

        ``plan_h9`` compiles explicit consumer world-axis needs and cache/provider
        request plans for that residual.  It never claims a provider lease and
        therefore performs no external/network I/O.
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
        inserted_h6_evidence, h9_residual_work = self.process_h6_for_consumer(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
            reprocess_completed=reprocess_completed_h6,
        )

        # process_numeric_pnf_h6_for_consumer owns the H6 completion/outcome and
        # H9 residual transition atomically.  Do not advance H6 a second time.
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

    def register_external_need(
        self,
        *,
        demand_id: int,
        consumer_ref: str,
        query_ref: str,
        need_kind: ExternalNeedKind,
        provider_id: int = 1,
        policy_ref: str = "",
        axis_kind: int | None = None,
        provider_property_numeric_id: int | None = None,
        priority: int = 100,
        revision: int = 1,
        active: bool = True,
        minimum_source_epoch: int | None = None,
    ) -> int:
        if need_kind is ExternalNeedKind.PROPERTY_ENRICHMENT:
            if axis_kind is None or provider_property_numeric_id is None:
                raise ValueError(
                    "property enrichment requires axis and provider property ids"
                )
        elif axis_kind is not None or provider_property_numeric_id is not None:
            raise ValueError(
                "discovery/identity needs do not accept property-axis coordinates"
            )
        if minimum_source_epoch is not None and minimum_source_epoch <= 0:
            raise ValueError("minimum source epoch must be positive")
        need_id = self._scalar_function(
            "execution.record_numeric_pnf_consumer_external_need",
            (
                demand_id,
                consumer_ref,
                query_ref,
                policy_ref,
                int(need_kind),
                provider_id,
                axis_kind,
                provider_property_numeric_id,
                priority,
                revision,
                active,
            ),
        )
        if minimum_source_epoch is not None:
            if not self._scalar_function(
                "execution.set_numeric_pnf_external_need_minimum_source_epoch",
                (need_id, minimum_source_epoch),
            ):
                raise RuntimeError("failed to persist external freshness requirement")
        return need_id

    def register_world_axis_contract(
        self,
        *,
        consumer_ref: str,
        query_ref: str,
        contract: ConsumerWorldAxisContract,
        policy_ref: str = "",
    ) -> int:
        contract.validate()
        return self._scalar_function(
            "execution.record_numeric_pnf_consumer_world_axis_contract",
            (
                consumer_ref,
                query_ref,
                policy_ref,
                contract.contract_ref,
                contract.contract_revision,
                contract.active,
                int(contract.need_kind),
                contract.provider_id,
                contract.axis_kind,
                contract.provider_property_numeric_id,
                contract.need_revision,
                contract.priority,
                contract.minimum_source_epoch,
                contract.expected_target_kind,
                contract.expected_factor_type_symbol_id,
                contract.expected_object_kind_symbol_id,
                contract.lexical_symbol_id,
                contract.role_symbol_id,
                contract.residual_type_symbol_id,
            ),
        )

    def compile_world_axis_contracts(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> int:
        """Rebuild contract-derived needs for one document's current H9 residual."""
        return self._scalar_function(
            "execution.compile_numeric_pnf_h9_external_needs_for_consumer",
            (run_id, document_id, consumer_ref, query_ref, policy_ref),
        )

    def plan_external_demands(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> int:
        planned = self._scalar_function(
            "execution.plan_numeric_pnf_external_demands_for_consumer",
            (run_id, document_id, consumer_ref, query_ref, policy_ref),
        )
        self._scalar_function("execution.wake_numeric_pnf_external_cache_hits", ())
        return planned

    def compile_and_plan_world_axis_contracts(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> tuple[int, int]:
        """Compile only observable H9 residuals, then plan cache/provider work."""
        compiled_need_count = self.compile_world_axis_contracts(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
        planner_work_units = self.plan_external_demands(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
        )
        return compiled_need_count, planner_work_units

    def claim_external_provider_batch(
        self,
        *,
        provider_id: int,
        worker_ref: str,
        limit: int = 32,
        lease_seconds: int = 300,
    ) -> tuple[ExternalRequest, ...]:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT * FROM execution.claim_numeric_pnf_external_provider_batch(%s,%s,%s,%s)",
                        (provider_id, worker_ref, limit, lease_seconds),
                    )
                    return tuple(
                        ExternalRequest(
                            request_id=int(row[0]),
                            request_kind=ExternalRequestKind(int(row[1])),
                            label_text=None if row[2] is None else str(row[2]),
                            provider_subject_numeric_id=None
                            if row[3] is None
                            else int(row[3]),
                            provider_property_numeric_id=None
                            if row[4] is None
                            else int(row[4]),
                            axis_kind=None if row[5] is None else int(row[5]),
                            request_revision=int(row[6]),
                            minimum_source_epoch=None
                            if row[7] is None
                            else int(row[7]),
                        )
                        for row in cursor.fetchall()
                    )
        finally:
            connection.close()

    def record_external_discovery_candidates(
        self,
        *,
        request: ExternalRequest,
        candidates: Sequence[DiscoveredWorldCandidate],
    ) -> None:
        if request.request_kind is not ExternalRequestKind.CANDIDATE_DISCOVERY:
            raise ValueError("discovery candidates require a discovery request")
        if not request.label_text:
            raise ValueError("discovery request is missing boundary label text")

        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT request.provider_id,request.label_symbol_id,symbol.symbol_text
                          FROM execution.semantic_pnf_external_request AS request
                          JOIN execution.semantic_symbol AS symbol
                            ON symbol.symbol_id=request.label_symbol_id
                         WHERE request.request_id=%s
                        """,
                        (request.request_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ValueError("unknown external discovery request")
                    provider_id = int(row[0])
                    label_symbol_id = int(row[1])
                    if str(row[2]) != request.label_text:
                        raise ValueError(
                            "provider label boundary no longer matches planned symbol"
                        )

                    # Discovery is monotone candidate evidence. A partial or
                    # empty source response cannot erase older alternatives.