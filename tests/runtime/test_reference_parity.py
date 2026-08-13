from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.runtime.reference_parity import (
    compare_reference_surfaces,
    reference_semantic_surface,
)


def test_reference_parity_import_is_safe_from_a_fresh_interpreter() -> None:
    """Reference-parity must not re-enter policy installation during import."""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.runtime.reference_parity import reference_semantic_surface",
        ],
        cwd=Path(__file__).parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def _build(*, factor_digest: str = "factor-digest") -> dict[str, object]:
    return {
        "document_ref": "document:test",
        "revision": 7,
        "owner_fingerprint": {"proposal_manifest_ref": "proposal:manifest"},
        "materialized_reduction": {"graph_ref": "graph:test"},
        "fixed_point_certificate": {
            "certificate_ref": "certificate:test",
            "ledger_ref": "ledger:test",
            "materialized_graph_ref": "graph:test",
            "local_fixed_point": "reached",
        },
        "family_manifests": {
            "factors": {
                "record_count": 4,
                "byte_count": 100,
                "ordered_digest": factor_digest,
                "encoding_ref": "canonical-jsonl:v1",
            },
            "residuals": {
                "record_count": 0,
                "byte_count": 0,
                "ordered_digest": "empty",
                "encoding_ref": "canonical-jsonl:v1",
            },
        },
        "reference_finalization_contract": "reference-backed-finalization:v1",
    }


def test_reference_surface_is_compact_and_stable() -> None:
    surface = reference_semantic_surface(_build())

    assert surface["materialized_graph_ref"] == "graph:test"
    assert surface["families"]["factors"]["record_count"] == 4
    assert "path" not in surface["families"]["factors"]
    assert surface["surface_ref"].startswith("reference-semantic-surface:")


def test_parity_uses_manifests_before_row_level_diff() -> None:
    matched = compare_reference_surfaces(_build(), _build())
    changed = compare_reference_surfaces(
        _build(factor_digest="new"),
        _build(),
    )

    assert matched["matched"] is True
    assert matched["row_level_diff_required"] is False
    assert matched["full_receipts_loaded_together"] is False
    assert changed["matched"] is False
    assert changed["row_level_diff_required"] is True
    assert "families" in changed["mismatches"]
