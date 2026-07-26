"""Canonical source-tree gateway for the SensibLaw command line.

Users and repository automation invoke ``python -m src.cli``. The top-level
:mod:`cli` package contains the command implementation, but is not a separate
public entry point.
"""

from __future__ import annotations


def main() -> None:
    """Load and run the internal command implementation."""
    from cli import main as real_main

    real_main()


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
