from __future__ import annotations

import os
from uuid import uuid4

import pytest

from src.pnf.streaming_fixed_point import OwnerKey, SolverJob, SolverReceipt
from src.runtime.strict_postgres_execution import PostgresLeasedExecution
from src.storage.postgres.deterministic_admission_execution import (
    install_deterministic_admission_execution,
)
from src.storage.postgres.distributed_semantic_execution import (
    ImmutableJobManifest,
    execute_serialized_streaming_job,
)
from src.storage.postgres.typed_execution_pool import install_typed_execution_pool


def _database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the strict PostgreSQL probe")
    return database_url


def _install_typed_execution() -> None:
    install_typed_execution_pool()
    install_deterministic_admission_execution()


def _manifest(
    *,
    run_ref: str,
    document_ref: str,
    owner_ref: str,
    ordinal: int,
) -> ImmutableJobManifest:
    job = SolverJob(
        owner_key=OwnerKey(
            document_ref,
            f"sentence:{ordinal}",
            "semantic.normative_relation",
        ),
        declaration_ref="declaration:probe:v1",
        input_revision=0,
        input_refs=(f"observation:{ordinal}",),
        input_payload={"observation_delta": {"observations": ()}},
        rule_set_revision="rules:probe:v1",
        coverage_requirements=("sentence",),
    )
    return ImmutableJobManifest.build(
        job_ref=job.job_ref,
        run_ref=run_ref,
        document_ref=document_ref,
        owner_ref=owner_ref,
        input_revision=0,
        input_payload=job.to_dict(),
    )


def test_strict_postgres_two_round_probe() -> None:
    database_url = _database_url()
    _install_typed_execution()

    import psycopg

    run_ref = f"probe:strict-replay:{uuid4().hex}"
    document_ref = f"document:probe:{uuid4().hex}"
    owner_ref = "owner:probe"
    manifest = _manifest(
        run_ref=run_ref,
        document_ref=document_ref,
        owner_ref=owner_ref,
        ordinal=1,
    )
    strategy = PostgresLeasedExecution(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        worker_count=2,
        max_rounds=4,
    )
    applied: list[tuple[int, str]] = []

    def apply(receipt: SolverReceipt, revision: int) -> None:
        applied.append((revision, receipt.job_ref))

    result = strategy.run_frontier(
        (manifest,),
        execute=execute_serialized_streaming_job,
        apply=apply,
        owner_ref=owner_ref,
    )

    assert len(set(result["worker_pids"])) >= 2
    assert len(set(result["backend_pids"])) >= 2
    assert result["replayed"] == 1
    assert applied == [(1, manifest.job_ref)]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT resulting_revision, payload IS NULL, receipt_ref IS NOT NULL
                FROM execution.semantic_immutable_delta
                WHERE run_ref = %s AND owner_ref = %s
                ORDER BY resulting_revision
                """,
                (run_ref, owner_ref),
            )
            assert cursor.fetchall() == [(1, True, True)]
            cursor.execute(
                """
                SELECT round_ordinal, input_owner_revision,
                       output_owner_revision, delta_count, state,
                       manifest IS NULL
                FROM execution.semantic_round_manifest
                WHERE run_ref = %s
                ORDER BY round_ordinal
                """,
                (run_ref,),
            )
            rounds = cursor.fetchall()
            assert len(rounds) >= 2
            assert rounds[-1][3:] == (0, "fixed_point", True)
            assert rounds[-1][1] == rounds[-1][2] == 1
            cursor.execute(
                """
                SELECT fixed_point_state, fixed_point_zero_change_round,
                       fixed_point_owner_revision,
                       fixed_point_certificate IS NULL,
                       fixed_point_sha256 IS NOT NULL
                FROM execution.semantic_run
                WHERE run_ref = %s
                """,
                (run_ref,),
            )
            state, zero_round, revision, legacy_null, digest_present = cursor.fetchone()
            assert state == "reached"
            assert int(zero_round) == int(rounds[-1][0])
            assert int(revision) == 1
            assert legacy_null is True
            assert digest_present is True


def test_concurrent_jobs_admit_in_stable_order_without_recomputation() -> None:
    database_url = _database_url()
    _install_typed_execution()

    import psycopg

    run_ref = f"probe:typed-admission:{uuid4().hex}"
    document_ref = f"document:typed-admission:{uuid4().hex}"
    owner_ref = "owner:typed-admission"
    manifests = tuple(
        _manifest(
            run_ref=run_ref,
            document_ref=document_ref,
            owner_ref=owner_ref,
            ordinal=ordinal,
        )
        for ordinal in range(4)
    )
    strategy = PostgresLeasedExecution(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        worker_count=4,
        max_rounds=4,
    )
    applied: list[tuple[int, str]] = []

    def apply(receipt: SolverReceipt, revision: int) -> None:
        applied.append((revision, receipt.job_ref))

    result = strategy.run_frontier(
        manifests,
        execute=execute_serialized_streaming_job,
        apply=apply,
        owner_ref=owner_ref,
    )

    expected_job_order = sorted(manifest.job_ref for manifest in manifests)
    assert result["replayed"] == 4
    assert applied == list(enumerate(expected_job_order, start=1))

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM execution.semantic_strict_job_attempt attempt
                JOIN execution.semantic_closure_job job USING (job_ref)
                WHERE job.run_ref = %s AND attempt.state = 'stale'
                """,
                (run_ref,),
            )
            assert int(cursor.fetchone()[0]) == 0
            cursor.execute(
                """
                SELECT admission.resulting_revision, delta.job_ref
                FROM execution.semantic_strict_delta_admission admission
                JOIN execution.semantic_immutable_delta delta USING (delta_ref)
                WHERE admission.run_ref = %s
                ORDER BY admission.resulting_revision
                """,
                (run_ref,),
            )
            assert cursor.fetchall() == list(enumerate(expected_job_order, start=1))
            cursor.execute(
                """
                SELECT count(*)
                FROM execution.semantic_closure_job
                WHERE run_ref = %s AND state = 'computed'
                """,
                (run_ref,),
            )
            assert int(cursor.fetchone()[0]) == 0
