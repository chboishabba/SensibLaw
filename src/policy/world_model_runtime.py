from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.policy.adapter_discovery import (
    AdapterRegistration,
    UnsupportedInputError,
    discover_adapter,
    register_adapter,
)
from src.policy.linkage_depth import (
    build_expected_layer_contract,
    build_linkage_depth_receipt,
)
from src.policy.linkage_workflows import attach_receipt as _attach_receipt
from src.policy.world_model import (
    CANDIDATE_WORLD_MODEL_SCHEMA_VERSION,
    build_state_node,
    build_world_model as build_candidate_world_model,
    normalize_world_model,
)
from src.policy.world_model_inputs import normalize_input_envelope
from src.policy.world_model_projections import (
    project_claim_table as _project_claim_table,
    project_linkage_case as _project_linkage_case,
    project_report as _project_report,
    project_review_surface as _project_review_surface,
    project_timeline as _project_timeline,
)

GENERIC_WORLD_MODEL_REPORT_SCHEMA_VERSION = "sl.generic_world_model_report.v0_1"
GENERIC_WORLD_MODEL_FAMILY_ID = "generic_input"
GENERIC_LINKAGE_CONTRACT_ID = "generic_input_linkage"
GENERIC_RECEIPT_ADAPTER_ID = "generic_input"
NAT_WIKIDATA_PROFILE_SCHEMA_VERSION = "sl.nat_wikidata_profile.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_root() -> Path:
    return _sensiblaw_root() / "tests" / "fixtures" / "wikidata"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _metadata_with_adapter(world_model: Mapping[str, Any], *, runtime_adapter: str) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    metadata = deepcopy(dict(model.get("metadata") or {}))
    metadata["runtime_adapter"] = runtime_adapter
    model["metadata"] = metadata
    return model


def _annotate_projection(payload: Mapping[str, Any], *, runtime_adapter: str) -> dict[str, Any]:
    artifact = deepcopy(dict(payload))
    if isinstance(artifact.get("metadata"), Mapping):
        artifact["metadata"] = deepcopy(dict(artifact["metadata"]))
    else:
        artifact["metadata"] = {}
    artifact["metadata"]["runtime_adapter"] = runtime_adapter
    artifact["metadata"]["receipt_adapter"] = runtime_adapter
    return artifact


