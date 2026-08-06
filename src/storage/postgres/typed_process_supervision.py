"""Install parent-death supervision for spawned typed PostgreSQL workers."""

from __future__ import annotations

from typing import Any

from src.runtime.durable_work_items import linux_parent_death_initializer


_INSTALL_MARKER = "_typed_process_supervision_installed"


def supervised_worker_main(*args: Any) -> None:
    """Arm PDEATHSIG before opening a worker database connection."""

    linux_parent_death_initializer()
    # Under spawn this module and typed_execution_pool are imported afresh in
    # the child, so the latter still exposes its original worker body rather
    # than the parent-process monkeypatch below.
    from src.storage.postgres.typed_execution_pool import _worker_main

    if _worker_main is supervised_worker_main:
        raise RuntimeError("typed worker supervision recursion detected")
    _worker_main(*args)


def install_typed_process_supervision() -> bool:
    from src.storage.postgres import typed_execution_pool

    if getattr(typed_execution_pool, _INSTALL_MARKER, False):
        return False
    typed_execution_pool._worker_main = supervised_worker_main
    setattr(typed_execution_pool, _INSTALL_MARKER, True)
    return True


__all__ = [
    "install_typed_process_supervision",
    "supervised_worker_main",
]
