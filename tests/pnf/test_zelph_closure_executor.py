from __future__ import annotations

from typing import Mapping, Sequence

from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
)
from src.pnf.zelph_closure_executor import (
    ZelphClosureExecutor,
    benchmark_closure_job,
)


def _proposal(job: SolverJob) -> FactorProposal:
    return FactorProposal(
        document_ref=job.owner_key.document_ref,
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=(job.owner_key.scope_ref,),
        input_observation_refs=job.input_refs,
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"conduct": "eventuality:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="producer:test:v1",
        declaration_revision=job.rule_set_revision,
        candidate_payload={"predicate_ref": "normative.obligation"},
    )


class _Codec:
    codec_ref = "codec:test:v1"
    rule_set_revision = "v1"

    def encode_facts(self, job: SolverJob) -> str:
        return f'input("{job.input_refs[0]}").'

    def rules_and_queries(self, job: SolverJob) -> str:
        return "derived(X) :- input(X).\n? derived(X)"

    def decode_proposals(
        self,
        job: SolverJob,
        triples: Sequence[Mapping[str, str]],
    ) -> Sequence[FactorProposal]:
        assert triples
        return (_proposal(job),)


def test_zelph_backend_is_candidate_only_and_parity_checked(monkeypatch) -> None:
    import src.pnf.zelph_closure_executor as module

    monkeypatch.setattr(
        module,
        "run_zelph_inference",
        lambda facts, rules: {
            "status": "ok",
            "triples": [{"subject": "input:1", "predicate": "derived", "object": "true"}],
            "stdout": "",
            "stderr": "",
        },
    )
    job = SolverJob(
        owner_key=OwnerKey(
            "document:1",
            "sentence:1",
            "semantic.normative_relation",
        ),
        declaration_ref="declaration:test:v1",
        input_revision=1,
        input_refs=("observation:1",),
        input_payload={},
        rule_set_revision="v1",
        coverage_requirements=("sentence",),
    )
    python = PythonClosureExecutor(
        {"declaration:test:v1": lambda value: (_proposal(value),)}
    )
    zelph = ZelphClosureExecutor(_Codec())

    parity = benchmark_closure_job(
        job=job,
        python_executor=python,
        zelph_executor=zelph,
    )
    payload = parity.to_dict()

    assert parity.proposal_digest_equal is True
    assert parity.reduction_digest_equal is True
    assert payload["identity_promoted"] is False
    assert payload["legal_truth_closed"] is False
    assert payload["zelph_metrics"]["engine_ms"] >= 0
