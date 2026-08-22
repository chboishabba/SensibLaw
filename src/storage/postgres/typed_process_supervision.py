"""Install parent-death supervision for spawned typed PostgreSQL workers."""

from __future__ import annotations

from typing import Any

from src.runtime.durable_work_items import linux_parent_death_initializer
from src.storage.postgres.typed_execution_pool import _worker_main as _typed_worker_body


_INSTALL_MARKER = "_typed_process_supervision_installed"


def supervised_worker_main(*args: Any) -> None:
    """Arm PDEATHSIG before opening a worker database connection."""

    linux_parent_death_initializer()
    _typed_worker_body(*args)


def install_typed_process_supervision() -> bool:
    from src.storage.postgres import typed_execution_pool

    if getattr(typed_execution_pool, _INSTALL_MARKER, False):
        return False
    typed_execution_pool._worker_main = supervised_worker_main
    setattr(typed_execution_pool, _INSTALL_MARKER, True)
    return True


__all__ = [
    "_typed_worker_body",
    "install_typed_process_supervision",
    "supervised_worker_main",
]
