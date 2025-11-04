"""Compatibility bridge to the real :mod:`pydantic` package."""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import PathFinder
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

__all__ = ["BaseModel", "Field"]


def _load_real_pydantic() -> ModuleType | None:
    """Attempt to load the genuine :mod:`pydantic` module from site-packages."""

    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent

    for entry in list(sys.path):
        if not entry:
            continue
        try:
            candidate = Path(entry).resolve()
        except Exception:  # pragma: no cover - defensive against odd sys.path entries
            continue
        if project_root in {candidate, candidate.parent}:
            continue

        spec = PathFinder.find_spec("pydantic", [str(candidate)])
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules["pydantic"] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module

    return None


_module = _load_real_pydantic()


if _module is not None:
    globals().update(
        {
            name: getattr(_module, name)
            for name in dir(_module)
            if not name.startswith("__")
        }
    )
    exported: Dict[str, Any] = getattr(_module, "__dict__", {})
    __all__ = getattr(_module, "__all__", sorted(exported))

    def __getattr__(name: str) -> Any:
        return getattr(_module, name)

    __doc__ = getattr(_module, "__doc__", __doc__)
    __version__ = getattr(_module, "__version__", None)
else:

    class ValidationError(Exception):
        """Fallback validation error used when pydantic is unavailable."""

    class BaseModel:  # type: ignore[override]
        """A permissive stand-in for :class:`pydantic.BaseModel`."""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

        def dict(self, **_: Any) -> Dict[str, Any]:
            return self.__dict__.copy()

    def Field(default: Any = None, **_: Any) -> Any:  # type: ignore[override]
        return default

    __all__ = ["BaseModel", "Field", "ValidationError"]
