"""Lightweight proxy to the real ``pydantic`` package when available.""" #PICK ONE
"""Compatibility bridge to the real :mod:`pydantic` package."""

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


    def Field(default=None, **kwargs):  # type: ignore[unused-argument]
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

from typing import Any, Dict

_THIS_FILE = Path(__file__).resolve()


def _load_real_pydantic() -> ModuleType | None:
    for entry in sys.path:
        candidate = Path(entry).joinpath("pydantic", "__init__.py")
        if not candidate.exists() or candidate.resolve() == _THIS_FILE:
            continue
        spec = importlib.util.spec_from_file_location("pydantic", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[__name__] = module
        spec.loader.exec_module(module)
        return module
    return None


_REAL_MODULE = _load_real_pydantic()

if _REAL_MODULE is None:
    class BaseModel:  # type: ignore[too-many-ancestors]
        """Minimal stand-in used when the real dependency is unavailable."""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)


    def Field(default: Any = None, **kwargs: Dict[str, Any]) -> Any:  # type: ignore[misc]
        return default


    __all__ = ["BaseModel", "Field"]


else:
    globals().update({name: getattr(_REAL_MODULE, name) for name in dir(_REAL_MODULE) if not name.startswith("_")})
    __all__ = [name for name in globals() if not name.startswith("_")]
