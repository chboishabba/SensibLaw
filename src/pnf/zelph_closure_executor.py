"""Zelph as an optional executor for monotone revision-bound closure jobs.

Zelph never owns document state.  A codec serialises one immutable SolverJob and decodes
only candidate FactorProposal values.  The keyed SensibLaw owner remains responsible for
admission, compatibility reduction, residual preservation, coverage barriers, and fixed-
point certification.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns
from typing import Any, Mapping, Protocol, Sequence

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.pnf.streaming_fixed_point import ClosureExecutor, SolverJob, SolverReceipt
from src.policy.carriers.canonical import canonical_sha256
from src.zelph_bridge import run_zelph_inference


ZELPH_CLOSURE_BACKEND_REF = "zelph-closure-executor:v0_1"
CLOSURE_PARITY_SCHEMA_VERSION = "sl.pnf.closure_backend_parity.v0_1"


class ZelphCodec(Protocol):
    codec_ref: str
    rule_set_revision: str

    def encode_facts(self, job: SolverJob) -> str: ...

    def rules_and_queries(self, job: SolverJob) -> str: ...

    def decode_proposals(
        self, job: SolverJob, triples: Sequence[Mapping[str, str]]
    ) -> Sequence[FactorProposal]: ...


class ZelphExecutionError(RuntimeError):
    pass


class ZelphClosureExecutor:
    backend_ref = ZELPH_CLOSURE_BACKEND_REF

    def __init__(self, codec: ZelphCodec):
        self.codec = codec

    def execute(self, job: SolverJob) -> SolverReceipt:
        if job.rule_set_revision != self.codec.rule_set_revision:
            raise ValueError("Zelph codec revision disagrees with solver job")
        started = monotonic_ns()
        facts = self.codec.encode_facts(job)
        serialized_ms = max(0, (monotonic_ns() - started) // 1_000_000)

        engine_started = monotonic_ns()
        result = run_zelph_inference(facts, self.codec.rules_and_queries(job))
        engine_ms = max(0, (monotonic_ns() - engine_started) // 1_000_000)
        if result.get("status") != "ok":
            raise ZelphExecutionError(
                f"Zelph closure failed: {result.get('status')}: {result.get('stderr')}"
            )

        decode_started = monotonic_ns()
        proposals = tuple(
            sorted(
                self.codec.decode_proposals(job, result.get("triples") or ()),
                key=lambda row: row.proposal_ref,
            )
        )
        deserialized_ms = max(0, (monotonic_ns() - decode_started) // 1_000_000)
        return SolverReceipt(
            job_ref=job.job_ref,
            owner_key=job.owner_key,
            input_revision=job.input_revision,
            input_refs=job.input_refs,
            rule_set_revision=job.rule_set_revision,
            proposals=proposals,
            residuals=(),
            assumptions=job.assumptions,
            coverage_requirements=job.coverage_requirements,
            metrics={
                "codec_ref": self.codec.codec_ref,
                "input_fact_bytes": len(facts.encode("utf-8")),
                "derived_triple_count": len(result.get("triples") or ()),
                "derived_proposal_count": len(proposals),
                "serialization_ms": serialized_ms,
                "engine_ms": engine_ms,
                "deserialization_ms": deserialized_ms,
                "total_ms": serialized_ms + engine_ms + deserialized_ms,
            },
            backend_ref=self.backend_ref,
        )


@dataclass(frozen=True)
class ClosureParityResult:
    job_ref: str
    python_backend_ref: str
    zelph_backend_ref: str
    python_proposal_refs: tuple[str, ...]
    zelph_proposal_refs: tuple[str, ...]
    python_graph_ref: str
    zelph_graph_ref: str
    python_metrics: Mapping[str, Any]
    zelph_metrics: Mapping[str, Any]

    @property
    def proposal_digest_equal(self) -> bool:
        return self.python_proposal_refs == self.zelph_proposal_refs

    @property
    def reduction_digest_equal(self) -> bool:
        return self.python_graph_ref == self.zelph_graph_ref

    @property
    def parity_ref(self) -> str:
        return "closure-parity:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": CLOSURE_PARITY_SCHEMA_VERSION,
            "job_ref": self.job_ref,
            "python_backend_ref": self.python_backend_ref,
            "zelph_backend_ref": self.zelph_backend_ref,
            "python_proposal_refs": list(self.python_proposal_refs),
            "zelph_proposal_refs": list(self.zelph_proposal_refs),
            "python_graph_ref": self.python_graph_ref,
            "zelph_graph_ref": self.zelph_graph_ref,
            "proposal_digest_equal": self.proposal_digest_equal,
            "reduction_digest_equal": self.reduction_digest_equal,
            "python_metrics": dict(self.python_metrics),
            "zelph_metrics": dict(self.zelph_metrics),
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["parity_ref"] = self.parity_ref
        return payload


def benchmark_closure_job(
    *,
    job: SolverJob,
    python_executor: ClosureExecutor,
    zelph_executor: ZelphClosureExecutor,
) -> ClosureParityResult:
    """Execute one immutable job through both backends and compare canonical outputs."""

    python_receipt = python_executor.execute(job)
    zelph_receipt = zelph_executor.execute(job)
    known = tuple(sorted(set(job.input_refs)))
    python_reduction = reduce_factor_proposals(
        document_ref=job.owner_key.document_ref,
        proposals=python_receipt.proposals,
        known_observation_refs=known,
    )
    zelph_reduction = reduce_factor_proposals(
        document_ref=job.owner_key.document_ref,
        proposals=zelph_receipt.proposals,
        known_observation_refs=known,
    )
    return ClosureParityResult(
        job_ref=job.job_ref,
        python_backend_ref=python_receipt.backend_ref,
        zelph_backend_ref=zelph_receipt.backend_ref,
        python_proposal_refs=tuple(
            row.proposal_ref for row in sorted(python_receipt.proposals, key=lambda row: row.proposal_ref)
        ),
        zelph_proposal_refs=tuple(
            row.proposal_ref for row in sorted(zelph_receipt.proposals, key=lambda row: row.proposal_ref)
        ),
        python_graph_ref=python_reduction.graph_ref,
        zelph_graph_ref=zelph_reduction.graph_ref,
        python_metrics=python_receipt.metrics,
        zelph_metrics=zelph_receipt.metrics,
    )


__all__ = [
    "CLOSURE_PARITY_SCHEMA_VERSION",
    "ClosureParityResult",
    "ZELPH_CLOSURE_BACKEND_REF",
    "ZelphClosureExecutor",
    "ZelphCodec",
    "ZelphExecutionError",
    "benchmark_closure_job",
]
