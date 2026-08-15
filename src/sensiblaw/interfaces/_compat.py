"""Compatibility helpers for the public ``sensiblaw.interfaces`` boundary."""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType


def install_src_package_aliases() -> None:
    """Bridge historical ``src.*`` imports onto the normal ``PYTHONPATH=.../src`` layout."""

    if "src" not in sys.modules:
        src_package = ModuleType("src")
        src_package.__path__ = [str(Path(__file__).resolve().parents[2])]
        sys.modules["src"] = src_package
    else:
        # A normal repository import already owns the package. Submodules are
        # imported by their actual consumers; eagerly importing every historical
        # child here creates cycles and loads optional NLP runtimes at the public
        # interface boundary.
        return
