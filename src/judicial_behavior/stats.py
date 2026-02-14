from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .model import CaseObservation, OutcomeLabel, normalize_observations
from .bayes import beta_binomial_posterior, empirical_bayes_prior, beta_credible_interval
from .gamma import empirical_bayes_gamma_prior, gamma_credible_interval, gamma_poisson_posterior
from .logistic import build_sparse_binary_design, fit_ridge_logistic_map
from .tail import lognormal_fit, lognormal_tail_prob


class IndividualStatsDisabledError(ValueError):
    pass


class SliceDeclarationError(ValueError):
    pass


_INTERPRETATION_GUARD = (
    "Observed rates/posteriors are empirical summaries of the selected corpus and slice definition; "
    "they do not imply causal tendency, personal disposition, or counterfactual behavior under different predicates."
)


def _group_key(obs: CaseObservation, group_by: Sequence[str]) -> Tuple[str, ...]:
    key: List[str] = []
    for f in group_by:
        if f == "jurisdiction_id":
            key.append(obs.jurisdiction_id)
        elif f == "court_id":
            key.append(obs.court_id)
        elif f == "court_level":
            key.append(obs.court_level)
        elif f == "wrong_type_id":
            key.append(obs.wrong_type_id or "")
        elif f == "decision_year":
            if obs.decision_date and len(obs.decision_date) >= 4:
                key.append(obs.decision_date[:4])
            else:
                key.append("")
        elif f == "judge_id":
            key.append(obs.judge_id or "")
        else:
            key.append("")
    return tuple(key)


