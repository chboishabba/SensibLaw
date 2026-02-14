from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True, slots=True)
class LogisticMapFit:
    feature_names: Tuple[str, ...]  # includes "(intercept)" at index 0
    coef: Tuple[float, ...]         # MAP coefficients aligned to feature_names
    se: Tuple[float, ...]           # sqrt(diag(inv_hessian)) approximation
    converged: bool
    n_iter: int


def _sigmoid(z: float) -> float:
    # Stable sigmoid.
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fit_ridge_logistic_map(
    rows: Sequence[Tuple[int, Sequence[int]]],
    *,
    n_features: int,
    l2: float = 1.0,
    max_iter: int = 50,
    tol: float = 1e-8,
) -> Tuple[Tuple[float, ...], Tuple[float, ...], bool, int]:
    """
    Deterministic ridge-logistic MAP fit using Newton/IRLS on sparse binary features.

    `rows`: list of (y, active_feature_indices) where indices are in [0, n_features).
    This function *does not* emit predictions; it returns coefficients + an uncertainty proxy.
    """
    lam = float(l2)
    if not math.isfinite(lam) or lam <= 0:
        lam = 1.0
    p = int(n_features)
    if p <= 0:
        return ((), (), True, 0)

    beta = [0.0] * p
    converged = False

    # Build a deterministic feature->rows adjacency for sparse Hessian blocks.
    feat_rows: List[List[int]] = [[] for _ in range(p)]
    for i, (_, idxs) in enumerate(rows):
        for j in idxs:
            if 0 <= int(j) < p:
                feat_rows[int(j)].append(i)

    for it in range(1, max_iter + 1):
        # Gradient and Hessian (dense p x p) for simplicity; p is expected to be small in v0.1.
        g = [0.0] * p
        H = [[0.0] * p for _ in range(p)]

        # L2 prior contributes lam*beta to gradient and lam to diagonal of Hessian (excluding intercept handling
        # is caller responsibility; treat intercept as feature 0 with l2 too for determinism simplicity).
        for j in range(p):
            g[j] += lam * beta[j]
            H[j][j] += lam

        for i, (y, idxs) in enumerate(rows):
            z = 0.0
            for j in idxs:
                if 0 <= j < p:
                    z += beta[j]
            pi = _sigmoid(z)
            w = pi * (1.0 - pi)
            # Avoid exact zeros which can cause singular Hessian in separable data.
            if w < 1e-12:
                w = 1e-12
            r = (pi - float(y))

            # Gradient and Hessian updates for active indices only.
            for a in idxs:
                if not (0 <= a < p):
                    continue
                g[a] += r
                for b in idxs:
                    if not (0 <= b < p):
                        continue
                    H[a][b] += w

        # Solve H * step = g  (Newton step). Use naive Gaussian elimination for determinism.
        # step = inv(H) * g
        step = _solve_linear(H, g)
        if step is None:
            break

        max_step = 0.0
        for j in range(p):
            beta[j] -= step[j]
            max_step = max(max_step, abs(step[j]))
        if max_step < tol:
            converged = True
            break

    # SE approximation from diagonal of inv(H) at final iterate.
    inv_diag = _inv_diag_approx(rows, beta, p, lam)
    se = tuple(math.sqrt(max(0.0, v)) for v in inv_diag)
    return (tuple(beta), se, converged, it)


def _solve_linear(A: List[List[float]], b: List[float]) -> List[float] | None:
    n = len(b)
    # Copy for elimination.
    M = [row[:] for row in A]
    x = b[:]

    for k in range(n):
        # Pivot (deterministic: pick max abs in column).
        piv = k
        piv_val = abs(M[k][k])
        for i in range(k + 1, n):
            v = abs(M[i][k])
            if v > piv_val:
                piv = i
                piv_val = v
        if piv_val < 1e-18:
            return None
        if piv != k:
            M[k], M[piv] = M[piv], M[k]
            x[k], x[piv] = x[piv], x[k]

        dk = M[k][k]
        inv = 1.0 / dk
        for j in range(k, n):
            M[k][j] *= inv
        x[k] *= inv

        for i in range(n):
            if i == k:
                continue
            factor = M[i][k]
            if abs(factor) < 1e-18:
                continue
            for j in range(k, n):
                M[i][j] -= factor * M[k][j]
            x[i] -= factor * x[k]

    return x


def _inv_diag_approx(rows: Sequence[Tuple[int, Sequence[int]]], beta: Sequence[float], p: int, lam: float) -> List[float]:
    # Use a diagonal approximation to inv(H) for a cheap uncertainty proxy.
    diag = [lam] * p
    for y, idxs in rows:
        z = 0.0
        for j in idxs:
            if 0 <= j < p:
                z += beta[j]
        pi = _sigmoid(z)
        w = pi * (1.0 - pi)
        if w < 1e-12:
            w = 1e-12
        for j in idxs:
            if 0 <= j < p:
                diag[j] += w
    return [1.0 / d if d > 0 else float("inf") for d in diag]


def build_sparse_binary_design(
    y: Sequence[int],
    predicate_keys: Sequence[Sequence[str]],
    *,
    max_features: int = 2000,
) -> Tuple[Tuple[str, ...], List[Tuple[int, Tuple[int, ...]]]]:
    """
    Deterministically build a sparse design from per-row predicate key sets.
    Features are one-hot for predicate presence.
    Returns (feature_names, rows) where feature 0 is '(intercept)'.
    """
    vocab = sorted({str(k).strip() for ks in predicate_keys for k in (ks or []) if str(k).strip()})
    if len(vocab) > max_features:
        vocab = vocab[:max_features]
    feat_names = ("(intercept)",) + tuple(vocab)
    index = {name: i for i, name in enumerate(feat_names)}

    rows: List[Tuple[int, Tuple[int, ...]]] = []
    for yi, ks in zip(y, predicate_keys):
        active = {index["(intercept)"]}
        for k in ks or []:
            kk = str(k).strip()
            if not kk:
                continue
            j = index.get(kk)
            if j is not None:
                active.add(int(j))
        rows.append((1 if int(yi) != 0 else 0, tuple(sorted(active))))
    return feat_names, rows

