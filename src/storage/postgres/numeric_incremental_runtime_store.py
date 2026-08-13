"""PostgreSQL coordination for lazy/incremental numeric PNF execution."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from src.policy.numeric_observation_tape import (
    NumericObservationRow,
    pack_numeric_observation_tape,
    verify_numeric_observation_tape,
)
from src.policy.reopenable_runtime import EvidenceHorizon, SignedEvidence
from src.policy.world_context import CandidateContextRequirement, ContextAxisSymbol
from src.policy.world_identifier import NumericWorldIdentifier, WorldProvider
from src.storage.postgres.reopenable_runtime_store import ReopenableRuntimeStore
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class CachedEntityCandidate:
    canonical_entity_id: int
    authority_class: int
    admitted_support_count: int


@dataclass(frozen=True, slots=True)
class WorldContextFitRow:
    context_witness_id: int
    token_id: int
    label_symbol_id: int
    world_entity_id: int
    requirement_count: int
    supporting_count: int
    contradicting_count: int
    unknown_count: int
    signed_margin: int
    requirements_satisfied: bool


class NumericIncrementalRuntimeStore(ReopenableRuntimeStore):
    """Coordinates the numeric/reopenable runtime constitution from 089-093."""

    def record_evidence(self, evidence: SignedEvidence) -> int:
        if evidence.horizon is not EvidenceHorizon.H3_LOCAL_STRUCTURAL:
            if not self.horizon_ready(evidence.candidate.demand_id, evidence.horizon):
                raise ValueError(
                    f"demand {evidence.candidate.demand_id} is not queued for horizon "
                    f"{int(evidence.horizon)}"
                )
        return super().record_evidence(evidence)

    def horizon_ready(self, demand_id: int, horizon: EvidenceHorizon) -> bool:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM execution.semantic_pnf_horizon_work_queue
                         WHERE demand_id=%s AND horizon=%s AND work_state=1
                    )
                    """,
                    (demand_id, int(horizon)),
                )
                return bool(cursor.fetchone()[0])
        finally:
            connection.close()

    def seed_h3(self, *, run_id: int, document_id: int) -> int:
        return self._scalar_function("execution.seed_numeric_pnf_h3_work", (run_id, document_id))

    def advance_horizon(self, *, run_id: int, document_id: int, completed_horizon: int) -> int:
        return self._scalar_function(
            "execution.advance_numeric_pnf_horizon_work",
            (run_id, document_id, completed_horizon),
        )

    def advance_horizon_for_consumer(
        self,
        *,
        run_id: int,
        document_id: int,
        completed_horizon: int,
        consumer_ref: str,
        query_ref: str,
        policy_ref: str = "",
    ) -> int:
        """Escalate only demands not already sufficient for this consumer/task.

        Stopping execution does not mutate the underlying semantic demand state.
        """
        return self._scalar_function(
            "execution.advance_numeric_pnf_horizon_work_for_consumer",
            (
                run_id,
                document_id,
                completed_horizon,
                consumer_ref,
                query_ref,
                policy_ref,
            ),
        )

    def consumer_stop_at_horizon(
        self,
        *,
        demand_id: int,
        consumer_ref: str,
        query_ref: str,
        horizon: int,
        policy_ref: str = "",
    ) -> bool:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT execution.numeric_pnf_consumer_stop_at_horizon(%s,%s,%s,%s,%s)",
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
    ) -> int:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_consumer_sufficiency_certificate
                            (demand_id,consumer_ref,query_ref,policy_ref,horizon,
                             certificate_kind,residual_required,certificate_ref,revision)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(certificate_ref) DO UPDATE SET
                            residual_required=EXCLUDED.residual_required,
                            revision=EXCLUDED.revision
                        RETURNING certificate_id
                        """,
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
                        ),
                    )
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def refresh_token_ancestors(
        self, *, run_ref: str, document_ref: str, max_depth: int = 8
    ) -> int:
        return self._scalar_function(
            "execution.refresh_numeric_parser_token_ancestors",
            (run_ref, document_ref, max_depth),
        )

    def enqueue_affected_demands(
        self, *, source_kind: int, source_id: int, horizon: int = 3
    ) -> int:
        return self._scalar_function(
            "execution.enqueue_numeric_pnf_affected_demands",
            (source_kind, source_id, horizon),
        )

    def refresh_entity_label_cache(self) -> int:
        return self._scalar_function("execution.refresh_numeric_pnf_corpus_entity_label_cache", ())

    def cached_entities_for_label(
        self, label_symbol_id: int, *, limit: int = 16
    ) -> tuple[CachedEntityCandidate, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM execution.numeric_pnf_cached_entities_for_label(%s,%s)",
                    (label_symbol_id, limit),
                )
                return tuple(
                    CachedEntityCandidate(int(row[0]), int(row[1]), int(row[2]))
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()

    def cache_world_candidate(
        self,
        *,
        label_symbol_id: int,
        world_identifier: NumericWorldIdentifier,
        candidate_ordinal: int,
        cache_revision: int = 1,
    ) -> int:
        if world_identifier.provider is not WorldProvider.WIKIDATA:
            raise ValueError("only numeric Wikidata provider is currently wired")
        return self._scalar_function(
            "execution.cache_numeric_pnf_wikidata_candidate",
            (
                label_symbol_id,
                world_identifier.numeric_id,
                candidate_ordinal,
                cache_revision,
            ),
        )

    def record_world_candidate_requirement(
        self,
        *,
        world_entity_id: int,
        requirement: CandidateContextRequirement,
        evidence_ref: str,
        revision: int = 1,
    ) -> None:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_world_candidate_requirement
                            (world_entity_id,axis_kind,required_symbol_id,
                             required_polarity,requirement_revision,evidence_ref)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(world_entity_id,axis_kind,required_symbol_id,required_polarity)
                        DO UPDATE SET requirement_revision=EXCLUDED.requirement_revision,
                                      evidence_ref=EXCLUDED.evidence_ref
                        """,
                        (
                            world_entity_id,
                            requirement.axis_kind,
                            requirement.symbol_id,
                            int(requirement.polarity),
                            revision,
                            evidence_ref,
                        ),
                    )
        finally:
            connection.close()

    def record_world_context_axis_symbol(
        self, *, context_witness_id: int, observation: ContextAxisSymbol
    ) -> None:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_world_context_axis_symbol
                            (context_witness_id,axis_kind,symbol_id,polarity)
                        VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING
                        """,
                        (
                            context_witness_id,
                            observation.axis_kind,
                            observation.symbol_id,
                            int(observation.polarity),
                        ),
                    )
        finally:
            connection.close()

    def refresh_world_context_preferences(
        self, *, context_witness_id: int, revision: int = 1
    ) -> int:
        return self._scalar_function(
            "execution.refresh_numeric_pnf_world_context_preferences",
            (context_witness_id, revision),
        )

    def world_context_fit(self, *, context_witness_id: int) -> tuple[WorldContextFitRow, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT context_witness_id,token_id,label_symbol_id,world_entity_id,
                           requirement_count,supporting_count,contradicting_count,
                           unknown_count,signed_margin,requirements_satisfied
                      FROM execution.semantic_pnf_world_context_fit_v1
                     WHERE context_witness_id=%s
                     ORDER BY requirements_satisfied DESC,signed_margin DESC,world_entity_id
                    """,
                    (context_witness_id,),
                )
                return tuple(
                    WorldContextFitRow(
                        context_witness_id=int(row[0]),
                        token_id=int(row[1]),
                        label_symbol_id=int(row[2]),
                        world_entity_id=int(row[3]),
                        requirement_count=int(row[4]),
                        supporting_count=int(row[5]),
                        contradicting_count=int(row[6]),
                        unknown_count=int(row[7]),
                        signed_margin=int(row[8]),
                        requirements_satisfied=bool(row[9]),
                    )
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()

    def attach_world_candidate(
        self,
        *,
        token_id: int,
        label_symbol_id: int,
        world_entity_id: int,
        context_witness_id: int,
    ) -> bool:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT execution.attach_numeric_pnf_world_candidate(%s,%s,%s,%s)",
                        (token_id, label_symbol_id, world_entity_id, context_witness_id),
                    )
                    return bool(cursor.fetchone()[0])
        finally:
            connection.close()

    def record_reuse_measurement(
        self, *, run_id: int, document_id: int, workload_ref: str
    ) -> int:
        return self._scalar_function(
            "execution.record_numeric_pnf_corpus_reuse_measurement",
            (run_id, document_id, workload_ref),
        )

    def record_controlled_reuse_measurement(
        self,
        *,
        run_id: int,
        document_id: int,
        workload_ref: str,
        workload_digest: bytes,
        consumer_ref: str,
        compiler_config_digest: bytes,
    ) -> int:
        if len(workload_digest) != 32 or len(compiler_config_digest) != 32:
            raise ValueError("controlled workload/config digests must be SHA-256 width")
        return self._scalar_function(
            "execution.record_numeric_pnf_controlled_reuse_measurement",
            (
                run_id,
                document_id,
                workload_ref,
                workload_digest,
                consumer_ref,
                compiler_config_digest,
            ),
        )

    @staticmethod
    def controlled_workload_digest(
        *, authority_digest: bytes, consumer_ref: str, query_ref: str, policy_ref: str = ""
    ) -> bytes:
        if len(authority_digest) != 32:
            raise ValueError("authority_digest must be SHA-256 width")
        payload = (
            b"PNF-WORKLOAD-V1\x00"
            + authority_digest
            + b"\x00"
            + consumer_ref.encode("utf-8")
            + b"\x00"
            + query_ref.encode("utf-8")
            + b"\x00"
            + policy_ref.encode("utf-8")
        )
        return sha256(payload).digest()

    def load_numeric_observation_rows(
        self, *, run_ref: str, document_ref: str
    ) -> tuple[NumericObservationRow, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT token.token_id,token.sentence_id,token.local_token_ordinal,
                           token.start_char,token.end_char,token.orth_symbol_id,
                           token.lemma_symbol_id,token.pos_symbol_id,token.tag_symbol_id,
                           token.dependency_symbol_id,token.morph_set_id,token.head_token_id
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
        rows = self.load_numeric_observation_rows(run_ref=run_ref, document_ref=document_ref)
        payload, receipt = pack_numeric_observation_tape(rows)
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT execution.register_numeric_parser_tape(%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            run_ref,
                            document_ref,
                            codebook_revision,
                            receipt.token_count,
                            receipt.authority_digest,
                            receipt.packed_digest,
                            payload,
                            receipt.codec_version,
                        ),
                    )
                    tape_id = int(cursor.fetchone()[0])
                    # Independent decode/equality check before SQL is allowed to mark
                    # the projection verified.  Supplying bytes alone never certifies it.
                    verification = verify_numeric_observation_tape(rows, payload)
                    cursor.execute(
                        "SELECT execution.verify_registered_numeric_parser_tape(%s,%s,%s)",
                        (tape_id, verification.authority_digest, verification.packed_digest),
                    )
                    if not bool(cursor.fetchone()[0]):
                        raise RuntimeError("numeric observation tape verification failed")
                    return tape_id
        finally:
            connection.close()

    def verify_hot_projection(self) -> bool:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT execution.verify_numeric_pnf_candidate_current_state()")
                return bool(cursor.fetchone()[0])
        finally:
            connection.close()
