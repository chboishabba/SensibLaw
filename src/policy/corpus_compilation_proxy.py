"""Import-order-stable proxy for the graph-enabled corpus compiler.

The tranche runner imports ``src.policy.corpus_compilation`` directly before it
loads the operational compiler.  A package ``__getattr__`` hook is therefore not
enough to select the graph execution override.  This proxy keeps the public
module identity stable, forwards ordinary reads and monkeypatches to the legacy
module, and owns only the explicitly graph-enabled attributes.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Mapping


class CorpusCompilationProxy(ModuleType):
    """Forward a module surface while retaining a small explicit override set."""

    def __init__(
        self,
        legacy: ModuleType,
        *,
        overrides: Mapping[str, Any],
    ) -> None:
        super().__init__(legacy.__name__, legacy.__doc__)
        local_names = frozenset(
            {
                "_proxy_legacy",
                "_proxy_local_names",
                *overrides,
            }
        )
        ModuleType.__setattr__(self, "_proxy_legacy", legacy)
        ModuleType.__setattr__(self, "_proxy_local_names", local_names)
        for name in (
            "__file__",
            "__loader__",
            "__package__",
            "__path__",
            "__spec__",
        ):
            if hasattr(legacy, name):
                ModuleType.__setattr__(self, name, getattr(legacy, name))
        for name, value in overrides.items():
            ModuleType.__setattr__(self, name, value)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._proxy_legacy, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") or name in self._proxy_local_names:
            ModuleType.__setattr__(self, name, value)
            return
        setattr(self._proxy_legacy, name, value)

    def __delattr__(self, name: str) -> None:
        if name.startswith("__") or name in self._proxy_local_names:
            ModuleType.__delattr__(self, name)
            return
        delattr(self._proxy_legacy, name)

    def __dir__(self) -> list[str]:
        return sorted(
            set(ModuleType.__dir__(self))
            | set(dir(self._proxy_legacy))
            | set(self._proxy_local_names)
        )


def build_corpus_compilation_proxy(
    legacy: ModuleType,
    *,
    overrides: Mapping[str, Any],
) -> CorpusCompilationProxy:
    return CorpusCompilationProxy(legacy, overrides=overrides)


__all__ = ["CorpusCompilationProxy", "build_corpus_compilation_proxy"]
