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
                    for candidate in candidates:
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_pnf_world_entity_numeric
                                (provider_id,provider_numeric_id)
                            VALUES (%s,%s)
                            ON CONFLICT(provider_id,provider_numeric_id) DO NOTHING
                            """,
                            (provider_id, candidate.provider_numeric_id),
                        )
                        cursor.execute(
                            """
                            SELECT world_entity_id
                              FROM execution.semantic_pnf_world_entity_numeric
                             WHERE provider_id=%s AND provider_numeric_id=%s
                            """,
                            (provider_id, candidate.provider_numeric_id),
                        )
                        world_entity_id = int(cursor.fetchone()[0])
                        cursor.execute(
                            """
                            SELECT execution.upsert_numeric_pnf_label_world_candidate(
                                %s,%s,%s,%s,%s,%s
                            )
                            """,
                            (
                                label_symbol_id,
                                world_entity_id,
                                candidate.candidate_ordinal,
                                request.request_revision,
                                candidate.source_epoch,
                                candidate.source_ref,
                            ),
                        )
                        if not bool(cursor.fetchone()[0]):
                            raise RuntimeError(
                                "failed to persist external discovery candidate"
                            )
        finally:
            connection.close()

    def record_external_evidence(
        self, *, request_id: int, evidence: ExternalEvidence
    ) -> int:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT request.provider_id,request.world_entity_id,
                               request.provider_property_numeric_id,request.axis_kind,
                               subject.provider_numeric_id
                          FROM execution.semantic_pnf_external_request AS request
                          JOIN execution.semantic_pnf_world_entity_numeric AS subject
                            ON subject.world_entity_id=request.world_entity_id
                           AND subject.provider_id=request.provider_id
                         WHERE request.request_id=%s
                        """,
                        (request_id,),
                    )
                    row = cursor.fetchone()
                    if row is None or row[1] is None:
                        raise ValueError(
                            "external evidence request has no local subject entity"
                        )
                    provider_id = int(row[0])
                    subject_world_entity_id = int(row[1])
                    request_property = None if row[2] is None else int(row[2])
                    request_axis = None if row[3] is None else int(row[3])
                    provider_subject_numeric_id = int(row[4])
                    if (
                        provider_subject_numeric_id
                        != evidence.provider_subject_numeric_id
                    ):
                        raise ValueError(
                            "external evidence subject differs from planned request"
                        )
                    if request_property != evidence.provider_property_numeric_id:
                        raise ValueError(
                            "external evidence property differs from planned request"
                        )

                    value_world_entity_id = value_symbol_id = value_numeric = None
                    if evidence.value_kind is ExternalValueKind.WORLD_ENTITY:
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_pnf_world_entity_numeric
                                (provider_id,provider_numeric_id)
                            VALUES (%s,%s)
                            ON CONFLICT(provider_id,provider_numeric_id) DO NOTHING
                            """,
                            (provider_id, evidence.value_provider_numeric_id),
                        )
                        cursor.execute(
                            """
                            SELECT world_entity_id
                              FROM execution.semantic_pnf_world_entity_numeric
                             WHERE provider_id=%s AND provider_numeric_id=%s
                            """,
                            (provider_id, evidence.value_provider_numeric_id),
                        )
                        value_world_entity_id = int(cursor.fetchone()[0])
                    elif evidence.value_kind is ExternalValueKind.SYMBOL:
                        kind = SymbolKind(int(evidence.value_symbol_kind))
                        mapping = intern_symbols(
                            cursor, ((kind, str(evidence.value_text)),)
                        )
                        value_symbol_id = symbol_id(
                            mapping, kind, str(evidence.value_text)
                        )
                    else:
                        value_numeric = int(evidence.value_numeric)

                    cursor.execute(
                        """
                        SELECT execution.record_numeric_pnf_external_evidence(
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        )
                        """,
                        (
                            request_id,
                            evidence.evidence_digest,
                            subject_world_entity_id,
                            evidence.provider_property_numeric_id,
                            request_axis,
                            int(evidence.value_kind),
                            value_world_entity_id,
                            value_symbol_id,
                            value_numeric,
                            evidence.provider_revision,
                            evidence.source_ref,
                        ),
                    )
                    external_evidence_id = int(cursor.fetchone()[0])
                    if evidence.source_epoch is not None:
                        cursor.execute(
                            "SELECT execution.set_numeric_pnf_external_evidence_source_epoch(%s,%s)",
                            (external_evidence_id, evidence.source_epoch),
                        )
                        if not bool(cursor.fetchone()[0]):
                            raise RuntimeError(
                                "external evidence source epoch conflicts with immutable receipt"
                            )
                    return external_evidence_id
        finally:
            connection.close()

    def complete_external_request(
        self,
        request_id: int,
        leased_minimum_source_epoch: int | None,
    ) -> bool:
        return bool(
            self._scalar_function(
                "execution.complete_numeric_pnf_external_request",
                (request_id, leased_minimum_source_epoch),
            )
        )

    def fail_external_request(self, request_id: int, error_ref: str) -> bool:
        return bool(
            self._scalar_function(
                "execution.fail_numeric_pnf_external_request", (request_id, error_ref)
            )
        )

    def block_external_request(self, request_id: int, error_ref: str) -> bool:
        return bool(
            self._scalar_function(
                "execution.block_numeric_pnf_external_request", (request_id, error_ref)
            )
        )

    def record_external_batch_receipt(
        self,
        *,
        provider_id: int,
        worker_ref: str,
        receipt: ExternalBatchReceipt,
    ) -> int:
        return self._scalar_function(
            "execution.record_numeric_pnf_external_provider_batch_receipt",
            (
                provider_id,
                worker_ref,
                receipt.leased_request_count,
                receipt.completed_request_count,
                receipt.failed_request_count,
                receipt.provider_call_count,
            ),
        )

    def external_call_economy(self) -> tuple[ExternalCallEconomyRow, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT provider_id,unique_external_requests,cache_satisfied_requests,
                           provider_ready_requests,leased_requests,acquired_requests,
                           blocked_requests,semantic_request_members,fresh_provider_calls,
                           semantic_members_per_unique_request,requests_per_provider_call
                      FROM execution.semantic_pnf_external_call_economy_v1
                     ORDER BY provider_id
                    """
                )
                return tuple(
                    ExternalCallEconomyRow(
                        provider_id=int(row[0]),
                        unique_external_requests=int(row[1]),
                        cache_satisfied_requests=int(row[2]),
                        provider_ready_requests=int(row[3]),
                        leased_requests=int(row[4]),
                        acquired_requests=int(row[5]),
                        blocked_requests=int(row[6]),
                        semantic_request_members=int(row[7]),
                        fresh_provider_calls=int(row[8]),
                        semantic_members_per_unique_request=(
                            None if row[9] is None else float(row[9])
                        ),
                        requests_per_provider_call=(
                            None if row[10] is None else float(row[10])
                        ),
                    )
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()
