"""Compatibility shim for environments without the real pydantic package."""

from __future__ import annotations

import site
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


_CURRENT_FILE = Path(__file__).resolve()
_REAL_MODULE = None

for base in site.getsitepackages():
    candidate = Path(base) / "pydantic" / "__init__.py"
    if not candidate.exists():
        continue
    resolved = candidate.resolve()
    if resolved == _CURRENT_FILE:
        continue
    spec = spec_from_file_location(
        "_pydantic_real",
        resolved,
        submodule_search_locations=[str(resolved.parent)],
    )
    if spec is None or spec.loader is None:
        continue
    module = module_from_spec(spec)
    module.__package__ = "pydantic"
    module.__path__ = [str(resolved.parent)]
    sys.modules[spec.name] = module
    sys.modules[__name__] = module
    spec.loader.exec_module(module)
    _REAL_MODULE = module
    break


if _REAL_MODULE is not None:
    __all__ = list(getattr(_REAL_MODULE, "__all__", []))
    __doc__ = getattr(_REAL_MODULE, "__doc__", None)
    __version__ = getattr(_REAL_MODULE, "__version__", None)

    for attr in __all__:
        globals()[attr] = getattr(_REAL_MODULE, attr)

    for attr in ("BaseModel", "Field", "ValidationError", "Extra", "create_model"):
        if hasattr(_REAL_MODULE, attr):
            globals()[attr] = getattr(_REAL_MODULE, attr)

    def __getattr__(name: str) -> Any:
        return getattr(_REAL_MODULE, name)

else:

    class BaseModel:
"""Compatibility shim for optional pydantic dependency."""
from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import PathFinder
from pathlib import Path
from types import ModuleType
"""Lightweight proxy to the real ``pydantic`` package when available.""" #PICK ONE
"""Compatibility bridge to the real :mod:`pydantic` package."""

from __future__ import annotations

import importlib.util
import sys
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

    def Field(default: Any = None, **kwargs: Any) -> Any:  # pragma: no cover - shim
        return default

    __all__ = ["BaseModel", "Field"]

    def Field(default: Any = None, **kwargs: Dict[str, Any]) -> Any:  # type: ignore[misc]
        return default


    __all__ = ["BaseModel", "Field"]


else:
    globals().update({name: getattr(_REAL_MODULE, name) for name in dir(_REAL_MODULE) if not name.startswith("_")})
    __all__ = [name for name in globals() if not name.startswith("_")]
