from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from scripts.benchmark_document_replay import (
    DocumentCase,
    _acceptance_ref,
    _process_execution,
    load_manifest,
)


def test_load_manifest_resolves_and_validates_documents(tmp_path: Path) -> None:
    source = tmp_path / "document.txt"
    source.write_text("bounded replay", encoding="utf-8")
    manifest = tmp_path / "manifest.pkl"
    manifest.write_bytes(
        pickle.dumps({"documents": [{"label": "medium", "path": str(source)}]})
    )

    cases = load_manifest(manifest)

    assert cases[0].label == "medium"
    assert cases[0].path == source.resolve()


def test_load_manifest_rejects_duplicate_labels(tmp_path: Path) -> None:
    source = tmp_path / "document.txt"
    source.write_text("bounded replay", encoding="utf-8")
    manifest = tmp_path / "manifest.pkl"
    manifest.write_bytes(
        pickle.dumps(
            {
                "documents": [
                    {"label": "same", "path": str(source)},
                    {"label": "same", "path": str(source)},
                ]
            }
        )
    )

    with pytest.raises(ValueError, match="duplicate document label"):
        load_manifest(manifest)


def test_acceptance_reference_starts_with_unique_run_token(tmp_path: Path) -> None:
    run_root = tmp_path / "replay-unique" / "medium" / "batched"

    reference = _acceptance_ref(
        case=DocumentCase(label="medium", path=tmp_path / "source.txt"),
        mode="batched",
        run_root=run_root,
    )

    assert reference.startswith("replay-")
    assert reference.endswith("-medium-batched")
    assert reference != _acceptance_ref(
        case=DocumentCase(label="medium", path=tmp_path / "source.txt"),
        mode="batched",
        run_root=tmp_path / "replay-other" / "medium" / "batched",
    )


def test_process_execution_comes_from_exact_acceptance_comparison(
    tmp_path: Path,
) -> None:
    strict_path = (
        tmp_path / "acceptance" / "replay" / "strict" / "acceptance-receipt.json"
    )
    strict_path.parent.mkdir(parents=True)
    strict_path.write_text("{}", encoding="utf-8")
    comparison_path = strict_path.parent.parent / "parallel-acceptance-comparison.json"
    comparison_path.write_text(
        json.dumps({"process_execution": {"distinct_semantic_worker_count": 2}}),
        encoding="utf-8",
    )

    assert _process_execution(strict_path=strict_path, strict_receipt={}) == {
        "distinct_semantic_worker_count": 2
    }
