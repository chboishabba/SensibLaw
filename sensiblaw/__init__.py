"""
Namespace shim so `import sensiblaw.*` resolves to the runtime code in src/sensiblaw.
This prevents the doc-side package at the repo root from shadowing the real
implementation modules (db, event_participants, ingest, etc.) when pytest runs
with rootdir at the project root.
"""

import pathlib
import pkgutil

_runtime_pkg = pathlib.Path(__file__).resolve().parent.parent / "src" / "sensiblaw"
if _runtime_pkg.exists():
    __path__ = pkgutil.extend_path(__path__, __name__)
    __path__.append(str(_runtime_pkg))

__all__: list[str] = []
