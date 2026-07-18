from __future__ import annotations

import hashlib

from src.policy import corpus_compilation as legacy
from src.policy.corpus_compilation import default_compiler_context
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    compile_document_operational,
)


def test_operational_compiler_never_materializes_pairwise_binding(monkeypatch) -> None:
    text = "Ada entered the hall. She spoke."

    def fail_pairwise(*_args, **_kwargs):
        raise AssertionError("pairwise binding evidence must not be materialized")

    monkeypatch.setattr(legacy, "_binding_evidence", fail_pairwise)
    compilation = compile_document_operational(
        {
            "document_ref": "document:operational-test",
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "media_type": "text/plain",
            "canonical_text": text,
            "source_ref": "source:operational-test",
        },
        default_compiler_context(),
    )

    assert compilation.status == "compiled"
    assert compilation.artifacts["phase_boundary"][
        "pairwise_binding_evidence_materialized"
    ] is False
    assert compilation.artifacts["reference_binding_operational_contract"] == (
        OPERATIONAL_COMPILER_CONTRACT
    )
    assert compilation.artifacts["binding_candidate_sets"]
    assert not any(
        row["evidence_type"] == "typed_binding_candidate"
        for row in compilation.artifacts["local_evidence"]
    )
