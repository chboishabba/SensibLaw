"""Typed PostgreSQL execution strategy for strict semantic acceptance.

PostgreSQL is the execution state machine.  Jobs, attempts, deltas, receipts,
proposals, cursors, and publication evidence are represented by typed columns
and child relations.  No execution identity or state transition is serialized
through JSON or JSONB.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import multiprocessing as mp
import os
import pickle
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import OwnerKey, SolverJob, SolverReceipt
from src.policy.carriers.canonical import canonical_fields_sha256, canonical_sha256
from src.storage.postgres.typed_value_store import (
    load_typed_value,
    persist_typed_value,
)


AUTHORITY_BACKEND = "postgresql"
STRICT_EXECUTION_CONTRACT = "postgresql-typed-leased-exact-execution:v2"
STREAMING_OPERATION_KIND = "streaming_operator"


def _digest(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _ordered(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class TypedToken:
    ordinal: int
    observation_ref: str
    semantic_coordinate_ref: str | None
    observation_type: str
    fibre_kind: str
    sentence_index: int
    authority_ref: str | None
    token_index: int
    token_text: str
    lemma: str | None
    pos_ref: str | None
    tag_ref: str | None
    dependency_ref: str | None
    head_index: int | None
    start_char: int
    end_char: int
    entity_type_ref: str | None = None
    whitespace_text: str | None = None

    @classmethod
    def from_observation(cls, ordinal: int, row: Mapping[str, Any]) -> "TypedToken":
        token = dict(row.get("token") or {})
        return cls(
            ordinal=ordinal,
            observation_ref=str(row.get("observation_ref") or ""),
            semantic_coordinate_ref=(
                str(row["semantic_coordinate_ref"])
                if row.get("semantic_coordinate_ref")
                else None
            ),
            observation_type=str(row.get("observation_type") or "parser.token"),
            fibre_kind=str(row.get("fibre_kind") or "observation"),
            sentence_index=int(row.get("sentence_index") or 0),
            authority_ref=str(row["authority"]) if row.get("authority") else None,
            token_index=int(token.get("index") or 0),
            token_text=str(token.get("text") or ""),
            lemma=str(token["lemma"]) if token.get("lemma") is not None else None,
            pos_ref=str(token["pos"]) if token.get("pos") is not None else None,
            tag_ref=str(token["tag"]) if token.get("tag") is not None else None,
            dependency_ref=str(token["dep"]) if token.get("dep") is not None else None,
            head_index=(
                int(token["head_index"])
                if token.get("head_index") is not None
                else None
            ),
            start_char=int(token.get("start") or 0),
            end_char=int(token.get("end") or token.get("start") or 0),
            entity_type_ref=(
                str(token["ent_type"]) if token.get("ent_type") is not None else None
            ),
            whitespace_text=(
                str(token["whitespace"])
                if token.get("whitespace") is not None
                else None
            ),
        )

    def token_mapping(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "index": self.token_index,
            "text": self.token_text,
            "start": self.start_char,
            "end": self.end_char,
        }
        if self.lemma is not None:
            row["lemma"] = self.lemma
        if self.pos_ref is not None:
            row["pos"] = self.pos_ref
        if self.tag_ref is not None:
            row["tag"] = self.tag_ref
        if self.dependency_ref is not None:
            row["dep"] = self.dependency_ref
        if self.head_index is not None:
            row["head_index"] = self.head_index
        if self.entity_type_ref is not None:
            row["ent_type"] = self.entity_type_ref
        if self.whitespace_text is not None:
            row["whitespace"] = self.whitespace_text
        return row

    def observation_mapping(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "observation_ref": self.observation_ref,
            "observation_type": self.observation_type,
            "fibre_kind": self.fibre_kind,
            "sentence_index": self.sentence_index,
            "token": self.token_mapping(),
        }
        if self.semantic_coordinate_ref is not None:
            row["semantic_coordinate_ref"] = self.semantic_coordinate_ref
        if self.authority_ref is not None:
            row["authority"] = self.authority_ref
        return row


@dataclass(frozen=True)
class ImmutableJobManifest:
    job_ref: str
    run_ref: str
    document_ref: str
    owner_ref: str
    owner_scope_ref: str
    owner_factor_family: str
    input_revision: int
    declaration_ref: str
    rule_set_revision: str
    priority: int
    input_refs: tuple[str, ...]
    coverage_requirements: tuple[str, ...]
    assumptions: tuple[str, ...]
    observation_delta_ref: str
    batch_ref: str
    sequence_no: int
    parser_contract: str
    token_start: int
    token_end: int
    char_start: int
    char_end: int
    token_count: int
    coverage_barrier: str
    coverage_complete: bool
    tokens: tuple[TypedToken, ...]
    input_sha256: str
    operation_kind: str = STREAMING_OPERATION_KIND

    @classmethod
    def build(
        cls,
        *,
        job_ref: str,
        run_ref: str,
        document_ref: str,
        owner_ref: str,
        input_revision: int,
        input_payload: Mapping[str, Any],
    ) -> "ImmutableJobManifest":
        if input_revision < 0:
            raise ValueError("input_revision must be non-negative")
        row = dict(input_payload)
        owner = dict(row.get("owner_key") or {})
        nested = dict(row.get("input_payload") or {})
        delta = dict(nested.get("observation_delta") or {})
        tokens = tuple(
            TypedToken.from_observation(ordinal, observation)
            for ordinal, observation in enumerate(delta.get("observations") or ())
        )
        input_refs = _ordered(row.get("input_refs") or ())
        coverage = _ordered(row.get("coverage_requirements") or ())
        assumptions = _ordered(row.get("assumptions") or ())
        stable_fields = (
            job_ref,
            run_ref,
            document_ref,
            owner_ref,
            str(owner.get("scope_ref") or delta.get("scope_ref") or ""),
            str(owner.get("factor_family") or ""),
            str(row.get("declaration_ref") or ""),
            str(row.get("rule_set_revision") or ""),
            int(row.get("priority") or 100),
            input_refs,
            coverage,
            assumptions,
            str(delta.get("delta_ref") or delta.get("batch_ref") or ""),
            str(delta.get("batch_ref") or ""),
            int(delta.get("sequence_no") or 0),
            str(delta.get("parser_contract") or ""),
            int(delta.get("token_start") or 0),
            int(delta.get("token_end") or 0),
            int(delta.get("char_start") or 0),
            int(delta.get("char_end") or 0),
            int(delta.get("token_count") or len(tokens)),
            str(delta.get("coverage_barrier") or "sentence"),
            bool(delta.get("coverage_complete")),
            [token.__dict__ for token in tokens],
        )
        return cls(
            job_ref=job_ref,
            run_ref=run_ref,
            document_ref=document_ref,
            owner_ref=owner_ref,
            owner_scope_ref=str(owner.get("scope_ref") or delta.get("scope_ref") or ""),
            owner_factor_family=str(owner.get("factor_family") or ""),
            input_revision=input_revision,
            declaration_ref=str(row.get("declaration_ref") or ""),
            rule_set_revision=str(row.get("rule_set_revision") or ""),
            priority=int(row.get("priority") or 100),
            input_refs=input_refs,
            coverage_requirements=coverage,
            assumptions=assumptions,
            observation_delta_ref=str(
                delta.get("delta_ref") or delta.get("batch_ref") or ""
            ),
            batch_ref=str(delta.get("batch_ref") or ""),
            sequence_no=int(delta.get("sequence_no") or 0),
            parser_contract=str(delta.get("parser_contract") or ""),
            token_start=int(delta.get("token_start") or 0),
            token_end=int(delta.get("token_end") or 0),
            char_start=int(delta.get("char_start") or 0),
            char_end=int(delta.get("char_end") or 0),
            token_count=int(delta.get("token_count") or len(tokens)),
            coverage_barrier=str(delta.get("coverage_barrier") or "sentence"),
            coverage_complete=bool(delta.get("coverage_complete")),
            tokens=tokens,
            input_sha256=canonical_fields_sha256(*stable_fields),
        )

    @property
    def stable_input_ref(self) -> str:
        return "typed-job-input:" + self.input_sha256

    @property
    def input_payload(self) -> Mapping[str, Any]:
        observations = [token.observation_mapping() for token in self.tokens]
        delta = {
            "delta_ref": self.observation_delta_ref,
            "document_ref": self.document_ref,
            "batch_ref": self.batch_ref,
            "scope_ref": self.owner_scope_ref,
            "sequence_no": self.sequence_no,
            "parser_contract": self.parser_contract,
            "observation_refs": list(self.input_refs),
            "observations": observations,
            "token_start": self.token_start,
            "token_end": self.token_end,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "token_count": self.token_count,
            "coverage_barrier": self.coverage_barrier,
            "coverage_complete": self.coverage_complete,
        }
        return {"observation_delta": delta}

    def to_solver_job(self) -> SolverJob:
        return SolverJob(
            owner_key=OwnerKey(
                self.document_ref,
                self.owner_scope_ref,
                self.owner_factor_family,
            ),
            declaration_ref=self.declaration_ref,
            input_revision=self.input_revision,
            input_refs=self.input_refs,
            input_payload=self.input_payload,
            rule_set_revision=self.rule_set_revision,
            coverage_requirements=self.coverage_requirements,
            assumptions=self.assumptions,
            priority=self.priority,
        )


@dataclass(frozen=True)
class Lease:
    manifest: ImmutableJobManifest
    worker_ref: str
    fence_token: str
    attempt_ref: str
    lease_epoch: int
    expected_owner_revision: int
    backend_pid: int | None = None


@dataclass(frozen=True)
class TypedSemanticDelta:
    delta_ref: str
    prior_revision: int
    resulting_revision: int
    receipt: SolverReceipt

    @property
    def output_sha256(self) -> str:
        return canonical_fields_sha256(
            self.delta_ref,
            self.prior_revision,
            self.resulting_revision,
            self.receipt.identity_payload(),
        )

    def __getitem__(self, key: str) -> Any:
        if key == "delta_ref":
            return self.delta_ref
        if key == "prior_revision":
            return self.prior_revision
        if key == "resulting_revision":
            return self.resulting_revision
        if key in {"payload", "receipt"}:
            return self.receipt
        raise KeyError(key)


def create_run(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    kernel_key: str | None = None,
    worker_budget: int | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO execution.semantic_run
            (run_ref, document_ref, authority_backend, lifecycle,
             kernel_key, kernel_contract, worker_budget)
        VALUES (%s, %s, %s, 'created', %s, %s, %s)
        ON CONFLICT (run_ref) DO UPDATE SET
            document_ref = EXCLUDED.document_ref,
            authority_backend = EXCLUDED.authority_backend,
            kernel_key = COALESCE(EXCLUDED.kernel_key, semantic_run.kernel_key),
            kernel_contract = COALESCE(EXCLUDED.kernel_contract, semantic_run.kernel_contract),
            worker_budget = COALESCE(EXCLUDED.worker_budget, semantic_run.worker_budget)
        """,
        (
            run_ref,
            document_ref,
            AUTHORITY_BACKEND,
            kernel_key,
            STRICT_EXECUTION_CONTRACT,
            worker_budget,
        ),
    )


