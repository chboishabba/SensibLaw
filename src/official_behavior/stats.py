from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .model import AlignmentLabel, AlignmentObservation, normalize_observations

# Reuse deterministic conjugate helpers (no sampling). This is intentionally a
# shared math primitive, not a domain merge.
from ..judicial_behavior.bayes import beta_binomial_posterior, beta_credible_interval, empirical_bayes_prior


class IndividualStatsDisabledError(ValueError):
    pass


class SliceDeclarationError(ValueError):
    pass


_INTERPRETATION_GUARD = (
    "Observed rates/posteriors are empirical summaries of the selected corpus and slice definition; "
    "they do not imply causal tendency, personal disposition, or counterfactual behavior under different predicates or constraints."
)


def _group_key(obs: AlignmentObservation, group_by: Sequence[str]) -> Tuple[str, ...]:
    key: List[str] = []
    for f in group_by:
        if f == "jurisdiction_id":
            key.append(obs.jurisdiction_id)
        elif f == "institution_id":
            key.append(obs.institution_id)
        elif f == "institution_kind":
            key.append(obs.institution_kind)
        elif f == "policy_area_id":
            key.append(obs.policy_area_id or "")
        elif f == "action_year":
            if obs.action_date and len(obs.action_date) >= 4:
                key.append(obs.action_date[:4])
            else:
                key.append("")
        elif f == "official_id":
            key.append(obs.official_id or "")
        elif f == "party_id":
            key.append(obs.party_id or "")
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


def _corpus_time_bounds(rows: Sequence[AlignmentObservation]) -> Tuple[str | None, str | None]:
    ds = [str(r.action_date) for r in rows if r.action_date]
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


def aggregate_alignment_counts(
    observations: Iterable[AlignmentObservation],
    *,
    group_by: Sequence[str] = ("jurisdiction_id", "institution_id", "institution_kind"),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Deterministic descriptive aggregation of observed alignment labels.

    Guardrail: grouping by individual identifiers (e.g. official_id) is disabled
    by default per `panopticon_refusal.md`.
    """
    gb = tuple(str(x) for x in (group_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "institution_id", "institution_kind")

    if ("official_id" in gb) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    rows = normalize_observations(observations)
    counts: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: Dict[Tuple[str, ...], int] = defaultdict(int)

    for obs in rows:
        k = _group_key(obs, gb)
        lab = AlignmentLabel.canonicalize(obs.alignment)
        counts[k][lab] += 1
        totals[k] += 1

    groups_out: List[Dict[str, Any]] = []
    for k in sorted(totals.keys()):
        total = int(totals[k])
        c = counts.get(k, {})
        labels = {}
        for lab in [
            AlignmentLabel.ALIGNED,
            AlignmentLabel.MISALIGNED,
            AlignmentLabel.AMBIGUOUS,
            AlignmentLabel.NOT_APPLICABLE,
            AlignmentLabel.UNKNOWN,
        ]:
            if int(c.get(lab, 0)) > 0:
                labels[lab] = int(c.get(lab, 0))
        groups_out.append({"group_by": list(gb), "group_key": list(k), "total": total, "labels": labels})

    time_min, time_max = _corpus_time_bounds(rows)
    return {
        "contract": "official_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "groups": groups_out,
    }


def aggregate_alignment_beta_binomial(
    observations: Iterable[AlignmentObservation],
    *,
    group_by: Sequence[str] = ("jurisdiction_id", "institution_id", "institution_kind"),
    baseline_by: Sequence[str] = ("jurisdiction_id", "institution_id", "institution_kind"),
    kappa: float = 40.0,
    quantiles: Tuple[float, float] = (0.10, 0.90),
    allow_individuals: bool = False,
    slice: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Descriptive Beta-Binomial posterior estimation for misalignment rate theta.

    The target is AlignmentLabel.MISALIGNED. This estimates a posterior over
    theta for each slice (not a predictive probability for any particular action).
    """
    gb = tuple(str(x) for x in (group_by or ()))
    bb = tuple(str(x) for x in (baseline_by or ()))
    if not gb:
        gb = ("jurisdiction_id", "institution_id", "institution_kind")
    if not bb:
        bb = ("jurisdiction_id", "institution_id", "institution_kind")

    if ("official_id" in gb) and not allow_individuals:
        raise IndividualStatsDisabledError("Individual-level grouping is disabled by default (allow_individuals=false).")

    slice_decl = _require_slice_decl(slice, group_by=gb)

    rows = normalize_observations(observations)
    tgt = AlignmentLabel.MISALIGNED

    base_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    base_n: Dict[Tuple[str, ...], int] = defaultdict(int)
    for obs in rows:
        bk = _group_key(obs, bb)
        base_n[bk] += 1
        if AlignmentLabel.canonicalize(obs.alignment) == tgt:
            base_y[bk] += 1

    slice_y: Dict[Tuple[str, ...], int] = defaultdict(int)
    slice_n: Dict[Tuple[str, ...], int] = defaultdict(int)
    slice_to_baseline: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    for obs in rows:
        sk = _group_key(obs, gb)
        slice_n[sk] += 1
        if AlignmentLabel.canonicalize(obs.alignment) == tgt:
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
                "target_label": tgt,
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
        "contract": "official_decision_behavior_v0_1",
        "mode": "descriptive_only",
        "method": "beta_binomial",
        "interpretation_guard": _INTERPRETATION_GUARD,
        "allow_individuals": bool(allow_individuals),
        "slice": slice_decl,
        "corpus": {"n_total": int(len(rows)), "time_min": time_min, "time_max": time_max},
        "group_by": list(gb),
        "baseline_by": list(bb),
        "groups": groups,
    }

