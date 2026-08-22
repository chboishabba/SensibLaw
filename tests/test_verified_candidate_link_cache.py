from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.storage.postgres import verified_candidate_link_cache as link_cache


class _Compiler:
    def __init__(self, batches):
        self.calls = 0
        self.batches = batches

        def iterator(_reader, _descriptor, _family):
            self.calls += 1
            yield from self.batches

        self._iter_descriptor_family = iterator


def test_candidate_link_cache_reuses_only_narrow_verified_projection(monkeypatch) -> None:
    runtime = SimpleNamespace()
    compiler = _Compiler(
        (
            (
                {
                    "demand_ref": "demand:1",
                    "candidate_set_refs": ("set:1", "set:2"),
                    "large_semantic_payload": {"must_not_be_cached": "x" * 1000},
                },
                {"demand_ref": "demand:2", "candidate_set_refs": ()},
            ),
        )
    )
    monkeypatch.setattr(link_cache, "_runtime", lambda: runtime)
    original, replacement = link_cache.install_verified_candidate_link_cache(compiler)

    first = tuple(replacement(None, {"artifact_key": "demands"}, "rows"))
    second = tuple(replacement(None, {"artifact_key": "demands"}, "rows"))

    assert first == compiler.batches
    assert compiler.calls == 1
    assert second == (
        (
            {
                "demand_ref": "demand:1",
                "candidate_set_refs": ("set:1", "set:2"),
            },
        ),
    )
    cached = runtime._verified_candidate_link_cache[("demands", "rows")]
    assert cached == second[0]
    assert "large_semantic_payload" not in cached[0]
    assert runtime.verified_candidate_link_rows_cached == 1
    assert original is not replacement


def test_empty_link_projection_is_cached_without_second_descriptor_read(monkeypatch) -> None:
    runtime = SimpleNamespace()
    compiler = _Compiler((({"demand_ref": "demand:1", "candidate_set_refs": ()},),))
    monkeypatch.setattr(link_cache, "_runtime", lambda: runtime)
    _original, replacement = link_cache.install_verified_candidate_link_cache(compiler)

    assert tuple(replacement(None, {"artifact_key": "demands"}, "rows")) == compiler.batches
    assert tuple(replacement(None, {"artifact_key": "demands"}, "rows")) == ()
    assert compiler.calls == 1


def test_interrupted_first_pass_never_publishes_cache(monkeypatch) -> None:
    runtime = SimpleNamespace()

    class Compiler:
        calls = 0

        @staticmethod
        def _iter_descriptor_family(_reader, _descriptor, _family):
            Compiler.calls += 1
            yield (
                {"meet_ref": "meet:1", "candidate_set_refs": ("set:1",)},
            )
            raise RuntimeError("verification failed")

    compiler = Compiler()
    monkeypatch.setattr(link_cache, "_runtime", lambda: runtime)
    _original, replacement = link_cache.install_verified_candidate_link_cache(compiler)

    iterator = replacement(None, {"artifact_key": "meets"}, "rows")
    assert next(iterator)[0]["meet_ref"] == "meet:1"
    with pytest.raises(RuntimeError, match="verification failed"):
        next(iterator)

    assert getattr(runtime, "_verified_candidate_link_cache", {}) == {}
