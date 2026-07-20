"""Provider-neutral external graph view, attachment, and pressure carriers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION = "sl.external_graph_bridge.v0_1"
GRAPH_VIEW_STATES = frozenset({"incomplete", "complete"})
BRIDGE_SUBJECT_KINDS = frozenset({"entity", "event", "claim", "relation", "concept"})
ATTACHMENT_KINDS = frozenset(
    {
        "same_entity",
        "same_event",
        "broader_concept",
        "narrower_concept",
        "related_concept",
        "structural_analogue",
        "authority_reference",
    }
)
BRIDGE_CANDIDATE_STATES = frozenset(
    {"proposed", "review_required", "accepted", "rejected", "conflicted", "stale"}
)
BRIDGE_DECISIONS = frozenset({"accepted", "rejected", "conflicted", "stale"})
PRESSURE_OUTCOMES = frozenset({"compatible", "warning", "conflict", "abstain"})
EXTERNAL_GRAPH_CONTEXT_SCHEMA_VERSION = "sl.external_graph_context.v0_1"
PROPERTY_EXPECTATION_STRENGTHS = frozenset(
    {
        "required_by_rule",
        "strong_expected",
        "common",
        "optional",
        "conditional",
        "discouraged",
    }
)
PROPERTY_OBSERVATION_STATES = frozenset(
    {"present", "observed_absent", "unknown", "not_applicable"}
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Sequence[Mapping[str, Any]] | Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _require_member(value: Any, *, field: str, allowed: frozenset[str]) -> str:
    normalized = _text(value)
    if normalized not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field} must be one of: {allowed_values}")
    return normalized


def build_graph_view(
    *,
    graph_view_id: str,
    artifact_id: str,
    artifact_revision: str,
    coverage_state: str,
    selected_sections: Sequence[str] = (),
    selected_chunks: Sequence[Mapping[str, Any]] = (),
    selected_bytes: int = 0,
    coverage_policy: Mapping[str, Any] | None = None,
    unresolved_coverage: Sequence[Mapping[str, Any]] = (),
    completeness_receipt_ref: str | None = None,
    source: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build revision-bound graph coverage without assigning semantic authority."""

    state = _require_member(
        coverage_state, field="coverage_state", allowed=GRAPH_VIEW_STATES
    )
    policy = deepcopy(dict(coverage_policy or {}))
    unresolved = _mapping_rows(unresolved_coverage)
    receipt_ref = _text(completeness_receipt_ref)
    if selected_bytes < 0:
        raise ValueError("selected_bytes must be non-negative")
    if state == "complete" and (not policy or unresolved or not receipt_ref):
        raise ValueError(
            "complete graph views require coverage_policy, no unresolved_coverage, and completeness_receipt_ref"
        )
    if state == "incomplete" and receipt_ref:
        raise ValueError("incomplete graph views cannot carry completeness_receipt_ref")
    payload = {
        "schema_version": EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION,
        "graph_view_id": _text(graph_view_id),
        "artifact_id": _text(artifact_id),
        "artifact_revision": _text(artifact_revision),
        "coverage_state": state,
        "selected_sections": [
            _text(section) for section in selected_sections if _text(section)
        ],
        "selected_chunks": _mapping_rows(selected_chunks),
        "selected_bytes": selected_bytes,
        "coverage_policy": policy,
        "unresolved_coverage": unresolved,
        "source": deepcopy(dict(source or {})),
        "diagnostics": deepcopy(dict(diagnostics or {})),
        "candidate_only": state == "incomplete",
        "complete_closure": state == "complete",
        "truth_authority": False,
        "support_authority": False,
        "admissibility_authority": False,
        "promotion_authority": False,
    }
    if receipt_ref:
        payload["completeness_receipt_ref"] = receipt_ref
    return payload


