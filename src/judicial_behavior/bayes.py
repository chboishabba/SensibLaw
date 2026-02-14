from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True, slots=True)
class BetaPosterior:
    alpha0: float
    beta0: float
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        d = self.alpha + self.beta
        return float(self.alpha / d) if d > 0 else 0.5


def empirical_bayes_prior(mu: float, kappa: float) -> Tuple[float, float]:
    """Deterministic prior from baseline mean + prior strength.

    `kappa` is the "equivalent sample size" for shrinkage.
    """
    m = float(mu)
    if not math.isfinite(m):
        m = 0.5
    m = max(0.0, min(1.0, m))
    k = float(kappa)
    if not math.isfinite(k) or k <= 0:
        k = 1.0
    return (m * k, (1.0 - m) * k)


def beta_binomial_posterior(y: int, n: int, alpha0: float, beta0: float) -> BetaPosterior:
    yy = max(0, int(y))
    nn = max(0, int(n))
    a0 = float(alpha0)
    b0 = float(beta0)
    if not math.isfinite(a0) or a0 <= 0:
        a0 = 1.0
    if not math.isfinite(b0) or b0 <= 0:
        b0 = 1.0
    yy = min(yy, nn)
    return BetaPosterior(alpha0=a0, beta0=b0, alpha=a0 + yy, beta=b0 + (nn - yy))


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-14) -> float:
    # Continued fraction for incomplete beta (Numerical Recipes / Cephes-style).
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m

        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        del_ = d * c
        h *= del_

        if abs(del_ - 1.0) < eps:
            break

    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a,b)."""
    xx = float(x)
    aa = float(a)
    bb = float(b)
    if not (math.isfinite(xx) and math.isfinite(aa) and math.isfinite(bb)):
        return float("nan")
    if aa <= 0 or bb <= 0:
        return float("nan")
    if xx <= 0.0:
        return 0.0
    if xx >= 1.0:
        return 1.0

    # Compute front factor in log-space for stability.
    ln_bt = (aa * math.log(xx)) + (bb * math.log(1.0 - xx)) - _log_beta(aa, bb)
    bt = math.exp(ln_bt)

    # Use symmetry to improve convergence.
    if xx < (aa + 1.0) / (aa + bb + 2.0):
        return bt * _betacf(aa, bb, xx) / aa
    return 1.0 - bt * _betacf(bb, aa, 1.0 - xx) / bb


def beta_ppf(p: float, a: float, b: float, *, tol: float = 2e-10) -> float:
    """Deterministic inverse CDF via bisection on [0,1]."""
    pp = float(p)
    if not (math.isfinite(pp) and math.isfinite(a) and math.isfinite(b)):
        return float("nan")
    if pp <= 0.0:
        return 0.0
    if pp >= 1.0:
        return 1.0

    lo = 0.0
    hi = 1.0

    # Conservative start: bisection only (no Newton) for determinism.
    for _ in range(120):
        mid = (lo + hi) / 2.0
        cmid = beta_cdf(mid, a, b)
        if not math.isfinite(cmid):
            # Degenerate numeric issue; split and continue.
            hi = mid
            continue
        if cmid < pp:
            lo = mid
        else:
            hi = mid
        if (hi - lo) <= tol:
            break

    return (lo + hi) / 2.0


def beta_credible_interval(a: float, b: float, q_lo: float, q_hi: float) -> Tuple[float, float]:
    lo = beta_ppf(q_lo, a, b)
    hi = beta_ppf(q_hi, a, b)
    return (lo, hi)

