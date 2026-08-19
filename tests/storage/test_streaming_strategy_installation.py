from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_streaming_worker_import_defers_strategy_install_until_module_is_ready() -> (
    None
):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import src.storage.postgres.streaming_spacy_execution as module; "
                "assert hasattr(module, 'materialize_numeric_document_hierarchy')"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
