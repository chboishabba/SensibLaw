"""PostgreSQL coordination for lazy/incremental numeric PNF execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.policy.reopenable_runtime import EvidenceHorizon, SignedEvidence
from src.policy.world_identifier import NumericWorldIdentifier, WorldProvider
from src.storage.postgres.reopenable_runtime_store import ReopenableRuntimeStore
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class CachedEntityCandidate:
    canonical_entity_id: int
    authority_class: int
    admitted_support_count: int


class NumericIncrementalRuntimeStore(ReopenableRuntimeStore):
    """Adds the 089-091 execution-economy contracts to the reopenable store."""

    def record_evidence(self, evidence: SignedEvidence) -> int:
        # H6/H9 evidence is illegal unless the previous horizon left this demand
        # unresolved and explicitly enqueued it. H3 is the initial work surface.
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

    def record_reuse_measurement(
        self, *, run_id: int, document_id: int, workload_ref: str
    ) -> int:
        return self._scalar_function(
            "execution.record_numeric_pnf_corpus_reuse_measurement",
            (run_id, document_id, workload_ref),
        )

    def verify_hot_projection(self) -> bool:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT execution.verify_numeric_pnf_candidate_current_state()")
                return bool(cursor.fetchone()[0])
        finally:
            connection.close()
