"""Compatibility shim for optional pydantic dependency."""
from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import PathFinder
from pathlib import Path
from types import ModuleType


def _load_real_pydantic() -> ModuleType:
    this_dir = Path(__file__).resolve().parent
    project_root = this_dir.parent
    for entry in list(sys.path):
        try:
            if Path(entry).resolve() == project_root:
                continue
        except Exception:
            continue
        spec = PathFinder.find_spec("pydantic", [entry])
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["pydantic"] = module
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            return module
    raise ImportError("pydantic not installed")


try:
    _module = _load_real_pydantic()
except ImportError:  # pragma: no cover - exercised when dependency missing
    class BaseModel:  # type: ignore[override]
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def Field(default=None, **kwargs):  # type: ignore[override]
        return default

    __all__ = ["BaseModel", "Field"]
else:
    globals().update({k: getattr(_module, k) for k in dir(_module) if not k.startswith("__")})
    __all__ = getattr(_module, "__all__", sorted(globals().keys()))
