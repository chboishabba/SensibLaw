from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True, slots=True)
class GammaPosterior:
    # Shape/rate parameterization.
    alpha0: float
    beta0: float
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return float(self.alpha / self.beta) if self.beta > 0 else float("nan")


def empirical_bayes_gamma_prior(mu: float, kappa: float) -> Tuple[float, float]:
    """Deterministic Gamma prior from baseline rate + strength.

    Uses:
      alpha0 = mu * kappa
      beta0  = kappa
    so the prior mean is mu and the prior "exposure" is kappa.
    """
    m = float(mu)
    if not math.isfinite(m) or m < 0:
        m = 0.0
    k = float(kappa)
    if not math.isfinite(k) or k <= 0:
        k = 1.0
    return (m * k, k)


def gamma_poisson_posterior(y: int, exposure: float, alpha0: float, beta0: float) -> GammaPosterior:
    yy = max(0, int(y))
    e = float(exposure)
    if not math.isfinite(e) or e < 0:
        e = 0.0
    a0 = float(alpha0)
    b0 = float(beta0)
    if not math.isfinite(a0) or a0 <= 0:
        a0 = 1.0
    if not math.isfinite(b0) or b0 <= 0:
        b0 = 1.0
    return GammaPosterior(alpha0=a0, beta0=b0, alpha=a0 + yy, beta=b0 + e)


def _gammainc_series(a: float, x: float, eps: float = 1e-14, max_iter: int = 2000) -> float:
    # Regularized lower incomplete gamma P(a,x) via series (x < a+1).
    gln = math.lgamma(a)
    ap = a
    sum_ = 1.0 / a
    del_ = sum_
    for _ in range(max_iter):
        ap += 1.0
        del_ *= x / ap
        sum_ += del_
        if abs(del_) < abs(sum_) * eps:
            break
    return sum_ * math.exp(-x + a * math.log(x) - gln)


def _gammainc_cf(a: float, x: float, eps: float = 1e-14, max_iter: int = 2000) -> float:
    # Regularized upper incomplete gamma Q(a,x) via continued fraction (x >= a+1).
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gamma_cdf(x: float, alpha: float, beta: float) -> float:
    """Gamma(shape=alpha, rate=beta) CDF at x (regularized)."""
    xx = float(x)
    a = float(alpha)
    b = float(beta)
    if not (math.isfinite(xx) and math.isfinite(a) and math.isfinite(b)):
        return float("nan")
    if a <= 0 or b <= 0:
        return float("nan")
    if xx <= 0.0:
        return 0.0
    # Convert to standard gamma with scale=1 via t=beta*x.
    t = b * xx
    if t < a + 1.0:
        return _gammainc_series(a, t)
    # Q(a,t) returned by CF; CDF = 1 - Q
    q = _gammainc_cf(a, t)
    return max(0.0, min(1.0, 1.0 - q))


def gamma_ppf(p: float, alpha: float, beta: float, *, tol: float = 2e-10) -> float:
    """Deterministic inverse CDF (PPF) via bisection on [0, hi]."""
    pp = float(p)
    if pp <= 0.0:
        return 0.0
    if pp >= 1.0:
        # Use a large finite cap.
        return float("inf")
    a = float(alpha)
    b = float(beta)
    if not (math.isfinite(pp) and math.isfinite(a) and math.isfinite(b)) or a <= 0 or b <= 0:
        return float("nan")

    # Bracket hi by doubling until CDF(hi) >= p.
    lo = 0.0
    hi = max(1.0 / b, 1e-12)
    for _ in range(200):
        if gamma_cdf(hi, a, b) >= pp:
            break
        hi *= 2.0
        if hi > 1e18:
            break

    for _ in range(200):
        mid = (lo + hi) / 2.0
        cmid = gamma_cdf(mid, a, b)
        if not math.isfinite(cmid):
            hi = mid
            continue
        if cmid < pp:
            lo = mid
        else:
            hi = mid
        if (hi - lo) <= tol * max(1.0, hi):
            break

    return (lo + hi) / 2.0


def gamma_credible_interval(alpha: float, beta: float, q_lo: float, q_hi: float) -> Tuple[float, float]:
    lo = gamma_ppf(float(q_lo), alpha, beta)
    hi = gamma_ppf(float(q_hi), alpha, beta)
    return (lo, hi)