def _normalize_slice_decl(slice_decl: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure deterministic key ordering + stable list content ordering.
    def norm(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: norm(x[k]) for k in sorted(x.keys(), key=lambda s: str(s))}
        if isinstance(x, (list, tuple)):
            items = [norm(v) for v in x]
            if all(isinstance(v, (str, int, float, bool, type(None))) for v in items):
                return sorted(items, key=lambda v: (str(type(v)), str(v)))
            return items
        return x

    return norm(dict(slice_decl or {}))


def _corpus_time_bounds(rows: Sequence[CaseObservation]) -> Tuple[str | None, str | None]:
    ds = [str(r.decision_date) for r in rows if r.decision_date]
    if not ds:
        return (None, None)
    ds_sorted = sorted(ds)
    return (ds_sorted[0], ds_sorted[-1])


def _require_slice_decl(slice_decl: Dict[str, Any] | None, *, group_by: Sequence[str]) -> Dict[str, Any]:
    if slice_decl is None:
        raise SliceDeclarationError("slice declaration is required (no silent defaults)")
    if not isinstance(slice_decl, dict):
        raise SliceDeclarationError("slice must be a dict")
    if "filters" not in slice_decl:
        raise SliceDeclarationError("slice.filters is required (may be empty)")
    if "time_bounds_declared" not in slice_decl:
        raise SliceDeclarationError("slice.time_bounds_declared is required (start/end may be null)")
    if "group_by" not in slice_decl:
        raise SliceDeclarationError("slice.group_by is required and must match group_by")
    declared_gb = tuple(str(x) for x in (slice_decl.get("group_by") or ()))
    gb = tuple(str(x) for x in (group_by or ()))
    if declared_gb != gb:
        raise SliceDeclarationError(f"slice.group_by mismatch: declared={list(declared_gb)} actual={list(gb)}")
    return _normalize_slice_decl(slice_decl)


def aggregate_outcomes(
    observations: Iterable[CaseObservation],
    *,
    group_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Deterministic descriptive aggregation of observed outcomes.

    Returns a JSON-friendly dict with stable key ordering.

    Guardrail: grouping by individual identifiers (e.g. judge_id) is disabled
    by default per `panopticon_refusal.md`.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "court_id", "court_level")

    if (("judge_id" in gb) or ("panel_id" in gb) or ("panel_ids" in gb)) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    rows = normalize_observations(observations)
    counts: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: Dict[Tuple[str, ...], int] = defaultdict(int)

    for obs in rows:
        k = _group_key(obs, gb)
        out = OutcomeLabel.canonicalize(obs.outcome)
        counts[k][out] += 1
        totals[k] += 1

    # Stable rendering: keys sorted lexicographically.
    groups_out: List[Dict[str, Any]] = []
    for k in sorted(totals.keys()):
        total = int(totals[k])
        c = counts.get(k, {})
        # Stable outcome ordering.
        outcomes = {}
        for lab in [
            OutcomeLabel.PLAINTIFF,
            OutcomeLabel.DEFENDANT,
            OutcomeLabel.MIXED,
            OutcomeLabel.REMITTED,
            OutcomeLabel.PROCEDURAL,
            OutcomeLabel.UNKNOWN,
        ]:
            if int(c.get(lab, 0)) > 0:
                outcomes[lab] = int(c.get(lab, 0))

        groups_out.append(
            {
                "group_by": list(gb),
                "group_key": list(k),
                "total": total,
                "outcomes": outcomes,
            }
        )

    time_min, time_max = _corpus_time_bounds(rows)
    return {
        "contract": "judicial_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "groups": groups_out,
    }


def aggregate_beta_binomial(
    observations: Iterable[CaseObservation],
    *,
    target_outcome: str = OutcomeLabel.PLAINTIFF,
    group_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    baseline_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    kappa: float = 40.0,
    quantiles: Tuple[float, float] = (0.10, 0.90),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Descriptive Beta-Binomial posterior estimation for a binary target.

    This estimates an underlying rate parameter theta for each slice. It must
    not be presented as "probability of ruling"; it is a posterior over theta.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    bb = tuple(str(x) for x in (baseline_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "court_id", "court_level")
    if not bb:
        bb = ("jurisdiction_id", "court_id", "court_level")

    if (("judge_id" in gb) or ("panel_id" in gb) or ("panel_ids" in gb)) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    rows = normalize_observations(observations)
    tgt = OutcomeLabel.canonicalize(target_outcome)

    # Baseline pool counts (y,n) keyed by baseline_by.
    base_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    base_n: Dict[Tuple[str, ...], int] = defaultdict(int)
    for obs in rows:
        bk = _group_key(obs, bb)
        base_n[bk] += 1
        if OutcomeLabel.canonicalize(obs.outcome) == tgt:
            base_y[bk] += 1

    # Slice counts (y,n) keyed by group_by.
    slice_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    slice_n: Dict[Tuple[str, ...], int] = defaultdict(int)
    # Also record mapping slice->baseline deterministically by projecting the slice key
    # to the baseline key via the original observation fields.
    slice_to_baseline: Dict[Tuple[str, ...], Tuple[str, ...]] = {}

    for obs in rows:
        sk = _group_key(obs, gb)
        slice_n[sk] += 1
        if OutcomeLabel.canonicalize(obs.outcome) == tgt:
            slice_y[sk] += 1
        if sk not in slice_to_baseline:
            slice_to_baseline[sk] = _group_key(obs, bb)

    q_lo, q_hi = float(quantiles[0]), float(quantiles[1])
    if not (0.0 < q_lo < q_hi < 1.0):
        q_lo, q_hi = 0.10, 0.90

    groups: List[Dict[str, Any]] = []
    for sk in sorted(slice_n.keys()):
        n = int(slice_n[sk])
        y = int(slice_y.get(sk, 0))
        bk = slice_to_baseline.get(sk, ("",) * len(bb))
        bn = int(base_n.get(bk, 0))
        by = int(base_y.get(bk, 0))
        mu = (float(by) / float(bn)) if bn > 0 else 0.5
        alpha0, beta0 = empirical_bayes_prior(mu, float(kappa))
        post = beta_binomial_posterior(y, n, alpha0, beta0)
        ci_lo, ci_hi = beta_credible_interval(post.alpha, post.beta, q_lo, q_hi)

        groups.append(
            {
                "group_by": list(gb),
                "group_key": list(sk),
                "baseline_by": list(bb),
                "baseline_key": list(bk),
                "target_outcome": tgt,
                "data": {"n": n, "y": y},
                "prior": {"mu": mu, "kappa": float(kappa), "alpha0": post.alpha0, "beta0": post.beta0, "baseline_n": bn},
                "posterior": {
                    "alpha": post.alpha,
                    "beta": post.beta,
                    "theta_mean": post.mean,
                    "q_lo": q_lo,
                    "q_hi": q_hi,
                    "theta_q_lo": float(ci_lo),
                    "theta_q_hi": float(ci_hi),
                },
            }
        )

    time_min, time_max = _corpus_time_bounds(rows)
    return {
        "contract": "judicial_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "method": "beta_binomial",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "baseline_by": list(bb),
        "target_outcome": tgt,
        "kappa": float(kappa),
        "quantiles": [q_lo, q_hi],
        "groups": groups,
    }


def aggregate_gamma_poisson(
    observations: Iterable[CaseObservation],
    *,
    event_key: str,
    group_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    baseline_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    kappa: float = 40.0,
    quantiles: Tuple[float, float] = (0.10, 0.90),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Descriptive Gamma-Poisson posterior for a rare event rate per exposure unit.

    Exposure is the number of cases in the slice. A case is counted as an event
    if `event_key` appears in `predicate_keys`.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    bb = tuple(str(x) for x in (baseline_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "court_id", "court_level")
    if not bb:
        bb = ("jurisdiction_id", "court_id", "court_level")

    if (("judge_id" in gb) or ("panel_id" in gb) or ("panel_ids" in gb)) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    ek = str(event_key or "").strip()
    if not ek:
        return {
            "contract": "judicial_decision_behavior_v0_1",
            "mode": "descriptive_only",
            "method": "gamma_poisson",
            "interpretation_guard": _INTERPRETATION_GUARD,
            "slice": slice_decl,
            "corpus": {"n_total": 0, "time_min": None, "time_max": None},
            "error": "event_key is required",
            "groups": [],
        }

    rows = normalize_observations(observations)

    base_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    base_e: Dict[Tuple[str, ...], int] = defaultdict(int)
    for obs in rows:
        bk = _group_key(obs, bb)
        base_e[bk] += 1
        if ek in set(obs.predicate_keys or ()):
            base_y[bk] += 1

    slice_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    slice_e: Dict[Tuple[str, ...], int] = defaultdict(int)
    slice_to_baseline: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    for obs in rows:
        sk = _group_key(obs, gb)
        slice_e[sk] += 1
        if ek in set(obs.predicate_keys or ()):
            slice_y[sk] += 1
        if sk not in slice_to_baseline:
            slice_to_baseline[sk] = _group_key(obs, bb)

    q_lo, q_hi = float(quantiles[0]), float(quantiles[1])
    if not (0.0 < q_lo < q_hi < 1.0):
        q_lo, q_hi = 0.10, 0.90

    groups: List[Dict[str, Any]] = []
    for sk in sorted(slice_e.keys()):
        E = int(slice_e[sk])
        y = int(slice_y.get(sk, 0))
        bk = slice_to_baseline.get(sk, ("",) * len(bb))
        bE = int(base_e.get(bk, 0))
        by = int(base_y.get(bk, 0))
        mu = (float(by) / float(bE)) if bE > 0 else 0.0
        alpha0, beta0 = empirical_bayes_gamma_prior(mu, float(kappa))
        post = gamma_poisson_posterior(y, float(E), alpha0, beta0)
        ci_lo, ci_hi = gamma_credible_interval(post.alpha, post.beta, q_lo, q_hi)

        groups.append(
            {
                "group_by": list(gb),
                "group_key": list(sk),
                "baseline_by": list(bb),
                "baseline_key": list(bk),
                "event_key": ek,
                "data": {"E": E, "y": y},
                "prior": {"mu": mu, "kappa": float(kappa), "alpha0": post.alpha0, "beta0": post.beta0, "baseline_E": bE},
                "posterior": {
                    "alpha": post.alpha,
                    "beta": post.beta,
                    "lambda_mean": post.mean,
                    "q_lo": q_lo,
                    "q_hi": q_hi,
                    "lambda_q_lo": float(ci_lo),
                    "lambda_q_hi": float(ci_hi),
                },
            }
        )

    time_min, time_max = _corpus_time_bounds(rows)
    return {
        "contract": "judicial_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "method": "gamma_poisson",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "baseline_by": list(bb),
        "event_key": ek,
        "kappa": float(kappa),
        "quantiles": [q_lo, q_hi],
        "groups": groups,
    }


def aggregate_ridge_logistic_map(
    observations: Iterable[CaseObservation],
    *,
    target_kind: str = "outcome",  # "outcome" | "predicate"
    target_outcome: str = OutcomeLabel.PLAINTIFF,
    event_key: str = "",
    group_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    l2: float = 1.0,
    max_features: int = 200,
    max_iter: int = 50,
    tol: float = 1e-8,
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Descriptive ridge-logistic MAP association fit over predicate_keys.

    This is not a prediction surface. Outputs are coefficients + uncertainty proxy only.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "court_id", "court_level")

    if (("judge_id" in gb) or ("panel_id" in gb) or ("panel_ids" in gb)) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    rows = normalize_observations(observations)
    kind = str(target_kind or "").strip().lower()
    if kind not in {"outcome", "predicate"}:
        kind = "outcome"

    tgt_out = OutcomeLabel.canonicalize(target_outcome)
    ek = str(event_key or "").strip()

    # Group rows deterministically.
    by_group: Dict[Tuple[str, ...], List[CaseObservation]] = defaultdict(list)
    for obs in rows:
        by_group[_group_key(obs, gb)].append(obs)

    groups: List[Dict[str, Any]] = []
    for gk in sorted(by_group.keys()):
        g_rows = by_group[gk]
        # Build y and predicate matrices.
        if kind == "predicate":
            if not ek:
                y = [0 for _ in g_rows]
            else:
                y = [1 if ek in set(r.predicate_keys or ()) else 0 for r in g_rows]
        else:
            y = [1 if OutcomeLabel.canonicalize(r.outcome) == tgt_out else 0 for r in g_rows]

        pred = [tuple(r.predicate_keys or ()) for r in g_rows]
        feat_names, sparse_rows = build_sparse_binary_design(y, pred, max_features=int(max_features))
        beta, se, converged, n_iter = fit_ridge_logistic_map(
            sparse_rows,
            n_features=len(feat_names),
            l2=float(l2),
            max_iter=int(max_iter),
            tol=float(tol),
        )

        groups.append(
            {
                "group_by": list(gb),
                "group_key": list(gk),
                "target": {"kind": kind, "outcome": tgt_out if kind == "outcome" else "", "event_key": ek if kind == "predicate" else ""},
                "data": {"n": int(len(g_rows)), "y_sum": int(sum(y))},
                "fit": {
                    "feature_names": list(feat_names),
                    "coef": list(beta),
                    "se": list(se),
                    "converged": bool(converged),
                    "n_iter": int(n_iter),
                    "l2": float(l2),
                    "max_features": int(max_features),
                },
            }
        )

    time_min, time_max = _corpus_time_bounds(rows)
    return {
        "contract": "judicial_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "method": "ridge_logistic_map",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "groups": groups,
    }


def aggregate_lognormal_tail(
    observations: Sequence[Tuple[CaseObservation, float]],
    *,
    value_label: str = "value",
    threshold: float | None = None,
    group_by: Sequence[str] = ("jurisdiction_id", "court_id", "court_level"),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Deterministic lognormal fit over positive continuous values.

    Input is a list of (CaseObservation, value) pairs so time bounds/grouping are
    computed from the same observation metadata used elsewhere.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "court_id", "court_level")

    if (("judge_id" in gb) or ("panel_id" in gb) or ("panel_ids" in gb)) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    pairs: List[Tuple[CaseObservation, float]] = []
    for obs, v in observations or []:
        if not isinstance(obs, CaseObservation):
            continue
        try:
            vv = float(v)
        except Exception:
            continue
        pairs.append((obs, vv))

    # Normalize observation metadata deterministically.
    norm_pairs: List[Tuple[CaseObservation, float]] = []
    for obs, v in pairs:
        n = obs.normalized()
        if n.case_id and n.jurisdiction_id and n.court_id and n.court_level:
            norm_pairs.append((n, float(v)))
    norm_pairs.sort(key=lambda x: (x[0].jurisdiction_id, x[0].court_id, x[0].court_level, x[0].decision_date or "", x[0].case_id, x[1]))

    # Group by group_by keys.
    by_group: Dict[Tuple[str, ...], List[float]] = defaultdict(list)
    by_group_meta: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(lambda: {"n_total": 0, "n_nonpositive": 0})

    for obs, v in norm_pairs:
        gk = _group_key(obs, gb)
        by_group_meta[gk]["n_total"] += 1
        if v > 0.0:
            by_group[gk].append(float(v))
        else:
            by_group_meta[gk]["n_nonpositive"] += 1

    groups: List[Dict[str, Any]] = []
    for gk in sorted(by_group_meta.keys()):
        xs = by_group.get(gk, [])
        fit = lognormal_fit(xs)
        tail_p = None
        if threshold is not None and fit is not None:
            tail_p = float(lognormal_tail_prob(fit.mu, fit.sigma, float(threshold)))
        groups.append(
            {
                "group_by": list(gb),
                "group_key": list(gk),
                "value_label": str(value_label or "value"),
                "data": {
                    "n_total": int(by_group_meta[gk]["n_total"]),
                    "n_used": int(len(xs)),
                    "n_nonpositive": int(by_group_meta[gk]["n_nonpositive"]),
                },
                "fit": None
                if fit is None
                else {
                    "mu": float(fit.mu),
                    "sigma": float(fit.sigma),
                },
                "tail": None if tail_p is None else {"threshold": float(threshold), "p_gt_threshold": float(tail_p)},
            }
        )

    time_min, time_max = _corpus_time_bounds([o for (o, _) in norm_pairs])
    return {
        "contract": "judicial_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "method": "lognormal_tail",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(norm_pairs)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "groups": groups,
    }
