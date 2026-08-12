"""PostgreSQL gateway for late, deduplicated external-provider work."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.policy.external_demand import (
    DiscoveredWorldCandidate,
    ExternalBatchReceipt,
    ExternalEvidence,
    ExternalNeedKind,
    ExternalRequest,
    ExternalRequestKind,
)
from src.storage.postgres.consumer_sufficient_runtime_store import ConsumerSufficientRuntimeStore
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
    """H9 external-demand planning and cold provider-evidence cache.

    Ordinary parser/PNF code should not call provider APIs through this class. It
    registers consumer-observable external needs, plans only H9 residual misses,
    and exposes bounded provider-ready microbatches.
    """

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
        # Cache-satisfied requests perform zero network calls. Re-open only their
        # member H9 fibres so local evidence is consumed immediately.
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
                            label_symbol_id=None if row[2] is None else int(row[2]),
                            world_entity_id=None if row[3] is None else int(row[3]),
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
        if request.label_symbol_id is None:
            raise ValueError("discovery request is missing label_symbol_id")

        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT provider_id FROM execution.semantic_pnf_external_request WHERE request_id=%s",
                        (request.request_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ValueError("unknown external request")
                    provider_id = int(row[0])

                    # This table is a rebuildable candidate cache, not proof
                    # authority. Replace this revision's ranking atomically.
                    cursor.execute(
                        "DELETE FROM execution.semantic_pnf_label_world_candidate WHERE label_symbol_id=%s AND cache_revision=%s",
                        (request.label_symbol_id, request.request_revision),
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
                                request.label_symbol_id,
                                world_entity_id,
                                candidate.candidate_ordinal,
                                request.request_revision,
                            ),
                        )
        finally:
            connection.close()

    def record_external_evidence(self, *, request_id: int, evidence: ExternalEvidence) -> int:
        return self._scalar_function(
            "execution.record_numeric_pnf_external_evidence",
            (
                request_id,
                evidence.evidence_digest,
                evidence.subject_world_entity_id,
                evidence.provider_property_numeric_id,
                evidence.axis_kind,
                int(evidence.value_kind),
                evidence.value_world_entity_id,
                evidence.value_symbol_id,
                evidence.value_numeric,
                evidence.provider_revision,
                evidence.source_ref,
            ),
        )

    def complete_external_request(self, request_id: int) -> bool:
        return bool(
            self._scalar_function("execution.complete_numeric_pnf_external_request", (request_id,))
        )

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
