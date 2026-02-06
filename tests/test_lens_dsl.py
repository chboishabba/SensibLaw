from __future__ import annotations

import pytest

from sensiblaw.ribbon.lens_dsl import LensDslError, evaluate_rho, hash_lens


def test_hash_is_deterministic():
    lens = {"lens_id": "time", "units": "seconds", "rho": {"op": "const", "value": 1}}
    assert hash_lens(lens) == hash_lens(lens)


def test_evaluate_const_signal_blend():
    lens = {
        "lens_id": "blend",
        "units": "points",
        "rho": {
            "op": "blend",
            "terms": [
                {"w": 0.6, "expr": {"op": "signal", "name": "a"}},
                {"w": 0.4, "expr": {"op": "const", "value": 2}},
            ],
        },
    }
    signals = {"a": [1.0, 2.0, 3.0]}
    rho = evaluate_rho(lens, signals)
    assert rho == pytest.approx([1.4, 2.0, 2.6])


def test_mask_zeroes_values():
    lens = {
        "lens_id": "mask",
        "units": "points",
        "rho": {
            "op": "mask",
            "expr": {"op": "signal", "name": "x"},
            "predicate": {"op": "signal", "name": "p"},
        },
    }
    signals = {"x": [1.0, 2.0, 3.0], "p": [1.0, 0.0, 1.0]}
    rho = evaluate_rho(lens, signals)
    assert rho == [1.0, 0.0, 3.0]


def test_smooth_window():
    lens = {
        "lens_id": "smooth",
        "units": "points",
        "rho": {"op": "smooth", "window": 2, "expr": {"op": "signal", "name": "x"}},
    }
    signals = {"x": [2.0, 4.0, 6.0]}
    rho = evaluate_rho(lens, signals)
    assert rho == [2.0, 3.0, 5.0]


def test_unknown_signal_raises():
    lens = {"lens_id": "bad", "units": "points", "rho": {"op": "signal", "name": "x"}}
    with pytest.raises(LensDslError):
        evaluate_rho(lens, {"y": [1.0]})


def test_unknown_op_raises():
    lens = {"lens_id": "bad", "units": "points", "rho": {"op": "explode"}}
    with pytest.raises(LensDslError):
        evaluate_rho(lens, {"x": [1.0]})
