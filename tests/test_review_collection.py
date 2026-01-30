import json
from pathlib import Path

import pytest
import yaml

from src.redflags.forbidden_language import assert_no_forbidden_language
from src.review_collection import (
    COLLECTION_VERSION,
    compare_bundles,
    load_collection,
    manifest,
    validate_collection_schema,
)

pytestmark = pytest.mark.redflag


def test_review_collection_schema_validation():
    collection = json.loads(Path("examples/review_collection_minimal.json").read_text())
    schema_path = Path("schemas/review.collection.v1.schema.yaml")
    validate_collection_schema(collection, schema_path)
    assert collection["version"] == COLLECTION_VERSION


def test_manifest_hash_deterministic(tmp_path: Path):
    collection_path = Path("examples/review_collection_minimal.json")
    first = manifest(collection_path)
    second = manifest(collection_path)
    assert first == second


def test_manifest_order_invariant(tmp_path: Path):
    # Reordering bundles must not change manifest content
    base = json.loads(Path("examples/review_collection_minimal.json").read_text())
    abs_bundles = [
        {**b, "path": str((Path("examples") / b["path"]).resolve())} for b in base["bundles"]
    ]
    swapped = {"version": base["version"], "bundles": list(reversed(abs_bundles))}
    base_abs = {"version": base["version"], "bundles": abs_bundles}

    col_path = tmp_path / "collection.json"

    col_path.write_text(json.dumps(base_abs), encoding="utf-8")
    man_a = manifest(col_path)

    col_path.write_text(json.dumps(swapped), encoding="utf-8")
    man_b = manifest(col_path)

    # collection_path differs only by write timing; compare bundle payloads
    assert man_a["bundles"] == man_b["bundles"]


def test_manifest_hash_ignores_notes(tmp_path: Path):
    """Changing non-payload metadata (note) must not change bundle hashes."""
    base = json.loads(Path("examples/review_collection_minimal.json").read_text())
    abs_bundles = [
        {**b, "path": str((Path("examples") / b["path"]).resolve())} for b in base["bundles"]
    ]
    with_note = {"version": base["version"], "bundles": abs_bundles}
    without_note = {
        "version": base["version"],
        "bundles": [{k: v for k, v in b.items() if k != "note"} for b in abs_bundles],
    }

    col_path = tmp_path / "collection.json"

    col_path.write_text(json.dumps(with_note), encoding="utf-8")
    man_with = manifest(col_path)

    col_path.write_text(json.dumps(without_note), encoding="utf-8")
    man_without = manifest(col_path)

    hashes_with = [b["hash"] for b in man_with["bundles"]]
    hashes_without = [b["hash"] for b in man_without["bundles"]]
    assert hashes_with == hashes_without


def test_collection_forbidden_language_absent():
    col_text = Path("examples/review_collection_minimal.json").read_text()
    assert_no_forbidden_language(col_text)


def test_compare_bundles_byte_diff():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    diff = compare_bundles(a, b)
    assert diff["same"] is True  # structurally equal dicts
