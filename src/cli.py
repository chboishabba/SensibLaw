"""Backward compatible wrapper for the new :mod:`cli` package."""

from __future__ import annotations

from cli import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - for direct execution
    main()
