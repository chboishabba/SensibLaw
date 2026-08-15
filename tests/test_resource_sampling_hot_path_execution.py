from __future__ import annotations

from src.policy.resource_sampling_hot_path_execution import cached_sampler


def test_cached_sampler_reuses_only_within_ttl(monkeypatch) -> None:
    calls = 0
    now = 1_000

    def sample() -> int:
        nonlocal calls
        calls += 1
        return calls * 100

    def monotonic() -> int:
        return now

    monkeypatch.setattr(
        "src.policy.resource_sampling_hot_path_execution.monotonic_ns",
        monotonic,
    )
    current = cached_sampler(sample, ttl_ns=5)

    assert current() == 100
    assert current() == 100
    assert calls == 1

    now = 1_006
    assert current() == 200
    assert calls == 2
