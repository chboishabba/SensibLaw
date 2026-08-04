from __future__ import annotations

import json
from pathlib import Path
import runpy
from types import SimpleNamespace


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_failed_serial_trace_normalizes_exact_parser_coverage(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "normalize_exact_0008_baseline.py")
    )
    document_ref = "document:baseline"
    state_path = tmp_path / "state.json"
    summaries = tmp_path / "summaries"
    _write(
        state_path,
        {
            "document_executor_contract_ref": "compiler:test",
            "corpus_ref": "corpus:test",
            "manifest_sha256": "manifest-sha",
            "worker_budget": 1,
            "document_workers": 1,
            "parser_workers": 1,
            "closure_workers": 1,
            "owner_partitions": 1,
            "parser_limit_chars": 100,
            "parser_target_chars": 40,
            "parser_overlap_chars": 4,
            "completed_document_count": 0,
            "failure_refs": ["failure:1"],
            "documents": {
                document_ref: {
                    "state": "failed",
                    "error_type": "DocumentResourceLimitError",
                }
            },
        },
    )
    for sequence_no, start, end in ((0, 0, 40), (1, 40, 75)):
        fibre_ref = f"document-fibre:{sequence_no}"
        _write(
            summaries / f"{sequence_no}.summary.json",
            {
                "contract_ref": "parser-document-fibres:v0_2",
                "fibre": {
                    "document_ref": document_ref,
                    "fibre_ref": fibre_ref,
                    "sequence_no": sequence_no,
                    "owner_start": start,
                    "owner_end": end,
                    "context_start": max(0, start - 4),
                    "context_end": min(75, end + 4),
                    "text_sha256": f"fibre-sha-{sequence_no}",
                },
                "counts": {"tokens": 12},
                "owned_sentence_count": 2,
                "owned_token_count": 10,
            },
        )

    args = SimpleNamespace(
        state=state_path,
        parser_summary_root=summaries,
        local_typing_seconds=10,
        streaming_closure_seconds=5,
        other_seconds=1,
        peak_rss_bytes=1234,
        processed_parser_tokens=20,
        local_type_alternatives=7,
        typed_meets=6,
        refinements=5,
        demands=4,
        factor_scans=3,
        output_nodes=2,
    )
    baseline = namespace["build_baseline"](args)

    assert baseline["configuration"]["worker_budget"] == 1
    assert baseline["parser_checkpoints"]["fibre_count"] == 2
    assert baseline["parser_checkpoints"]["canonical_character_count"] == 75
    assert baseline["parser_checkpoints"]["owned_token_count"] == 20
    assert baseline["parser_checkpoints"]["context_token_count"] == 24
    assert baseline["parser_checkpoints"]["exact_owner_coverage"] is True
    assert baseline["failure"]["completed_document_count"] == 0
    assert baseline["failure"]["compiler_publication_state"] == "not_started"
    assert baseline["semantic_output_identity"] is None
    assert baseline["publication_identity"] is None
