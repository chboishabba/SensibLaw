from __future__ import annotations

import pytest

from src.rules import get_dependencies


def _flatten(dependencies):
    return {
        label: [candidate.text for candidate in candidates]
        for label, candidates in dependencies.items()
    }


def test_dependency_candidates_simple_sentence():
    try:
        parses = get_dependencies("A person must not sell spray paint.")
    except (RuntimeError, ModuleNotFoundError) as exc:  # pragma: no cover - handled as skipped test
        pytest.skip(str(exc))
    assert len(parses) == 1

    candidates = _flatten(parses[0].candidates)
    assert candidates["nsubj"] == ["person"]
    assert candidates["verb"] == ["sell"]
    assert candidates["obj"] == ["spray paint"]
    assert candidates["aux"] == ["must"]
    assert candidates["neg"] == ["not"]
