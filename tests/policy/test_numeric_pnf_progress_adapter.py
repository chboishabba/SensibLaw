from __future__ import annotations

from src.policy.numeric_pnf_compilation import compile_numeric_pnf_document


def test_numeric_compilation_adapts_mapping_progress_to_keyword_details(
    monkeypatch,
) -> None:
    captured = {}

    class Progress:
        def observe(self, **kwargs):
            captured.update(kwargs)

    def fake_streaming(**kwargs):
        captured["observer"] = kwargs["progress_observer"]
        raise RuntimeError("stop after adapter capture")

    monkeypatch.setattr(
        "src.policy.numeric_pnf_compilation.run_streaming_spacy_execution",
        fake_streaming,
    )

    try:
        compile_numeric_pnf_document(
            database_url="postgresql://unused",
            run_ref="run:test",
            document_ref="document:test",
            content_sha256="content",
            media_type="text/plain",
            canonical_text="text",
            canonical_text_sha256="text",
            media_adapter_ref="adapter:test",
            parser_contract_ref="parser:test",
            build_key_sha256="build",
            parser_workers=1,
            parser_target_chars=1024,
            parser_overlap_chars=64,
            parser_checkpoint_dir=None,
            progress=Progress(),
        )
    except RuntimeError as error:
        assert str(error) == "stop after adapter capture"
    else:
        raise AssertionError("streaming executor should have been intercepted")

    observer = captured["observer"]
    observer({"current_kernel": "hierarchy_materialization"})
    assert captured["details"] == {"current_kernel": "hierarchy_materialization"}
