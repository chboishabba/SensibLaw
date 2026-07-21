"""Inspect one text through the operational local reference-binding compiler."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.operational_corpus_compilation import (  # noqa: E402
    compile_document_operational,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    text = args.text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with tempfile.TemporaryDirectory(prefix="reference-binding-inspect-"):
        compilation = compile_document_operational(
            {
                "document_ref": f"document:inspect:{digest}",
                "content_sha256": digest,
                "media_type": "text/plain",
                "canonical_text": text,
                "source_ref": f"source:inspect:{digest}",
            },
            default_compiler_context(),
        )
    artifacts = compilation.artifacts
    reference_factor_refs = {
        str(row["reference_factor_ref"])
        for row in artifacts.get("binding_candidate_sets") or ()
    }
    candidate_factor_refs = {
        str(member["candidate_factor_ref"])
        for row in artifacts.get("binding_candidate_sets") or ()
        for member in row.get("members") or ()
    }
    interesting_refs = reference_factor_refs | candidate_factor_refs
    output = {
        "text": text,
        "reference_factors": [
            row
            for row in artifacts["refined_pnf_graph"]["factors"]
            if str(row["factor_ref"]) in reference_factor_refs
        ],
        "nominal_or_argument_factors": [
            row
            for row in artifacts["pnf_graph"]["factors"]
            if str(row.get("factor_type") or "").startswith("semantic.argument.")
            or str(row.get("factor_type") or "") == "semantic.mention_identity"
        ],
        "interesting_factor_anchors": [
            row
            for row in artifacts.get("factor_anchors") or ()
            if str(row["factor_ref"]) in interesting_refs
            or row.get("parser_pos") in {"NOUN", "PROPN", "PRON"}
        ],
        "candidate_sets": artifacts.get("binding_candidate_sets") or (),
        "exclusion_summaries": artifacts.get("binding_exclusion_summaries") or (),
        "projection_summaries": {
            "argument_role": artifacts.get("argument_role_projection_summary"),
            "reference_argument": artifacts.get(
                "reference_argument_projection_summary"
            ),
            "binding": artifacts.get("binding_compaction_summary"),
        },
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
