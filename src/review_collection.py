from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

COLLECTION_VERSION = "review.collection.v1"
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)  # fixed timestamp for deterministic zips


def load_collection(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != COLLECTION_VERSION:
        raise ValueError(f"Expected version {COLLECTION_VERSION}, got {data.get('version')}")
    return data


def bundle_hash(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _canonicalize_bundles(bundles: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return bundles sorted deterministically by (hash, path, label, note).

    Sorting by the bundle hash first ensures manifests and exports remain stable even
    if callers reorder the collection entries. Path/label/note act as stable
    tiebreakers while preserving payload identity.
    """

    def key(item: Mapping[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(item.get("hash", "")),
            str(item.get("path", "")),
            str(item.get("label", "")),
            str(item.get("note", "")),
        )

    return sorted((dict(item) for item in bundles), key=key)


def compare_bundles(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict:
    """
    Structural, byte-level diff. No semantics.
    """
    hash_a = hashlib.sha256(json.dumps(a, sort_keys=True).encode("utf-8")).hexdigest()
    hash_b = hashlib.sha256(json.dumps(b, sort_keys=True).encode("utf-8")).hexdigest()
    return {"same": hash_a == hash_b, "hash_a": hash_a, "hash_b": hash_b}


def manifest(collection_path: Path) -> dict:
    col = load_collection(collection_path)
    entries = []
    for item in col["bundles"]:
        item_path = Path(item["path"])
        bpath = (collection_path.parent / item_path).resolve() if not item_path.is_absolute() else item_path
        entries.append(
            {
                "path": str(item["path"]),
                "label": item.get("label"),
                "note": item.get("note"),
                "hash": bundle_hash(bpath),
            }
        )
    entries = _canonicalize_bundles(entries)
    return {
        "collection_version": COLLECTION_VERSION,
        "collection_path": str(collection_path),
        "bundles": entries,
    }


def validate_collection_schema(collection: Mapping[str, Any], schema_path: Path) -> None:
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema required for validation") from exc
    jsonschema.validate(collection, schema)


def export_collection(collection_path: Path, out_zip: Path) -> dict:
    """
    Create a deterministic export zip containing:
    - collection JSON
    - manifest.json
    - referenced bundles (as provided)
    """

    collection = load_collection(collection_path)
    manifest_payload = manifest(collection_path)

    # Use canonical bundle ordering from the manifest to ensure export stability
    canonical_bundles = manifest_payload["bundles"]
    collection_for_export = {
        "version": COLLECTION_VERSION,
        "bundles": [{k: v for k, v in bundle.items() if k != "hash"} for bundle in canonical_bundles],
    }

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            zipfile.ZipInfo("collection.json", date_time=_ZIP_EPOCH),
            json.dumps(collection_for_export, ensure_ascii=False, indent=2, sort_keys=True),
        )
        zf.writestr(
            zipfile.ZipInfo("manifest.json", date_time=_ZIP_EPOCH),
            json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True),
        )

        for item in canonical_bundles:
            rel_path = Path(item["path"])
            bpath = (collection_path.parent / rel_path).resolve() if not rel_path.is_absolute() else rel_path
            data = bpath.read_bytes()
            info = zipfile.ZipInfo(str(rel_path), date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16  # -rw-r--r--
            zf.writestr(info, data)

    return manifest_payload


__all__ = [
    "COLLECTION_VERSION",
    "load_collection",
    "bundle_hash",
    "compare_bundles",
    "manifest",
    "validate_collection_schema",
    "export_collection",
]
