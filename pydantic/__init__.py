"""Compatibility bridge to the real :mod:`pydantic` package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
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
