from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_strict_numeric_publication_never_reenters_legacy_document_compiler() -> None:
    wrapper = (
        ROOT / "src/policy/streaming_spacy_parser_execution.py"
    ).read_text(encoding="utf-8")
    native = (
        ROOT / "src/policy/numeric_pnf_compilation.py"
    ).read_text(encoding="utf-8")

    strict_compile = wrapper.split("def compile_wrapper", 1)[1].split(
        "def persist_wrapper", 1
    )[0]
    strict_persist = wrapper.split("def persist_wrapper", 1)[1]

    assert "compile_numeric_pnf_document(" in strict_compile
    assert strict_compile.count("original_compile(") == 1
    assert "persist_numeric_pnf_document(" in strict_persist
    assert strict_persist.count("original_persist(") == 1
    assert '"legacy_document_materialisation": False' in native
    assert '"legacy_projection_invoked": False' in native
    assert "build_entity_resolution_carrier" not in native
    assert "build_indexed_projection" not in native
    assert "parse_document_fibres" not in native


def test_numeric_publication_exposes_only_document_interface_and_residual_demands() -> None:
    native = (
        ROOT / "src/policy/numeric_pnf_compilation.py"
    ).read_text(encoding="utf-8")

    assert "numeric-pnf-interface:" in native
    assert "numeric-pnf-demand:" in native
    assert "world_resolution_deferred" in native
    assert "canonical_text" not in native.split(
        '"numeric_pnf_authority":', 1
    )[1].split('"phase_boundary":', 1)[0]