def normalize_graph_view(graph_view: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a supplied graph view before it enters a generic context."""

    if not isinstance(graph_view, Mapping):
        raise ValueError("graph_view must be a mapping")
    return build_graph_view(
        graph_view_id=_text(graph_view.get("graph_view_id")),
        artifact_id=_text(graph_view.get("artifact_id")),
        artifact_revision=_text(graph_view.get("artifact_revision")),
        coverage_state=_text(graph_view.get("coverage_state")) or "incomplete",
        selected_sections=graph_view.get("selected_sections", ()),
        selected_chunks=graph_view.get("selected_chunks", ()),
        selected_bytes=int(graph_view.get("selected_bytes") or 0),
        coverage_policy=graph_view.get("coverage_policy")
        if isinstance(graph_view.get("coverage_policy"), Mapping)
        else None,
        unresolved_coverage=graph_view.get("unresolved_coverage", ()),
        completeness_receipt_ref=_text(graph_view.get("completeness_receipt_ref"))
        or None,
        source=graph_view.get("source")
        if isinstance(graph_view.get("source"), Mapping)
        else None,
        diagnostics=graph_view.get("diagnostics")
        if isinstance(graph_view.get("diagnostics"), Mapping)
        else None,
    )


def build_graph_view_from_transport(
    transport_view: Mapping[str, Any],
    *,
    graph_view_id: str,
    coverage_policy: Mapping[str, Any] | None = None,
    unresolved_coverage: Sequence[Mapping[str, Any]] = (),
    completeness_receipt_ref: str | None = None,
) -> dict[str, Any]:
    """Adapt a normalized ITIR bounded transport view into the generic carrier."""

    view = (
        transport_view.get("graph_view")
        if isinstance(transport_view.get("graph_view"), Mapping)
        else transport_view
    )
    identity = view.get("artifact_identity")
    if not isinstance(identity, Mapping):
        raise ValueError("transport_view.artifact_identity is required")
    selected_shards = _mapping_rows(view.get("selected_shards"))
    selected_bytes = int(
        view.get("selected_bytes")
        or sum(int(row.get("sizeBytes") or 0) for row in selected_shards)
    )
    transport_completeness = (
        _text(view.get("coverage_state"))
        or _text(view.get("completeness"))
        or "partial"
    )
    coverage_state = (
        "complete" if transport_completeness == "complete" else "incomplete"
    )
    declared_unresolved = view.get("unresolved_coverage")
    unresolved = (
        _mapping_rows(unresolved_coverage)
        if unresolved_coverage
        else [deepcopy(dict(declared_unresolved))]
        if isinstance(declared_unresolved, Mapping)
        else []
    )
    return build_graph_view(
        graph_view_id=graph_view_id,
        artifact_id=_text(identity.get("artifactId")),
        artifact_revision=_text(identity.get("artifactRevision")),
        coverage_state=coverage_state,
        selected_sections=view.get("selected_sections", ()),
        selected_chunks=selected_shards,
        selected_bytes=selected_bytes,
        coverage_policy=coverage_policy,
        unresolved_coverage=unresolved,
        completeness_receipt_ref=completeness_receipt_ref,
        source={
            "transport_contract_version": _text(identity.get("contractVersion")),
            "artifact_class": _text(identity.get("artifactClass")),
            "selectors": [
                _text(value) for value in view.get("selectors", ()) if _text(value)
            ],
            "manifest_source": deepcopy(
                dict(transport_view.get("manifest_source") or {})
            ),
        },
        diagnostics={
            "transport_completeness": transport_completeness,
            "subset_of_artifact": bool(view.get("subset_of_artifact", True)),
        },
    )


def build_external_bridge_candidate(
    *,
    bridge_candidate_id: str,
    subject_ref: str,
    subject_kind: str,
    bridge_namespace: str,
    external_ref: str,
    attachment_kind: str,
    graph_view_ref: str,
    basis: Sequence[Mapping[str, Any]] = (),
    external_revision_ref: str | None = None,
    confidence: float | None = None,
    candidate_status: str = "proposed",
    residuals: Sequence[Mapping[str, Any]] = (),
    adapter_id: str | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Propose an external attachment without replacing the local target."""

    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    payload = {
        "bridge_candidate_id": _text(bridge_candidate_id),
        "subject_ref": _text(subject_ref),
        "subject_kind": _require_member(
            subject_kind, field="subject_kind", allowed=BRIDGE_SUBJECT_KINDS
        ),
        "bridge_namespace": _text(bridge_namespace),
        "external_ref": _text(external_ref),
        "attachment_kind": _require_member(
            attachment_kind, field="attachment_kind", allowed=ATTACHMENT_KINDS
        ),
        "graph_view_ref": _text(graph_view_ref),
        "basis": _mapping_rows(basis),
        "candidate_status": _require_member(
            candidate_status, field="candidate_status", allowed=BRIDGE_CANDIDATE_STATES
        ),
        "residuals": _mapping_rows(residuals),
        "identity_authority": False,
        "role_authority": False,
        "legal_authority": False,
        "promotion_authority": False,
    }
    if _text(external_revision_ref):
        payload["external_revision_ref"] = _text(external_revision_ref)
    if confidence is not None:
        payload["confidence"] = confidence
    if _text(adapter_id):
        payload["adapter_id"] = _text(adapter_id)
    if _text(profile_id):
        payload["profile_id"] = _text(profile_id)
    return payload


def build_external_bridge_decision(
    *,
    bridge_decision_id: str,
    bridge_candidate_ref: str,
    decision: str,
    review_basis: Sequence[Mapping[str, Any]] = (),
    reviewer_ref: str | None = None,
    residuals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "bridge_decision_id": _text(bridge_decision_id),
        "bridge_candidate_ref": _text(bridge_candidate_ref),
        "decision": _require_member(
            decision, field="decision", allowed=BRIDGE_DECISIONS
        ),
        "review_basis": _mapping_rows(review_basis),
        "residuals": _mapping_rows(residuals),
        "reviewer_ref": _text(reviewer_ref) or None,
        "authority_inherited": False,
        "promotion_authority": False,
    }


def build_external_pressure_result(
    *,
    pressure_result_id: str,
    target_ref: str,
    graph_view_ref: str,
    profile_id: str,
    outcome: str,
    diagnostics: Sequence[Mapping[str, Any]] = (),
    residuals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "pressure_result_id": _text(pressure_result_id),
        "target_ref": _text(target_ref),
        "graph_view_ref": _text(graph_view_ref),
        "profile_id": _text(profile_id),
        "outcome": _require_member(outcome, field="outcome", allowed=PRESSURE_OUTCOMES),
        "diagnostics": _mapping_rows(diagnostics),
        "residuals": _mapping_rows(residuals),
        "diagnostic_only": True,
        "mutation_authority": False,
        "promotion_authority": False,
    }


def build_expected_property_pressure(
    *,
    pressure_result_id: str,
    target_ref: str,
    graph_view_ref: str,
    profile_id: str,
    coverage_state: str,
    expected_properties: Sequence[Mapping[str, Any]],
    observed_properties: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare observed property presence with a bounded expected shape.

    The caller supplies observations from its chosen external graph adapter.
    Incomplete coverage never turns an observed absence into a global absence:
    a required or strongly expected property then yields ``abstain`` and an
    explicit coverage residual instead of a type repair or promotion.
    """

    state = _require_member(
        coverage_state, field="coverage_state", allowed=GRAPH_VIEW_STATES
    )
    observations: dict[str, dict[str, Any]] = {}
    for row in _mapping_rows(observed_properties):
        property_ref = _text(row.get("property_ref"))
        if not property_ref:
            raise ValueError("observed property requires property_ref")
        observation_state = _require_member(
            row.get("state"),
            field="observed property state",
            allowed=PROPERTY_OBSERVATION_STATES,
        )
        observations[property_ref] = {
            **row,
            "property_ref": property_ref,
            "state": observation_state,
        }

    diagnostics: list[dict[str, Any]] = []
    residuals: list[dict[str, Any]] = []
    has_definite_warning = False
    has_coverage_limited_gap = False
    has_unknown_required_property = False
    required_strengths = {"required_by_rule", "strong_expected"}

    for expectation in _mapping_rows(expected_properties):
        property_ref = _text(expectation.get("property_ref"))
        if not property_ref:
            raise ValueError("property expectation requires property_ref")
        strength = _require_member(
            expectation.get("strength"),
            field="property expectation strength",
            allowed=PROPERTY_EXPECTATION_STRENGTHS,
        )
        observation = observations.get(
            property_ref,
            {"property_ref": property_ref, "state": "unknown"},
        )
        observed_state = str(observation["state"])
        diagnostic = {
            "kind": "expected_property_presence",
            "property_ref": property_ref,
            "strength": strength,
            "observed_state": observed_state,
            "coverage_state": state,
        }
        evidence_ref = _text(observation.get("evidence_ref"))
        if evidence_ref:
            diagnostic["evidence_ref"] = evidence_ref
        diagnostics.append(diagnostic)

        if strength in required_strengths and observed_state == "observed_absent":
            if state == "complete":
                has_definite_warning = True
            else:
                has_coverage_limited_gap = True
                residuals.append(
                    {
                        "kind": "coverage_limited_absence",
                        "property_ref": property_ref,
                        "reason": "observed absence is not global absence in an incomplete graph view",
                    }
                )
        elif strength in required_strengths and observed_state == "unknown":
            has_unknown_required_property = True
            residuals.append(
                {
                    "kind": "property_observation_missing",
                    "property_ref": property_ref,
                    "reason": "no bounded observation supplied for a required property",
                }
            )
        elif strength == "discouraged" and observed_state == "present":
            has_definite_warning = True

    outcome = (
        "warning"
        if has_definite_warning
        else "abstain"
        if has_coverage_limited_gap or has_unknown_required_property
        else "compatible"
    )
    return build_external_pressure_result(
        pressure_result_id=pressure_result_id,
        target_ref=target_ref,
        graph_view_ref=graph_view_ref,
        profile_id=profile_id,
        outcome=outcome,
        diagnostics=diagnostics,
        residuals=residuals,
    )


def build_bounded_type_closure_pressure(
    *,
    pressure_result_id: str,
    target_ref: str,
    graph_view_ref: str,
    profile_id: str,
    coverage_state: str,
    direct_type_refs: Sequence[str],
    closure_observations: Sequence[Mapping[str, Any]],
    expected_superclass_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Diagnose only explicitly supplied direct-type/superclass observations.

    This is intentionally not a graph traversal. An adapter supplies direct
    type references and the named ``P279`` rows it inspected. Under incomplete
    coverage, a missing row or unobserved expected superclass is an abstention,
    never evidence that the type relation does not hold elsewhere.
    """

    state = _require_member(
        coverage_state, field="coverage_state", allowed=GRAPH_VIEW_STATES
    )
    direct_types = sorted({_text(value) for value in direct_type_refs if _text(value)})
    expected = sorted(
        {_text(value) for value in expected_superclass_refs if _text(value)}
    )
    observations: dict[str, dict[str, Any]] = {}
    for row in _mapping_rows(closure_observations):
        type_ref = _text(row.get("type_ref"))
        if not type_ref:
            raise ValueError("closure observation requires type_ref")
        observations[type_ref] = {
            "type_ref": type_ref,
            "superclass_refs": sorted(
                {
                    _text(value)
                    for value in row.get("superclass_refs", ())
                    if _text(value)
                }
            ),
            "evidence_refs": sorted(
                {_text(value) for value in row.get("evidence_refs", ()) if _text(value)}
            ),
        }

    diagnostics: list[dict[str, Any]] = []
    residuals: list[dict[str, Any]] = []
    if not direct_types:
        residuals.append(
            {
                "kind": "direct_type_observation_missing",
                "reason": "bounded superclass pressure requires an observed direct type",
            }
        )
    observed_superclasses: set[str] = set()
    for type_ref in direct_types:
        observation = observations.get(type_ref)
        if observation is None:
            residuals.append(
                {
                    "kind": "type_closure_observation_missing",
                    "type_ref": type_ref,
                    "reason": "no named bounded superclass observation supplied",
                }
            )
            continue
        observed_superclasses.update(observation["superclass_refs"])
        diagnostics.append(
            {
                "kind": "bounded_direct_superclass",
                "property_ref": "P279",
                "direct_type_ref": type_ref,
                "superclass_refs": observation["superclass_refs"],
                "evidence_refs": observation["evidence_refs"],
                "coverage_state": state,
            }
        )

    missing_expected = sorted(set(expected) - observed_superclasses)
    if missing_expected:
        residuals.append(
            {
                "kind": "coverage_limited_superclass_expectation",
                "expected_superclass_refs": missing_expected,
                "reason": "unobserved superclass is not global absence in an incomplete graph view",
            }
        )
    if not residuals:
        outcome = "compatible"
    elif state == "complete" and missing_expected:
        outcome = "warning"
    else:
        outcome = "abstain"
    return build_external_pressure_result(
        pressure_result_id=pressure_result_id,
        target_ref=target_ref,
        graph_view_ref=graph_view_ref,
        profile_id=profile_id,
        outcome=outcome,
        diagnostics=diagnostics,
        residuals=residuals,
    )


def build_external_graph_context(
    *,
    model_id: str,
    graph_views: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]] = (),
    events: Sequence[Mapping[str, Any]] = (),
    claims: Sequence[Mapping[str, Any]] = (),
    bridge_candidates: Sequence[Mapping[str, Any]] = (),
    bridge_decisions: Sequence[Mapping[str, Any]] = (),
    pressure_results: Sequence[Mapping[str, Any]] = (),
    provenance_graph: Sequence[Mapping[str, Any]] = (),
    residuals: Sequence[Mapping[str, Any]] = (),
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Make external graph data an ordinary generic world-model input envelope."""

    return {
        "schema_version": EXTERNAL_GRAPH_CONTEXT_SCHEMA_VERSION,
        "model_id": _text(model_id),
        "entities": _mapping_rows(entities),
        "events": _mapping_rows(events),
        "claims": _mapping_rows(claims),
        "external_graph_views": [
            normalize_graph_view(graph_view)
            for graph_view in graph_views
            if isinstance(graph_view, Mapping)
        ],
        "external_bridge_candidates": _mapping_rows(bridge_candidates),
        "external_bridge_decisions": _mapping_rows(bridge_decisions),
        "external_pressure_results": _mapping_rows(pressure_results),
        "provenance_graph": _mapping_rows(provenance_graph),
        "residuals": _mapping_rows(residuals),
        "metadata": deepcopy(dict(metadata or {})),
    }


__all__ = [
    "ATTACHMENT_KINDS",
    "BRIDGE_CANDIDATE_STATES",
    "BRIDGE_DECISIONS",
    "BRIDGE_SUBJECT_KINDS",
    "EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION",
    "EXTERNAL_GRAPH_CONTEXT_SCHEMA_VERSION",
    "GRAPH_VIEW_STATES",
    "PRESSURE_OUTCOMES",
    "PROPERTY_EXPECTATION_STRENGTHS",
    "PROPERTY_OBSERVATION_STATES",
    "build_external_bridge_candidate",
    "build_external_bridge_decision",
    "build_bounded_type_closure_pressure",
    "build_expected_property_pressure",
    "build_external_pressure_result",
    "build_external_graph_context",
    "build_graph_view",
    "build_graph_view_from_transport",
    "normalize_graph_view",
]
