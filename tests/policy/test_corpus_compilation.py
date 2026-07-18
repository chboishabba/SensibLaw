from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from src.policy.corpus_compilation import (
    build_corpus_manifest,
    compile_directory,
    default_compiler_context,
)


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "corpora" / "gwb-mini"


def test_directory_kernel_compiles_fixture_without_network_or_cross_document_closure(
    tmp_path,
):
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_DIR, corpus)
    output = corpus / "artifacts"

    result = compile_directory(
        corpus,
        context=default_compiler_context(),
        output_store=output,
    )

    assert result["summary"]["compiled_document_count"] == 3
    assert result["summary"]["unsupported_document_count"] == 1
    assert result["summary"]["network_performed"] is False
    assert result["summary"]["cross_document_identity_closed"] is False
    assert (output / "manifest.json").is_file()
    assert (output / "corpus" / "demand-groups.json").is_file()
    assert all(
        row["artifacts"]["phase_boundary"]["readiness_invoked"] is False
        for row in result["compilations"]
        if row["status"] == "compiled"
    )


def test_directory_kernel_is_deterministic_and_append_only_on_rerun(tmp_path):
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_DIR, corpus)
    output = tmp_path / "artifacts"

    first = compile_directory(
        corpus, context=default_compiler_context(), output_store=output
    )
    second = compile_directory(
        corpus, context=default_compiler_context(), output_store=output
    )

    assert first["manifest"]["manifest_sha256"] == second["manifest"]["manifest_sha256"]
    assert first["summary"]["summary_sha256"] == second["summary"]["summary_sha256"]
    assert first["demand_groups"] == second["demand_groups"]


def test_inventory_uses_content_identity_and_preserves_duplicate_occurrences(tmp_path):
    (tmp_path / "a.txt").write_text("Bush", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.txt").write_text("Bush", encoding="utf-8")

    manifest = build_corpus_manifest(tmp_path, context=default_compiler_context())
    rows = manifest.to_dict()["ordered_documents"]

    assert [row["relative_path"] for row in rows] == ["a.txt", "nested/b.txt"]
    assert rows[0]["document_ref"] == rows[1]["document_ref"]
    assert rows[0]["relative_path"] != rows[1]["relative_path"]

    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    assert result["summary"]["compiled_document_count"] == 1


def test_invalid_text_isolated_and_remainder_compiles(tmp_path):
    (tmp_path / "good.txt").write_text("Bush met Bush.", encoding="utf-8")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    output = tmp_path / "artifacts"

    result = compile_directory(
        tmp_path, context=default_compiler_context(), output_store=output
    )

    assert result["summary"]["compiled_document_count"] == 1
    assert result["summary"]["failed_document_count"] == 1
    failed = next(row for row in result["compilations"] if row["status"] != "compiled")
    assert failed["status"] == "normalisation_failed"


def test_existing_output_rejects_changed_manifest(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "source.txt"
    source.write_text("first", encoding="utf-8")
    output = tmp_path / "artifacts"
    compile_directory(corpus, context=default_compiler_context(), output_store=output)
    source.write_text("second", encoding="utf-8")

    with pytest.raises(ValueError, match="append-only artifact differs"):
        compile_directory(
            corpus, context=default_compiler_context(), output_store=output
        )


def test_local_recurrence_meet_does_not_close_identity(tmp_path):
    (tmp_path / "source.txt").write_text("Bush met Bush.", encoding="utf-8")
    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    compilation = next(
        row for row in result["compilations"] if row["status"] == "compiled"
    )
    meets = compilation["artifacts"]["typed_meets"]
    refinements = compilation["artifacts"]["factor_refinements"]

    assert any(row["state"] == "compatible_with_refinement" for row in meets)
    assert all(
        row["prior_factor"]["residuals"] == row["resulting_factor"]["residuals"]
        for row in refinements
    )
