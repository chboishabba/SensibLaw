from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True, slots=True)
class LognormalFit:
    mu: float
    sigma: float


def lognormal_fit(values: Sequence[float]) -> Optional[LognormalFit]:
    """Deterministic lognormal MLE fit for positive values.

    Returns mu/sigma for log(X) ~ Normal(mu, sigma^2). Filters non-positive values.
    """
    xs = []
    for v in values or []:
        try:
            x = float(v)
        except Exception:
            continue
        if not math.isfinite(x) or x <= 0.0:
            continue
        xs.append(x)

    if len(xs) < 2:
        return None

    logs = [math.log(x) for x in xs]
    mu = sum(logs) / float(len(logs))
    var = sum((z - mu) ** 2 for z in logs) / float(len(logs))
    sigma = math.sqrt(max(0.0, var))
    return LognormalFit(mu=float(mu), sigma=float(sigma))


def _normal_cdf(z: float) -> float:
    # Standard normal CDF via erf (deterministic, no external deps).
    return 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0)))


def lognormal_tail_prob(mu: float, sigma: float, threshold: float) -> float:
    """P(X > threshold) for X ~ LogNormal(mu, sigma^2), deterministic."""
    t = float(threshold)
    if not math.isfinite(t) or t <= 0.0:
        return float("nan")
    m = float(mu)
    s = float(sigma)
    if not (math.isfinite(m) and math.isfinite(s)) or s < 0.0:
        return float("nan")
    if s == 0.0:
        # Degenerate at exp(mu).
        return 1.0 if math.exp(m) > t else 0.0
    z = (math.log(t) - m) / s
    return max(0.0, min(1.0, 1.0 - _normal_cdf(z)))

