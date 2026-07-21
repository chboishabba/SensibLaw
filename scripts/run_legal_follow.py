#!/usr/bin/env python3
"""Run one bounded AU/GB/US legal source follow profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sources.legal_follow import follow_legal_sources, profile_for  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction", required=True, choices=("AU", "GB", "US"))
    parser.add_argument("--seed-url", action="append", default=[])
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-documents", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _file_name(index: int, url: str, media_type: str | None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:100]
    suffix = ".html" if media_type in {"text/html", "application/xhtml+xml"} else ".txt"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{index:04d}_{slug}_{digest}{suffix}"


def main() -> int:
    args = _parse_args()
    profile = profile_for(args.jurisdiction)
    result = follow_legal_sources(
        args.jurisdiction,
        seed_urls=args.seed_url,
        max_depth=args.max_depth,
        max_documents=args.max_documents,
    )
    output_dir = args.output_dir.resolve()
    raw_dir = output_dir / "raw"
    canonical_dir = output_dir / "canonical"
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for index, followed in enumerate(result.documents, start=1):
        document = followed.document
        final_url = document.final_url or document.requested_url
        name = _file_name(index, final_url, document.media_type)
        raw_path = raw_dir / name
        canonical_path = canonical_dir / (Path(name).stem + ".txt")
        raw_path.write_bytes(document.raw_bytes)
        canonical_path.write_text(document.canonical_text, encoding="utf-8")
        documents.append(
            {
                "requested_url": document.requested_url,
                "final_url": document.final_url,
                "depth": followed.depth,
                "raw_path": str(raw_path.relative_to(output_dir)),
                "canonical_path": str(canonical_path.relative_to(output_dir)),
                "links": [row.to_dict() for row in followed.links],
                "receipt": document.receipt.to_dict(),
            }
        )
    manifest = {
        "schema_version": "sl.legal_follow_manifest.v0_2",
        "profile": profile.to_dict(),
        "documents": documents,
        "receipts": [row.to_dict() for row in result.receipts],
        "discovered_urls": list(result.discovered_urls),
        "truncated": result.truncated,
        "summary": {
            "fetched_document_count": len(documents),
            "failure_count": sum(row.status != "fetched" for row in result.receipts),
            "discovered_url_count": len(result.discovered_urls),
        },
        "authority": "source-discovery-only",
    }
    manifest_path = output_dir / "follow_manifest.json"
    encoded = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
    manifest_path.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
