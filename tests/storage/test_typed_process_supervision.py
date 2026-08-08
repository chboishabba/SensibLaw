from __future__ import annotations

from src.storage.postgres import typed_execution_pool
from src.storage.postgres.typed_process_supervision import (
    _typed_worker_body,
    install_typed_process_supervision,
    supervised_worker_main,
)


def test_supervision_binds_original_worker_body_before_patch() -> None:
    assert _typed_worker_body is not supervised_worker_main
    assert _typed_worker_body.__module__ == (
        "src.storage.postgres.typed_execution_pool"
    )


def test_supervision_install_is_idempotent() -> None:
    prior = typed_execution_pool._worker_main
    first = install_typed_process_supervision()
    second = install_typed_process_supervision()

    assert typed_execution_pool._worker_main is supervised_worker_main
    assert second is False
    if prior is supervised_worker_main:
        assert first is False
    else:
        assert first is True
