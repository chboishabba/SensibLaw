"""Legacy wrapper for the :mod:`cli` package.

This module provides a tiny shim so that existing entry points which
referenced ``src.cli`` continue to operate.  The real command line
interface now lives in the top-level :mod:`cli` package.
"""

from __future__ import annotations

def main() -> None:
    """Entry point that defers loading the heavy ``cli`` package."""
    from cli import main as real_main

    real_main()


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()

