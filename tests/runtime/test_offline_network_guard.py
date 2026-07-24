import socket

import pytest

from src.runtime.offline_network_guard import (
    OfflineNetworkGuard,
    OfflineNetworkViolation,
)


def test_offline_guard_records_and_rejects_network_attempts() -> None:
    guard = OfflineNetworkGuard()
    with pytest.raises(OfflineNetworkViolation):
        with guard:
            socket.create_connection(("example.test", 443))

    receipt = guard.receipt.to_dict()
    assert receipt["network_attempt_count"] == 1
    assert receipt["network_absent"] is False


def test_offline_guard_certifies_pure_local_work() -> None:
    guard = OfflineNetworkGuard()
    with guard:
        assert sorted([3, 1, 2]) == [1, 2, 3]

    receipt = guard.receipt.to_dict()
    assert receipt["network_attempt_count"] == 0
    assert receipt["network_absent"] is True
