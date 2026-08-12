"""Consumer/query-specific execution over the shared numeric semantic fibre.

The global H3/H6/H9 queue remains the proof-required semantic lane.  This gateway
uses the independent consumer queue introduced by migration 094 so one consumer's
safe early stop cannot suppress deeper work required by another consumer.
"""
from __future__ import annotations

from src.storage.postgres.numeric_incremental_runtime_store import NumericIncrementalRuntimeStore


class ConsumerSufficientRuntimeStore(NumericIncrementalRuntimeStore):
    def seed_h3_for_consumer(
        self,
        *,
        run_id: int,
        document_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> int:
        return self._scalar_function(
            "execution.seed_numeric_pnf_h3_work_for_consumer",
            (run_id, document_id, consumer_ref, query_ref, policy_ref),
        )

    def consumer_horizon_ready(
        self,
        *,
        demand_id: int,
        horizon: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> bool:
        from src.storage.postgres.spacy_parser_model import connect

        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                          FROM execution.semantic_pnf_consumer_horizon_work_queue
                         WHERE demand_id=%s
                           AND consumer_ref=%s
                           AND query_ref=%s
                           AND policy_ref=%s
                           AND horizon=%s
                           AND work_state=1
                    )
                    """,
                    (demand_id, consumer_ref, query_ref, policy_ref, horizon),
                )
                return bool(cursor.fetchone()[0])
        finally:
            connection.close()

    def register_consumer_dependency(
        self,
        *,
        source_kind: int,
        source_id: int,
        demand_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
        minimum_horizon: int = 3,
        dependency_kind: int = 1,
    ) -> None:
        from src.storage.postgres.spacy_parser_model import connect

        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_consumer_reverse_dependency
                            (source_kind,source_id,demand_id,consumer_ref,query_ref,
                             policy_ref,minimum_horizon,dependency_kind)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(source_kind,source_id,demand_id,consumer_ref,
                                    query_ref,policy_ref,dependency_kind)
                        DO UPDATE SET minimum_horizon=LEAST(
                            execution.semantic_pnf_consumer_reverse_dependency.minimum_horizon,
                            EXCLUDED.minimum_horizon
                        )
                        """,
                        (
                            source_kind,
                            source_id,
                            demand_id,
                            consumer_ref,
                            query_ref,
                            policy_ref,
                            minimum_horizon,
                            dependency_kind,
                        ),
                    )
        finally:
            connection.close()

    def enqueue_affected_consumer_demands(
        self,
        *,
        source_kind: int,
        source_id: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> int:
        return self._scalar_function(
            "execution.enqueue_numeric_pnf_affected_consumer_demands",
            (source_kind, source_id, consumer_ref, query_ref, policy_ref),
        )

    def rebuild_numeric_observation_tape(
        self,
        *,
        run_ref: str,
        document_ref: str,
        codebook_revision: int = 0,
    ) -> int:
        # Codec v1 packs canonical SymbolId values directly.  A non-zero
        # frequency-codebook revision would be false metadata until a codebook-aware
        # codec is implemented and independently roundtrip-verified.
        if codebook_revision != 0:
            raise ValueError(
                "codec v1 stores canonical SymbolId values; frequency-codebook "
                "revisions are not yet encoded"
            )
        return super().rebuild_numeric_observation_tape(
            run_ref=run_ref,
            document_ref=document_ref,
            codebook_revision=codebook_revision,
        )
