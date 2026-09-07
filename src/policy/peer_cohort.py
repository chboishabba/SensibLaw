"""Coverage-qualified peer-cohort residual evaluation.

This module converts a governed ``DomainInvariantSnapshot`` plus caller-supplied
bounded graph/query coverage into one ``peer_cohort`` residual row suitable for
``build_pressure_assessment``.  It is diagnostic only: it does not promote a
candidate, mutate an invariant, infer an external identity, or edit a graph.

The safety contract mirrors DASHI's ``ExternalContextSafetyBoundary`` and
``GovernedResidualOntologyLearning``:

- incomplete/uninspected/invalid coverage keeps the residual unresolved;
- an empty trusted cohort keeps the residual unresolved;
- only already admitted/reviewed invariant members may provide peer evidence;
- exact peer agreement is evidence about one residual coordinate, not migration
  safety or property equivalence.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .domain_invariants import DOMAIN_INVARIANT_SNAPSHOT_SCHEMA_VERSION
from .domain_pressure import COVERAGE_STATES

PEER_COHORT_RESIDUAL_KIND = "peer_cohort"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _candidate_feature_rows(values: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        feature = _text(value.get("feature"))
        observed_value = _text(value.get("value"))
        condition = _text(value.get("condition"))
        if not feature or not observed_value:
            raise ValueError("peer cohort candidate features require feature and value")
        row = {"feature": feature, "value": observed_value}
        if condition:
            row["condition"] = condition
        rows.append(row)
    rows.sort(key=lambda row: (row["feature"], row.get("condition", ""), row["value"]))
    return rows


def _empirical_index(snapshot: Mapping[str, Any]) -> dict[tuple[str, str], set[str]]:
    index: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in snapshot.get("empirical_features") or ():
        if not isinstance(row, Mapping):
            continue
        feature = _text(row.get("feature"))
        value = _text(row.get("value"))
        condition = _text(row.get("condition"))
        if feature and value:
            index[(feature, condition)].add(value)
    return dict(index)


def build_peer_cohort_residual(
    *,
    candidate_ref: str,
    invariant_snapshot: Mapping[str, Any],
    candidate_features: Sequence[Mapping[str, Any]],
    coverage_state: str,
    graph_revision_ref: str,
    coverage_policy_ref: str,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate peer evidence without creating any promotion/edit authority.

    ``coverage_state`` uses the same vocabulary as ``DomainPressureAssessment``.
    ``observed`` means that the caller's declared bounded policy was covered; it
    does not mean the whole external graph is globally complete.
    """

    if _text(invariant_snapshot.get("schema_version")) != DOMAIN_INVARIANT_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("peer cohort evaluation requires a domain invariant snapshot")

    normalized_candidate = _text(candidate_ref)
    normalized_coverage = _text(coverage_state) or "uninspected"
    revision_ref = _text(graph_revision_ref)
    policy_ref = _text(coverage_policy_ref)
    if not normalized_candidate or not revision_ref or not policy_ref:
        raise ValueError(
            "peer cohort evaluation requires candidate_ref, graph_revision_ref, and coverage_policy_ref"
        )
    if normalized_coverage not in COVERAGE_STATES:
        raise ValueError(f"unsupported peer cohort coverage state: {normalized_coverage}")

    trusted_members = _strings(invariant_snapshot.get("trusted_member_refs") or ())
    empirical = _empirical_index(invariant_snapshot)
    features = _candidate_feature_rows(candidate_features)

    matched: list[dict[str, Any]] = []
    contradicted: list[dict[str, Any]] = []
    unmodelled: list[dict[str, Any]] = []

    if normalized_coverage == "observed" and trusted_members:
        for feature in features:
            key = (feature["feature"], feature.get("condition", ""))
            peer_values = sorted(empirical.get(key, set()))
            if not peer_values:
                unmodelled.append({**feature, "peer_values": []})
            elif feature["value"] in peer_values:
                matched.append({**feature, "peer_values": peer_values})
            else:
                contradicted.append({**feature, "peer_values": peer_values})

    if normalized_coverage != "observed" or not trusted_members:
        state = "unresolved"
        summary = (
            "peer evidence remains unresolved until declared bounded coverage is observed "
            "and independently reviewed conforming members exist"
        )
    elif contradicted:
        state = "contradictory"
        summary = "candidate feature values contradict the admitted peer-cohort empirical surface"
    elif not features:
        state = "unresolved"
        summary = "peer comparison requires candidate feature contributions"
    elif unmodelled:
        state = "partial"
        summary = "peer cohort covers some candidate features but leaves others unmodelled"
    else:
        state = "exact"
        summary = "all supplied candidate features are represented in the admitted peer-cohort empirical surface"

    snapshot_ref = _text(invariant_snapshot.get("snapshot_id"))
    return {
        "residual_kind": PEER_COHORT_RESIDUAL_KIND,
        "state": state,
        "expected": {
            "domain_invariant_ref": snapshot_ref,
            "trusted_member_count": len(trusted_members),
            "empirical_feature_count": sum(len(values) for values in empirical.values()),
            "coverage_policy_ref": policy_ref,
        },
        "observed": {
            "candidate_ref": normalized_candidate,
            "graph_revision_ref": revision_ref,
            "trusted_member_refs": trusted_members,
            "matched_features": matched,
            "contradicted_features": contradicted,
            "unmodelled_features": unmodelled,
        },
        "coverage_state": normalized_coverage,
        "evidence_refs": _strings(evidence_refs),
        "summary": summary,
    }


__all__ = ["PEER_COHORT_RESIDUAL_KIND", "build_peer_cohort_residual"]
