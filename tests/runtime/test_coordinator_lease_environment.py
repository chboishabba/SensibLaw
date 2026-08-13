from __future__ import annotations

import pytest

from src.runtime.coordinator_lease_guard import (
    COORDINATOR_LEASE_ENV,
    DEFAULT_COORDINATOR_LEASE_SECONDS,
    coordinator_lease_seconds,
)


def test_coordinator_lease_uses_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(COORDINATOR_LEASE_ENV, raising=False)
    assert coordinator_lease_seconds() == DEFAULT_COORDINATOR_LEASE_SECONDS


def test_coordinator_lease_uses_explicit_environment(monkeypatch) -> None:
    monkeypatch.setenv(COORDINATOR_LEASE_ENV, "3")
    assert coordinator_lease_seconds() == 3


def test_coordinator_lease_rejects_invalid_or_too_small_values(monkeypatch) -> None:
    monkeypatch.setenv(COORDINATOR_LEASE_ENV, "not-an-integer")
    with pytest.raises(ValueError, match="must be an integer"):
        coordinator_lease_seconds()

    monkeypatch.setenv(COORDINATOR_LEASE_ENV, "2")
    with pytest.raises(ValueError, match="at least three"):
        coordinator_lease_seconds()
