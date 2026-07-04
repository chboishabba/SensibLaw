from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from src.policy import linkage_depth as linkage_depth_policy
from src.policy.linkage_depth import (
    EXPECTED_LAYER_CONTRACT_SCHEMA_VERSION,
    LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
    audit_linkage_depth_case,
    build_expected_layer_contract,
    build_linkage_depth_audit,
    build_linkage_depth_case,
    build_linkage_depth_receipt,
)

WIKIDATA_LINKAGE_DEPTH_CASE_SCHEMA_VERSION = "sl.wikidata_linkage_depth_case.v0_1"
WIKIDATA_LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION = "sl.wikidata_linkage_depth_audit.v0_1"
SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID = "sensiblaw_pnf_wd_linkage"
WIKIDATA_DISJOINTNESS_REVIEW_LINKAGE_CONTRACT_ID = "wikidata_disjointness_review_linkage"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_sensiblaw_pnf_wd_linkage_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID,
        domain="sensiblaw_pnf_wd_linkage",
        anchor_kind="token_or_span",
        expected_layers=[
            "token_span",
            "sentence_document",
            "sentence_pnf",
            "document_pnf",
            "entity_topic_candidate",
            "wd_lexical_or_semantic_candidate",
            "zelph_wd_review_surface",
            "review_packet_tranche",
        ],
        required_bridges=[
            ["token_span", "sentence_document"],
            ["sentence_document", "sentence_pnf"],
            ["sentence_pnf", "document_pnf"],
            ["document_pnf", "entity_topic_candidate"],
            ["entity_topic_candidate", "wd_lexical_or_semantic_candidate"],
            ["wd_lexical_or_semantic_candidate", "zelph_wd_review_surface"],
            ["zelph_wd_review_surface", "review_packet_tranche"],
        ],
        terminal_anchor="review_packet_tranche",
        required_authority_boundaries=[
            "source_document",
            "wd_candidate_review_boundary",
            "review_packet_tranche",
        ],
        linkage_policy={
            "soft_stitch_status": "soft_stitch",
            "soft_stitch_promotion": "blocked",
            "review_candidate_status": "semantic_review_candidate",
            "review_candidate_promotion": "candidate_only",
        },
        notes=[
            "PNF stays the typed middle layer; WD does not define flatness.",
            "Early token->WD soft stitches are allowed but do not replace the required PNF/document spine.",
        ],
    )


def build_wikidata_disjointness_review_linkage_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=WIKIDATA_DISJOINTNESS_REVIEW_LINKAGE_CONTRACT_ID,
        domain="wikidata_disjointness_review_linkage",
        anchor_kind="source_window",
        expected_layers=[
            "source_window",
            "statement_bundle",
            "disjoint_pair",
            "violation_candidate",
            "wd_lexical_or_semantic_candidate",
            "zelph_wd_review_surface",
            "review_packet_tranche",
        ],
        required_bridges=[
            ["source_window", "statement_bundle"],
            ["statement_bundle", "disjoint_pair"],
            ["disjoint_pair", "violation_candidate"],
            ["violation_candidate", "wd_lexical_or_semantic_candidate"],
            ["wd_lexical_or_semantic_candidate", "zelph_wd_review_surface"],
            ["zelph_wd_review_surface", "review_packet_tranche"],
        ],
        terminal_anchor="review_packet_tranche",
        required_authority_boundaries=[
            "source_window",
            "wikidata_contradiction_boundary",
            "review_packet_tranche",
        ],
        linkage_policy={
            "review_candidate_status": "semantic_review_candidate",
            "review_candidate_promotion": "candidate_only",
        },
        notes=[
            "Disjointness remains a bounded WD structural lane; the generic WD adapter stays lane-agnostic.",
            "The receipt must preserve source window, statement bundle, disjoint pair, contradiction candidate, and review surfaces.",
        ],
    )


def _node(node_id: str, *, layer: str, label: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": node_id,
        "layer": layer,
        "label": label,
        "metadata": dict(metadata or {}),
    }


def _edge(
    source: str,
    target: str,
    *,
    kind: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "kind": kind,
        "metadata": dict(metadata or {}),
    }


