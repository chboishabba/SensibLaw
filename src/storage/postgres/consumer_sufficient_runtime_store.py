"""Consumer/query-specific execution over the shared numeric semantic fibre.

The global H3/H6/H9 queue remains the proof-required semantic lane. This gateway
uses the independent consumer queue introduced by migration 094 so one consumer's
safe early stop cannot suppress deeper work required by another consumer.
"""
from __future__ import annotations

from src.policy.numeric_observation_tape import NumericObservationRow
from src.storage.postgres.numeric_incremental_runtime_store import NumericIncrementalRuntimeStore
from src.storage.postgres.spacy_parser_model import connect


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

    def record_consumer_sufficiency(
        self,
        *,
        demand_id: int,
        consumer_ref: str,
        query_ref: str,
        horizon: int,
        certificate_kind: int,
        residual_required: bool,
        certificate_ref: str,
        policy_ref: str = "",
        revision: int = 1,
        certificate_state: int = 1,
    ) -> int:
        """Append a query/policy/future-safety receipt without rewriting history."""
        return self._scalar_function(
            "execution.record_numeric_pnf_consumer_sufficiency",
            (
                demand_id,
                consumer_ref,
                query_ref,
                policy_ref,
                horizon,
                certificate_kind,
                residual_required,
                certificate_ref,
                revision,
                certificate_state,
            ),
        )

    def withdraw_consumer_sufficiency(
        self,
        *,
        demand_id: int,
        consumer_ref: str,
        query_ref: str,
        horizon: int,
        certificate_kind: int,
        certificate_ref: str,
        policy_ref: str = "",
        revision: int,
        residual_required: bool = True,
    ) -> int:
        """Append a withdrawn/superseded revision; the earlier receipt remains."""
        return self.record_consumer_sufficiency(
            demand_id=demand_id,
            consumer_ref=consumer_ref,
            query_ref=query_ref,
            policy_ref=policy_ref,
            horizon=horizon,
            certificate_kind=certificate_kind,
            residual_required=residual_required,
            certificate_ref=certificate_ref,
            revision=revision,
            certificate_state=2,
        )

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

    def load_numeric_observation_rows(
        self, *, run_ref: str, document_ref: str
    ) -> tuple[NumericObservationRow, ...]:
        """Read the complete v2 numeric token authority, including provenance origins."""
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT token.token_id,token.sentence_id,token.local_token_ordinal,
                           token.start_char,token.end_char,token.orth_symbol_id,
                           token.lemma_symbol_id,token.pos_symbol_id,token.tag_symbol_id,
                           token.dependency_symbol_id,token.morph_set_id,token.head_token_id,
                           token.lemma_origin_id,token.pos_origin_id,token.tag_origin_id,
                           token.dependency_origin_id
                      FROM execution.semantic_parser_token AS token
                     WHERE token.run_ref=%s AND token.document_ref=%s
                       AND token.representation_version=2
                     ORDER BY token.start_char,token.end_char,token.token_id
                    """,
                    (run_ref, document_ref),
                )
                return tuple(
                    NumericObservationRow(
                        token_id=int(row[0]),
                        sentence_id=int(row[1]),
                        local_ordinal=int(row[2]),
                        start_char=int(row[3]),
                        end_char=int(row[4]),
                        orth_symbol_id=int(row[5]),
                        lemma_symbol_id=int(row[6]),
                        pos_symbol_id=None if row[7] is None else int(row[7]),
                        tag_symbol_id=None if row[8] is None else int(row[8]),
                        dependency_symbol_id=None if row[9] is None else int(row[9]),
                        morph_set_id=None if row[10] is None else int(row[10]),
                        head_token_id=int(row[11]),
                        lemma_origin_id=int(row[12]),
                        pos_origin_id=int(row[13]),
                        tag_origin_id=int(row[14]),
                        dependency_origin_id=int(row[15]),
                    )
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()

    def rebuild_numeric_observation_tape(
        self,
        *,
        run_ref: str,
        document_ref: str,
        codebook_revision: int = 0,
    ) -> int:
        # Codec v2 packs canonical SymbolId values directly. A non-zero frequency
        # codebook revision would be false metadata until a codebook-aware codec is
        # implemented and independently roundtrip-verified.
        if codebook_revision != 0:
            raise ValueError(
                "codec v2 stores canonical SymbolId values; frequency-codebook "
                "revisions are not yet encoded"
            )
        return super().rebuild_numeric_observation_tape(
            run_ref=run_ref,
            document_ref=document_ref,
            codebook_revision=codebook_revision,
        )