def _annotate_report(report: Mapping[str, Any], *, runtime_adapter: str) -> dict[str, Any]:
    payload = deepcopy(dict(report))
    projection = payload.get("projection")
    if isinstance(projection, Mapping):
        payload["projection"] = _annotate_projection(projection, runtime_adapter=runtime_adapter)
    for key in ("claim_table", "review_surface", "timeline", "linkage_case"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            payload[key] = _annotate_projection(value, runtime_adapter=runtime_adapter)
    return payload


def _generic_claim_nodes_from_text(text: str, *, model_id: str) -> list[dict[str, Any]]:
    normalized = _text(text)
    if not normalized:
        return []
    preview = normalized[:120]
    return [
        build_state_node(
            node_id=f"claim:{model_id}:source_excerpt",
            node_kind="parsed_form",
            label=preview,
            status="candidate",
            source_anchor_ids=[f"source:{model_id}"],
            authority_surface="generic_review_surface",
            promotion_status="candidate_only",
            metadata={"text_excerpt": preview, "candidate_vs_promoted_visibility": True},
        )
    ]


def _build_generic_world_model_from_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    input_kind = _text(envelope.get("input_kind")) or "opaque"
    payload = envelope.get("payload")
    input_id = _text(envelope.get("input_id")) or input_kind
    metadata = deepcopy(dict(envelope.get("metadata") or {}))

    text_fragments: list[str] = []
    if input_kind in {"text", "text_file"} and isinstance(payload, Mapping):
        text_fragments.append(_text(payload.get("text")))
    elif input_kind == "mapping" and isinstance(payload, Mapping):
        text_fragments.append(_text(payload.get("text")))
        text_fragments.append(_text(payload.get("title")))
    elif input_kind == "sequence":
        for row in _mapping_rows(payload):
            text_fragments.extend([_text(row.get("text")), _text(row.get("title")), _text(row.get("label"))])
    elif input_kind == "document_bundle" and isinstance(payload, Mapping):
        for row in _mapping_rows(payload.get("documents")):
            text_fragments.extend([_text(row.get("text")), _text(row.get("name"))])
    normalized_text = "\n".join(fragment for fragment in text_fragments if fragment)

    claims = _generic_claim_nodes_from_text(normalized_text, model_id=input_id)
    summary = {
        "claim_count": len(claims),
        "input_kind": input_kind,
    }
    world_model = build_candidate_world_model(
        model_id=input_id,
        lane_family=GENERIC_WORLD_MODEL_FAMILY_ID,
        model_status="candidate",
        source_mode=input_kind,
        claims=claims,
        authority_surfaces=[{"surface_id": "generic_review_surface", "status": "reviewed"}],
        provenance_graph=[
            {
                "input_kind": input_kind,
                "input_id": input_id,
            }
        ],
        summary=summary,
        metadata={
            **metadata,
            "input_envelope": deepcopy(dict(envelope)),
            "artifact_id": input_id,
            "lane_id": GENERIC_WORLD_MODEL_FAMILY_ID,
            "runtime_adapter": GENERIC_RECEIPT_ADAPTER_ID,
        },
    )
    return world_model


def _is_au_bundle(payload: Any) -> float:
    if isinstance(payload, Mapping) and _text(payload.get("version")) == "fact.review.bundle.v1":
        return 1.0
    return 0.0


def _is_gwb_broader_review(payload: Any) -> float:
    if isinstance(payload, Mapping) and _text(payload.get("fixture_kind")) == "gwb_broader_review":
        return 1.0
    return 0.0


def _is_gwb_narrative(payload: Any) -> float:
    if isinstance(payload, Mapping) and bool(payload.get("per_event")) and bool(_text(payload.get("run_id"))):
        return 0.9
    return 0.0


def _is_brexit_records(payload: Any) -> float:
    rows = _mapping_rows(payload)
    if not rows:
        return 0.0
    required = {"doc_id", "title", "collection", "url"}
    if all(required.issubset(set(row.keys())) for row in rows[:2]):
        return 0.9
    return 0.0


def _is_normalized_world_model(payload: Any) -> float:
    if isinstance(payload, Mapping) and _text(payload.get("schema_version")) == CANDIDATE_WORLD_MODEL_SCHEMA_VERSION:
        return 1.0
    return 0.0


def _is_nat_profile(payload: Any) -> float:
    if isinstance(payload, Mapping) and _text(payload.get("schema_version")) == NAT_WIKIDATA_PROFILE_SCHEMA_VERSION:
        return 1.0
    return 0.0


def _is_generic_input(payload: Any) -> float:
    """Fallback adapter — always matches with minimal score."""
    return 0.01


# ---------------------------------------------------------------------------
# Adapter registration — predicates registered at module load time.
# ---------------------------------------------------------------------------

def _register_builtin_adapters() -> None:
    """Register the built-in content-sniffing adapters."""
    _builtin_adapters = [
        AdapterRegistration(
            adapter_id="au_review_bundle",
            can_handle=_is_au_bundle,
            produces=frozenset({"CandidateWorldModel", "ClaimCandidate"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="gwb_broader_review",
            can_handle=_is_gwb_broader_review,
            produces=frozenset({"CandidateWorldModel", "ClaimCandidate"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="gwb_narrative_timeline",
            can_handle=_is_gwb_narrative,
            produces=frozenset({"CandidateWorldModel", "EventCandidate", "ClaimCandidate"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="brexit_records",
            can_handle=_is_brexit_records,
            produces=frozenset({"CandidateWorldModel", "ClaimCandidate", "SourceAnchor"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="normalized_world_model",
            can_handle=_is_normalized_world_model,
            produces=frozenset({"CandidateWorldModel"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="nat_profile",
            can_handle=_is_nat_profile,
            produces=frozenset({"CandidateWorldModel", "ClaimCandidate"}),
            requires=frozenset(),
        ),
        AdapterRegistration(
            adapter_id="generic_input",
            can_handle=_is_generic_input,
            produces=frozenset({"CandidateWorldModel"}),
            requires=frozenset(),
        ),
    ]
    for adapter in _builtin_adapters:
        register_adapter(adapter)


_register_builtin_adapters()


def _build_nat_profile_world_model(profile: str, **kwargs: Any) -> dict[str, Any]:
    from src.ontology.wikidata_linkage_depth import (
        build_climate_review_world_model,
        build_disjointness_world_model,
    )
    from src.ontology.wikidata_superclass_linkage import build_world_model as build_superclass_world_model

    if profile == "climate_review_demonstrator":
        return build_climate_review_world_model()
    if profile == "disjointness_report":
        return build_disjointness_world_model()
    if profile == "q43229_superclass_pressure":
        if not kwargs:
            fixture_root = _fixture_root()
            kwargs = {
                "review_bucket": _read_json(fixture_root / "wikidata_nat_cohort_b_review_bucket_20260402.json"),
                "operator_packet": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_packet_20260402.json"),
                "operator_queue": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_queue_20260402.json"),
                "operator_report": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_report_20260402.json"),
                "batch_report": _read_json(fixture_root / "wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
            }
        return build_superclass_world_model(**kwargs)
    raise ValueError(f"unsupported nat compatibility profile: {profile}")


def _build_world_model_from_adapter(envelope: Mapping[str, Any], *, adapter_id: str) -> dict[str, Any]:
    payload = envelope.get("payload")
    metadata = deepcopy(dict(envelope.get("metadata") or {}))
    if adapter_id == "generic_input":
        return _build_generic_world_model_from_envelope(envelope)
    if adapter_id == "normalized_world_model":
        return _metadata_with_adapter(payload if isinstance(payload, Mapping) else {}, runtime_adapter=adapter_id)
    if adapter_id == "au_review_bundle":
        from src.policy.au_world_model import build_world_model as build_au_world_model

        return _metadata_with_adapter(build_au_world_model(payload), runtime_adapter=adapter_id)
    if adapter_id == "gwb_broader_review":
        from src.policy.gwb_broader_review_world_model import build_world_model as build_gwb_world_model

        return _metadata_with_adapter(build_gwb_world_model(payload), runtime_adapter=adapter_id)
    if adapter_id == "gwb_narrative_timeline":
        from src.policy.gwb_narrative_world_model import build_world_model as build_gwb_narrative_world_model

        run_id = _text(metadata.get("run_id"))
        if isinstance(payload, Mapping):
            run_id = run_id or _text(payload.get("run_id"))
        return _metadata_with_adapter(build_gwb_narrative_world_model(payload, run_id=run_id or None), runtime_adapter=adapter_id)
    if adapter_id == "brexit_records":
        from src.sources.national_archives.brexit_national_archives_lane import build_world_model as build_brexit_world_model

        return _metadata_with_adapter(build_brexit_world_model(payload), runtime_adapter=adapter_id)
    if adapter_id == "nat_profile":
        # Profile discovered from schema marker on payload — no smuggled hints.
        profile = _text(payload.get("profile_id")) if isinstance(payload, Mapping) else ""
        if not profile:
            profile = _text(envelope.get("input_id"))
        kwargs = deepcopy(dict(payload)) if isinstance(payload, Mapping) else {}
        kwargs.pop("schema_version", None)
        kwargs.pop("profile_id", None)
        return _metadata_with_adapter(_build_nat_profile_world_model(profile, **kwargs), runtime_adapter=f"nat:{profile}")
    raise ValueError(f"unsupported world-model adapter: {adapter_id}")


def build_world_model(
    input_data: Any,
    *,
    envelope: Mapping[str, Any] | None = None,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_envelope = normalize_input_envelope(
        envelope if envelope is not None else input_data,
    )
    if envelope is None and normalized_envelope is not input_data:
        if input_data is not normalized_envelope:
            normalized_envelope["payload"] = deepcopy(input_data)
    elif envelope is not None and input_data is not None:
        try:
            normalized_envelope["payload"] = deepcopy(input_data)
        except Exception:
            normalized_envelope["payload"] = input_data
    if isinstance(options, Mapping):
        normalized_envelope["metadata"] = {
            **deepcopy(dict(normalized_envelope.get("metadata") or {})),
            **deepcopy(dict(options)),
        }
    result = discover_adapter(normalized_envelope)
    return _build_world_model_from_adapter(normalized_envelope, adapter_id=result.adapter_id)


def _generic_linkage_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=GENERIC_LINKAGE_CONTRACT_ID,
        domain="generic_input",
        anchor_kind="source_anchor",
        expected_layers=[
            "source_anchor",
            "parsed_form",
            "review_surface",
            "tranche_anchor",
        ],
        required_bridges=[
            ["source_anchor", "parsed_form"],
            ["parsed_form", "review_surface"],
            ["review_surface", "tranche_anchor"],
        ],
        terminal_anchor="tranche_anchor",
        required_visibility_fields=[
            "candidate_vs_promoted_visibility",
        ],
        notes=["Generic bounded input linkage path."],
    )


def _generic_linkage_projection(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    metadata = deepcopy(dict(model.get("metadata") or {}))
    model_id = _text(model.get("model_id")) or "generic_input"
    claim_nodes = _mapping_rows(model.get("claims"))
    parsed_node_id = _text(claim_nodes[0].get("node_id")) if claim_nodes else f"parsed:{model_id}"
    nodes = [
        {
            "id": f"source:{model_id}",
            "layer": "source_anchor",
            "label": _text(metadata.get("input_id")) or model_id,
            "metadata": {"candidate_vs_promoted_visibility": True},
        },
        {
            "id": parsed_node_id,
            "layer": "parsed_form",
            "label": _text(claim_nodes[0].get("label")) if claim_nodes else "Parsed input surface",
            "metadata": {"candidate_vs_promoted_visibility": True},
        },
        {
            "id": f"review_surface:{model_id}",
            "layer": "review_surface",
            "label": "Generic review surface",
            "metadata": {"candidate_vs_promoted_visibility": True},
        },
        {
            "id": f"tranche:{model_id}",
            "layer": "tranche_anchor",
            "label": "Workflow tranche",
            "metadata": {"candidate_vs_promoted_visibility": True},
        },
    ]
    edges = [
        {"source": f"source:{model_id}", "target": parsed_node_id, "kind": "normalized_into"},
        {"source": parsed_node_id, "target": f"review_surface:{model_id}", "kind": "presented_for_review"},
        {"source": f"review_surface:{model_id}", "target": f"tranche:{model_id}", "kind": "queued_in_tranche"},
    ]
    return _annotate_projection(
        _project_linkage_case(
            model,
            case_id=f"generic_input:{model_id}",
            contract_id=GENERIC_LINKAGE_CONTRACT_ID,
            nodes=nodes,
            edges=edges,
            expected_anchor_ids=[f"source:{model_id}"],
            expected_terminal_ids=[f"tranche:{model_id}"],
            metadata={"lane_id": GENERIC_WORLD_MODEL_FAMILY_ID},
        ),
        runtime_adapter=GENERIC_RECEIPT_ADAPTER_ID,
    )


def _runtime_adapter(world_model_or_projection: Mapping[str, Any]) -> str:
    metadata = world_model_or_projection.get("metadata") if isinstance(world_model_or_projection.get("metadata"), Mapping) else {}
    if _text(metadata.get("runtime_adapter")):
        return _text(metadata.get("runtime_adapter"))
    if isinstance(world_model_or_projection.get("projection"), Mapping):
        projection_metadata = (
            world_model_or_projection["projection"].get("metadata")
            if isinstance(world_model_or_projection["projection"].get("metadata"), Mapping)
            else {}
        )
        if _text(projection_metadata.get("runtime_adapter")):
            return _text(projection_metadata.get("runtime_adapter"))
    if _text(world_model_or_projection.get("lane_family")) == GENERIC_WORLD_MODEL_FAMILY_ID:
        return GENERIC_RECEIPT_ADAPTER_ID
    return ""


def project_report(world_model: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    runtime_adapter = _runtime_adapter(model) or GENERIC_RECEIPT_ADAPTER_ID
    if runtime_adapter == "au_review_bundle":
        from src.policy.au_world_model import project_report as project_au_report

        return _annotate_report(project_au_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "gwb_broader_review":
        from src.policy.gwb_broader_review_world_model import project_report as project_gwb_report

        return _annotate_report(project_gwb_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "gwb_narrative_timeline":
        from src.policy.gwb_narrative_world_model import project_report as project_gwb_narrative_report

        return _annotate_report(project_gwb_narrative_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "brexit_records":
        from src.sources.national_archives.brexit_national_archives_lane import project_report as project_brexit_report

        return _annotate_report(project_brexit_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "nat:climate_review_demonstrator":
        from src.ontology.wikidata_linkage_depth import project_climate_review_report

        return _annotate_report(project_climate_review_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "nat:disjointness_report":
        from src.ontology.wikidata_linkage_depth import project_disjointness_report

        return _annotate_report(project_disjointness_report(model), runtime_adapter=runtime_adapter)
    if runtime_adapter == "nat:q43229_superclass_pressure":
        from src.ontology.wikidata_superclass_linkage import project_report as project_q43229_report

        return _annotate_report(project_q43229_report(model), runtime_adapter=runtime_adapter)
    report = _project_report(
        world_model=model,
        schema_version=GENERIC_WORLD_MODEL_REPORT_SCHEMA_VERSION,
        artifact_id=_text(model.get("model_id")) or GENERIC_WORLD_MODEL_FAMILY_ID,
        lane_id=GENERIC_WORLD_MODEL_FAMILY_ID,
        family_id=_text(model.get("lane_family")) or GENERIC_WORLD_MODEL_FAMILY_ID,
        claims=model.get("claims") if isinstance(model.get("claims"), Sequence) else None,
        summary=model.get("summary") if isinstance(model.get("summary"), Mapping) else None,
        extra_fields={
            "claim_table": project_claim_table(model),
            "review_surface": project_review_surface(model),
            "linkage_case": project_linkage_case(model),
        },
    )
    return _annotate_report(report, runtime_adapter=GENERIC_RECEIPT_ADAPTER_ID)


def _projection_from_report(world_model: Mapping[str, Any], key: str) -> dict[str, Any]:
    report = project_report(world_model)
    value = report.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"project_report(...) did not expose expected projection {key}")
    return dict(value)


def project_claim_table(world_model: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    runtime_adapter = _runtime_adapter(model)
    if runtime_adapter and runtime_adapter != GENERIC_RECEIPT_ADAPTER_ID:
        report = project_report(model)
        if isinstance(report.get("claim_table"), Mapping):
            return dict(report["claim_table"])
    return _annotate_projection(_project_claim_table(model, **kwargs), runtime_adapter=runtime_adapter or GENERIC_RECEIPT_ADAPTER_ID)


def project_timeline(world_model: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    runtime_adapter = _runtime_adapter(model)
    if runtime_adapter and runtime_adapter != GENERIC_RECEIPT_ADAPTER_ID:
        report = project_report(model)
        if isinstance(report.get("timeline"), Mapping):
            return dict(report["timeline"])
    return _annotate_projection(_project_timeline(model, **kwargs), runtime_adapter=runtime_adapter or GENERIC_RECEIPT_ADAPTER_ID)


def project_review_surface(world_model: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    runtime_adapter = _runtime_adapter(model)
    if runtime_adapter and runtime_adapter != GENERIC_RECEIPT_ADAPTER_ID:
        report = project_report(model)
        if isinstance(report.get("review_surface"), Mapping):
            return dict(report["review_surface"])
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    return _annotate_projection(
        _project_review_surface(
            model,
            workflow_summary=metadata.get("workflow_summary") if isinstance(metadata.get("workflow_summary"), Mapping) else None,
            operator_workflow_surface=metadata.get("operator_workflow_surface")
            if isinstance(metadata.get("operator_workflow_surface"), Mapping)
            else None,
            **kwargs,
        ),
        runtime_adapter=runtime_adapter or GENERIC_RECEIPT_ADAPTER_ID,
    )


def project_linkage_case(world_model: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    runtime_adapter = _runtime_adapter(model) or GENERIC_RECEIPT_ADAPTER_ID
    if runtime_adapter == GENERIC_RECEIPT_ADAPTER_ID:
        return _generic_linkage_projection(model)
    report = project_report(model)
    if isinstance(report.get("linkage_case"), Mapping):
        return dict(report["linkage_case"])
    raise ValueError("project_report(...) did not expose linkage_case projection")


def _generic_receipt_builder(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    linkage_case = artifact.get("linkage_case") if isinstance(artifact.get("linkage_case"), Mapping) else artifact
    if not isinstance(linkage_case, Mapping):
        raise ValueError("generic receipt attachment requires linkage_case projection")
    payload = linkage_case.get("payload") if isinstance(linkage_case.get("payload"), Mapping) else {}
    case = {
        "case_id": _text(payload.get("case_id")) or "generic_input",
        "case_kind": "generic_input_linkage",
        "contract_id": _text(payload.get("contract_id")) or GENERIC_LINKAGE_CONTRACT_ID,
        "expected_anchor_ids": deepcopy(payload.get("expected_anchor_ids", [])),
        "expected_terminal_ids": deepcopy(payload.get("expected_terminal_ids", [])),
        "nodes": deepcopy(payload.get("nodes", [])),
        "edges": deepcopy(payload.get("edges", [])),
        "lane_id": GENERIC_WORLD_MODEL_FAMILY_ID,
        "case_source": "projected_world_model_artifact",
        "contract": _generic_linkage_contract(),
    }
    return build_linkage_depth_receipt(case=case, contract=_generic_linkage_contract())


def _receipt_builder_for_adapter(adapter_id: str) -> Callable[[Mapping[str, Any]], Mapping[str, Any]]:
    if adapter_id == GENERIC_RECEIPT_ADAPTER_ID:
        return _generic_receipt_builder
    if adapter_id == "au_review_bundle":
        from src.policy.au_linkage_depth import build_receipt

        return build_receipt
    if adapter_id == "gwb_broader_review":
        from src.policy.gwb_linkage_depth import build_receipt

        return build_receipt
    if adapter_id == "gwb_narrative_timeline":
        from src.policy.gwb_narrative_linkage import build_receipt

        return build_receipt
    if adapter_id == "brexit_records":
        from src.policy.brexit_linkage import build_receipt

        return build_receipt
    if adapter_id == "nat:climate_review_demonstrator":
        from src.ontology.wikidata_linkage_depth import build_climate_review_linkage_receipt

        return build_climate_review_linkage_receipt
    if adapter_id == "nat:disjointness_report":
        from src.ontology.wikidata_linkage_depth import build_disjointness_report_linkage_receipt

        return build_disjointness_report_linkage_receipt
    if adapter_id == "nat:q43229_superclass_pressure":
        from src.ontology.wikidata_superclass_linkage import build_receipt

        return build_receipt
    raise ValueError(f"unsupported receipt adapter: {adapter_id}")


def attach_receipt(projection_or_artifact: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(projection_or_artifact, Mapping):
        raise ValueError("receipt attachment requires projection or report mapping")
    artifact = projection_or_artifact
    if _text(artifact.get("projection_kind")) == "linkage_case":
        artifact = {"linkage_case": deepcopy(dict(artifact))}
    elif not isinstance(artifact.get("linkage_case"), Mapping):
        raise ValueError(
            "linkage receipt attachment requires a linkage_case projection; "
            "project_linkage_case(...) must run before attach_receipt(...)"
        )
    runtime_adapter = _runtime_adapter(artifact) or _runtime_adapter(artifact.get("linkage_case") if isinstance(artifact.get("linkage_case"), Mapping) else {}) or GENERIC_RECEIPT_ADAPTER_ID
    return _attach_receipt(artifact, receipt_builder=_receipt_builder_for_adapter(runtime_adapter))


__all__ = [
    "GENERIC_WORLD_MODEL_FAMILY_ID",
    "GENERIC_WORLD_MODEL_REPORT_SCHEMA_VERSION",
    "attach_receipt",
    "build_world_model",
    "project_claim_table",
    "project_linkage_case",
    "project_report",
    "project_review_surface",
    "project_timeline",
]