def _edge_with_contract(
    source: str,
    target: str,
    *,
    source_layer: str,
    target_layer: str,
    kind: str,
    promotion_status: str | None = None,
    authority_surface: str | None = None,
    source_anchor: str | None = None,
    residual_notes: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    edge_metadata = dict(metadata or {})
    edge_metadata.setdefault("from_layer", source_layer)
    edge_metadata.setdefault("to_layer", target_layer)
    if promotion_status:
        edge_metadata.setdefault("promotion_status", promotion_status)
    if authority_surface:
        edge_metadata.setdefault("authority_surface", authority_surface)
    if source_anchor:
        edge_metadata.setdefault("source_anchor", source_anchor)
    if residual_notes is not None:
        edge_metadata.setdefault("residual_notes", list(residual_notes))
    return _edge(source, target, kind=kind, metadata=edge_metadata)


def build_dog_soft_stitch_linkage_case() -> dict[str, Any]:
    return build_linkage_depth_case(
        case_id="dog_soft_stitch",
        case_kind="synthetic_fixture",
        lane_id=None,
        contract_id=SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID,
        notes=[
            "Synthetic control that preserves the PNF/document spine and an early WD soft stitch.",
        ],
        expected_anchor_ids=["token_span:dog"],
        expected_terminal_ids=["review_packet:dog"],
        nodes=[
            _node(
                "token_span:dog",
                layer="token_span",
                label="dog token/span",
                metadata={"surface": "dog", "source_kind": "synthetic"},
            ),
            _node(
                "sentence_document:dog",
                layer="sentence_document",
                label="dog sentence/document",
                metadata={"sentence_text": "I walked the dog to the park."},
            ),
            _node(
                "sentence_pnf:dog",
                layer="sentence_pnf",
                label="generic predicate carrier",
                metadata={
                    "pnf_carrier_kind": "generic_predicate_carrier",
                    "carrier_roles": ["subject", "predicate", "object", "goal"],
                },
            ),
            _node(
                "document_pnf:dog",
                layer="document_pnf",
                label="document PNF carrier",
                metadata={"document_id": "synthetic:dog_walk_note"},
            ),
            _node(
                "entity_topic_candidate:dog",
                layer="entity_topic_candidate",
                label="dog entity/topic candidate",
                metadata={"candidate_status": "candidate_only", "topic_kind": "animal_mention"},
            ),
            _node(
                "wd_candidate:dog_soft",
                layer="wd_lexical_or_semantic_candidate",
                label="dog WD soft stitch",
                metadata={
                    "wd_stage": "soft_stitch",
                    "promotion_status": "blocked",
                    "candidate_qid": "Q144",
                },
            ),
            _node(
                "wd_candidate:dog_review",
                layer="wd_lexical_or_semantic_candidate",
                label="dog WD semantic review candidate",
                metadata={
                    "wd_stage": "semantic_review_candidate",
                    "promotion_status": "candidate_only",
                    "candidate_qid": "Q144",
                },
            ),
            _node(
                "zelph_review:dog",
                layer="zelph_wd_review_surface",
                label="Zelph/WD review surface",
                metadata={"review_surface_kind": "synthetic_bridge"},
            ),
            _node(
                "review_packet:dog",
                layer="review_packet_tranche",
                label="review packet / tranche",
                metadata={"packet_id": "packet:synthetic:dog", "tranche_id": "tranche:synthetic"},
            ),
        ],
        edges=[
            _edge("token_span:dog", "sentence_document:dog", kind="anchored_in_sentence"),
            _edge("sentence_document:dog", "sentence_pnf:dog", kind="normalized_to_pnf"),
            _edge("sentence_pnf:dog", "document_pnf:dog", kind="aggregated_into_document_pnf"),
            _edge("document_pnf:dog", "entity_topic_candidate:dog", kind="yields_entity_topic_candidate"),
            _edge("entity_topic_candidate:dog", "wd_candidate:dog_review", kind="semantic_wd_candidate"),
            _edge("wd_candidate:dog_review", "zelph_review:dog", kind="review_surface_projection"),
            _edge("zelph_review:dog", "review_packet:dog", kind="review_packet_projection"),
            _edge(
                "token_span:dog",
                "wd_candidate:dog_soft",
                kind="wd_soft_stitch",
                metadata={"wd_stage": "soft_stitch"},
            ),
        ],
        contract=build_sensiblaw_pnf_wd_linkage_contract(),
    )


def _load_climate_review_demonstrator_report() -> dict[str, Any]:
    from .nat import load_fixture

    return load_fixture(profile="climate_review_demonstrator", with_receipt=True)


def _load_disjointness_report() -> dict[str, Any]:
    from .nat import load_fixture

    return load_fixture(profile="disjointness_report", with_receipt=True)


def _build_climate_review_linkage_case_payload(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    bridge_cases = report.get("residual_completeness_surface", {}).get("bridge_cases", [])
    if not isinstance(bridge_cases, list) or not bridge_cases:
        raise ValueError("climate review demonstrator did not expose bridge cases")
    bridge_case = bridge_cases[0]
    if not isinstance(bridge_case, Mapping):
        raise ValueError("bridge case must be an object")

    candidate = report.get("candidate_change_surface", {}).get("candidates", [])
    candidate_rows = candidate if isinstance(candidate, list) else []
    candidate_row = next(
        (
            row
            for row in candidate_rows
            if isinstance(row, Mapping) and _text(row.get("candidate_id")) == _text(bridge_case.get("candidate_id"))
        ),
        None,
    )
    if not isinstance(candidate_row, Mapping):
        raise ValueError("unable to align climate bridge case to selected candidate")

    packet_context = report.get("inputs", {}).get("packet_context", {})
    if not isinstance(packet_context, Mapping):
        packet_context = {}
    review_disposition = report.get("review_disposition", {})
    if not isinstance(review_disposition, Mapping):
        review_disposition = {}

    observations = bridge_case.get("text_observations", [])
    if not isinstance(observations, list) or not observations:
        raise ValueError("bridge case requires text observations")

    candidate_id = _text(bridge_case.get("candidate_id"))
    entity_qid = _text(candidate_row.get("entity_qid"))
    wd_review_node_id = f"wd_candidate:review:{candidate_id}"
    review_surface_node_id = f"zelph_review:{candidate_id}"
    review_packet_node_id = f"review_packet:{candidate_id}"

    nodes: list[dict[str, Any]] = [
        _node(
            wd_review_node_id,
            layer="wd_lexical_or_semantic_candidate",
            label=f"WD review candidate {candidate_id}",
            metadata={
                "wd_stage": "semantic_review_candidate",
                "promotion_status": "candidate_only",
                "entity_qid": entity_qid,
                "candidate_id": candidate_id,
            },
        ),
        _node(
            review_surface_node_id,
            layer="zelph_wd_review_surface",
            label=f"Zelph/WD review surface {candidate_id}",
            metadata={
                "bridge_case_ref": _text(bridge_case.get("bridge_case_ref")),
                "pressure": _text(bridge_case.get("pressure")),
                "authority_surface": "zelph_wd_review_surface",
            },
        ),
        _node(
            review_packet_node_id,
            layer="review_packet_tranche",
            label=f"review packet / tranche {candidate_id}",
            metadata={
                "packet_id": _text(packet_context.get("packet_id")),
                "split_plan_id": _text(packet_context.get("split_plan_id")),
                "review_final_state": _text(review_disposition.get("final_state")),
                "authority_surface": "review_packet_tranche",
            },
        ),
    ]
    edges: list[dict[str, Any]] = [
        _edge_with_contract(
            wd_review_node_id,
            review_surface_node_id,
            source_layer="wd_lexical_or_semantic_candidate",
            target_layer="zelph_wd_review_surface",
            kind="review_surface_projection",
            promotion_status="candidate_only",
            authority_surface="zelph_wd_review_surface",
        ),
        _edge_with_contract(
            review_surface_node_id,
            review_packet_node_id,
            source_layer="zelph_wd_review_surface",
            target_layer="review_packet_tranche",
            kind="review_packet_projection",
            promotion_status=_text(review_disposition.get("final_state")) or "held",
            authority_surface="review_packet_tranche",
        ),
    ]
    anchor_ids: list[str] = []

    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        observation_ref = _text(observation.get("observation_ref"))
        source_ref = _text(observation.get("source_ref"))
        token_id = f"token_span:{observation_ref}"
        sentence_id = f"sentence_document:{observation_ref}"
        sentence_pnf_id = f"sentence_pnf:{observation_ref}"
        document_pnf_id = f"document_pnf:{source_ref}"
        entity_topic_id = f"entity_topic_candidate:{candidate_id}:{observation_ref}"
        wd_soft_id = f"wd_candidate:soft:{observation_ref}"
        anchor_ids.append(token_id)

        anchors = observation.get("anchors", [])
        anchor_text = ""
        if isinstance(anchors, list) and anchors and isinstance(anchors[0], Mapping):
            anchor_text = _text(anchors[0].get("text"))

        nodes.extend(
            [
                _node(
                    token_id,
                    layer="token_span",
                    label=f"token/span {observation_ref}",
                    metadata={
                        "surface": anchor_text,
                        "observation_ref": observation_ref,
                        "source_ref": source_ref,
                    },
                ),
                _node(
                    sentence_id,
                    layer="sentence_document",
                    label=f"sentence/document {observation_ref}",
                    metadata={
                        "source_ref": source_ref,
                        "sentence_text": anchor_text,
                    },
                ),
                _node(
                    sentence_pnf_id,
                    layer="sentence_pnf",
                    label=f"generic predicate carrier {observation_ref}",
                    metadata={
                        "pnf_carrier_kind": "generic_predicate_carrier",
                        "carrier_roles": ["subject", "predicate", "object", "qualifier:P585", "qualifier:P518"],
                        "predicate": _text(observation.get("predicate")),
                    },
                ),
                _node(
                    document_pnf_id,
                    layer="document_pnf",
                    label=f"document PNF {source_ref}",
                    metadata={
                        "document_ref": source_ref,
                        "entity_qid": entity_qid,
                    },
                ),
                _node(
                    entity_topic_id,
                    layer="entity_topic_candidate",
                    label=f"entity/topic candidate {observation_ref}",
                    metadata={
                        "candidate_id": candidate_id,
                        "entity_qid": entity_qid,
                        "classification": _text(candidate_row.get("classification")),
                    },
                ),
                _node(
                    wd_soft_id,
                    layer="wd_lexical_or_semantic_candidate",
                    label=f"WD soft stitch {observation_ref}",
                    metadata={
                        "wd_stage": "soft_stitch",
                        "promotion_status": "blocked",
                        "entity_qid": entity_qid,
                    },
                ),
            ]
        )
        edges.extend(
            [
                _edge_with_contract(
                    token_id,
                    sentence_id,
                    source_layer="token_span",
                    target_layer="sentence_document",
                    kind="anchored_in_sentence",
                    promotion_status="source_local",
                    authority_surface="source_document",
                    source_anchor=token_id,
                ),
                _edge_with_contract(
                    sentence_id,
                    sentence_pnf_id,
                    source_layer="sentence_document",
                    target_layer="sentence_pnf",
                    kind="normalized_to_pnf",
                    promotion_status="source_local",
                    authority_surface="sentence_pnf",
                    source_anchor=token_id,
                ),
                _edge_with_contract(
                    sentence_pnf_id,
                    document_pnf_id,
                    source_layer="sentence_pnf",
                    target_layer="document_pnf",
                    kind="aggregated_into_document_pnf",
                    promotion_status="source_local",
                    authority_surface="document_pnf",
                    source_anchor=token_id,
                ),
                _edge_with_contract(
                    document_pnf_id,
                    entity_topic_id,
                    source_layer="document_pnf",
                    target_layer="entity_topic_candidate",
                    kind="yields_entity_topic_candidate",
                    promotion_status="candidate_only",
                    authority_surface="entity_topic_candidate",
                    source_anchor=token_id,
                ),
                _edge_with_contract(
                    entity_topic_id,
                    wd_review_node_id,
                    source_layer="entity_topic_candidate",
                    target_layer="wd_lexical_or_semantic_candidate",
                    kind="semantic_wd_candidate",
                    promotion_status="candidate_only",
                    authority_surface="wd_candidate_review_boundary",
                    source_anchor=token_id,
                ),
                _edge_with_contract(
                    token_id,
                    wd_soft_id,
                    source_layer="token_span",
                    target_layer="wd_lexical_or_semantic_candidate",
                    kind="wd_soft_stitch",
                    promotion_status="blocked",
                    authority_surface="wd_candidate_review_boundary",
                    source_anchor=token_id,
                    metadata={"wd_stage": "soft_stitch"},
                ),
            ]
        )

    return build_linkage_depth_case(
        case_id="climate_review_demonstrator",
        case_kind="real_text_fixture",
        lane_id="climate_review_demonstrator",
        contract_id=SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "Bounded real-text case projected from the repo-pinned climate review demonstrator bridge surface.",
        ],
        expected_anchor_ids=anchor_ids,
        expected_terminal_ids=[review_packet_node_id],
        nodes=nodes,
        edges=edges,
        contract=build_sensiblaw_pnf_wd_linkage_contract(),
    )


def build_climate_review_linkage_receipt(
    report: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = (
        dict(contract)
        if isinstance(contract, Mapping)
        else build_sensiblaw_pnf_wd_linkage_contract()
    )
    case_payload = _build_climate_review_linkage_case_payload(report)
    return build_linkage_depth_receipt(
        case=case_payload,
        contract=contract_payload,
        source_mode="emitted_bridge_artifact",
        notes=[
            "Bridge-emitted linkage receipt for the climate demonstrator.",
            "This artifact carries the PNF x Zelph/WD spine directly instead of relying on later audit reconstruction.",
        ],
    )


def _build_disjointness_report_linkage_case_payload(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    pairs = report.get("disjoint_pairs", [])
    pair = pairs[0] if isinstance(pairs, list) and pairs and isinstance(pairs[0], Mapping) else {}
    if not isinstance(pair, Mapping) or not _text(pair.get("pair_id")):
        raise ValueError("disjointness report requires at least one disjoint pair")

    review_summary = report.get("review_summary") if isinstance(report.get("review_summary"), Mapping) else {}
    culprit_classes = [
        row for row in report.get("culprit_classes", []) if isinstance(row, Mapping)
    ]
    culprit_items = [
        row for row in report.get("culprit_items", []) if isinstance(row, Mapping)
    ]
    pair_id = _text(pair.get("pair_id"))
    source_window_id = _text(report.get("source_window_id")) or "unknown_window"
    source_window_node_id = f"source_window:{source_window_id}"
    statement_bundle_node_id = f"statement_bundle:{pair_id}"
    disjoint_pair_node_id = f"disjoint_pair:{pair_id}"
    violation_candidate_node_id = f"violation_candidate:{pair_id}"
    wd_review_node_id = f"wd_candidate:disjointness:{pair_id}"
    review_surface_node_id = f"zelph_review:disjointness:{pair_id}"
    review_packet_node_id = f"review_packet:disjointness:{pair_id}"

    culprit_qids = sorted(
        {
            _text(row.get("qid"))
            for row in culprit_classes + culprit_items
            if _text(row.get("qid"))
        }
    )
    nodes = [
        _node(
            source_window_node_id,
            layer="source_window",
            label=f"source window {source_window_id}",
            metadata={
                "source_window_id": source_window_id,
                "active_statement_count": int(
                    report.get("bounded_slice", {}).get("active_statement_count", 0) or 0
                ),
            },
        ),
        _node(
            statement_bundle_node_id,
            layer="statement_bundle",
            label=f"P2738 statement bundle {pair_id}",
            metadata={
                "property_pid": _text(pair.get("property_pid")),
                "qualifier_pid": _text(pair.get("qualifier_pid")),
                "holder_qid": _text(pair.get("holder_qid")),
                "statement_value": _text(pair.get("statement_value")),
            },
        ),
        _node(
            disjoint_pair_node_id,
            layer="disjoint_pair",
            label=f"disjoint pair {pair_id}",
            metadata={
                "pair_id": pair_id,
                "holder_qid": _text(pair.get("holder_qid")),
                "left_qid": _text(pair.get("left_qid")),
                "right_qid": _text(pair.get("right_qid")),
            },
        ),
        _node(
            violation_candidate_node_id,
            layer="violation_candidate",
            label=f"bounded contradiction candidate {pair_id}",
            metadata={
                "subclass_violation_count": int(report.get("subclass_violation_count", 0) or 0),
                "instance_violation_count": int(report.get("instance_violation_count", 0) or 0),
                "culprit_class_count": int(review_summary.get("culprit_class_count", 0) or 0),
                "culprit_item_count": int(review_summary.get("culprit_item_count", 0) or 0),
                "culprit_qids": culprit_qids,
            },
        ),
        _node(
            wd_review_node_id,
            layer="wd_lexical_or_semantic_candidate",
            label=f"WD contradiction review candidate {pair_id}",
            metadata={
                "wd_stage": "semantic_review_candidate",
                "promotion_status": "candidate_only",
                "holder_qid": _text(pair.get("holder_qid")),
                "left_qid": _text(pair.get("left_qid")),
                "right_qid": _text(pair.get("right_qid")),
            },
        ),
        _node(
            review_surface_node_id,
            layer="zelph_wd_review_surface",
            label=f"Zelph/WD disjointness review surface {pair_id}",
            metadata={
                "authority_surface": "zelph_wd_review_surface",
                "lane_id": "disjointness_report",
                "review_kind": "disjointness_case",
            },
        ),
        _node(
            review_packet_node_id,
            layer="review_packet_tranche",
            label=f"review packet / tranche {pair_id}",
            metadata={
                "authority_surface": "review_packet_tranche",
                "lane_id": "disjointness_report",
                "review_kind": "disjointness_case",
                "review_disposition": "candidate_only",
            },
        ),
    ]
    edges = [
        _edge_with_contract(
            source_window_node_id,
            statement_bundle_node_id,
            source_layer="source_window",
            target_layer="statement_bundle",
            kind="window_statement_bundle_projection",
            authority_surface="source_window",
            source_anchor=source_window_id,
        ),
        _edge_with_contract(
            statement_bundle_node_id,
            disjoint_pair_node_id,
            source_layer="statement_bundle",
            target_layer="disjoint_pair",
            kind="pair_extraction",
            authority_surface="wikidata_disjointness_pair",
            source_anchor=pair_id,
        ),
        _edge_with_contract(
            disjoint_pair_node_id,
            violation_candidate_node_id,
            source_layer="disjoint_pair",
            target_layer="violation_candidate",
            kind="contradiction_candidate_projection",
            promotion_status="candidate_only",
            authority_surface="wikidata_contradiction_boundary",
            source_anchor=pair_id,
        ),
        _edge_with_contract(
            violation_candidate_node_id,
            wd_review_node_id,
            source_layer="violation_candidate",
            target_layer="wd_lexical_or_semantic_candidate",
            kind="semantic_wd_candidate",
            promotion_status="candidate_only",
            authority_surface="wikidata_contradiction_boundary",
            source_anchor=pair_id,
        ),
        _edge_with_contract(
            wd_review_node_id,
            review_surface_node_id,
            source_layer="wd_lexical_or_semantic_candidate",
            target_layer="zelph_wd_review_surface",
            kind="review_surface_projection",
            promotion_status="candidate_only",
            authority_surface="zelph_wd_review_surface",
            source_anchor=pair_id,
        ),
        _edge_with_contract(
            review_surface_node_id,
            review_packet_node_id,
            source_layer="zelph_wd_review_surface",
            target_layer="review_packet_tranche",
            kind="review_packet_projection",
            promotion_status="candidate_only",
            authority_surface="review_packet_tranche",
            source_anchor=pair_id,
        ),
    ]
    return build_linkage_depth_case(
        case_id="disjointness_report",
        case_kind="wd_structural_fixture",
        lane_id="disjointness_report",
        contract_id=WIKIDATA_DISJOINTNESS_REVIEW_LINKAGE_CONTRACT_ID,
        notes=[
            "Bounded disjointness lane preserving source window -> statement bundle -> pair -> contradiction candidate -> WD review -> tranche.",
        ],
        expected_anchor_ids=[source_window_node_id],
        expected_terminal_ids=[review_packet_node_id],
        nodes=nodes,
        edges=edges,
        contract=build_wikidata_disjointness_review_linkage_contract(),
    )


def build_disjointness_report_linkage_receipt(
    report: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = (
        dict(contract)
        if isinstance(contract, Mapping)
        else build_wikidata_disjointness_review_linkage_contract()
    )
    case_payload = _build_disjointness_report_linkage_case_payload(report)
    return build_linkage_depth_receipt(
        case=case_payload,
        contract=contract_payload,
        source_mode="emitted_bridge_artifact",
        notes=[
            "Bridge-emitted linkage receipt for the bounded disjointness report lane.",
            "The lane-level surface preserves contradiction depth without teaching the generic WD adapter a disjointness ladder.",
        ],
    )


def build_climate_review_linkage_case() -> dict[str, Any]:
    report = _load_climate_review_demonstrator_report()
    receipt = report.get("linkage_depth_receipt")
    if isinstance(receipt, Mapping) and _text(receipt.get("schema_version")) == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return build_linkage_depth_case(
            case_id=_text(receipt.get("case_id")) or "climate_review_demonstrator",
            case_kind="real_text_fixture",
            lane_id=_text(receipt.get("lane_id")) or "climate_review_demonstrator",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id"))
            or SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID,
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=[
                "Bounded real-text case loaded from the bridge-emitted climate linkage receipt.",
            ],
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            contract=receipt.get("contract") if isinstance(receipt.get("contract"), Mapping) else build_sensiblaw_pnf_wd_linkage_contract(),
        )
    return _build_climate_review_linkage_case_payload(report)


def build_disjointness_report_linkage_case() -> dict[str, Any]:
    report = _load_disjointness_report()
    receipt = report.get("linkage_depth_receipt")
    if isinstance(receipt, Mapping) and _text(receipt.get("schema_version")) == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return build_linkage_depth_case(
            case_id=_text(receipt.get("case_id")) or "disjointness_report",
            case_kind="wd_structural_fixture",
            lane_id=_text(receipt.get("lane_id")) or "disjointness_report",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id"))
            or WIKIDATA_DISJOINTNESS_REVIEW_LINKAGE_CONTRACT_ID,
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=[
                "Bounded disjointness case loaded from the bridge-emitted lane receipt.",
            ],
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            contract=receipt.get("contract") if isinstance(receipt.get("contract"), Mapping) else build_wikidata_disjointness_review_linkage_contract(),
        )
    return _build_disjointness_report_linkage_case_payload(report)


def build_wikidata_linkage_depth_case(case_id: str) -> dict[str, Any]:
    if case_id == "dog_soft_stitch":
        return build_dog_soft_stitch_linkage_case()
    if case_id == "climate_review_demonstrator":
        return build_climate_review_linkage_case()
    if case_id == "disjointness_report":
        return build_disjointness_report_linkage_case()
    raise ValueError(f"unknown linkage-depth case: {case_id}")


def _case_registry() -> list[str]:
    return ["dog_soft_stitch", "climate_review_demonstrator", "disjointness_report"]


def build_wikidata_linkage_depth_audit(case_id: str | None = None) -> dict[str, Any]:
    case_ids = [case_id] if case_id else _case_registry()
    cases = [build_wikidata_linkage_depth_case(selected_case_id) for selected_case_id in case_ids]
    return build_linkage_depth_audit(
        cases=cases,
        contracts=[
            build_sensiblaw_pnf_wd_linkage_contract(),
            build_wikidata_disjointness_review_linkage_contract(),
        ],
        audit_scope="bounded_pnf_x_zelph_wd_linkage_depth",
        schema_version=WIKIDATA_LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION,
        next_actions=[
            "Keep the PNF/document spine mandatory when adding future Zelph/WD bridge surfaces.",
            "Treat token->WD soft stitches as auxiliary hints; they do not satisfy linkage depth by themselves.",
            "Keep WD structural lanes on lane-level emitted receipts rather than teaching generic adapters lane-specific ladders.",
            "Only hand this surface to itir-svelte after linkage-depth remains complete on real fixtures.",
        ],
    )


__all__ = [
    "EXPECTED_LAYER_CONTRACT_SCHEMA_VERSION",
    "LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION",
    "SENSIBLAW_PNF_WD_LINKAGE_CONTRACT_ID",
    "WIKIDATA_DISJOINTNESS_REVIEW_LINKAGE_CONTRACT_ID",
    "WIKIDATA_LINKAGE_DEPTH_AUDIT_SCHEMA_VERSION",
    "WIKIDATA_LINKAGE_DEPTH_CASE_SCHEMA_VERSION",
    "audit_linkage_depth_case",
    "build_climate_review_linkage_case",
    "build_climate_review_linkage_receipt",
    "build_disjointness_report_linkage_case",
    "build_disjointness_report_linkage_receipt",
    "build_dog_soft_stitch_linkage_case",
    "build_linkage_depth_audit",
    "build_sensiblaw_pnf_wd_linkage_contract",
    "build_wikidata_disjointness_review_linkage_contract",
    "build_wikidata_linkage_depth_audit",
    "build_wikidata_linkage_depth_case",
    "linkage_depth_policy",
]