def register_kernel(
    cursor: Any,
    *,
    run_ref: str,
    kernel_key: str,
    worker_budget: int,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    del metadata
    if not kernel_key or worker_budget < 1:
        raise ValueError(
            "kernel registration requires a key and positive worker budget"
        )
    cursor.execute(
        """
        INSERT INTO execution.semantic_kernel_registration
            (run_ref, kernel_key, kernel_contract, worker_budget)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (run_ref) DO UPDATE SET
            kernel_key = EXCLUDED.kernel_key,
            kernel_contract = EXCLUDED.kernel_contract,
            worker_budget = EXCLUDED.worker_budget
        """,
        (run_ref, kernel_key, STRICT_EXECUTION_CONTRACT, worker_budget),
    )


def record_lifecycle(
    cursor: Any,
    *,
    run_ref: str,
    lifecycle: str,
    detail: Mapping[str, Any] | None = None,
) -> None:
    detail = dict(detail or {})
    cursor.execute(
        "SELECT lifecycle FROM execution.semantic_run WHERE run_ref = %s FOR UPDATE",
        (run_ref,),
    )
    row = cursor.fetchone()
    prior = str(row[0]) if row is not None else None
    event_ref = f"lifecycle:{run_ref}:{lifecycle}:{uuid4().hex}"
    cursor.execute(
        """
        INSERT INTO execution.semantic_lifecycle_event
            (event_ref, run_ref, lifecycle, prior_lifecycle,
             resulting_lifecycle, owner_ref, owner_revision, round_ordinal)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            event_ref,
            run_ref,
            lifecycle,
            prior,
            lifecycle,
            detail.get("owner_ref"),
            detail.get("owner_revision"),
            detail.get("round_ordinal") or detail.get("round_count"),
        ),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_run
        SET lifecycle = %s, updated_at = CURRENT_TIMESTAMP
        WHERE run_ref = %s
        """,
        (lifecycle, run_ref),
    )


def _insert_ref_rows(
    cursor: Any,
    *,
    table: str,
    column: str,
    job_ref: str,
    values: Sequence[str],
) -> None:
    if not values:
        return
    cursor.executemany(
        f"INSERT INTO execution.{table} (job_ref, ordinal, {column}) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        [(job_ref, ordinal, value) for ordinal, value in enumerate(values)],
    )


def enqueue_canonical_closure_jobs(
    cursor: Any,
    manifests: Iterable[ImmutableJobManifest],
) -> int:
    count = 0
    for manifest in manifests:
        cursor.execute(
            """
            INSERT INTO execution.semantic_closure_job
                (job_ref, run_ref, document_ref, owner_ref, input_revision,
                 input_manifest, input_sha256, declaration_ref,
                 rule_set_revision, scope_ref, factor_family,
                 stable_input_ref, priority, operation_kind,
                 expected_owner_revision)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            (
                manifest.job_ref,
                manifest.run_ref,
                manifest.document_ref,
                manifest.owner_ref,
                manifest.input_revision,
                bytes.fromhex(manifest.input_sha256),
                manifest.declaration_ref,
                manifest.rule_set_revision,
                manifest.owner_scope_ref,
                manifest.owner_factor_family,
                manifest.stable_input_ref,
                manifest.priority,
                manifest.operation_kind,
                manifest.input_revision,
            ),
        )
        count += int(cursor.rowcount == 1)
        _insert_ref_rows(
            cursor,
            table="semantic_job_input_ref",
            column="input_ref",
            job_ref=manifest.job_ref,
            values=manifest.input_refs,
        )
        _insert_ref_rows(
            cursor,
            table="semantic_job_coverage_requirement",
            column="requirement_ref",
            job_ref=manifest.job_ref,
            values=manifest.coverage_requirements,
        )
        _insert_ref_rows(
            cursor,
            table="semantic_job_assumption",
            column="assumption_ref",
            job_ref=manifest.job_ref,
            values=manifest.assumptions,
        )
        cursor.execute(
            """
            INSERT INTO execution.semantic_streaming_operator_job_input
                (job_ref, observation_delta_ref, batch_ref, scope_ref,
                 sequence_no, parser_contract, token_start, token_end,
                 char_start, char_end, token_count, coverage_barrier,
                 coverage_complete)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            (
                manifest.job_ref,
                manifest.observation_delta_ref,
                manifest.batch_ref,
                manifest.owner_scope_ref,
                manifest.sequence_no,
                manifest.parser_contract,
                manifest.token_start,
                manifest.token_end,
                manifest.char_start,
                manifest.char_end,
                manifest.token_count,
                manifest.coverage_barrier,
                manifest.coverage_complete,
            ),
        )
        if manifest.tokens:
            cursor.executemany(
                """
                INSERT INTO execution.semantic_streaming_operator_token
                    (job_ref, ordinal, observation_ref, semantic_coordinate_ref,
                     observation_type, fibre_kind, sentence_index, authority_ref,
                     token_index, token_text, lemma, pos_ref, tag_ref,
                     dependency_ref, head_index, start_char, end_char,
                     entity_type_ref, whitespace_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_ref, ordinal) DO NOTHING
                """,
                [
                    (
                        manifest.job_ref,
                        token.ordinal,
                        token.observation_ref,
                        token.semantic_coordinate_ref,
                        token.observation_type,
                        token.fibre_kind,
                        token.sentence_index,
                        token.authority_ref,
                        token.token_index,
                        token.token_text,
                        token.lemma,
                        token.pos_ref,
                        token.tag_ref,
                        token.dependency_ref,
                        token.head_index,
                        token.start_char,
                        token.end_char,
                        token.entity_type_ref,
                        token.whitespace_text,
                    )
                    for token in manifest.tokens
                ],
            )
    return count


def _load_ref_values(
    cursor: Any, table: str, column: str, job_ref: str
) -> tuple[str, ...]:
    cursor.execute(
        f"SELECT {column} FROM execution.{table} WHERE job_ref = %s ORDER BY ordinal",
        (job_ref,),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def _load_manifest(cursor: Any, job_ref: str) -> ImmutableJobManifest:
    cursor.execute(
        """
        SELECT j.job_ref, j.run_ref, j.document_ref, j.owner_ref,
               j.scope_ref, j.factor_family, j.input_revision,
               j.declaration_ref, j.rule_set_revision, j.priority,
               encode(j.input_sha256, 'hex'), j.operation_kind,
               i.observation_delta_ref, i.batch_ref, i.sequence_no,
               i.parser_contract, i.token_start, i.token_end,
               i.char_start, i.char_end, i.token_count,
               i.coverage_barrier, i.coverage_complete
        FROM execution.semantic_closure_job j
        JOIN execution.semantic_streaming_operator_job_input i USING (job_ref)
        WHERE j.job_ref = %s
        """,
        (job_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"typed closure job is incomplete: {job_ref}")
    cursor.execute(
        """
        SELECT ordinal, observation_ref, semantic_coordinate_ref,
               observation_type, fibre_kind, sentence_index, authority_ref,
               token_index, token_text, lemma, pos_ref, tag_ref,
               dependency_ref, head_index, start_char, end_char,
               entity_type_ref, whitespace_text
        FROM execution.semantic_streaming_operator_token
        WHERE job_ref = %s
        ORDER BY ordinal
        """,
        (job_ref,),
    )
    tokens = tuple(TypedToken(*token_row) for token_row in cursor.fetchall())
    manifest = ImmutableJobManifest(
        job_ref=str(row[0]),
        run_ref=str(row[1]),
        document_ref=str(row[2]),
        owner_ref=str(row[3]),
        owner_scope_ref=str(row[4]),
        owner_factor_family=str(row[5]),
        input_revision=int(row[6]),
        declaration_ref=str(row[7]),
        rule_set_revision=str(row[8]),
        priority=int(row[9]),
        input_refs=_load_ref_values(
            cursor, "semantic_job_input_ref", "input_ref", job_ref
        ),
        coverage_requirements=_load_ref_values(
            cursor,
            "semantic_job_coverage_requirement",
            "requirement_ref",
            job_ref,
        ),
        assumptions=_load_ref_values(
            cursor, "semantic_job_assumption", "assumption_ref", job_ref
        ),
        observation_delta_ref=str(row[12]),
        batch_ref=str(row[13]),
        sequence_no=int(row[14]),
        parser_contract=str(row[15]),
        token_start=int(row[16]),
        token_end=int(row[17]),
        char_start=int(row[18]),
        char_end=int(row[19]),
        token_count=int(row[20]),
        coverage_barrier=str(row[21]),
        coverage_complete=bool(row[22]),
        tokens=tokens,
        input_sha256=str(row[10]),
        operation_kind=str(row[11]),
    )
    rebuilt = ImmutableJobManifest.build(
        job_ref=manifest.job_ref,
        run_ref=manifest.run_ref,
        document_ref=manifest.document_ref,
        owner_ref=manifest.owner_ref,
        input_revision=manifest.input_revision,
        input_payload=manifest.to_solver_job().to_dict(),
    )
    if rebuilt.input_sha256 != manifest.input_sha256:
        raise ValueError("typed closure job digest mismatch")
    return manifest


def lease_next_job(
    cursor: Any,
    *,
    run_ref: str,
    worker_ref: str,
    lease_seconds: int = 60,
) -> Lease | None:
    cursor.execute(
        """
        SELECT job_ref, lease_epoch, expected_owner_revision
        FROM execution.semantic_closure_job
        WHERE run_ref = %s
          AND (
            state = 'open'
            OR (state = 'leased' AND lease_expires_at < CURRENT_TIMESTAMP)
          )
        ORDER BY priority, input_revision, job_ref
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """,
        (run_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    job_ref, prior_epoch, expected_revision = str(row[0]), int(row[1]), int(row[2])
    manifest = _load_manifest(cursor, job_ref)
    token = uuid4().hex
    epoch = prior_epoch + 1
    attempt_ref = f"attempt:{run_ref}:{job_ref}:{epoch}:{token}"
    cursor.execute("SELECT pg_backend_pid()")
    backend_pid = int(cursor.fetchone()[0])
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET state = 'leased', lease_owner = %s, lease_token = %s,
            lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
            lease_epoch = %s, attempts = attempts + 1,
            worker_pid = %s, backend_pid = %s
        WHERE job_ref = %s
        """,
        (
            worker_ref,
            token,
            lease_seconds,
            epoch,
            os.getpid(),
            backend_pid,
            job_ref,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_strict_job_attempt
            (attempt_ref, job_ref, worker_ref, lease_token, input_sha256,
             state, lease_epoch, worker_pid, backend_pid)
        VALUES (%s, %s, %s, %s, %s, 'leased', %s, %s, %s)
        """,
        (
            attempt_ref,
            job_ref,
            worker_ref,
            token,
            bytes.fromhex(manifest.input_sha256),
            epoch,
            os.getpid(),
            backend_pid,
        ),
    )
    return Lease(
        manifest=replace(manifest, input_revision=expected_revision),
        worker_ref=worker_ref,
        fence_token=token,
        attempt_ref=attempt_ref,
        lease_epoch=epoch,
        expected_owner_revision=expected_revision,
        backend_pid=backend_pid,
    )


def renew_lease(cursor: Any, *, lease: Lease, lease_seconds: int = 60) -> bool:
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
            renewals = renewals + 1
        WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
          AND state = 'leased'
        """,
        (
            lease_seconds,
            lease.manifest.job_ref,
            lease.fence_token,
            lease.lease_epoch,
        ),
    )
    return cursor.rowcount == 1


def _persist_receipt_refs(
    cursor: Any,
    receipt_ref: str,
    kind: str,
    values: Sequence[str],
) -> None:
    if not values:
        return
    cursor.executemany(
        """
        INSERT INTO execution.semantic_solver_receipt_ref
            (receipt_ref, ref_kind, ordinal, value_ref)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        [(receipt_ref, kind, ordinal, value) for ordinal, value in enumerate(values)],
    )


def _persist_proposal_refs(
    cursor: Any,
    proposal_ref: str,
    kind: str,
    values: Sequence[str],
) -> None:
    if not values:
        return
    cursor.executemany(
        """
        INSERT INTO execution.semantic_factor_proposal_ref
            (proposal_ref, ref_kind, ordinal, value_ref)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        [(proposal_ref, kind, ordinal, value) for ordinal, value in enumerate(values)],
    )


def _persist_factor_proposal(cursor: Any, proposal: FactorProposal) -> None:
    qualifier_root = persist_typed_value(cursor, proposal.qualifier_state)
    candidate_root = persist_typed_value(cursor, proposal.candidate_payload)
    execution_root = persist_typed_value(cursor, proposal.execution_metadata)
    cursor.execute(
        """
        INSERT INTO execution.semantic_factor_proposal
            (proposal_ref, document_ref, source_revision_ref,
             semantic_coordinate_ref, scope_ref, statement_role,
             coordinate_kind, fibre_kind, derivation_role, factor_type_ref,
             structural_signature, producer_contract, producer_scope,
             operation_contract, declaration_revision, support_state,
             confidence, qualifier_root_ref, candidate_root_ref,
             execution_root_ref, proposal_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (proposal_ref) DO NOTHING
        """,
        (
            proposal.proposal_ref,
            proposal.document_ref,
            proposal.source_revision_ref,
            proposal.semantic_coordinate_ref,
            proposal.scope_ref,
            proposal.statement_role,
            proposal.coordinate_kind,
            proposal.fibre_kind,
            proposal.derivation_role,
            proposal.factor_type_ref,
            proposal.structural_signature,
            proposal.producer_contract,
            proposal.producer_scope,
            proposal.operation_contract,
            proposal.declaration_revision,
            proposal.support_state,
            proposal.confidence,
            qualifier_root,
            candidate_root,
            execution_root,
            bytes.fromhex(proposal.proposal_digest),
        ),
    )
    for role_ref, value_ref in sorted(proposal.role_bindings.items()):
        cursor.execute(
            """
            INSERT INTO execution.semantic_factor_proposal_role
                (proposal_ref, role_ref, value_ref)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (proposal.proposal_ref, role_ref, value_ref),
        )
    for kind, values in (
        ("source_span", proposal.source_span_refs),
        ("input_observation", proposal.input_observation_refs),
        ("dependency_factor", proposal.dependency_factor_refs),
        ("residual", proposal.residuals),
        ("ontology_axis", proposal.ontology_axis_refs),
        ("transport", proposal.transport_refs),
        ("assumption", proposal.assumptions),
        ("coverage", proposal.coverage_requirements),
    ):
        _persist_proposal_refs(cursor, proposal.proposal_ref, kind, values)


def _persist_solver_receipt(
    cursor: Any,
    *,
    delta: TypedSemanticDelta,
    lease: Lease,
) -> None:
    receipt = delta.receipt
    metrics_root = persist_typed_value(cursor, receipt.metrics)
    cursor.execute(
        """
        INSERT INTO execution.semantic_solver_receipt
            (receipt_ref, delta_ref, job_ref, run_ref, document_ref,
             owner_ref, owner_scope_ref, owner_factor_family,
             input_revision, rule_set_revision, backend_ref,
             metrics_root_ref, receipt_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            receipt.receipt_ref,
            delta.delta_ref,
            lease.manifest.job_ref,
            lease.manifest.run_ref,
            lease.manifest.document_ref,
            lease.manifest.owner_ref,
            receipt.owner_key.scope_ref,
            receipt.owner_key.factor_family,
            receipt.input_revision,
            receipt.rule_set_revision,
            receipt.backend_ref,
            metrics_root,
            bytes.fromhex(canonical_sha256(receipt.identity_payload())),
        ),
    )
    for kind, values in (
        ("input", receipt.input_refs),
        ("residual", receipt.residuals),
        ("assumption", receipt.assumptions),
        ("coverage", receipt.coverage_requirements),
    ):
        _persist_receipt_refs(cursor, receipt.receipt_ref, kind, values)
    for ordinal, proposal in enumerate(
        sorted(receipt.proposals, key=lambda value: value.proposal_ref)
    ):
        _persist_factor_proposal(cursor, proposal)
        cursor.execute(
            """
            INSERT INTO execution.semantic_solver_receipt_proposal
                (receipt_ref, ordinal, proposal_ref)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (receipt.receipt_ref, ordinal, proposal.proposal_ref),
        )


def _coerce_delta(value: Any, manifest: ImmutableJobManifest) -> TypedSemanticDelta:
    if isinstance(value, TypedSemanticDelta):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("strict worker must return TypedSemanticDelta")
    payload = value.get("receipt", value.get("payload"))
    if isinstance(payload, SolverReceipt):
        receipt = payload
    elif isinstance(payload, Mapping):
        from src.policy.parallel_semantic_execution import _solver_receipt_from_row

        receipt = _solver_receipt_from_row(payload)
    else:
        raise TypeError("strict worker result is missing a typed solver receipt")
    return TypedSemanticDelta(
        delta_ref=str(value.get("delta_ref") or receipt.receipt_ref),
        prior_revision=int(value.get("prior_revision", manifest.input_revision)),
        resulting_revision=int(
            value.get("resulting_revision", manifest.input_revision + 1)
        ),
        receipt=receipt,
    )


def semantic_delta_admission(
    cursor: Any,
    *,
    lease: Lease,
    delta: TypedSemanticDelta,
) -> str:
    if delta.resulting_revision != delta.prior_revision + 1:
        raise ValueError("semantic delta revisions must advance by one")
    cursor.execute(
        """
        SELECT fence_token
        FROM execution.semantic_strict_delta_admission
        WHERE delta_ref = %s
        """,
        (delta.delta_ref,),
    )
    existing = cursor.fetchone()
    if existing is not None:
        return "duplicate" if str(existing[0]) == lease.fence_token else "stale"

    cursor.execute(
        """
        UPDATE execution.semantic_strict_owner_stream
        SET current_revision = %s
        WHERE run_ref = %s AND owner_ref = %s AND current_revision = %s
        RETURNING current_revision
        """,
        (
            delta.resulting_revision,
            lease.manifest.run_ref,
            lease.manifest.owner_ref,
            delta.prior_revision,
        ),
    )
    if cursor.fetchone() is None:
        cursor.execute(
            """
            SELECT current_revision
            FROM execution.semantic_strict_owner_stream
            WHERE run_ref = %s AND owner_ref = %s
            """,
            (lease.manifest.run_ref, lease.manifest.owner_ref),
        )
        current = int(cursor.fetchone()[0])
        cursor.execute(
            """
            UPDATE execution.semantic_closure_job
            SET state = 'open', input_revision = %s,
                expected_owner_revision = %s,
                lease_owner = NULL, lease_token = NULL,
                lease_expires_at = NULL
            WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
            """,
            (
                current,
                current,
                lease.manifest.job_ref,
                lease.fence_token,
                lease.lease_epoch,
            ),
        )
        return "stale"

    cursor.execute(
        """
        INSERT INTO execution.semantic_immutable_delta
            (delta_ref, run_ref, document_ref, owner_ref,
             resulting_revision, prior_revision, payload, payload_sha256,
             job_ref, lease_epoch, expected_owner_revision,
             receipt_ref, receipt_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_ref, owner_ref, resulting_revision) DO NOTHING
        """,
        (
            delta.delta_ref,
            lease.manifest.run_ref,
            lease.manifest.document_ref,
            lease.manifest.owner_ref,
            delta.resulting_revision,
            delta.prior_revision,
            bytes.fromhex(delta.output_sha256),
            lease.manifest.job_ref,
            lease.lease_epoch,
            lease.expected_owner_revision,
            delta.receipt.receipt_ref,
            bytes.fromhex(canonical_sha256(delta.receipt.identity_payload())),
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("owner revision advanced without a durable delta")
    _persist_solver_receipt(cursor, delta=delta, lease=lease)
    cursor.execute(
        """
        INSERT INTO execution.semantic_strict_delta_admission
            (delta_ref, run_ref, owner_ref, resulting_revision,
             prior_revision, fence_token, lease_epoch)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            delta.delta_ref,
            lease.manifest.run_ref,
            lease.manifest.owner_ref,
            delta.resulting_revision,
            delta.prior_revision,
            lease.fence_token,
            lease.lease_epoch,
        ),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET state = 'completed', lease_expires_at = NULL
        WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
        """,
        (lease.manifest.job_ref, lease.fence_token, lease.lease_epoch),
    )
    return "accepted"


def _load_receipt_refs(cursor: Any, receipt_ref: str, kind: str) -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT value_ref
        FROM execution.semantic_solver_receipt_ref
        WHERE receipt_ref = %s AND ref_kind = %s
        ORDER BY ordinal
        """,
        (receipt_ref, kind),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def _load_proposal_refs(cursor: Any, proposal_ref: str, kind: str) -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT value_ref
        FROM execution.semantic_factor_proposal_ref
        WHERE proposal_ref = %s AND ref_kind = %s
        ORDER BY ordinal
        """,
        (proposal_ref, kind),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def _load_factor_proposal(cursor: Any, proposal_ref: str) -> FactorProposal:
    cursor.execute(
        """
        SELECT document_ref, source_revision_ref, semantic_coordinate_ref,
               scope_ref, statement_role, coordinate_kind, fibre_kind,
               derivation_role, factor_type_ref, structural_signature,
               producer_contract, producer_scope, operation_contract,
               declaration_revision, support_state, confidence,
               qualifier_root_ref, candidate_root_ref, execution_root_ref,
               encode(proposal_sha256, 'hex')
        FROM execution.semantic_factor_proposal
        WHERE proposal_ref = %s
        """,
        (proposal_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"missing typed factor proposal: {proposal_ref}")
    cursor.execute(
        """
        SELECT role_ref, value_ref
        FROM execution.semantic_factor_proposal_role
        WHERE proposal_ref = %s
        ORDER BY role_ref
        """,
        (proposal_ref,),
    )
    roles = {str(role): str(value) for role, value in cursor.fetchall()}
    proposal = FactorProposal(
        document_ref=str(row[0]),
        source_revision_ref=str(row[1]),
        semantic_coordinate_ref=str(row[2]),
        scope_ref=str(row[3]),
        statement_role=str(row[4]),
        coordinate_kind=str(row[5]),
        fibre_kind=str(row[6]),
        derivation_role=str(row[7]),
        factor_type_ref=str(row[8]),
        structural_signature=str(row[9]),
        producer_contract=str(row[10]),
        producer_scope=str(row[11]),
        operation_contract=str(row[12]),
        declaration_revision=str(row[13]),
        support_state=str(row[14]),
        confidence=float(row[15]) if row[15] is not None else None,
        qualifier_state=load_typed_value(cursor, row[16]),
        candidate_payload=load_typed_value(cursor, row[17]),
        execution_metadata=load_typed_value(cursor, row[18]),
        role_bindings=roles,
        source_span_refs=_load_proposal_refs(cursor, proposal_ref, "source_span"),
        input_observation_refs=_load_proposal_refs(
            cursor, proposal_ref, "input_observation"
        ),
        dependency_factor_refs=_load_proposal_refs(
            cursor, proposal_ref, "dependency_factor"
        ),
        residuals=_load_proposal_refs(cursor, proposal_ref, "residual"),
        ontology_axis_refs=_load_proposal_refs(cursor, proposal_ref, "ontology_axis"),
        transport_refs=_load_proposal_refs(cursor, proposal_ref, "transport"),
        assumptions=_load_proposal_refs(cursor, proposal_ref, "assumption"),
        coverage_requirements=_load_proposal_refs(cursor, proposal_ref, "coverage"),
    )
    if proposal.proposal_ref != proposal_ref or proposal.proposal_digest != str(
        row[19]
    ):
        raise ValueError("typed factor proposal identity mismatch")
    return proposal


def _load_solver_receipt(cursor: Any, receipt_ref: str) -> SolverReceipt:
    cursor.execute(
        """
        SELECT job_ref, document_ref, owner_scope_ref, owner_factor_family,
               input_revision, rule_set_revision, backend_ref,
               metrics_root_ref, encode(receipt_sha256, 'hex')
        FROM execution.semantic_solver_receipt
        WHERE receipt_ref = %s
        """,
        (receipt_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"missing typed solver receipt: {receipt_ref}")
    cursor.execute(
        """
        SELECT proposal_ref
        FROM execution.semantic_solver_receipt_proposal
        WHERE receipt_ref = %s
        ORDER BY ordinal
        """,
        (receipt_ref,),
    )
    proposals = tuple(
        _load_factor_proposal(cursor, str(proposal_row[0]))
        for proposal_row in cursor.fetchall()
    )
    receipt = SolverReceipt(
        job_ref=str(row[0]),
        owner_key=OwnerKey(str(row[1]), str(row[2]), str(row[3])),
        input_revision=int(row[4]),
        input_refs=_load_receipt_refs(cursor, receipt_ref, "input"),
        rule_set_revision=str(row[5]),
        proposals=proposals,
        residuals=_load_receipt_refs(cursor, receipt_ref, "residual"),
        assumptions=_load_receipt_refs(cursor, receipt_ref, "assumption"),
        coverage_requirements=_load_receipt_refs(cursor, receipt_ref, "coverage"),
        metrics=load_typed_value(cursor, row[7]),
        backend_ref=str(row[6]),
    )
    if receipt.receipt_ref != receipt_ref:
        raise ValueError("typed solver receipt reference mismatch")
    if canonical_sha256(receipt.identity_payload()) != str(row[8]):
        raise ValueError("typed solver receipt digest mismatch")
    return receipt


def replay_accepted_deltas(
    cursor: Any,
    *,
    run_ref: str,
    owner_ref: str,
    apply: Callable[[SolverReceipt, int], None],
    starting_revision: int = 0,
    rehydrate: Callable[[ImmutableJobManifest], None] | None = None,
) -> int:
    cursor.execute(
        """
        SELECT d.resulting_revision, d.receipt_ref, d.job_ref, d.delta_ref
        FROM execution.semantic_immutable_delta d
        JOIN execution.semantic_strict_delta_admission a USING (delta_ref)
        WHERE d.run_ref = %s AND d.owner_ref = %s
          AND d.resulting_revision > %s
        ORDER BY d.resulting_revision
        """,
        (run_ref, owner_ref, starting_revision),
    )
    rows = tuple(cursor.fetchall())
    expected = starting_revision + 1
    count = 0
    for revision, receipt_ref, job_ref, delta_ref in rows:
        revision = int(revision)
        if revision != expected:
            raise ValueError(
                f"non-contiguous accepted owner revision: expected {expected}, got {revision}"
            )
        if rehydrate is not None:
            rehydrate(_load_manifest(cursor, str(job_ref)))
        receipt = _load_solver_receipt(cursor, str(receipt_ref))
        apply(receipt, revision)
        cursor.execute(
            """
            INSERT INTO execution.semantic_owner_revision_history
                (run_ref, owner_ref, revision, delta_ref)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (run_ref, owner_ref, revision, str(delta_ref)),
        )
        expected += 1
        count += 1
    return count


class DistributedSemanticWorker:
    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        run_ref: str,
        worker_ref: str,
        execute: Callable[[ImmutableJobManifest], Any],
        lease_seconds: int = 60,
    ) -> None:
        self.connection_factory = connection_factory
        self.run_ref = run_ref
        self.worker_ref = worker_ref
        self.execute = execute
        self.lease_seconds = lease_seconds

    def run_once(self) -> str:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = lease_next_job(
                        cursor,
                        run_ref=self.run_ref,
                        worker_ref=self.worker_ref,
                        lease_seconds=self.lease_seconds,
                    )
            if lease is None:
                return "idle"
            try:
                delta = _coerce_delta(self.execute(lease.manifest), lease.manifest)
            except Exception:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_strict_job_attempt
                            SET state = 'failed', completed_at = CURRENT_TIMESTAMP
                            WHERE attempt_ref = %s
                            """,
                            (lease.attempt_ref,),
                        )
                        cursor.execute(
                            """
                            UPDATE execution.semantic_closure_job
                            SET state = 'open', lease_owner = NULL,
                                lease_token = NULL, lease_expires_at = NULL,
                                retry_count = retry_count + 1
                            WHERE job_ref = %s AND lease_token = %s
                              AND lease_epoch = %s
                            """,
                            (
                                lease.manifest.job_ref,
                                lease.fence_token,
                                lease.lease_epoch,
                            ),
                        )
                raise
            with connection.transaction():
                with connection.cursor() as cursor:
                    status = semantic_delta_admission(
                        cursor,
                        lease=lease,
                        delta=delta,
                    )
                    cursor.execute(
                        """
                        UPDATE execution.semantic_strict_job_attempt
                        SET state = %s, output_sha256 = %s,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE attempt_ref = %s AND lease_epoch = %s
                        """,
                        (
                            "stale" if status == "stale" else "completed",
                            bytes.fromhex(delta.output_sha256),
                            lease.attempt_ref,
                            lease.lease_epoch,
                        ),
                    )
                    return status
        finally:
            connection.close()

    def run_until_idle(self) -> dict[str, int]:
        counts = {"accepted": 0, "duplicate": 0, "stale": 0, "idle": 0}
        while True:
            status = self.run_once()
            counts[status] = counts.get(status, 0) + 1
            if status == "idle":
                return counts


@dataclass(frozen=True)
class WorkerReceipt:
    worker_ref: str
    worker_pid: int
    backend_pid: int | None
    application_name: str
    leases: int
    renewals: int
    accepted: int
    duplicates: int
    stale: int
    retries: int
    failures: int

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _process_worker_main(
    database_url: str,
    run_ref: str,
    worker_ref: str,
    execute: Callable[[ImmutableJobManifest], Any],
    lease_seconds: int,
    result_queue: Any,
) -> None:
    application_name = f"sensiblaw-strict:{run_ref}:{worker_ref}"
    import psycopg

    connection = psycopg.connect(database_url, application_name=application_name)
    stats: dict[str, Any] = {
        "worker_ref": worker_ref,
        "worker_pid": os.getpid(),
        "backend_pid": None,
        "application_name": application_name,
        "leases": 0,
        "renewals": 0,
        "accepted": 0,
        "duplicates": 0,
        "stale": 0,
        "retries": 0,
        "failures": 0,
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            stats["backend_pid"] = int(cursor.fetchone()[0])
        connection.commit()
        while True:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = lease_next_job(
                        cursor,
                        run_ref=run_ref,
                        worker_ref=worker_ref,
                        lease_seconds=lease_seconds,
                    )
            if lease is None:
                break
            stats["leases"] += 1
            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        if renew_lease(
                            cursor,
                            lease=lease,
                            lease_seconds=lease_seconds,
                        ):
                            stats["renewals"] += 1
                delta = _coerce_delta(execute(lease.manifest), lease.manifest)
                with connection.transaction():
                    with connection.cursor() as cursor:
                        status = semantic_delta_admission(
                            cursor,
                            lease=lease,
                            delta=delta,
                        )
                        stats["duplicates" if status == "duplicate" else status] += 1
                        cursor.execute(
                            """
                            UPDATE execution.semantic_strict_job_attempt
                            SET state = %s, output_sha256 = %s,
                                completed_at = CURRENT_TIMESTAMP
                            WHERE attempt_ref = %s AND lease_epoch = %s
                            """,
                            (
                                "stale" if status == "stale" else "completed",
                                bytes.fromhex(delta.output_sha256),
                                lease.attempt_ref,
                                lease.lease_epoch,
                            ),
                        )
            except Exception:
                stats["failures"] += 1
                stats["retries"] += 1
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_strict_job_attempt
                            SET state = 'failed', completed_at = CURRENT_TIMESTAMP
                            WHERE attempt_ref = %s
                            """,
                            (lease.attempt_ref,),
                        )
                        cursor.execute(
                            """
                            UPDATE execution.semantic_closure_job
                            SET state = 'open', lease_owner = NULL,
                                lease_token = NULL, lease_expires_at = NULL,
                                retry_count = retry_count + 1
                            WHERE job_ref = %s AND lease_token = %s
                              AND lease_epoch = %s
                            """,
                            (
                                lease.manifest.job_ref,
                                lease.fence_token,
                                lease.lease_epoch,
                            ),
                        )
                raise
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_worker_receipt
                        (receipt_ref, run_ref, document_ref, worker_ref,
                         worker_pid, backend_pid, application_name,
                         leases, renewals, accepted, duplicates, stale,
                         retries, failures)
                    VALUES (%s, %s,
                            (SELECT document_ref FROM execution.semantic_run WHERE run_ref = %s),
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_ref, worker_ref) DO UPDATE SET
                        leases = EXCLUDED.leases,
                        renewals = EXCLUDED.renewals,
                        accepted = EXCLUDED.accepted,
                        duplicates = EXCLUDED.duplicates,
                        stale = EXCLUDED.stale,
                        retries = EXCLUDED.retries,
                        failures = EXCLUDED.failures
                    """,
                    (
                        f"worker-receipt:{run_ref}:{worker_ref}",
                        run_ref,
                        run_ref,
                        worker_ref,
                        stats["worker_pid"],
                        stats["backend_pid"],
                        application_name,
                        stats["leases"],
                        stats["renewals"],
                        stats["accepted"],
                        stats["duplicates"],
                        stats["stale"],
                        stats["retries"],
                        stats["failures"],
                    ),
                )
        result_queue.put(stats)
    except Exception as error:
        stats["error"] = repr(error)
        result_queue.put(stats)
        raise
    finally:
        connection.close()


class ProcessPostgresWorkerPool:
    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        worker_count: int,
        execute: Callable[[ImmutableJobManifest], Any],
        lease_seconds: int = 60,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        try:
            pickle.dumps(execute)
        except (pickle.PicklingError, AttributeError, TypeError) as error:
            raise TypeError(
                "strict process worker executor must be spawn-picklable"
            ) from error
        self.database_url = database_url
        self.run_ref = run_ref
        self.worker_count = worker_count
        self.execute = execute
        self.lease_seconds = lease_seconds

    def run_until_idle(self) -> dict[str, Any]:
        context = mp.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(
                target=_process_worker_main,
                args=(
                    self.database_url,
                    self.run_ref,
                    f"{self.run_ref}:worker:{index}",
                    self.execute,
                    self.lease_seconds,
                    queue,
                ),
                name=f"sensiblaw-strict-worker-{index}",
            )
            for index in range(self.worker_count)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join()
        receipts: list[dict[str, Any]] = []
        while True:
            try:
                receipts.append(queue.get_nowait())
            except Exception:
                break
        if any(process.exitcode not in (0, None) for process in processes):
            errors = [
                receipt.get("error") for receipt in receipts if receipt.get("error")
            ]
            detail = "; ".join(str(error) for error in errors) or (
                "child exited without acknowledgement"
            )
            raise RuntimeError(
                "strict PostgreSQL worker failed; durable leases remain recoverable: "
                + detail
            )
        return {
            "worker_pids": [
                int(receipt["worker_pid"])
                for receipt in receipts
                if receipt.get("worker_pid")
            ],
            "backend_pids": [
                int(receipt["backend_pid"])
                for receipt in receipts
                if receipt.get("backend_pid")
            ],
            "receipts": receipts,
        }


def execute_serialized_streaming_job(
    manifest: ImmutableJobManifest,
) -> TypedSemanticDelta:
    from src.pnf.streaming_fixed_point import PythonClosureExecutor
    from src.pnf.streaming_operator_executor import solve_operator_job

    job = manifest.to_solver_job()
    receipt = PythonClosureExecutor({job.declaration_ref: solve_operator_job}).execute(
        job
    )
    receipt = replace(
        receipt,
        job_ref=manifest.job_ref,
        input_revision=manifest.input_revision,
    )
    return TypedSemanticDelta(
        delta_ref=receipt.receipt_ref,
        prior_revision=manifest.input_revision,
        resulting_revision=manifest.input_revision + 1,
        receipt=receipt,
    )


@dataclass(frozen=True)
class PublicationDescriptor:
    graph_ref: str
    ledger_ref: str | None
    certificate_ref: str | None
    owner_fingerprint_ref: str | None
    factor_count: int
    residual_count: int
    byte_count: int
    build_ref: str | None
    digest: bytes


def _publication_descriptor(manifest: Mapping[str, Any]) -> PublicationDescriptor:
    reduction = dict(manifest.get("materialized_reduction") or {})
    certificate = dict(manifest.get("fixed_point_certificate") or {})
    ledger = dict(manifest.get("ledger") or {})
    families = dict(manifest.get("family_manifests") or {})
    factor_family = dict(families.get("factors") or reduction.get("factors") or {})
    residual_family = dict(
        families.get("residuals") or reduction.get("residuals") or {}
    )
    graph_ref = str(manifest.get("graph_ref") or reduction.get("graph_ref") or "")
    ledger_ref = str(ledger.get("ledger_ref") or "") or None
    certificate_ref = (
        str(
            certificate.get("certificate_ref")
            or certificate.get("fixed_point_ref")
            or ""
        )
        or None
    )
    fingerprint = manifest.get("owner_fingerprint")
    fingerprint_ref = (
        "owner-fingerprint:" + canonical_sha256(fingerprint)
        if fingerprint is not None
        else None
    )
    factor_count = int(
        reduction.get("factor_count") or factor_family.get("record_count") or 0
    )
    residual_count = int(
        reduction.get("residual_count") or residual_family.get("record_count") or 0
    )
    byte_count = int(factor_family.get("byte_count") or 0) + int(
        residual_family.get("byte_count") or 0
    )
    build_ref = str(manifest.get("build_ref") or "") or None
    digest = bytes.fromhex(
        canonical_fields_sha256(
            graph_ref,
            ledger_ref,
            certificate_ref,
            fingerprint_ref,
            factor_count,
            residual_count,
            byte_count,
            build_ref,
        )
    )
    return PublicationDescriptor(
        graph_ref=graph_ref,
        ledger_ref=ledger_ref,
        certificate_ref=certificate_ref,
        owner_fingerprint_ref=fingerprint_ref,
        factor_count=factor_count,
        residual_count=residual_count,
        byte_count=byte_count,
        build_ref=build_ref,
        digest=digest,
    )


class DistributedFinalizationWorker:
    def __init__(self, *, connection_factory: Callable[[], Any], worker_ref: str):
        self.connection_factory = connection_factory
        self.worker_ref = worker_ref

    def checkpoint(
        self,
        cursor: Any,
        *,
        run_ref: str,
        document_ref: str,
        owner_ref: str,
        cursor_revision: int,
        manifest: Mapping[str, Any],
    ) -> str:
        descriptor = _publication_descriptor(manifest)
        cursor_ref = f"finalization:{run_ref}:{owner_ref}:{cursor_revision}"
        cursor.execute(
            """
            SELECT encode(manifest_sha256, 'hex')
            FROM execution.semantic_finalization_cursor
            WHERE cursor_ref = %s
            """,
            (cursor_ref,),
        )
        existing = cursor.fetchone()
        if existing is not None and str(existing[0]) != descriptor.digest.hex():
            raise ValueError("finalization checkpoint digest mismatch")
        cursor.execute(
            """
            INSERT INTO execution.semantic_finalization_cursor
                (cursor_ref, run_ref, document_ref, owner_ref,
                 cursor_revision, batch_ordinal, manifest, manifest_sha256,
                 state, graph_ref, ledger_ref, certificate_ref,
                 owner_fingerprint_ref, factor_count, residual_count,
                 byte_count)
            VALUES (%s, %s, %s, %s, %s, 0, NULL, %s, 'committed',
                    %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cursor_ref) DO NOTHING
            """,
            (
                cursor_ref,
                run_ref,
                document_ref,
                owner_ref,
                cursor_revision,
                descriptor.digest,
                descriptor.graph_ref,
                descriptor.ledger_ref,
                descriptor.certificate_ref,
                descriptor.owner_fingerprint_ref,
                descriptor.factor_count,
                descriptor.residual_count,
                descriptor.byte_count,
            ),
        )
        return cursor_ref

    def stage_then_commit_descriptor(
        self,
        *,
        run_ref: str,
        document_ref: str,
        descriptor: PublicationDescriptor,
    ) -> str:
        connection = self.connection_factory()
        publication_ref = f"publication:{run_ref}:{document_ref}"
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT encode(manifest_sha256, 'hex')
                        FROM execution.semantic_publication
                        WHERE publication_ref = %s
                        """,
                        (publication_ref,),
                    )
                    existing = cursor.fetchone()
                    if (
                        existing is not None
                        and str(existing[0]) != descriptor.digest.hex()
                    ):
                        raise ValueError("publication descriptor digest mismatch")
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_publication
                            (publication_ref, run_ref, document_ref, state,
                             manifest, manifest_sha256, graph_ref,
                             certificate_ref, build_ref, factor_count,
                             residual_count, publication_sha256)
                        VALUES (%s, %s, %s, 'staged', NULL, %s, %s, %s,
                                %s, %s, %s, %s)
                        ON CONFLICT (publication_ref) DO UPDATE SET
                            graph_ref = EXCLUDED.graph_ref,
                            certificate_ref = EXCLUDED.certificate_ref,
                            build_ref = EXCLUDED.build_ref,
                            factor_count = EXCLUDED.factor_count,
                            residual_count = EXCLUDED.residual_count,
                            publication_sha256 = EXCLUDED.publication_sha256
                        """,
                        (
                            publication_ref,
                            run_ref,
                            document_ref,
                            descriptor.digest,
                            descriptor.graph_ref,
                            descriptor.certificate_ref,
                            descriptor.build_ref,
                            descriptor.factor_count,
                            descriptor.residual_count,
                            descriptor.digest,
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE execution.semantic_publication
                        SET state = 'committed'
                        WHERE publication_ref = %s
                        """,
                        (publication_ref,),
                    )
            return publication_ref
        finally:
            connection.close()

    def stage_then_commit(
        self,
        *,
        run_ref: str,
        document_ref: str,
        manifest: Mapping[str, Any],
    ) -> str:
        return self.stage_then_commit_descriptor(
            run_ref=run_ref,
            document_ref=document_ref,
            descriptor=_publication_descriptor(manifest),
        )


def _fresh_publication_main(
    database_url: str,
    run_ref: str,
    document_ref: str,
    descriptor: PublicationDescriptor,
    queue: Any,
) -> None:
    worker = DistributedFinalizationWorker(
        connection_factory=lambda: __import__("psycopg").connect(
            database_url,
            application_name=f"sensiblaw-publish:{run_ref}",
        ),
        worker_ref=f"{run_ref}:publisher",
    )
    queue.put(
        {
            "pid": os.getpid(),
            "publication_ref": worker.stage_then_commit_descriptor(
                run_ref=run_ref,
                document_ref=document_ref,
                descriptor=descriptor,
            ),
        }
    )


def publish_in_fresh_process(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    manifest: Mapping[str, Any],
) -> str:
    descriptor = _publication_descriptor(manifest)
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_fresh_publication_main,
        args=(database_url, run_ref, document_ref, descriptor, queue),
        name=f"sensiblaw-strict-publisher-{run_ref}",
    )
    process.start()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError("fresh publication process failed")
    return str(queue.get()["publication_ref"])


__all__ = [
    "AUTHORITY_BACKEND",
    "STRICT_EXECUTION_CONTRACT",
    "DistributedFinalizationWorker",
    "DistributedSemanticWorker",
    "ImmutableJobManifest",
    "Lease",
    "ProcessPostgresWorkerPool",
    "PublicationDescriptor",
    "TypedSemanticDelta",
    "TypedToken",
    "WorkerReceipt",
    "create_run",
    "enqueue_canonical_closure_jobs",
    "execute_serialized_streaming_job",
    "lease_next_job",
    "publish_in_fresh_process",
    "record_lifecycle",
    "register_kernel",
    "renew_lease",
    "replay_accepted_deltas",
    "semantic_delta_admission",
]
