"""Compact deterministic GWB and AU end-to-end resolution proofs."""
from __future__ import annotations

from typing import Any

from .resolution_evidence import (
    EvidenceRole,
    adapt_wikidata_snapshot,
    adapt_worldmonitor_snapshot,
    assess_entity_resolution,
    assess_event_resolution,
    assess_readiness,
    refine_partial_pnf_factor,
)


def run_gwb_resolution_proof() -> dict[str, Any]:
    bush_local = {
        "local_ref": "gwb:cluster:bush",
        "labels": ["George W. Bush", "Bush", "the president"],
        "aliases": ["President Bush"],
        "type_refs": ["person"],
    }
    wikidata = adapt_wikidata_snapshot(
        subject_ref="gwb:subject:bush",
        entity={
            "id": "Q207",
            "revision": "gwb-proof-rev-1",
            "labels": {"en": {"value": "George W. Bush"}},
            "aliases": {
                "en": [
                    {"value": "Bush"},
                    {"value": "President Bush"},
                ]
            },
            "properties": {"P31": [{"entity_ref": "person"}]},
        },
        requested_revision="gwb-proof-rev-1",
        provenance_refs=("fixture:gwb:wikidata",),
    ).to_dict()
    entity_assessment = assess_entity_resolution(
        subject_ref="gwb:subject:bush",
        local=bush_local,
        snapshot=wikidata,
    ).to_dict()

    event_local = {
        "local_ref": "gwb:event:september-11",
        "labels": [
            "9/11",
            "September 11",
            "September Eleven",
            "the attacks",
        ],
        "aliases": ["S11"],
        "type_refs": ["terrorist_attack"],
        "temporal": {"occurred_on": "2001-09-11"},
        "spatial": {"country": "United States"},
        "participants": {"affected_party": ["United States"]},
    }
    worldmonitor = adapt_worldmonitor_snapshot(
        subject_ref="gwb:event:september-11",
        record={
            "id": "wm:gwb:september-11",
            "title": "September 11 attacks",
            "canonical_aliases": ["9/11", "September Eleven"],
            "event_type": "terrorist_attack",
            "date": "2001-09-11",
            "country": "United States",
            "participants": {"affected_party": ["United States"]},
            "source_name": "fixture-source",
        },
        record_role=EvidenceRole.OCCURRENCE,
        snapshot_version="gwb-proof-v1",
        provenance_refs=("fixture:gwb:worldmonitor",),
    ).to_dict()
    event_assessment = assess_event_resolution(
        subject_ref="gwb:event:september-11",
        local=event_local,
        snapshot=worldmonitor,
    ).to_dict()

    pnf = {
        "partial_pnf_ref": "gwb:pnf:1",
        "slots": [
            {
                "slot_ref": "subject",
                "alternatives": ["gwb:cluster:bush"],
                "residual_refs": ["external_identity_unresolved"],
            },
            {
                "slot_ref": "eventuality",
                "alternatives": ["gwb:event:september-11"],
                "residual_refs": ["external_identity_unresolved"],
            },
        ],
    }
    pnf, subject_receipt = refine_partial_pnf_factor(
        partial_pnf=pnf,
        slot_ref="subject",
        assessments=(entity_assessment,),
    )
    pnf, event_receipt = refine_partial_pnf_factor(
        partial_pnf=pnf,
        slot_ref="eventuality",
        assessments=(event_assessment,),
    )
    readiness = assess_readiness(
        subject_ref="gwb:claim:1",
        partial_pnf=pnf,
        assessments=(entity_assessment, event_assessment),
        refinement_refs=(
            subject_receipt.refinement_ref,
            event_receipt.refinement_ref,
        ),
    ).to_dict()
    return {
        "proof_ref": "gwb:resolution-proof:v1",
        "entity_assessment": entity_assessment,
        "event_assessment": event_assessment,
        "refined_pnf": pnf,
        "refinement_receipts": [
            subject_receipt.to_dict(),
            event_receipt.to_dict(),
        ],
        "readiness": readiness,
    }


def run_au_resolution_proof() -> dict[str, Any]:
    court_local = {
        "local_ref": "au:entity:hca",
        "labels": ["High Court", "High Court of Australia"],
        "type_refs": ["court"],
    }
    snapshot = adapt_wikidata_snapshot(
        subject_ref="au:entity:hca",
        entity={
            "id": "Q421567",
            "revision": "au-proof-rev-1",
            "labels": {"en": {"value": "High Court of Australia"}},
            "aliases": {"en": [{"value": "High Court"}]},
            "properties": {"P31": [{"entity_ref": "court"}]},
        },
        requested_revision="au-proof-rev-1",
        provenance_refs=("fixture:au:wikidata",),
    ).to_dict()
    assessment = assess_entity_resolution(
        subject_ref="au:entity:hca",
        local=court_local,
        snapshot=snapshot,
    ).to_dict()
    pnf = {
        "partial_pnf_ref": "au:pnf:1",
        "slots": [
            {
                "slot_ref": "institution",
                "alternatives": ["au:entity:hca"],
                "residual_refs": ["external_identity_unresolved"],
            },
            {
                "slot_ref": "eventuality",
                "alternatives": ["judgment_delivered"],
                "residual_refs": [],
            },
            {
                "slot_ref": "legal_work",
                "alternatives": ["statute:fixture"],
                "residual_refs": [],
            },
        ],
    }
    refined, receipt = refine_partial_pnf_factor(
        partial_pnf=pnf,
        slot_ref="institution",
        assessments=(assessment,),
    )
    readiness = assess_readiness(
        subject_ref="au:claim:1",
        partial_pnf=refined,
        assessments=(assessment,),
        refinement_refs=(receipt.refinement_ref,),
    ).to_dict()
    return {
        "proof_ref": "au:resolution-proof:v1",
        "assessment": assessment,
        "refined_pnf": refined,
        "refinement_receipt": receipt.to_dict(),
        "readiness": readiness,
        "shared_semantics_only": True,
    }
