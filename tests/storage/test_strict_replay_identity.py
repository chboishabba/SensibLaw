from __future__ import annotations

from src.pnf.streaming_fixed_point import OwnerKey, StreamingSemanticOwner, SolverJob
from src.storage.postgres.distributed_semantic_execution import (
    ImmutableJobManifest,
    execute_serialized_streaming_job,
)


def _job(*, revision: int = 1) -> SolverJob:
    return SolverJob(
        owner_key=OwnerKey(
            "document:replay", "sentence:1", "semantic.normative_relation"
        ),
        declaration_ref="declaration:test:v1",
        input_revision=revision,
        input_refs=("observation:1",),
        input_payload={"observation_delta": {"observations": ()}},
        rule_set_revision="rules:v1",
        coverage_requirements=("sentence",),
    )


def test_serialized_execution_uses_manifest_revision_and_stable_job_ref() -> None:
    job = _job(revision=1)
    leased_ref = "semantic-job:leased-identity"
    manifest = ImmutableJobManifest.build(
        job_ref=leased_ref,
        run_ref="run:replay",
        document_ref="document:replay",
        owner_ref="owner:replay",
        input_revision=7,
        input_payload=job.to_dict(),
    )

    delta = execute_serialized_streaming_job(manifest)
    receipt = dict(delta["payload"])

    assert delta["delta_ref"] == receipt["receipt_ref"]
    assert receipt["job_ref"] == leased_ref
    assert receipt["input_revision"] == 7
    assert delta["prior_revision"] == 7
    assert delta["resulting_revision"] == 8


def test_rehydrate_solver_job_contract_is_public_and_validates_identity() -> None:
    owner = StreamingSemanticOwner(document_ref="document:replay")
    job = _job()

    owner.rehydrate_solver_job_contract(job, job_ref="semantic-job:leased-identity")
    assert "semantic-job:leased-identity" in owner._in_flight_jobs

    mismatched = SolverJob(**{**job.__dict__, "rule_set_revision": "rules:wrong"})
    try:
        owner.rehydrate_solver_job_contract(
            mismatched, job_ref="semantic-job:leased-identity"
        )
    except ValueError as error:
        assert "contract" in str(error)
    else:
        raise AssertionError("mismatched replay contract was admitted")
