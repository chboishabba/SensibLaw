import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from src.redflags.forbidden_language import assert_no_forbidden_language

pytestmark = pytest.mark.redflag


def _run_export(collection: Path, out_zip: Path) -> bytes:
    cmd = [
        sys.executable,
        "-m",
        "cli",
        "review",
        "export",
        "--collection",
        str(collection),
        "--out",
        str(out_zip),
    ]
    subprocess.run(cmd, check=True)
    return out_zip.read_bytes()


def test_review_export_cli(tmp_path: Path):
    out_zip = tmp_path / "export.zip"
    collection = Path("examples/review_collection_minimal.json")
    _run_export(collection, out_zip)
    assert out_zip.exists()

    with zipfile.ZipFile(out_zip, "r") as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["collection_version"] == "review.collection.v1"
        # bundle is included
    assert any(name.endswith("review_bundle_minimal.json") for name in names)


def test_export_zip_is_deterministic(tmp_path: Path):
    collection = Path("examples/review_collection_minimal.json")
    zip_a = tmp_path / "a.zip"
    zip_b = tmp_path / "b.zip"

    bytes_a = _run_export(collection, zip_a)
    bytes_b = _run_export(collection, zip_b)

    hash_a = hashlib.sha256(bytes_a).hexdigest()
    hash_b = hashlib.sha256(bytes_b).hexdigest()
    assert hash_a == hash_b


def test_export_zip_order_invariant(tmp_path: Path):
    base = json.loads(Path("examples/review_collection_minimal.json").read_text())
    abs_bundles = [
        {**b, "path": str((Path("examples") / b["path"]).resolve())} for b in base["bundles"]
    ]
    swapped = {"version": base["version"], "bundles": list(reversed(abs_bundles))}
    base_abs = {"version": base["version"], "bundles": abs_bundles}

    col_path = tmp_path / "collection.json"
    zip_a = tmp_path / "a.zip"
    zip_b = tmp_path / "b.zip"

    col_path.write_text(json.dumps(base_abs), encoding="utf-8")
    hash_a = hashlib.sha256(_run_export(col_path, zip_a)).hexdigest()

    col_path.write_text(json.dumps(swapped), encoding="utf-8")
    hash_b = hashlib.sha256(_run_export(col_path, zip_b)).hexdigest()

    assert hash_a == hash_b


def test_export_forbidden_language_absent(tmp_path: Path):
    out_zip = tmp_path / "export.zip"
    collection = Path("examples/review_collection_minimal.json")
    zip_bytes = _run_export(collection, out_zip)
    text = zip_bytes.decode("latin1", errors="ignore")
    assert_no_forbidden_language(text)
