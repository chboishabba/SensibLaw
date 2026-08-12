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
from src.storage.postgres.consumer_sufficient_runtime_store import ConsumerSufficientRuntimeStore
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
    semantic_request_members: int
    fresh_provider_calls: int
    semantic_members_per_unique_request: float | None
    requests_per_provider_call: float | None


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
    ) -> int:
        if need_kind is ExternalNeedKind.PROPERTY_ENRICHMENT:
            if axis_kind is None or provider_property_numeric_id is None:
                raise ValueError("property enrichment requires axis and provider property ids")
        elif axis_kind is not None or provider_property_numeric_id is not None:
            raise ValueError("discovery/identity needs do not accept property-axis coordinates")
        return self._scalar_function(
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
                            provider_subject_numeric_id=None if row[3] is None else int(row[3]),
                            provider_property_numeric_id=None if row[4] is None else int(row[4]),
                            axis_kind=None if row[5] is None else int(row[5]),
                            request_revision=int(row[6]),
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
                        raise ValueError("provider label boundary no longer matches planned symbol")

                    cursor.execute(
                        "DELETE FROM execution.semantic_pnf_label_world_candidate WHERE label_symbol_id=%s AND cache_revision=%s",
                        (label_symbol_id, request.request_revision),
                    )
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
                            INSERT INTO execution.semantic_pnf_label_world_candidate
                                (label_symbol_id,world_entity_id,candidate_ordinal,cache_revision)
                            VALUES (%s,%s,%s,%s)
                            ON CONFLICT(label_symbol_id,world_entity_id) DO UPDATE SET
                                candidate_ordinal=EXCLUDED.candidate_ordinal,
                                cache_revision=EXCLUDED.cache_revision
                            """,
                            (
                                label_symbol_id,
                                world_entity_id,
                                candidate.candidate_ordinal,
                                request.request_revision,
                            ),
                        )
        finally:
            connection.close()

    def record_external_evidence(self, *, request_id: int, evidence: ExternalEvidence) -> int:
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
                        raise ValueError("external evidence request has no local subject entity")
                    provider_id = int(row[0])
                    subject_world_entity_id = int(row[1])
                    request_property = None if row[2] is None else int(row[2])
                    request_axis = None if row[3] is None else int(row[3])
                    provider_subject_numeric_id = int(row[4])
                    if provider_subject_numeric_id != evidence.provider_subject_numeric_id:
                        raise ValueError("external evidence subject differs from planned request")
                    if request_property != evidence.provider_property_numeric_id:
                        raise ValueError("external evidence property differs from planned request")

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
                        mapping = intern_symbols(cursor, ((kind, str(evidence.value_text)),))
                        value_symbol_id = symbol_id(mapping, kind, str(evidence.value_text))
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
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def complete_external_request(self, request_id: int) -> bool:
        return bool(self._scalar_function("execution.complete_numeric_pnf_external_request", (request_id,)))

    def fail_external_request(self, request_id: int, error_ref: str) -> bool:
        return bool(
            self._scalar_function("execution.fail_numeric_pnf_external_request", (request_id, error_ref))
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
                           semantic_request_members,fresh_provider_calls,
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
                        semantic_request_members=int(row[6]),
                        fresh_provider_calls=int(row[7]),
                        semantic_members_per_unique_request=(None if row[8] is None else float(row[8])),
                        requests_per_provider_call=(None if row[9] is None else float(row[9])),
                    )
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()
