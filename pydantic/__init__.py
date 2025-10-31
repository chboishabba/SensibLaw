"""Lightweight proxy to the real ``pydantic`` package when available."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _locate_real_pydantic() -> ModuleType | None:
    """Return the first installable ``pydantic`` module outside the project."""

    current = Path(__file__).resolve()
    for path in list(sys.path):
        if not path:
            continue
        candidate = Path(path).resolve() / "pydantic" / "__init__.py"
        if not candidate.exists() or candidate == current:
            continue

        spec = importlib.util.spec_from_file_location(
            "pydantic",
            candidate,
            submodule_search_locations=[str(candidate.parent)],
        )
        if not spec or not spec.loader:
            continue

        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get("pydantic")
        sys.modules["pydantic"] = module
        try:
            spec.loader.exec_module(module)
        except Exception:  # pragma: no cover - fall back to stub
            if previous is None:
                sys.modules.pop("pydantic", None)
            else:
                sys.modules["pydantic"] = previous
            continue
        else:
            if previous is not None:
                sys.modules["pydantic"] = previous
            return module

    return None


_REAL_MODULE = _locate_real_pydantic()

if _REAL_MODULE is not None:
    globals().update(_REAL_MODULE.__dict__)
    sys.modules[__name__] = _REAL_MODULE
else:

    class ValidationError(Exception):
        """Fallback validation error used when pydantic is unavailable."""


    class BaseModel:
        """A permissive stand-in for ``pydantic.BaseModel``."""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)


    class Extra:  # pragma: no cover - compatibility shim
        allow = "allow"
        forbid = "forbid"
        ignore = "ignore"


    def Field(default=None, **kwargs):  # pragma: no cover - compatibility shim
        return default


    def create_model(name: str, **fields):  # pragma: no cover - compatibility shim
        return type(name, (BaseModel,), fields)


    __all__ = [
        "BaseModel",
        "ValidationError",
        "Extra",
        "Field",
        "create_model",
    ]

