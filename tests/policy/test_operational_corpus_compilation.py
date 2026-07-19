from __future__ import annotations

import hashlib

from src.pnf.reference_binding import REFERENCE_BINDING_CONTRACT_REF
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
        REFERENCE_BINDING_CONTRACT_REF
    )
    assert OPERATIONAL_COMPILER_CONTRACT == "postgres-semantic-compiler:v0_8"
    assert compilation.artifacts["binding_candidate_sets"]
    assert not any(
        row["evidence_type"] == "typed_binding_candidate"
        for row in compilation.artifacts["local_evidence"]
    )


def test_operational_html_uses_one_canonical_coordinate_system() -> None:
    html = """
    <html data-pnf-poison="raw-tag">
      <head><style>.hidden { display: none; }</style></head>
      <body>
        <h1>George W. Bush</h1>
        <p>President Bush signed the Patriot Act. He discussed the law.</p>
        <script>RawTagActor should never be parsed.</script>
      </body>
    </html>
    """
    compilation = compile_document_operational(
        {
            "document_ref": "document:operational-html-test",
            "content_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "media_type": "text/html",
            "canonical_text": html,
            "source_ref": "source:operational-html-test",
        },
        default_compiler_context(),
    )

    artifacts = compilation.artifacts
    canonical_text = artifacts["canonical_text"]
    canonical_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    assert OPERATIONAL_COMPILER_CONTRACT == "postgres-semantic-compiler:v0_8"
    assert artifacts["reference_binding_operational_contract"] == (
        REFERENCE_BINDING_CONTRACT_REF
    )
    assert "George W. Bush" in canonical_text
    assert "Patriot Act" in canonical_text
    assert "RawTagActor" not in canonical_text
    assert "data-pnf-poison" not in canonical_text
    assert "<html" not in canonical_text
    assert artifacts["canonical_text_sha256"] == canonical_sha256
    assert artifacts["annotation_layer"]["text_sha256"] == canonical_sha256
    assert artifacts["semantic_annotation_layer"]["text_sha256"] == canonical_sha256

    for mention in artifacts["licensing"]["mentions"]:
        start = int(mention["start_char"])
        end = int(mention["end_char"])
        assert canonical_text[start:end] == mention["canonical_surface"]
