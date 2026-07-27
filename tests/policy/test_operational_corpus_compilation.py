from __future__ import annotations

import hashlib
from io import StringIO

from src.pnf.reference_binding import REFERENCE_BINDING_CONTRACT_REF
from src.policy import corpus_compilation as legacy
from src.policy.corpus_compilation import default_compiler_context
from src.policy.operational_corpus_compilation import (
    DOCUMENT_COMPILE_STAGE_NAMES,
    OPERATIONAL_COMPILER_CONTRACT,
    compile_document_operational,
)
from src.runtime.progress import PhaseRecorder


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
    assert compilation.artifacts["operational_compiler_contract"] == (
        OPERATIONAL_COMPILER_CONTRACT
    )
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

    assert artifacts["operational_compiler_contract"] == OPERATIONAL_COMPILER_CONTRACT
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


def test_operational_compiler_emits_document_stage_progress() -> None:
    text = "Ada entered the hall. She spoke."
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase(
        "document_compile",
        total=len(DOCUMENT_COMPILE_STAGE_NAMES),
        subject_ref="document:operational-test",
        message="document compile",
        worker="document-test",
    ) as phase:
        compilation = compile_document_operational(
            {
                "document_ref": "document:operational-test",
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "media_type": "text/plain",
                "canonical_text": text,
                "source_ref": "source:operational-test",
            },
            default_compiler_context(),
            progress=phase,
        )

    assert compilation.status == "compiled"
    running_messages = [
        event["message"]
        for event in recorder.events
        if event["phase"] == "document_compile" and event["state"] == "running"
    ]
    assert running_messages == list(DOCUMENT_COMPILE_STAGE_NAMES)


def test_operational_compiler_chunks_oversized_parser_input(
    monkeypatch,
    tmp_path,
) -> None:
    text = ("Ada entered the hall. She spoke.\n\n" * 8).strip()
    observed_lengths: list[int] = []
    original = legacy.parse_canonical_text

    def bounded_parser(value: str):
        observed_lengths.append(len(value))
        if len(value) >= 100:
            raise AssertionError("oversized text reached parser boundary")
        return original(value)

    monkeypatch.setattr(legacy, "parse_canonical_text", bounded_parser)
    compilation = compile_document_operational(
        {
            "document_ref": "document:operational-fibre-test",
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "media_type": "text/plain",
            "canonical_text": text,
            "source_ref": "source:operational-fibre-test",
        },
        default_compiler_context(),
        parser_workers=2,
        parser_limit_chars=100,
        parser_target_chars=40,
        parser_overlap_chars=5,
        parser_checkpoint_dir=str(tmp_path),
    )

    receipt = compilation.artifacts["parser_receipt"]
    assert compilation.status == "compiled"
    assert receipt["contract_ref"] == "parser-document-fibres:v0_1"
    assert receipt["fibre_count"] > 1
    assert observed_lengths
    assert max(observed_lengths) < 100
    assert receipt["cross_fibre_fixed_point"]["semantic_object"] == "document"
