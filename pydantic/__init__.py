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
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default: Any = None, **kwargs: Any) -> Any:  # pragma: no cover - shim
        return default

    __all__ = ["BaseModel", "Field"]
