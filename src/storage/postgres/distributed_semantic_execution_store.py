"""PostgreSQL authority for distributed semantic execution.

Workers execute at least once. PostgreSQL admits an immutable delta at most
once by combining deterministic identities, row-level revision compare-and-swap
and monotonically increasing lease epochs. No Python process is the semantic
owner; ``execution.semantic_owner_stream`` is the serial authority per owner
key while unrelated owner keys may advance concurrently.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Any, Iterable, Iterator, Mapping, Sequence, TypeVar

from src.policy.carriers.canonical import canonical_sha256


T = TypeVar("T")
DEFAULT_BATCH_SIZE = 256


class StaleSemanticLeaseError(RuntimeError):
    """A worker attempted to commit after its lease epoch was superseded."""


class StaleOwnerRevisionError(RuntimeError):
    """A delta was computed from an owner revision that no longer exists."""


@dataclass(frozen=True)
class SemanticJobLease:
    job_ref: str
    document_ref: str
    owner_ref: str
    operation_contract_ref: str
    input_manifest_ref: str
    expected_owner_revision: int
    canonical_ordinal: int
    priority: int
    lease_owner: str
    lease_epoch: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class SemanticDeltaAdmission:
    delta_ref: str
    job_ref: str
    owner_ref: str
    lease_epoch: int
    prior_owner_revision: int
    resulting_owner_revision: int
    state: str


@dataclass(frozen=True)
class FinalizationLease:
    checkpoint_ref: str
    document_ref: str
    owner_revision: int
    phase_ref: str
    cursor_ordinal: int
    total_rows: int | None
    lease_owner: str
    lease_epoch: int
    input_manifest_ref: str | None


def _digest(value: Any) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _batches(values: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    if size < 1:
        raise ValueError("batch size must be positive")
    iterator = iter(values)
    while batch := tuple(islice(iterator, size)):
        yield batch


class DistributedSemanticExecutionStore:
    """Transactional store methods; callers own the surrounding transaction."""

    def ensure_owner_stream(
        self,
        cursor: Any,
        *,
        document_ref: str,
        scope_ref: str,
        factor_family: str,
    ) -> str:
        identity = {
            "document_ref": document_ref,
            "scope_ref": scope_ref,
            "factor_family": factor_family,
        }
        owner_ref = "semantic-owner:" + canonical_sha256(identity)
        cursor.execute(
            """
            INSERT INTO execution.semantic_owner_stream
                (owner_ref, document_ref, scope_ref, factor_family)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_ref) DO NOTHING
            """,
            (owner_ref, document_ref, scope_ref, factor_family),
        )
        return owner_ref

    def enqueue_job(
        self,
        cursor: Any,
        *,
        document_ref: str,
        owner_ref: str,
        operation_contract_ref: str,
        input_manifest_ref: str,
        input_manifest_sha256: str,
        expected_owner_revision: int,
        canonical_ordinal: int,
        payload: Mapping[str, Any],
        dependency_job_refs: Sequence[str] = (),
        priority: int = 100,
    ) -> str:
        identity = {
            "owner_ref": owner_ref,
            "operation_contract_ref": operation_contract_ref,
            "input_manifest_ref": input_manifest_ref,
        }
        job_ref = "semantic-job:" + canonical_sha256(identity)
        initial_state = "blocked" if dependency_job_refs else "ready"
        cursor.execute(
            """
            INSERT INTO execution.semantic_job
                (job_ref, document_ref, owner_ref, operation_contract_ref,
                 input_manifest_ref, input_manifest_sha256,
                 expected_owner_revision, canonical_ordinal, priority,
                 state_ref, payload, payload_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            (
                job_ref,
                document_ref,
                owner_ref,
                operation_contract_ref,
                input_manifest_ref,
                bytes.fromhex(input_manifest_sha256),
                expected_owner_revision,
                canonical_ordinal,
                priority,
                initial_state,
                dict(payload),
                _digest(payload),
            ),
        )
        if dependency_job_refs:
            cursor.executemany(
                """
                INSERT INTO execution.semantic_job_dependency
                    (job_ref, dependency_job_ref)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                [(job_ref, value) for value in dependency_job_refs],
            )
        return job_ref

    def awaken_ready_jobs(self, cursor: Any, *, document_ref: str) -> int:
        cursor.execute(
            """
            UPDATE execution.semantic_job AS candidate
            SET state_ref = 'ready', updated_at = CURRENT_TIMESTAMP
            WHERE candidate.document_ref = %s
              AND candidate.state_ref = 'blocked'
              AND NOT EXISTS (
                  SELECT 1
                  FROM execution.semantic_job_dependency AS dependency
                  JOIN execution.semantic_job AS required
                    ON required.job_ref = dependency.dependency_job_ref
                  WHERE dependency.job_ref = candidate.job_ref
                    AND required.state_ref <> 'completed'
              )
            """,
            (document_ref,),
        )
        return int(cursor.rowcount or 0)

    def recover_expired_leases(self, cursor: Any, *, document_ref: str) -> int:
        cursor.execute(
            """
            WITH expired AS (
                UPDATE execution.semantic_job
                SET state_ref = 'retryable',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_ref = %s
                  AND state_ref = 'leased'
                  AND lease_expires_at <= CURRENT_TIMESTAMP
                RETURNING job_ref, lease_epoch
            )
            UPDATE execution.semantic_job_attempt AS attempt
            SET state_ref = 'expired'
            FROM expired
            WHERE attempt.job_ref = expired.job_ref
              AND attempt.lease_epoch = expired.lease_epoch
              AND attempt.state_ref = 'leased'
            """,
            (document_ref,),
        )
        cursor.execute(
            """
            UPDATE execution.semantic_job
            SET state_ref = 'ready', updated_at = CURRENT_TIMESTAMP
            WHERE document_ref = %s AND state_ref = 'retryable'
            """,
            (document_ref,),
        )
        return int(cursor.rowcount or 0)

    def lease_jobs(
        self,
        cursor: Any,
        *,
        document_ref: str,
        worker_ref: str,
        limit: int,
        lease_seconds: int = 300,
    ) -> tuple[SemanticJobLease, ...]:
        if limit < 1 or lease_seconds < 1:
            raise ValueError("lease limit and duration must be positive")
        cursor.execute(
            """
            WITH selected AS (
                SELECT job_ref
                FROM execution.semantic_job
                WHERE document_ref = %s
                  AND state_ref = 'ready'
                  AND not_before <= CURRENT_TIMESTAMP
                ORDER BY priority, canonical_ordinal, job_ref
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            ), leased AS (
                UPDATE execution.semantic_job AS job
                SET state_ref = 'leased',
                    lease_owner = %s,
                    lease_epoch = job.lease_epoch + 1,
                    lease_expires_at =
                        CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    attempt_count = job.attempt_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                FROM selected
                WHERE job.job_ref = selected.job_ref
                RETURNING job.*
            ), attempts AS (
                INSERT INTO execution.semantic_job_attempt
                    (job_ref, lease_epoch, worker_ref, state_ref,
                     lease_expires_at)
                SELECT job_ref, lease_epoch, %s, 'leased', lease_expires_at
                FROM leased
                ON CONFLICT (job_ref, lease_epoch) DO NOTHING
            )
            SELECT job_ref, document_ref, owner_ref, operation_contract_ref,
                   input_manifest_ref, expected_owner_revision,
                   canonical_ordinal, priority, lease_owner, lease_epoch, payload
            FROM leased
            ORDER BY priority, canonical_ordinal, job_ref
            """,
            (document_ref, limit, worker_ref, lease_seconds, worker_ref),
        )
        return tuple(
            SemanticJobLease(
                job_ref=str(row[0]),
                document_ref=str(row[1]),
                owner_ref=str(row[2]),
                operation_contract_ref=str(row[3]),
                input_manifest_ref=str(row[4]),
                expected_owner_revision=int(row[5]),
                canonical_ordinal=int(row[6]),
                priority=int(row[7]),
                lease_owner=str(row[8]),
                lease_epoch=int(row[9]),
                payload=dict(row[10] or {}),
            )
            for row in cursor.fetchall()
        )

    def renew_lease(
        self,
        cursor: Any,
        *,
        job_ref: str,
        worker_ref: str,
        lease_epoch: int,
        lease_seconds: int = 300,
    ) -> None:
        cursor.execute(
            """
            UPDATE execution.semantic_job
            SET lease_expires_at =
                    CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                updated_at = CURRENT_TIMESTAMP
            WHERE job_ref = %s
              AND state_ref = 'leased'
              AND lease_owner = %s
              AND lease_epoch = %s
            """,
            (lease_seconds, job_ref, worker_ref, lease_epoch),
        )
        if cursor.rowcount != 1:
            raise StaleSemanticLeaseError(job_ref)

    def _existing_admission(
        self, cursor: Any, *, job_ref: str
    ) -> SemanticDeltaAdmission | None:
        cursor.execute(
            """
            SELECT admission.delta_ref, admission.job_ref,
                   admission.owner_ref, admission.lease_epoch,
                   admission.prior_owner_revision,
                   admission.resulting_owner_revision,
                   admission.admission_state_ref
            FROM execution.semantic_delta_admission AS admission
            WHERE admission.job_ref = %s
            """,
            (job_ref,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return SemanticDeltaAdmission(
            delta_ref=str(row[0]),
            job_ref=str(row[1]),
            owner_ref=str(row[2]),
            lease_epoch=int(row[3]),
            prior_owner_revision=int(row[4]),
            resulting_owner_revision=int(row[5]),
            state="duplicate" if str(row[6]) == "accepted" else str(row[6]),
        )

    def admit_delta(
        self,
        cursor: Any,
        *,
        lease: SemanticJobLease,
        delta_ref: str,
        output_manifest_ref: str,
        output_manifest_sha256: str,
        payload: Mapping[str, Any],
        resource_receipt: Mapping[str, Any] | None = None,
    ) -> SemanticDeltaAdmission:
        cursor.execute(
            """
            SELECT state_ref, lease_owner, lease_epoch, expected_owner_revision
            FROM execution.semantic_job
            WHERE job_ref = %s
            FOR UPDATE
            """,
            (lease.job_ref,),
        )
        job = cursor.fetchone()
        if job is None:
            raise StaleSemanticLeaseError(lease.job_ref)
        if str(job[0]) == "completed":
            existing = self._existing_admission(cursor, job_ref=lease.job_ref)
            if existing is None:
                raise RuntimeError("completed semantic job lacks an admission")
            return existing
        if (
            str(job[0]) != "leased"
            or str(job[1]) != lease.lease_owner
            or int(job[2]) != lease.lease_epoch
        ):
            raise StaleSemanticLeaseError(lease.job_ref)

        cursor.execute(
            """
            SELECT revision
            FROM execution.semantic_owner_stream
            WHERE owner_ref = %s
            FOR UPDATE
            """,
            (lease.owner_ref,),
        )
        owner = cursor.fetchone()
        if owner is None:
            raise ValueError("semantic owner stream does not exist")
        prior_revision = int(owner[0])
        if prior_revision != lease.expected_owner_revision:
            cursor.execute(
                """
                UPDATE execution.semantic_job
                SET state_ref = 'retryable', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP,
                    expected_owner_revision = %s
                WHERE job_ref = %s AND lease_epoch = %s
                """,
                (prior_revision, lease.job_ref, lease.lease_epoch),
            )
            raise StaleOwnerRevisionError(lease.job_ref)

        cursor.execute(
            """
            INSERT INTO execution.semantic_delta
                (delta_ref, job_ref, lease_epoch, owner_ref,
                 input_owner_revision, output_manifest_ref,
                 output_manifest_sha256, payload, payload_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (delta_ref) DO NOTHING
            """,
            (
                delta_ref,
                lease.job_ref,
                lease.lease_epoch,
                lease.owner_ref,
                prior_revision,
                output_manifest_ref,
                bytes.fromhex(output_manifest_sha256),
                dict(payload),
                _digest(payload),
            ),
        )
        resulting_revision = prior_revision + 1
        cursor.execute(
            """
            UPDATE execution.semantic_owner_stream
            SET revision = %s, dirty = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE owner_ref = %s AND revision = %s
            """,
            (resulting_revision, lease.owner_ref, prior_revision),
        )
        if cursor.rowcount != 1:
            raise StaleOwnerRevisionError(lease.job_ref)

        cursor.execute(
            """
            INSERT INTO execution.semantic_delta_admission
                (delta_ref, job_ref, owner_ref, lease_epoch,
                 prior_owner_revision, resulting_owner_revision,
                 admission_state_ref)
            VALUES (%s, %s, %s, %s, %s, %s, 'accepted')
            ON CONFLICT (job_ref) DO NOTHING
            """,
            (
                delta_ref,
                lease.job_ref,
                lease.owner_ref,
                lease.lease_epoch,
                prior_revision,
                resulting_revision,
            ),
        )
        cursor.execute(
            """
            UPDATE execution.semantic_job
            SET state_ref = 'completed', lease_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_ref = %s AND state_ref = 'leased'
              AND lease_owner = %s AND lease_epoch = %s
            """,
            (lease.job_ref, lease.lease_owner, lease.lease_epoch),
        )
        if cursor.rowcount != 1:
            raise StaleSemanticLeaseError(lease.job_ref)
        cursor.execute(
            """
            UPDATE execution.semantic_job_attempt
            SET state_ref = 'completed', completed_at = CURRENT_TIMESTAMP,
                resource_receipt = %s::jsonb
            WHERE job_ref = %s AND lease_epoch = %s
            """,
            (dict(resource_receipt or {}), lease.job_ref, lease.lease_epoch),
        )
        self.awaken_ready_jobs(cursor, document_ref=lease.document_ref)
        return SemanticDeltaAdmission(
            delta_ref=delta_ref,
            job_ref=lease.job_ref,
            owner_ref=lease.owner_ref,
            lease_epoch=lease.lease_epoch,
            prior_owner_revision=prior_revision,
            resulting_owner_revision=resulting_revision,
            state="accepted",
        )

    def persist_graph_manifest(
        self,
        cursor: Any,
        *,
        manifest_ref: str,
        document_ref: str,
        graph_ref: str,
        graph_revision: int,
        root_sha256: str,
        coverage_digest: str,
        node_count: int,
        edge_count: int,
        unresolved_count: int,
        operation_contract_refs: Sequence[str],
        parent_manifest_refs: Sequence[str] = (),
        owner_ref: str | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_graph_manifest
                (manifest_ref, document_ref, owner_ref, graph_ref,
                 graph_revision, parent_manifest_refs, root_sha256,
                 node_count, edge_count, unresolved_count, coverage_digest,
                 operation_contract_refs)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s,
                    %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (manifest_ref) DO NOTHING
            """,
            (
                manifest_ref,
                document_ref,
                owner_ref,
                graph_ref,
                graph_revision,
                list(parent_manifest_refs),
                bytes.fromhex(root_sha256),
                node_count,
                edge_count,
                unresolved_count,
                bytes.fromhex(coverage_digest),
                list(operation_contract_refs),
            ),
        )

    def persist_factor_revisions(
        self,
        cursor: Any,
        *,
        manifest_ref: str,
        rows: Iterable[Mapping[str, Any]],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> int:
        completed = 0
        for batch in _batches(rows, batch_size):
            payloads = []
            for offset, row in enumerate(batch, start=completed):
                factor_ref = str(row["factor_ref"])
                revision_ref = str(
                    row.get("factor_revision_ref")
                    or "factor-revision:" + canonical_sha256(row)
                )
                payloads.append(
                    (
                        manifest_ref,
                        factor_ref,
                        revision_ref,
                        offset,
                        dict(row),
                        _digest(row),
                    )
                )
            cursor.executemany(
                """
                INSERT INTO execution.semantic_factor_revision
                    (manifest_ref, factor_ref, factor_revision_ref,
                     sequence_no, payload, payload_sha256)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (manifest_ref, factor_ref) DO NOTHING
                """,
                payloads,
            )
            completed += len(batch)
        return completed

    def persist_residual_revisions(
        self,
        cursor: Any,
        *,
        manifest_ref: str,
        rows: Iterable[Mapping[str, Any]],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> int:
        completed = 0
        for batch in _batches(rows, batch_size):
            payloads = [
                (
                    manifest_ref,
                    str(row["residual_ref"]),
                    completed + offset,
                    dict(row),
                    _digest(row),
                )
                for offset, row in enumerate(batch)
            ]
            cursor.executemany(
                """
                INSERT INTO execution.semantic_residual_revision
                    (manifest_ref, residual_ref, sequence_no,
                     payload, payload_sha256)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (manifest_ref, residual_ref) DO NOTHING
                """,
                payloads,
            )
            completed += len(batch)
        return completed

    def upsert_finalization_checkpoint(
        self,
        cursor: Any,
        *,
        checkpoint_ref: str,
        document_ref: str,
        owner_revision: int,
        phase_ref: str,
        state_ref: str,
        cursor_ordinal: int,
        checkpoint_sha256: str,
        total_rows: int | None = None,
        input_manifest_ref: str | None = None,
        output_manifest_ref: str | None = None,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_finalization_checkpoint
                (checkpoint_ref, document_ref, owner_revision, phase_ref,
                 state_ref, cursor_ordinal, total_rows, input_manifest_ref,
                 output_manifest_ref, checkpoint_sha256, metrics)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (checkpoint_ref) DO UPDATE
            SET state_ref = EXCLUDED.state_ref,
                cursor_ordinal = GREATEST(
                    execution.semantic_finalization_checkpoint.cursor_ordinal,
                    EXCLUDED.cursor_ordinal
                ),
                total_rows = EXCLUDED.total_rows,
                input_manifest_ref = EXCLUDED.input_manifest_ref,
                output_manifest_ref = EXCLUDED.output_manifest_ref,
                checkpoint_sha256 = EXCLUDED.checkpoint_sha256,
                metrics = EXCLUDED.metrics,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                checkpoint_ref,
                document_ref,
                owner_revision,
                phase_ref,
                state_ref,
                cursor_ordinal,
                total_rows,
                input_manifest_ref,
                output_manifest_ref,
                bytes.fromhex(checkpoint_sha256),
                dict(metrics or {}),
            ),
        )

    def lease_finalization_checkpoint(
        self,
        cursor: Any,
        *,
        document_ref: str,
        worker_ref: str,
        lease_seconds: int = 300,
    ) -> FinalizationLease | None:
        cursor.execute(
            """
            WITH selected AS (
                SELECT checkpoint_ref
                FROM execution.semantic_finalization_checkpoint
                WHERE document_ref = %s AND state_ref = 'ready'
                ORDER BY owner_revision, phase_ref, checkpoint_ref
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            ), leased AS (
                UPDATE execution.semantic_finalization_checkpoint AS checkpoint
                SET state_ref = 'leased', lease_owner = %s,
                    lease_epoch = checkpoint.lease_epoch + 1,
                    lease_expires_at =
                        CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP
                FROM selected
                WHERE checkpoint.checkpoint_ref = selected.checkpoint_ref
                RETURNING checkpoint.*
            )
            SELECT checkpoint_ref, document_ref, owner_revision, phase_ref,
                   cursor_ordinal, total_rows, lease_owner, lease_epoch,
                   input_manifest_ref
            FROM leased
            """,
            (document_ref, worker_ref, lease_seconds),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return FinalizationLease(
            checkpoint_ref=str(row[0]),
            document_ref=str(row[1]),
            owner_revision=int(row[2]),
            phase_ref=str(row[3]),
            cursor_ordinal=int(row[4]),
            total_rows=int(row[5]) if row[5] is not None else None,
            lease_owner=str(row[6]),
            lease_epoch=int(row[7]),
            input_manifest_ref=str(row[8]) if row[8] is not None else None,
        )

    def complete_finalization_checkpoint(
        self,
        cursor: Any,
        *,
        lease: FinalizationLease,
        output_manifest_ref: str,
        cursor_ordinal: int,
        checkpoint_sha256: str,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        cursor.execute(
            """
            UPDATE execution.semantic_finalization_checkpoint
            SET state_ref = 'completed', cursor_ordinal = %s,
                output_manifest_ref = %s, checkpoint_sha256 = %s,
                metrics = %s::jsonb, lease_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE checkpoint_ref = %s AND state_ref = 'leased'
              AND lease_owner = %s AND lease_epoch = %s
            """,
            (
                cursor_ordinal,
                output_manifest_ref,
                bytes.fromhex(checkpoint_sha256),
                dict(metrics or {}),
                lease.checkpoint_ref,
                lease.lease_owner,
                lease.lease_epoch,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleSemanticLeaseError(lease.checkpoint_ref)

    def persist_fixed_point_receipt(
        self,
        cursor: Any,
        *,
        certificate_ref: str,
        document_ref: str,
        graph_manifest_ref: str,
        document_revision: int,
        accepted_job_set_digest: str,
        unresolved_demand_digest: str,
        coverage_digest: str,
        operation_contract_refs: Sequence[str],
        local_fixed_point: bool,
        payload: Mapping[str, Any],
    ) -> None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_fixed_point_receipt
                (certificate_ref, document_ref, graph_manifest_ref,
                 document_revision, accepted_job_set_digest,
                 unresolved_demand_digest, coverage_digest,
                 operation_contract_refs, local_fixed_point,
                 payload, payload_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s, %s::jsonb, %s)
            ON CONFLICT (certificate_ref) DO NOTHING
            """,
            (
                certificate_ref,
                document_ref,
                graph_manifest_ref,
                document_revision,
                bytes.fromhex(accepted_job_set_digest),
                bytes.fromhex(unresolved_demand_digest),
                bytes.fromhex(coverage_digest),
                list(operation_contract_refs),
                local_fixed_point,
                dict(payload),
                _digest(payload),
            ),
        )

    def persist_execution_receipt(
        self,
        cursor: Any,
        *,
        receipt_ref: str,
        document_ref: str,
        graph_manifest_ref: str,
        certificate_ref: str,
        build_key_sha256: str,
        receipt_contract_ref: str,
        payload: Mapping[str, Any],
    ) -> None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_execution_receipt
                (receipt_ref, document_ref, graph_manifest_ref,
                 certificate_ref, build_key_sha256, receipt_contract_ref,
                 payload, payload_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            (
                receipt_ref,
                document_ref,
                graph_manifest_ref,
                certificate_ref,
                bytes.fromhex(build_key_sha256),
                receipt_contract_ref,
                dict(payload),
                _digest(payload),
            ),
        )

    def stage_publication(
        self,
        cursor: Any,
        *,
        publication_ref: str,
        document_ref: str,
        graph_manifest_ref: str,
        certificate_ref: str,
        publication_digest: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO execution.publication_build
                (publication_ref, document_ref, graph_manifest_ref,
                 certificate_ref, state_ref, publication_digest)
            VALUES (%s, %s, %s, %s, 'staged', %s)
            ON CONFLICT (publication_ref) DO NOTHING
            """,
            (
                publication_ref,
                document_ref,
                graph_manifest_ref,
                certificate_ref,
                bytes.fromhex(publication_digest),
            ),
        )

    def commit_publication(
        self,
        cursor: Any,
        *,
        publication_ref: str,
        expected_digest: str,
    ) -> None:
        cursor.execute(
            """
            UPDATE execution.publication_build
            SET state_ref = 'committed', committed_at = CURRENT_TIMESTAMP
            WHERE publication_ref = %s AND state_ref = 'staged'
              AND publication_digest = %s
            """,
            (publication_ref, bytes.fromhex(expected_digest)),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("publication was not in the expected staged state")

    def fixed_point_counts(
        self, cursor: Any, *, document_ref: str
    ) -> dict[str, int]:
        cursor.execute(
            """
            SELECT
                count(*) FILTER (
                    WHERE state_ref IN ('ready', 'leased', 'retryable')
                ) AS open_jobs,
                count(*) FILTER (WHERE state_ref = 'leased') AS leased_jobs
            FROM execution.semantic_job
            WHERE document_ref = %s
            """,
            (document_ref,),
        )
        job_counts = cursor.fetchone() or (0, 0)
        cursor.execute(
            """
            SELECT
                count(*) FILTER (WHERE owner.dirty) AS dirty_owners,
                COALESCE(sum(owner.unresolved_obligation_count), 0) AS obligations,
                count(*) FILTER (WHERE NOT owner.coverage_closed) AS open_coverage
            FROM execution.semantic_owner_stream AS owner
            WHERE owner.document_ref = %s
            """,
            (document_ref,),
        )
        owner_counts = cursor.fetchone() or (0, 0, 0)
        cursor.execute(
            """
            SELECT count(*)
            FROM execution.semantic_delta AS delta
            JOIN execution.semantic_job AS job ON job.job_ref = delta.job_ref
            LEFT JOIN execution.semantic_delta_admission AS admission
              ON admission.delta_ref = delta.delta_ref
            WHERE job.document_ref = %s AND admission.delta_ref IS NULL
            """,
            (document_ref,),
        )
        unadmitted = cursor.fetchone() or (0,)
        return {
            "open_jobs": int(job_counts[0]),
            "leased_jobs": int(job_counts[1]),
            "dirty_owners": int(owner_counts[0]),
            "unresolved_obligations": int(owner_counts[1]),
            "open_coverage": int(owner_counts[2]),
            "unadmitted_deltas": int(unadmitted[0]),
        }

    def document_fixed(self, cursor: Any, *, document_ref: str) -> bool:
        counts = self.fixed_point_counts(cursor, document_ref=document_ref)
        return all(value == 0 for value in counts.values())


__all__ = [
    "DistributedSemanticExecutionStore",
    "FinalizationLease",
    "SemanticDeltaAdmission",
    "SemanticJobLease",
    "StaleOwnerRevisionError",
    "StaleSemanticLeaseError",
]
