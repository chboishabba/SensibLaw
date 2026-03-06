import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("SensibLaw/scripts/check_wiki_timeline_parity_offline.js")


def test_wiki_timeline_parity_offline():
    if not SCRIPT.exists():
        raise AssertionError(f"Missing parity script at {SCRIPT}")
    env = os.environ.copy()
    env.setdefault("ITIR_LEXEME_TOKENIZER_MODE", "deterministic_legal")
    try:
        subprocess.run(
            ["node", str(SCRIPT)],
            check=True,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # Node not available; skip instead of fail.
        import pytest

        pytest.skip("node not available for offline parity check")
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stdout)
        sys.stderr.write(exc.stderr)
        raise
