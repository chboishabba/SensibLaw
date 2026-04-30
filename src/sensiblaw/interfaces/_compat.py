from __future__ import annotations

"""Compatibility helpers for the public ``sensiblaw.interfaces`` boundary."""

import importlib
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
        src_package = sys.modules["src"]

    for child_name in ("nlp", "reporting", "sensiblaw", "text"):
        alias_name = f"src.{child_name}"
        if alias_name in sys.modules:
            child_module = sys.modules[alias_name]
        else:
            child_module = importlib.import_module(alias_name)
            sys.modules[alias_name] = child_module
        setattr(src_package, child_name, child_module)
