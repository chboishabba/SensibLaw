from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.runtime.numeric_kernel_progress import numeric_kernel_progress_measures


ROOT = Path(__file__).resolve().parents[2]


def test_numeric_progress_module_imports_before_storage_policy_initialization() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.runtime.numeric_kernel_progress import "
                "numeric_kernel_progress_snapshot; "
                "import src.policy.numeric_pnf_compilation; "
                "print(numeric_kernel_progress_snapshot.__name__)"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "numeric_kernel_progress_snapshot"


def test_numeric_snapshot_projects_only_defensible_named_eta_measures() -> None:
    measures = numeric_kernel_progress_measures(
        {
            "parser": {
                "partition_total": 48,
                "partition_completed": 24,
                "completed_token_count": 135_000,
            },
            "region_closure_by_kind": {
                "1": {
                    "total": 2_000,
                    "locally_or_fully_closed": 1_500,
                    "fully_closed": 1_300,
                },
                "3": {
                    "total": 100,
                    "locally_or_fully_closed": 20,
                    "fully_closed": 10,
                },
            },
            "frontier_reduction_by_kind": {
                "1": {"receipt_count": 1_200},
                "3": {"receipt_count": 25},
            },
            "frontier_stage_receipts": {
                "root_publication": {"row_count": 12, "elapsed_ms": 4.5}
            },
        }
    )

    assert measures["parser_partitions"] == {
        "completed": 24,
        "total": 48,
        "unit": "partitions",
    }
    assert measures["parser_tokens"] == {
        "completed": 135_000,
        "unit": "tokens",
    }
    assert measures["pnf_region_kind_1"] == {
        "completed": 1_500,
        "total": 2_000,
        "unit": "regions",
    }
    assert measures["frontier_reductions_kind_3"] == {
        "completed": 25,
        "total": 100,
        "unit": "interfaces",
    }
    assert measures["frontier_stage_root_publication"] == {
        "completed": 12,
        "unit": "rows",
    }
