from __future__ import annotations

from importlib import util as _importlib_util
from importlib.machinery import PathFinder as _PathFinder
from pathlib import Path as _Path
import sys as _sys


def _load_real_pydantic():  # type: ignore[return-type]
    root = _Path(__file__).resolve().parent.parent
    search_paths = [p for p in _sys.path if _Path(p).resolve() != root]
    spec = _PathFinder.find_spec("pydantic", search_paths)
    if spec is None or spec.loader is None:
        return None
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_REAL = _load_real_pydantic()

if _REAL is not None:
    globals().update(_REAL.__dict__)
    __all__ = getattr(
        _REAL,
        "__all__",
        [name for name in _REAL.__dict__ if not name.startswith("_")],
    )
else:

    class BaseModel:  # type: ignore[too-few-public-methods]
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)


    def Field(default=None, **kwargs):  # type: ignore[unused-argument]
        return default


    __all__ = ["BaseModel", "Field"]
