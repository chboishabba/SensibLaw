"""SensibLaw package bootstrap utilities."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Iterable


def _alias_modules(names: Iterable[str]) -> None:
    """Expose ``src.<name>`` packages as top-level module aliases.

    The historical codebase imported modules such as ``models`` or ``storage``
    directly from the project root.  The tests, however, expect to import the
    modern ``src.<name>`` packages.  To keep both styles working we eagerly
    import the ``src`` package counterparts and register them in
    :data:`sys.modules` under their legacy names.  This keeps runtime imports
    backwards compatible without requiring every module to be updated
    simultaneously.
    """

    for name in names:
        target = f"{__name__}.{name}"
        try:
            module = import_module(target)
        except ModuleNotFoundError:
            continue
        sys.modules[name] = module


_alias_modules(
    (
        "models",
        "graph",
        "concepts",
        "culture",
        "glossary",
        "ingestion",
        "rules",
        "text",
        "storage",
    )
)


__all__ = []
