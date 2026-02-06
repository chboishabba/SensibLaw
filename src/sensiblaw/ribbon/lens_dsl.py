from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


class LensDslError(ValueError):
    pass


@dataclass(frozen=True)
class LensDefinition:
    lens_id: str
    units: str
    rho: Dict[str, Any]


ALLOWED_OPS = {
    "signal",
    "const",
    "add",
    "sub",
    "mul",
    "div",
    "clamp",
    "smooth",
    "abs",
    "log1p",
    "sqrt",
    "threshold",
    "blend",
    "mask",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def hash_lens(lens: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(lens).encode("utf-8")).hexdigest()


def _ensure_op(node: Dict[str, Any]) -> str:
    op = node.get("op")
    if op not in ALLOWED_OPS:
        raise LensDslError(f"unsupported op: {op}")
    return op


def _get_signal(signals: Dict[str, List[float]], name: str) -> List[float]:
    if name not in signals:
        raise LensDslError(f"missing signal: {name}")
    return signals[name]


def _check_len(values: Iterable[List[float]]) -> int:
    lengths = {len(v) for v in values}
    if len(lengths) != 1:
        raise LensDslError("signals must share a common length")
    return next(iter(lengths))


def _pointwise_binary(op: str, a: List[float], b: List[float]) -> List[float]:
    if op == "add":
        return [x + y for x, y in zip(a, b)]
    if op == "sub":
        return [x - y for x, y in zip(a, b)]
    if op == "mul":
        return [x * y for x, y in zip(a, b)]
    if op == "div":
        return [x / y if y != 0 else 0.0 for x, y in zip(a, b)]
    raise LensDslError(f"unsupported binary op: {op}")


def _smooth(window: int, series: List[float]) -> List[float]:
    if window <= 1:
        return list(series)
    out: List[float] = []
    for idx in range(len(series)):
        start = max(0, idx - window + 1)
        chunk = series[start : idx + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _eval(node: Dict[str, Any], signals: Dict[str, List[float]]) -> List[float]:
    op = _ensure_op(node)
    if op == "signal":
        return _get_signal(signals, node["name"])
    if op == "const":
        length = _check_len(signals.values())
        return [float(node["value"]) for _ in range(length)]
    if op in {"add", "sub", "mul", "div"}:
        args = node.get("args", [])
        if len(args) != 2:
            raise LensDslError(f"{op} requires exactly 2 args")
        left = _eval(args[0], signals)
        right = _eval(args[1], signals)
        return _pointwise_binary(op, left, right)
    if op == "clamp":
        inner = _eval(node["expr"], signals)
        lo = float(node["min"])
        hi = float(node["max"])
        return [min(max(x, lo), hi) for x in inner]
    if op == "smooth":
        inner = _eval(node["expr"], signals)
        window = int(node["window"])
        return _smooth(window, inner)
    if op == "abs":
        inner = _eval(node["expr"], signals)
        return [abs(x) for x in inner]
    if op == "log1p":
        inner = _eval(node["expr"], signals)
        return [math.log1p(max(x, 0.0)) for x in inner]
    if op == "sqrt":
        inner = _eval(node["expr"], signals)
        return [math.sqrt(max(x, 0.0)) for x in inner]
    if op == "threshold":
        inner = _eval(node["expr"], signals)
        k = float(node["k"])
        return [1.0 if x >= k else 0.0 for x in inner]
    if op == "blend":
        terms = node.get("terms", [])
        if not terms:
            raise LensDslError("blend requires at least one term")
        series_list = []
        weights = []
        for term in terms:
            weights.append(float(term["w"]))
            series_list.append(_eval(term["expr"], signals))
        length = _check_len(series_list)
        total_w = sum(weights)
        if total_w == 0:
            return [0.0 for _ in range(length)]
        out = [0.0 for _ in range(length)]
        for w, series in zip(weights, series_list):
            for idx, value in enumerate(series):
                out[idx] += w * value
        return [x / total_w for x in out]
    if op == "mask":
        expr = _eval(node["expr"], signals)
        predicate = _eval(node["predicate"], signals)
        return [x if p else 0.0 for x, p in zip(expr, predicate)]
    raise LensDslError(f"unsupported op: {op}")


def evaluate_rho(lens: Dict[str, Any], signals: Dict[str, List[float]]) -> List[float]:
    if "rho" not in lens:
        raise LensDslError("lens missing rho")
    if not signals:
        raise LensDslError("signals are required")
    _check_len(signals.values())
    rho = _eval(lens["rho"], signals)
    return [max(0.0, x) for x in rho]
