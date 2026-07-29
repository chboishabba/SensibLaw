from __future__ import annotations

from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    ObservationDelta,
    PythonClosureExecutor,
    StreamingDeclaration,
    StreamingSemanticOwner,
    execute_ready_jobs,
)
from src.runtime.document_execution_policy import (
    DocumentRetentionPolicy,
    RetentionMode,
)


def _delta(sequence_no: int = 0) -> ObservationDelta:
    ref = f"observation:{sequence_no}"
    return ObservationDelta(
        document_ref="document:1",
        batch_ref=f"batch:{sequence_no}",
        scope_ref=f"sentence:{sequence_no}",
        sequence_no=sequence_no,
        parser_contract="parser:test:v1",
        observation_refs=(ref,),
        observations=(
            {
                "observation_ref": ref,
                "observation_type": "parser.token",
                "token": {
                    "index": sequence_no,
                    "text": "must",
                    "start": sequence_no * 5,
                    "end": sequence_no * 5 + 4,
                },
            },
        ),
        token_start=sequence_no,
        token_end=sequence_no + 1,
        char_start=sequence_no * 5,
        char_end=sequence_no * 5 + 4,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _declaration() -> StreamingDeclaration:
    return StreamingDeclaration(
        declaration_ref="declaration:test:v1",
        producer_ref="producer:test:v1",
        requires=("parser.token",),
        optional=(),
        emits=("semantic.normative_relation",),
        scope_kind="sentence",
        coverage_barrier="sentence",
        affected_index="semantic.normative_relation",
        declaration_revision="v1",
        priority=10,
    )


def _proposal(job) -> FactorProposal:
    return FactorProposal(
        document_ref=job.owner_key.document_ref,
        source_revision_ref="source-revision:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=(job.owner_key.scope_ref,),
        input_observation_refs=job.input_refs,
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"conduct": job.owner_key.scope_ref},
        qualifier_state={"modality": "obligation"},
        producer_contract="producer:test:v1",
        declaration_revision=job.rule_set_revision,
        candidate_payload={"predicate_ref": "normative.obligation"},
    )


def _run(owner):
    owner.register_declarations((_declaration(),))
    owner.admit_observation_delta(_delta(0))
    owner.admit_observation_delta(_delta(1))
    executor = PythonClosureExecutor(
        {"declaration:test:v1": lambda job: (_proposal(job),)}
    )
    execute_ready_jobs(owner, executor, workers=2)
    owner.reduce_dirty_groups()
    return owner


def test_bounded_owner_preserves_materialized_reduction_parity() -> None:
    legacy = _run(StreamingSemanticOwner(document_ref="document:1"))
    bounded = _run(
        BoundedStreamingSemanticOwner(
            document_ref="document:1",
            retention=DocumentRetentionPolicy(mode=RetentionMode.AUDIT_FULL),
        )
    )

    assert (
        bounded.materialized_reduction.to_dict()
        == legacy.materialized_reduction.to_dict()
    )
    assert bounded.fixed_point_certificate().local_fixed_point_reached is True


def test_jobs_use_bounded_observation_slice_not_complete_delta_serialization() -> None:
    owner = BoundedStreamingSemanticOwner(
        document_ref="document:1",
        retention=DocumentRetentionPolicy(mode=RetentionMode.AUDIT_FULL),
    )
    owner.register_declarations((_declaration(),))
    delta = _delta(0)
    owner.admit_observation_delta(delta)

    job = owner.drain_ready_jobs(limit=1)[0]
    payload = dict(job.input_payload)
    compact_delta = dict(payload["observation_delta"])

    assert payload["input_delta_ref"] == delta.delta_ref
    assert set(compact_delta) == {"delta_ref", "scope_ref", "observations"}
    assert "parser_contract" not in compact_delta
    assert "token_start" not in compact_delta
    assert "char_start" not in compact_delta


def test_coverage_completion_uses_the_bounded_owner_index() -> None:
    owner = BoundedStreamingSemanticOwner(document_ref="document:1")
    owner.register_declarations((_declaration(),))
    delta = _delta(0)
    owner.admit_observation_delta(delta)

    # The canonical notice remains available for artifacts, but lookup must
    # not degrade into a scan over that growing collection.
    owner._coverage_notices.clear()

    assert owner.coverage_complete(
        scope_ref=delta.scope_ref,
        barrier=delta.coverage_barrier,
    )
    assert owner.retention_counts()["coverage_index_entries"] == 1


def test_production_compaction_releases_diagnostic_history() -> None:
    owner = _run(
        BoundedStreamingSemanticOwner(
            document_ref="document:1",
            retention=DocumentRetentionPolicy(mode=RetentionMode.PRODUCTION_COMPACT),
        )
    )

    receipt = owner.compact_retained_history()
    counts = owner.retention_counts()
    artifact = owner.to_dict()

    assert counts["jobs"] == 0
    assert counts["receipts"] == 0
    assert counts["state_deltas"] == 0
    assert counts["compact_jobs"] == 2
    assert counts["compact_receipts"] == 2
    assert counts["compact_receipt_refs"] == 2
    assert receipt["compaction_count"] == 1
    assert len(owner.materialized_reduction.factors) == 2

    assert len(artifact["solver_jobs"]) == 2
    assert len(artifact["solver_receipts"]) == 2
    assert all(row["payload_compacted"] for row in artifact["solver_jobs"])
    assert all(row["proposals_compacted"] for row in artifact["solver_receipts"])
    assert all("observation_delta" not in row for row in artifact["solver_jobs"])
    assert all("proposals" not in row for row in artifact["solver_receipts"])


def test_proposals_are_indexed_by_owner_key() -> None:
    owner = BoundedStreamingSemanticOwner(document_ref="document:1")
    first = _proposal(
        type(
            "Job",
            (),
            {
                "owner_key": type(
                    "Key",
                    (),
                    {
                        "document_ref": "document:1",
                        "scope_ref": "sentence:1",
                    },
                )(),
                "input_refs": (),
                "rule_set_revision": "v1",
            },
        )()
    )
    owner.admit_proposals((first,), stage="base")
    owner.reduce_dirty_groups()

    counts = owner.retention_counts()
    assert counts["proposal_owner_groups"] == 1
    assert counts["known_dependency_refs"] == 1
