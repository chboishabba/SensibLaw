from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.structure_report import TextUnit
from src.storage.manifest_runtime import load_versioned_json_object, resolve_sensiblaw_manifest_path
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run

from .au_review_bundle import build_au_fact_review_bundle, build_fact_intake_payload_from_au_semantic_report
from .payload_mutations import append_payload_contestation, append_payload_observation, append_payload_review
from .read_model import (
    OBSERVATION_PREDICATE_TO_FAMILY,
    build_fact_intake_payload_from_text_units,
    persist_fact_intake_payload,
    record_fact_workflow_link,
)
from .transcript_review_bundle import build_fact_intake_payload_from_transcript_report, build_transcript_fact_review_bundle

FACT_REVIEW_ACCEPTANCE_FIXTURE_MANIFEST_VERSION = "fact.review.acceptance.fixtures.v1"


_DEFAULT_MANIFEST_BY_WAVE: dict[str, str] = {
    "wave1_legal": "wave1_legal_fixture_manifest_v1.json",
    "wave2_balanced": "wave2_balanced_fixture_manifest_v1.json",
    "wave3_trauma_advocacy": "wave3_trauma_advocacy_fixture_manifest_v1.json",
    "wave3_public_knowledge": "wave3_public_knowledge_fixture_manifest_v1.json",
    "wave4_family_law": "wave4_family_law_fixture_manifest_v1.json",
    "wave4_medical_regulatory": "wave4_medical_regulatory_fixture_manifest_v1.json",
    "wave5_handoff_false_coherence": "wave5_handoff_false_coherence_fixture_manifest_v1.json",
}


def default_fact_review_fixture_manifest_path(wave: str = "wave1_legal") -> Path:
    filename = _DEFAULT_MANIFEST_BY_WAVE.get(wave)
    if filename is None:
        raise ValueError(f"unsupported fixture manifest wave: {wave}")
    return resolve_sensiblaw_manifest_path("data", "fact_review", filename)


def default_wave1_fixture_manifest_path() -> Path:
    return default_fact_review_fixture_manifest_path("wave1_legal")


def _manifest_fixtures(path: Path | None = None, *, wave: str = "wave1_legal") -> list[dict[str, Any]]:
    manifest_path = path or default_fact_review_fixture_manifest_path(wave)
    payload = load_versioned_json_object(
        manifest_path,
        expected_version=FACT_REVIEW_ACCEPTANCE_FIXTURE_MANIFEST_VERSION,
    )
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("fixture manifest fixtures must be a list")
    return [dict(row) for row in fixtures if isinstance(row, Mapping)]


def load_fact_review_acceptance_fixture_manifest(path: Path | None = None, *, wave: str = "wave1_legal") -> dict[str, Any]:
    manifest_path = path or default_fact_review_fixture_manifest_path(wave)
    return load_versioned_json_object(
        manifest_path,
        expected_version=FACT_REVIEW_ACCEPTANCE_FIXTURE_MANIFEST_VERSION,
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    ensure_au_semantic_schema(conn)
    return conn


def _append_observation(
    payload: dict[str, Any],
    *,
    fixture_key: str,
    statement_index: int,
    predicate_key: str,
    object_text: str,
    object_type: str,
    subject_text: str | None = None,
    object_ref: str | None = None,
    observation_status: str = "captured",
    provenance: Mapping[str, Any] | None = None,
) -> None:
    append_payload_observation(
        payload,
        statement_index=statement_index,
        predicate_key=predicate_key,
        predicate_family=OBSERVATION_PREDICATE_TO_FAMILY[predicate_key],
        object_text=object_text,
        object_type=object_type,
        subject_text=subject_text,
        object_ref=object_ref,
        observation_status=observation_status,
        identity_fields={
            "fixture_key": fixture_key,
            "statement_id": payload["statements"][statement_index]["statement_id"],
            "predicate_key": predicate_key,
            "object_text": object_text,
        },
        provenance=dict(provenance or {"source": "acceptance_fixture", "fixture_key": fixture_key}),
    )


def _append_review(
    payload: dict[str, Any],
    *,
    fixture_key: str,
    fact_index: int,
    review_status: str,
    note: str,
) -> None:
    append_payload_review(
        payload,
        fact_index=fact_index,
        review_status=review_status,
        reviewer="mary-parity-acceptance",
        note=note,
        identity_fields={
            "fixture_key": fixture_key,
            "fact_id": payload["fact_candidates"][fact_index]["fact_id"],
            "review_status": review_status,
            "note": note,
        },
        provenance={"source": "acceptance_fixture", "fixture_key": fixture_key},
    )


def _append_contestation(
    payload: dict[str, Any],
    *,
    fixture_key: str,
    fact_index: int,
    statement_index: int,
    reason_text: str,
    status: str = "disputed",
    contestation_scope: str | None = None,
) -> None:
    append_payload_contestation(
        payload,
        fact_index=fact_index,
        statement_index=statement_index,
        status=status,
        reason_text=reason_text,
        author="mary-parity-acceptance",
        identity_fields={
            "fixture_key": fixture_key,
            "fact_id": payload["fact_candidates"][fact_index]["fact_id"],
            "statement_id": payload["statements"][statement_index]["statement_id"],
            "reason_text": reason_text,
        },
        provenance={
            "source": "acceptance_fixture",
            "fixture_key": fixture_key,
            **({"contestation_scope": contestation_scope} if contestation_scope else {}),
        },
    )


def _set_source_signal_classes(payload: dict[str, Any], mapping: Mapping[str, list[str]]) -> None:
    for source in payload.get("sources", []):
        source_type = str(source.get("source_type") or "")
        signals = mapping.get(source_type)
        if not signals:
            continue
        provenance = source.get("provenance") if isinstance(source.get("provenance"), Mapping) else {}
        source["provenance"] = {**provenance, "source_signal_classes": list(signals)}


def _persist_and_link(
    conn: sqlite3.Connection,
    *,
    workflow_kind: str,
    workflow_run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    persist_fact_intake_payload(conn, payload)
    record_fact_workflow_link(
        conn,
        workflow_kind=workflow_kind,
        workflow_run_id=workflow_run_id,
        fact_run_id=payload["run"]["run_id"],
        source_label=payload["run"]["source_label"],
    )
    return {
        "fact_run_id": payload["run"]["run_id"],
        "workflow_kind": workflow_kind,
        "workflow_run_id": workflow_run_id,
        "source_label": payload["run"]["source_label"],
    }


def _build_real_transcript_intake_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("triage-1", "client_intake", "interview_note", "The client said the police visit happened after midnight on 2024-01-05."),
        TextUnit("triage-2", "call_recording", "transcript_file", "Q: Who arrived first? A: I think my brother was already there."),
        TextUnit("triage-3", "staff_followup", "annotation_note", "Later note: a hospital discharge summary suggests the visit may have been on 2024-01-06."),
    ]
    workflow_run_id = "transcript_acceptance_real_intake_v1"
    with _connect(db_path) as conn:
        result = run_transcript_semantic_pipeline(
            conn,
            units,
            known_participants_by_source={"client_intake": ["client"], "call_recording": ["client", "brother"]},
            run_id=workflow_run_id,
        )
        semantic_report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
        payload = build_fact_intake_payload_from_transcript_report(
            semantic_report,
            source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
            notes="Wave 1 legal acceptance transcript intake fixture",
        )
        payload["fact_candidates"][0]["canonical_label"] = "Police visit timing"
        payload["fact_candidates"][0]["chronology_sort_key"] = "2024-01-05"
        payload["fact_candidates"][0]["chronology_label"] = "2024-01-05"
        payload["fact_candidates"][1]["canonical_label"] = "Brother arrival timing"
        payload["fact_candidates"][2]["canonical_label"] = "Hospital summary note"
        _set_source_signal_classes(
            payload,
            {
                "interview_note": ["party_material"],
                "transcript_file": ["procedural_record"],
                "annotation_note": ["later_annotation"],
            },
        )
        _append_observation(
            payload,
            fixture_key="real_transcript_intake_v1_date",
            statement_index=0,
            predicate_key="event_date",
            object_text="2024-01-05",
            object_type="date",
            provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_intake_v1_date", "signal_classes": ["party_assertion"]},
        )
        _append_observation(
            payload,
            fixture_key="real_transcript_intake_v1_actor",
            statement_index=0,
            predicate_key="actor",
            object_text="Client",
            object_type="person",
            provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_intake_v1_actor", "signal_classes": ["party_assertion"]},
        )
        _append_review(payload, fixture_key="real_transcript_intake_v1_review", fact_index=0, review_status="needs_followup", note="Confirm which date is supported by the primary record.")
        _append_contestation(payload, fixture_key="real_transcript_intake_v1_conflict", fact_index=0, statement_index=2, reason_text="Later note points to a different date for the visit.", contestation_scope="chronology")
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id=result["run_id"], payload=payload)
        bundle = build_transcript_fact_review_bundle(conn, fact_run_id=payload["run"]["run_id"], semantic_report=semantic_report)
    return {**dict(fixture), **persisted, "semantic_run_id": workflow_run_id, "bundle_version": bundle["version"]}


def _seed_au_timeline_fixture(db_path: Path, fixture_key: str, events: list[dict[str, Any]]) -> str:
    timeline_path = db_path.parent / f"{fixture_key}_timeline_aoo.json"
    payload = {
        "generated_at": "2026-03-15T00:00:00Z",
        "parser": {"name": "acceptance_fixture"},
        "source_timeline": {"path": str(timeline_path), "snapshot": None},
        "events": events,
    }
    persisted = persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=payload, timeline_path=timeline_path)
    return persisted.run_id


def _seed_au_linkage(conn: sqlite3.Connection) -> None:
    seed_path = resolve_sensiblaw_manifest_path("data", "ontology", "au_semantic_linkage_seed_v1.json")
    seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
    import_au_semantic_seed_payload(conn, seed_payload)


def _build_real_au_procedural_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    timeline_suffix = "real_au_procedural_v1_timeline_aoo.json"
    timeline_run_id = _seed_au_timeline_fixture(
        db_path,
        "real_au_procedural_v1",
        [
            {
                "event_id": "au-ev-1",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "The plaintiff claimed the privative clause denied review, and the Commonwealth denied that challenge before the High Court.",
            },
            {
                "event_id": "au-ev-2",
                "anchor": {"year": 2003, "text": "2003-06-01"},
                "section": "Orders",
                "text": "The High Court ruled on the challenge and ordered the matter to proceed.",
            },
            {
                "event_id": "au-ev-3",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Criminal appeal",
                "text": "In House v The King the appellant appealed and the matter was heard by the High Court.",
            },
        ],
    )
    with _connect(db_path) as conn:
        _seed_au_linkage(conn)
        result = run_au_semantic_pipeline(conn, timeline_suffix=timeline_suffix)
        semantic_report = build_au_semantic_report(conn, run_id=result["run_id"])
        source_payload = load_run_payload_from_normalized(conn, timeline_run_id)
        source_events = source_payload.get("events") if isinstance(source_payload, Mapping) and isinstance(source_payload.get("events"), list) else []
        if not source_events:
            source_events = [
                {"event_id": row.get("event_id"), "text": row.get("text"), "anchor": row.get("anchor"), "section": row.get("section")}
                for row in semantic_report.get("per_event", [])
                if isinstance(row, Mapping)
            ]
        payload = build_fact_intake_payload_from_au_semantic_report(
            semantic_report,
            timeline_events=source_events,
            source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
            notes="Wave 1 legal acceptance AU procedural fixture",
        )
        _set_source_signal_classes(payload, {"timeline_payload": ["procedural_record"]})
        for row in payload["fact_candidates"]:
            row["candidate_status"] = "candidate"
        _append_observation(payload, fixture_key="real_au_procedural_v1_claimed", statement_index=0, predicate_key="claimed", object_text="Judicial review challenge", object_type="legal_claim", subject_text="Plaintiff")
        _append_observation(payload, fixture_key="real_au_procedural_v1_denied", statement_index=0, predicate_key="denied", object_text="Judicial review challenge", object_type="legal_claim", subject_text="Commonwealth of Australia")
        _append_observation(payload, fixture_key="real_au_procedural_v1_ruled", statement_index=1, predicate_key="ruled", object_text="Judicial review challenge", object_type="procedural_outcome", subject_text="High Court of Australia")
        _append_observation(payload, fixture_key="real_au_procedural_v1_ordered", statement_index=1, predicate_key="ordered", object_text="matter to proceed", object_type="procedural_outcome", subject_text="High Court of Australia")
        _append_review(payload, fixture_key="real_au_procedural_v1_review", fact_index=0, review_status="needs_followup", note="Confirm whether the claim or denial is supported by the judgment text.")
        _append_contestation(payload, fixture_key="real_au_procedural_v1_contest", fact_index=0, statement_index=0, reason_text="Competing accounts of what was denied affect the procedural chronology.", contestation_scope="chronology")
        persisted = _persist_and_link(conn, workflow_kind="au_semantic", workflow_run_id=result["run_id"], payload=payload)
        bundle = build_au_fact_review_bundle(
            conn,
            fact_run_id=payload["run"]["run_id"],
            semantic_report=semantic_report,
            source_events=source_events,
        )
    return {**dict(fixture), **persisted, "semantic_run_id": result["run_id"], "bundle_version": bundle["version"]}


def _build_synthetic_sparse_dates_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("sd-1", "support_note", "interview_note", "The incident happened around early March 2024."),
        TextUnit("sd-2", "support_note", "interview_note", "Two days later there was another confrontation."),
        TextUnit("sd-3", "filing_note", "annotation_note", "No witness is identified in the note."),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label=str(fixture.get("source_label") or fixture.get("fixture_id")), notes="Wave 1 synthetic sparse chronology fixture")
    payload["fact_candidates"][0]["canonical_label"] = "Incident timing"
    payload["fact_candidates"][0]["chronology_sort_key"] = "early March 2024"
    payload["fact_candidates"][0]["chronology_label"] = "early March 2024"
    payload["fact_candidates"][1]["canonical_label"] = "Second confrontation"
    payload["fact_candidates"][1]["chronology_sort_key"] = "two days later"
    payload["fact_candidates"][1]["chronology_label"] = "two days later"
    payload["fact_candidates"][2]["canonical_label"] = "Anonymous note"
    _set_source_signal_classes(
        payload,
        {
            "interview_note": ["party_material"],
            "annotation_note": ["later_annotation"],
        },
    )
    for index in (0, 1):
        payload["fact_candidates"][index]["candidate_status"] = "candidate"
    _append_observation(
        payload,
        fixture_key="synthetic_sparse_dates_actor",
        statement_index=0,
        predicate_key="actor",
        object_text="Client",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_sparse_dates_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_sparse_dates_date1",
        statement_index=0,
        predicate_key="event_date",
        object_text="early March 2024",
        object_type="date_hint",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_sparse_dates_date1", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_sparse_dates_action1",
        statement_index=0,
        predicate_key="performed_action",
        object_text="incident",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_sparse_dates_action1", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_sparse_dates_relation",
        statement_index=1,
        predicate_key="sequence_marker",
        object_text="two days later",
        object_type="temporal_phrase",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_sparse_dates_relation", "signal_classes": ["procedural_context"]},
    )
    _append_observation(payload, fixture_key="synthetic_sparse_dates_action2", statement_index=1, predicate_key="performed_action", object_text="confrontation", object_type="action")
    _append_review(payload, fixture_key="synthetic_sparse_dates_review", fact_index=1, review_status="needs_followup", note="Anchor the relative timing to a dated event.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_sparse_dates_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_sparse_dates_v1"}


def _build_synthetic_assertion_outcome_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("ao-1", "party_material", "party_submission", "The applicant claimed the order was invalid."),
        TextUnit("ao-2", "party_material", "party_submission", "The respondent denied the allegation."),
        TextUnit("ao-3", "court_record", "judgment_extract", "The Court ruled that the order was valid and ordered costs."),
        TextUnit("ao-4", "internal_note", "annotation_note", "Later note: counsel says the costs order may be limited."),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label=str(fixture.get("source_label") or fixture.get("fixture_id")), notes="Wave 1 synthetic assertion/outcome fixture")
    labels = ("Applicant claim", "Respondent denial", "Court ruling", "Later annotation")
    for row, label in zip(payload["fact_candidates"], labels):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "party_submission": ["party_material"],
            "judgment_extract": ["procedural_record"],
            "annotation_note": ["later_annotation"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_assertion_claim", statement_index=0, predicate_key="claimed", object_text="order invalidity", object_type="legal_claim", subject_text="Applicant")
    _append_observation(payload, fixture_key="synthetic_assertion_claim_actor", statement_index=0, predicate_key="actor", object_text="Applicant", object_type="person")
    _append_observation(payload, fixture_key="synthetic_assertion_denied", statement_index=1, predicate_key="denied", object_text="order invalidity", object_type="legal_claim", subject_text="Respondent")
    _append_observation(payload, fixture_key="synthetic_assertion_denied_actor", statement_index=1, predicate_key="actor", object_text="Respondent", object_type="person")
    _append_observation(payload, fixture_key="synthetic_assertion_ruled", statement_index=2, predicate_key="ruled", object_text="order validity", object_type="procedural_outcome", subject_text="Court")
    _append_observation(payload, fixture_key="synthetic_assertion_ordered", statement_index=2, predicate_key="ordered", object_text="costs", object_type="procedural_outcome", subject_text="Court")
    _append_observation(payload, fixture_key="synthetic_assertion_court_actor", statement_index=2, predicate_key="actor", object_text="Court", object_type="institution")
    _append_review(payload, fixture_key="synthetic_assertion_review", fact_index=2, review_status="needs_followup", note="Keep the court outcome distinct from party assertions and the later note.")
    _append_contestation(payload, fixture_key="synthetic_assertion_note_conflict", fact_index=2, statement_index=3, reason_text="Later annotation may narrow the costs order.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="au_semantic", workflow_run_id="synthetic_assertion_outcome_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_assertion_outcome_v1"}


def _build_synthetic_conflict_cluster_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("cc-1", "witness_a", "affidavit", "Witness A says the arrest was on 2024-04-01."),
        TextUnit("cc-2", "witness_b", "affidavit", "Witness B says the arrest was on 2024-04-03."),
        TextUnit("cc-3", "court_record", "transcript_file", "The hearing proceeded after the disputed arrest date."),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label=str(fixture.get("source_label") or fixture.get("fixture_id")), notes="Wave 1 synthetic chronology conflict fixture")
    for index, label in enumerate(("Witness A arrest date", "Witness B arrest date", "Hearing sequence"), start=0):
        payload["fact_candidates"][index]["canonical_label"] = label
        payload["fact_candidates"][index]["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "affidavit": ["party_material"],
            "transcript_file": ["procedural_record"],
        },
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_a_actor",
        statement_index=0,
        predicate_key="actor",
        object_text="Witness A",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_a_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_a_date",
        statement_index=0,
        predicate_key="event_date",
        object_text="2024-04-01",
        object_type="date",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_a_date", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_a_action",
        statement_index=0,
        predicate_key="performed_action",
        object_text="arrest",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_a_action", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_b_actor",
        statement_index=1,
        predicate_key="actor",
        object_text="Witness B",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_b_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_b_date",
        statement_index=1,
        predicate_key="event_date",
        object_text="2024-04-03",
        object_type="date",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_b_date", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_b_action",
        statement_index=1,
        predicate_key="performed_action",
        object_text="arrest",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_b_action", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_conflict_seq",
        statement_index=2,
        predicate_key="sequence_marker",
        object_text="after the disputed arrest date",
        object_type="temporal_phrase",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_conflict_seq", "signal_classes": ["procedural_context"]},
    )
    _append_review(payload, fixture_key="synthetic_conflict_review", fact_index=0, review_status="needs_followup", note="Resolve arrest chronology before relying on the sequence.")
    _append_contestation(payload, fixture_key="synthetic_conflict_contest", fact_index=0, statement_index=1, reason_text="Another source gives a different arrest date, creating a chronology conflict.", contestation_scope="chronology")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_conflict_cluster_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_conflict_cluster_v1"}


def _build_synthetic_personal_fragments_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("pf-1", "phone_note", "personal_note", "I think the clinic call was sometime in late February."),
        TextUnit("pf-2", "screenshot_dump", "screenshot_note", "Screenshot reminder says the meeting happened after the clinic call."),
        TextUnit("pf-3", "voice_memo", "voice_memo_note", "I am not sure whether the follow-up happened that same week."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 2 synthetic personal reconstruction fixture",
    )
    labels = ("Clinic call memory", "Meeting reminder fragment", "Follow-up uncertainty")
    for row, label in zip(payload["fact_candidates"], labels):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    payload["fact_candidates"][0]["chronology_sort_key"] = "late February"
    payload["fact_candidates"][0]["chronology_label"] = "late February"
    payload["fact_candidates"][1]["chronology_sort_key"] = "after clinic call"
    payload["fact_candidates"][1]["chronology_label"] = "after clinic call"
    payload["fact_candidates"][2]["candidate_status"] = "abstained"
    _set_source_signal_classes(
        payload,
        {
            "personal_note": ["party_material"],
            "screenshot_note": ["party_material"],
            "voice_memo_note": ["later_annotation"],
        },
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_actor",
        statement_index=0,
        predicate_key="actor",
        object_text="User",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_personal_fragments_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_action",
        statement_index=0,
        predicate_key="performed_action",
        object_text="clinic call",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_personal_fragments_action", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_date",
        statement_index=0,
        predicate_key="event_date",
        object_text="late February",
        object_type="date_hint",
        provenance={
            "source": "acceptance_fixture",
            "fixture_key": "synthetic_personal_fragments_date",
            "signal_classes": ["party_assertion"],
            "time_precision": "approximate",
        },
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_sequence",
        statement_index=1,
        predicate_key="sequence_marker",
        object_text="after the clinic call",
        object_type="temporal_phrase",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_personal_fragments_sequence", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_meeting",
        statement_index=1,
        predicate_key="performed_action",
        object_text="meeting",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_personal_fragments_meeting", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_personal_fragments_uncertain",
        statement_index=2,
        predicate_key="event_time",
        object_text="that same week",
        object_type="temporal_phrase",
        observation_status="abstained",
        provenance={
            "source": "acceptance_fixture",
            "fixture_key": "synthetic_personal_fragments_uncertain",
            "signal_classes": ["later_annotation"],
            "time_precision": "approximate",
        },
    )
    _append_review(
        payload,
        fixture_key="synthetic_personal_fragments_review",
        fact_index=2,
        review_status="needs_followup",
        note="Keep the follow-up fragment visible without forcing a dated placement.",
    )
    _append_contestation(
        payload,
        fixture_key="synthetic_personal_fragments_contest",
        fact_index=1,
        statement_index=2,
        reason_text="Voice memo uncertainty means the follow-up sequence may be incomplete.",
        contestation_scope="chronology",
    )
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_personal_fragments_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_personal_fragments_v1"}


def _build_synthetic_investigative_reopen_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("ir-1", "field_note", "investigator_note", "Source A says the transfer happened on 2024-06-01."),
        TextUnit("ir-2", "email_extract", "document_note", "Email record suggests the transfer may have been approved two days later."),
        TextUnit("ir-3", "hearing_extract", "transcript_file", "At hearing, counsel disputed whether the approval covered the same transfer."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 2 synthetic investigative reopen fixture",
    )
    labels = ("Transfer date", "Approval timing", "Hearing dispute")
    for row, label in zip(payload["fact_candidates"], labels):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    payload["fact_candidates"][0]["chronology_sort_key"] = "2024-06-01"
    payload["fact_candidates"][0]["chronology_label"] = "2024-06-01"
    payload["fact_candidates"][1]["chronology_sort_key"] = "two days later"
    payload["fact_candidates"][1]["chronology_label"] = "two days later"
    _set_source_signal_classes(
        payload,
        {
            "investigator_note": ["party_material"],
            "document_note": ["procedural_record"],
            "transcript_file": ["procedural_record"],
        },
    )
    _append_observation(
        payload,
        fixture_key="synthetic_investigative_reopen_actor",
        statement_index=0,
        predicate_key="actor",
        object_text="Source A",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_investigative_reopen_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_investigative_reopen_transfer",
        statement_index=0,
        predicate_key="performed_action",
        object_text="transfer",
        object_type="action",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_investigative_reopen_transfer", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_investigative_reopen_date",
        statement_index=0,
        predicate_key="event_date",
        object_text="2024-06-01",
        object_type="date",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_investigative_reopen_date", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="synthetic_investigative_reopen_approval",
        statement_index=1,
        predicate_key="sequence_marker",
        object_text="two days later",
        object_type="temporal_phrase",
        provenance={
            "source": "acceptance_fixture",
            "fixture_key": "synthetic_investigative_reopen_approval",
            "signal_classes": ["procedural_context"],
            "time_precision": "approximate",
        },
    )
    _append_observation(
        payload,
        fixture_key="synthetic_investigative_reopen_claim",
        statement_index=2,
        predicate_key="claimed",
        object_text="approval dispute",
        object_type="legal_claim",
        subject_text="Counsel",
        provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_investigative_reopen_claim", "signal_classes": ["procedural_context"]},
    )
    _append_review(
        payload,
        fixture_key="synthetic_investigative_reopen_review",
        fact_index=1,
        review_status="needs_followup",
        note="Reopen the run later to compare the email timing against the hearing dispute.",
    )
    _append_contestation(
        payload,
        fixture_key="synthetic_investigative_reopen_contest",
        fact_index=1,
        statement_index=2,
        reason_text="Hearing record disputes whether the approval covered the same transfer.",
        contestation_scope="chronology",
    )
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_investigative_reopen_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_investigative_reopen_v1"}


def _build_real_transcript_fragmented_support_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("ts-1", "survivor_note", "survivor_note", "I think the first incident was in early April, but I am not ready to pin the exact date down."),
        TextUnit("ts-2", "support_worker_note", "support_worker_note", "Support worker note: user wants the hospital contact kept separate from later service follow-up."),
        TextUnit("ts-3", "service_record", "service_record", "Service intake record notes a clinic presentation on 2024-04-09."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 trauma/advocacy fragmented support fixture",
    )
    labels = ("User incident fragment", "Support-worker context note", "Clinic presentation record")
    for row, label in zip(payload["fact_candidates"], labels):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    payload["fact_candidates"][0]["chronology_sort_key"] = "early April 2024"
    payload["fact_candidates"][0]["chronology_label"] = "early April 2024"
    payload["fact_candidates"][1]["candidate_status"] = "abstained"
    payload["fact_candidates"][2]["chronology_sort_key"] = "2024-04-09"
    payload["fact_candidates"][2]["chronology_label"] = "2024-04-09"
    _set_source_signal_classes(
        payload,
        {
            "survivor_note": ["user_authored", "party_material"],
            "support_worker_note": ["support_worker_note", "later_annotation"],
            "service_record": ["third_party_record", "procedural_record"],
        },
    )
    _append_observation(
        payload,
        fixture_key="real_transcript_fragmented_support_actor",
        statement_index=0,
        predicate_key="actor",
        object_text="User",
        object_type="person",
        provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_fragmented_support_actor", "signal_classes": ["party_assertion"]},
    )
    _append_observation(
        payload,
        fixture_key="real_transcript_fragmented_support_date",
        statement_index=0,
        predicate_key="event_date",
        object_text="early April 2024",
        object_type="date_hint",
        provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_fragmented_support_date", "signal_classes": ["party_assertion"], "time_precision": "approximate"},
    )
    _append_observation(
        payload,
        fixture_key="real_transcript_fragmented_support_abstain",
        statement_index=1,
        predicate_key="event_time",
        object_text="not ready to specify",
        object_type="temporal_phrase",
        observation_status="abstained",
        provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_fragmented_support_abstain", "signal_classes": ["later_annotation"], "time_precision": "approximate"},
    )
    _append_observation(
        payload,
        fixture_key="real_transcript_fragmented_support_record",
        statement_index=2,
        predicate_key="event_date",
        object_text="2024-04-09",
        object_type="date",
        provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_fragmented_support_record", "signal_classes": ["procedural_context"]},
    )
    _append_review(payload, fixture_key="real_transcript_fragmented_support_review", fact_index=1, review_status="needs_followup", note="Keep the support note as context, not as a replacement for the user fragment.")
    _append_contestation(payload, fixture_key="real_transcript_fragmented_support_contest", fact_index=0, statement_index=2, reason_text="Service record anchors one later event but does not settle the earlier incident date.", contestation_scope="chronology")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="real_transcript_fragmented_support_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "real_transcript_fragmented_support_v1"}


def _build_synthetic_trauma_fragment_cluster_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("tf-1", "journal", "survivor_note", "I remember leaving before dawn, maybe around the end of May."),
        TextUnit("tf-2", "journal", "survivor_note", "Another fragment says it might have been the following week."),
        TextUnit("tf-3", "later_note", "annotation_note", "Later note: sequence uncertain; do not collapse the fragments."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic trauma fragment cluster fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Leaving fragment", "Alternative fragment", "Do-not-collapse note")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    payload["fact_candidates"][2]["candidate_status"] = "abstained"
    _set_source_signal_classes(
        payload,
        {
            "survivor_note": ["user_authored", "party_material"],
            "annotation_note": ["later_annotation"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_trauma_fragment_cluster_a", statement_index=0, predicate_key="event_date", object_text="end of May", object_type="date_hint", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trauma_fragment_cluster_a", "signal_classes": ["party_assertion"], "time_precision": "approximate"})
    _append_observation(payload, fixture_key="synthetic_trauma_fragment_cluster_b", statement_index=1, predicate_key="event_date", object_text="the following week", object_type="temporal_phrase", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trauma_fragment_cluster_b", "signal_classes": ["party_assertion"], "time_precision": "approximate"})
    _append_observation(payload, fixture_key="synthetic_trauma_fragment_cluster_note", statement_index=2, predicate_key="sequence_marker", object_text="do not collapse the fragments", object_type="temporal_phrase", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trauma_fragment_cluster_note", "signal_classes": ["later_annotation"]})
    _append_contestation(payload, fixture_key="synthetic_trauma_fragment_cluster_conflict", fact_index=0, statement_index=1, reason_text="Fragments disagree on timing and should remain unresolved.", contestation_scope="chronology")
    _append_review(payload, fixture_key="synthetic_trauma_fragment_cluster_review", fact_index=2, review_status="needs_followup", note="Preserve abstention and uncertainty instead of forcing sequence.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_trauma_fragment_cluster_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_trauma_fragment_cluster_v1"}


def _build_synthetic_support_worker_handoff_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("sh-1", "client_note", "survivor_note", "User note: the complaint call happened before the housing meeting."),
        TextUnit("sh-2", "advocate_file", "support_worker_note", "Advocate note: preserve the user wording and mark the housing timing as unresolved."),
        TextUnit("sh-3", "agency_record", "service_record", "Agency email confirms a housing meeting on 2024-08-14."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic support-worker handoff fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Complaint call", "Advocate handoff note", "Housing meeting")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    payload["fact_candidates"][0]["chronology_sort_key"] = "before housing meeting"
    payload["fact_candidates"][0]["chronology_label"] = "before housing meeting"
    payload["fact_candidates"][2]["chronology_sort_key"] = "2024-08-14"
    payload["fact_candidates"][2]["chronology_label"] = "2024-08-14"
    _set_source_signal_classes(
        payload,
        {
            "survivor_note": ["user_authored", "party_material"],
            "support_worker_note": ["support_worker_note", "later_annotation"],
            "service_record": ["third_party_record", "procedural_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_support_worker_handoff_seq", statement_index=0, predicate_key="sequence_marker", object_text="before the housing meeting", object_type="temporal_phrase", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_support_worker_handoff_seq", "signal_classes": ["party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_support_worker_handoff_date", statement_index=2, predicate_key="event_date", object_text="2024-08-14", object_type="date", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_support_worker_handoff_date", "signal_classes": ["procedural_context"]})
    _append_review(payload, fixture_key="synthetic_support_worker_handoff_review", fact_index=1, review_status="needs_followup", note="Support-facing summary should preserve user wording and unresolved timing.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_support_worker_handoff_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_support_worker_handoff_v1"}


def _build_real_gwb_contested_public_figure_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit(
            "gwb-1",
            "wiki_page",
            "wiki_article",
            "Revision by GWBModerator: Reverted unqualified unlawful framing until judgment scope is checked.",
        ),
        TextUnit("gwb-2", "hearing_record", "transcript_file", "At hearing, counsel disputed that the public summary captured the legal posture."),
        TextUnit("gwb-3", "judgment_extract", "judgment_extract", "The judgment describes procedural findings and limits the scope of the ruling."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 real-like GWB contested public-figure fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Public summary claim", "Hearing dispute", "Judgment scope")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "wiki_article": ["public_summary", "wiki_article", "weak_public_source", "revision_history"],
            "transcript_file": ["procedural_record", "strong_legal_source"],
            "judgment_extract": ["legal_record", "strong_legal_source", "procedural_record"],
        },
    )
    _append_observation(payload, fixture_key="real_gwb_contested_public_figure_claim", statement_index=0, predicate_key="claimed", object_text="program unlawfulness", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "real_gwb_contested_public_figure_claim", "signal_classes": ["public_summary_claim", "overstatement_risk"]})
    _append_observation(payload, fixture_key="real_gwb_contested_public_figure_ruled", statement_index=2, predicate_key="ruled", object_text="procedural limits", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "real_gwb_contested_public_figure_ruled", "signal_classes": ["procedural_outcome"]})
    _append_contestation(payload, fixture_key="real_gwb_contested_public_figure_contest", fact_index=0, statement_index=1, reason_text="Public summary may overstate the narrower legal record.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="real_gwb_contested_public_figure_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "real_gwb_contested_public_figure_v1"}


def _build_synthetic_trump_public_figure_legality_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("tp-1", "public_timeline", "wiki_article", "Public summary says the conduct was plainly illegal."),
        TextUnit("tp-2", "charge_record", "judgment_extract", "Charging and court material show allegations, denials, and procedural rulings."),
        TextUnit("tp-3", "hearing_notes", "transcript_file", "At hearing, counsel disputed whether the public timeline collapsed allegations into findings."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic Trump-style public-figure legality fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Public illegality claim", "Procedural/legal record", "Hearing challenge")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "wiki_article": ["public_summary", "wiki_article", "weak_public_source"],
            "judgment_extract": ["legal_record", "strong_legal_source", "procedural_record"],
            "transcript_file": ["procedural_record", "strong_legal_source"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_trump_public_figure_legality_claim", statement_index=0, predicate_key="claimed", object_text="plain illegality", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trump_public_figure_legality_claim", "signal_classes": ["public_summary_claim", "overstatement_risk"]})
    _append_observation(payload, fixture_key="synthetic_trump_public_figure_legality_denied", statement_index=1, predicate_key="denied", object_text="plain illegality", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trump_public_figure_legality_denied", "signal_classes": ["party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_trump_public_figure_legality_ruled", statement_index=1, predicate_key="ruled", object_text="procedural posture only", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_trump_public_figure_legality_ruled", "signal_classes": ["procedural_outcome"]})
    _append_review(payload, fixture_key="synthetic_trump_public_figure_legality_review", fact_index=0, review_status="needs_followup", note="Keep the public illegality framing separate from the procedural record.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_trump_public_figure_legality_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_trump_public_figure_legality_v1"}


def _build_synthetic_wikipedia_defamation_review_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit(
            "wd-1",
            "article_text",
            "wiki_article",
            "Revision by ExampleEditor: Reverted unqualified accusation wording pending attribution.",
        ),
        TextUnit("wd-2", "reporting", "reporting_note", "Reporting attributes the accusation to named sources."),
        TextUnit("wd-3", "record", "judgment_extract", "The legal record remains narrower and partly procedural."),
        TextUnit("wd-4", "editor", "editor_note", "Editor note: wording may create defamation risk if left unqualified."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic Wikipedia defamation review fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Article accusation", "Attributed reporting", "Legal record", "Editor caution")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "wiki_article": ["public_summary", "wiki_article", "weak_public_source", "revision_history"],
            "reporting_note": ["reporting_source", "public_summary"],
            "judgment_extract": ["legal_record", "strong_legal_source", "procedural_record"],
            "editor_note": ["editorial_note", "later_annotation"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_wikipedia_defamation_review_claim", statement_index=0, predicate_key="claimed", object_text="accusation", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wikipedia_defamation_review_claim", "signal_classes": ["public_summary_claim", "unsupported_assertion"]})
    _append_observation(payload, fixture_key="synthetic_wikipedia_defamation_review_note", statement_index=3, predicate_key="sequence_marker", object_text="qualify or attribute the wording", object_type="note", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wikipedia_defamation_review_note", "signal_classes": ["editorial_framing"]})
    _append_contestation(payload, fixture_key="synthetic_wikipedia_defamation_review_contest", fact_index=0, statement_index=3, reason_text="Article wording may overstate or defame if not attributed.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_wikipedia_defamation_review_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_wikipedia_defamation_review_v1"}


def _build_synthetic_wikidata_claim_worker_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("wc-1", "wikidata_claim", "wikidata_claim_sheet", "Claim sheet links a public figure, an office, and a contested action claim."),
        TextUnit("wc-2", "office_record", "office_record", "Office record distinguishes the office-holder from the institution."),
        TextUnit("wc-3", "institutional_record", "institutional_record", "Institutional record separates agency action from personal action."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic Wikidata claim worker fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Contested claim sheet", "Office-holder boundary", "Institutional boundary")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "wikidata_claim_sheet": ["wikidata_claim", "public_summary"],
            "office_record": ["office_record", "strong_legal_source"],
            "institutional_record": ["institutional_record", "jurisdiction_record", "strong_legal_source"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_wikidata_claim_worker_identity", statement_index=0, predicate_key="actor_role", object_text="office-holder", object_type="role", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wikidata_claim_worker_identity", "signal_classes": ["identity_claim", "structural_ambiguity", "office_holder_role"]})
    _append_observation(payload, fixture_key="synthetic_wikidata_claim_worker_actor", statement_index=1, predicate_key="actor", object_text="Office-holder", object_type="person")
    _append_observation(payload, fixture_key="synthetic_wikidata_claim_worker_org", statement_index=2, predicate_key="organization", object_text="Institution", object_type="organization", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wikidata_claim_worker_org", "signal_classes": ["institutional_boundary"]})
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_wikidata_claim_worker_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_wikidata_claim_worker_v1"}


def _build_synthetic_wiki_legal_fidelity_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("wf-1", "article_text", "wiki_article", "The article compresses allegation, trial finding, and appeal into one line."),
        TextUnit("wf-2", "trial_record", "judgment_extract", "Trial record contains narrower findings."),
        TextUnit("wf-3", "appeal_record", "judgment_extract", "Appeal record changes part of the procedural posture."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic wiki legal-fidelity fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Article compression", "Trial posture", "Appeal posture")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "wiki_article": ["public_summary", "wiki_article", "weak_public_source"],
            "judgment_extract": ["legal_record", "strong_legal_source", "procedural_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_wiki_legal_fidelity_claim", statement_index=0, predicate_key="claimed", object_text="compressed legal summary", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wiki_legal_fidelity_claim", "signal_classes": ["public_summary_claim", "overstatement_risk"]})
    _append_observation(payload, fixture_key="synthetic_wiki_legal_fidelity_trial", statement_index=1, predicate_key="ruled", object_text="trial finding", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wiki_legal_fidelity_trial", "signal_classes": ["procedural_outcome"]})
    _append_observation(payload, fixture_key="synthetic_wiki_legal_fidelity_appeal", statement_index=2, predicate_key="appealed", object_text="appeal change", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_wiki_legal_fidelity_appeal", "signal_classes": ["procedural_context"]})
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_wiki_legal_fidelity_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_wiki_legal_fidelity_v1"}


def _build_real_wiki_history_fixture(db_path: Path, fixture: Mapping[str, Any], wiki: str, title: str, history_filename: str) -> dict[str, Any]:
    history_path = resolve_sensiblaw_manifest_path(
        "demo",
        "ingest",
        "wiki_revision_monitor",
        "wiki_revision_contested_v1",
        "history",
        history_filename,
    )
    with history_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    rows = data.get("rows", [])[:10]  # Limit to 10 to find a reversion
    units = [
        TextUnit("legal-auth-1", "legal_record", "legal_record", f"Formal regulation reference for {title} content standards.")
    ]
    for row in rows:
        unit_id = f"wiki-{row['revid']}"
        comment = row.get("comment") or "[no comment]"
        units.append(TextUnit(unit_id, "wiki_article", "wiki_article", f"Revision by {row['user']}: {comment}"))
        
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes=f"Wave 3 real wiki history fixture for {title}",
    )
    payload["fact_candidates"][0]["canonical_label"] = "Legal Standard"
    payload["fact_candidates"][0]["candidate_status"] = "candidate"
    _append_observation(
        payload, 
        fixture_key=f"{fixture['fixture_id']}_legal_signal", 
        statement_index=0, 
        predicate_key="ruled", 
        object_text="True", 
        object_type="boolean",
        provenance={"source": "acceptance_fixture", "fixture_key": fixture["fixture_id"], "signal_classes": ["procedural_outcome"]}
    )
    _set_source_signal_classes(payload, {"legal_record": ["legal_record", "strong_legal_source"]})
    
    for i, row in enumerate(rows, start=1):
        payload["fact_candidates"][i]["canonical_label"] = f"Revision {row['revid']}"
        payload["fact_candidates"][i]["candidate_status"] = "candidate"
        
    _set_source_signal_classes(
        payload,
        {
            "wiki_article": ["public_summary", "wiki_article", "revision_history"],
        },
    )
    
    # Note: volatility signals (is_reversion, volatility_signal) are now inferred
    # systemically by Zelph rules based on the revision comment lexemes.
    # No manual injection needed here.

    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id=fixture["fixture_id"], payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": fixture["fixture_id"]}

def _build_real_wiki_covid19_contested_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    return _build_real_wiki_history_fixture(db_path, fixture, "enwiki", "COVID-19", "enwiki__COVID-19__history__d6247063a39d.json")

def _build_real_wiki_trump_contested_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    return _build_real_wiki_history_fixture(db_path, fixture, "enwiki", "Donald Trump", "enwiki__Donald_Trump__history__72d04f084782.json")


def _build_synthetic_lawyer_maintainer_conflict_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("lm-1", "advocate_brief", "advocate_brief", "Advocate brief leans heavily on a Wikipedia-style summary."),
        TextUnit("lm-2", "wiki_article", "wiki_article", "Public summary uses strong language about wrongdoing."),
        TextUnit("lm-3", "maintainer_note", "maintainer_note", "Maintainer note warns the legal record is thinner than the framing."),
        TextUnit("lm-4", "court_record", "judgment_extract", "Court material gives a narrower procedural finding."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 3 synthetic lawyer-maintainer conflict fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Advocate framing", "Public summary wording", "Maintainer caution", "Court record")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "advocate_brief": ["advocate_framing", "party_material"],
            "wiki_article": ["public_summary", "wiki_article", "weak_public_source"],
            "maintainer_note": ["maintainer_caution", "later_annotation"],
            "judgment_extract": ["legal_record", "strong_legal_source", "procedural_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_lawyer_maintainer_conflict_claim", statement_index=0, predicate_key="claimed", object_text="wrongdoing framing", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_lawyer_maintainer_conflict_claim", "signal_classes": ["public_summary_claim", "overstatement_risk", "source_shopping_risk"]})
    _append_observation(payload, fixture_key="synthetic_lawyer_maintainer_conflict_note", statement_index=2, predicate_key="sequence_marker", object_text="record thinner than framing", object_type="note", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_lawyer_maintainer_conflict_note", "signal_classes": ["editorial_framing", "minimization_risk"]})
    _append_observation(payload, fixture_key="synthetic_lawyer_maintainer_conflict_record", statement_index=3, predicate_key="ruled", object_text="narrow procedural finding", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_lawyer_maintainer_conflict_record", "signal_classes": ["procedural_outcome"]})
    _append_contestation(payload, fixture_key="synthetic_lawyer_maintainer_conflict_contest", fact_index=0, statement_index=2, reason_text="Advocacy framing and maintainer caution diverge over what the legal record supports.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_lawyer_maintainer_conflict_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_lawyer_maintainer_conflict_v1"}


def _build_synthetic_family_client_circumstances_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("fam-1", "client_account", "client_account", "The client says handovers changed after separation and the child was distressed."),
        TextUnit("fam-2", "other_side_account", "other_side_account", "The other side disputes the timing and says the child was settled."),
        TextUnit("fam-3", "school_record", "school_record", "School record notes the child was collected early on 2025-02-14."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic family-law client circumstances fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Client account", "Other side account", "School record")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "client_account": ["client_account", "side_a_material", "user_authored"],
            "other_side_account": ["other_side_account", "side_b_material", "third_party_record"],
            "school_record": ["child_record", "third_party_record", "legal_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_family_client_circumstances_date", statement_index=2, predicate_key="event_date", object_text="2025-02-14", object_type="date")
    _append_observation(payload, fixture_key="synthetic_family_client_circumstances_child", statement_index=0, predicate_key="harm_type", object_text="child distress", object_type="harm", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_family_client_circumstances_child", "signal_classes": ["child_sensitive_context", "child_related_issue"]})
    _append_contestation(payload, fixture_key="synthetic_family_client_circumstances_contest", fact_index=0, statement_index=1, reason_text="The other side disputes the account of what happened at handover.", contestation_scope="circumstances")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_family_client_circumstances_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_family_client_circumstances_v1"}


def _build_synthetic_family_both_sides_review_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("fam-4", "side_a_submission", "side_a_submission", "Side A says the care arrangement changed after repeated late pickups."),
        TextUnit("fam-5", "side_b_submission", "side_b_submission", "Side B denies lateness and seeks equal time."),
        TextUnit("fam-6", "interim_order", "court_record", "The interim order records a temporary timetable and a review hearing."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic family-law both-sides review fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Side A submission", "Side B submission", "Interim order")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "side_a_submission": ["side_a_material", "party_material", "user_authored"],
            "side_b_submission": ["side_b_material", "party_material", "third_party_record"],
            "court_record": ["legal_record", "procedural_record", "third_party_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_family_both_sides_review_claimed", statement_index=0, predicate_key="claimed", object_text="late pickups", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_family_both_sides_review_claimed", "signal_classes": ["party_assertion", "child_sensitive_context"]})
    _append_observation(payload, fixture_key="synthetic_family_both_sides_review_denied", statement_index=1, predicate_key="denied", object_text="late pickups", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_family_both_sides_review_denied", "signal_classes": ["party_assertion", "child_sensitive_context"]})
    _append_observation(payload, fixture_key="synthetic_family_both_sides_review_ordered", statement_index=2, predicate_key="ordered", object_text="temporary timetable", object_type="procedural_outcome", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_family_both_sides_review_ordered", "signal_classes": ["procedural_outcome"]})
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_family_both_sides_review_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_family_both_sides_review_v1"}


def _build_synthetic_child_sensitive_context_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("fam-7", "client_account", "client_account", "The child said they did not want to move houses again."),
        TextUnit("fam-8", "support_note", "support_worker_note", "Support note: timing is uncertain but the child appeared distressed after contact."),
        TextUnit("fam-9", "clinic_note", "clinic_note", "Clinic note records a review later that week without a precise date."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic child-sensitive context fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Child account", "Support note", "Clinic note")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "client_account": ["client_account", "user_authored", "side_a_material"],
            "support_worker_note": ["support_worker_note", "later_annotation"],
            "clinic_note": ["third_party_record", "legal_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_child_sensitive_context_child", statement_index=0, predicate_key="harm_type", object_text="child distress", object_type="harm", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_child_sensitive_context_child", "signal_classes": ["child_sensitive_context", "child_related_issue", "party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_child_sensitive_context_note", statement_index=1, predicate_key="sequence_marker", object_text="later that week", object_type="relative_time", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_child_sensitive_context_note", "signal_classes": ["later_annotation"]})
    _append_review(payload, fixture_key="synthetic_child_sensitive_context_review", fact_index=1, review_status="needs_followup", note="Precise date remains uncertain and should not be reconstructed beyond the record.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_child_sensitive_context_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_child_sensitive_context_v1"}


def _build_synthetic_cross_side_handoff_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("fam-10", "client_timeline", "client_account", "Client timeline says changeover was moved after a school issue."),
        TextUnit("fam-11", "other_side_bundle", "other_side_account", "Other side bundle disputes that description and adds a different reason."),
        TextUnit("fam-12", "lawyer_handoff", "handoff_note", "Handoff note keeps both versions and links them to the school email."),
        TextUnit("fam-13", "school_email", "school_record", "School email confirms a meeting occurred but not who caused it."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic cross-side handoff fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Client timeline", "Other side bundle", "Handoff note", "School email")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "client_account": ["client_account", "side_a_material", "user_authored"],
            "other_side_account": ["other_side_account", "side_b_material", "third_party_record"],
            "handoff_note": ["later_annotation", "support_worker_note"],
            "school_record": ["third_party_record", "legal_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_cross_side_handoff_claim", statement_index=0, predicate_key="claimed", object_text="reason for changeover", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_cross_side_handoff_claim", "signal_classes": ["party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_cross_side_handoff_denied", statement_index=1, predicate_key="denied", object_text="reason for changeover", object_type="legal_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_cross_side_handoff_denied", "signal_classes": ["party_assertion"]})
    _append_contestation(payload, fixture_key="synthetic_cross_side_handoff_contest", fact_index=0, statement_index=1, reason_text="The sides offer competing accounts and the handoff note preserves both.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_cross_side_handoff_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_cross_side_handoff_v1"}


def _build_synthetic_medical_negligence_review_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("med-1", "patient_account", "patient_account", "The patient says no warning was given before the procedure."),
        TextUnit("med-2", "clinical_record", "clinical_record", "Clinical record notes the procedure and later complications."),
        TextUnit("med-3", "expert_note", "expert_note", "Expert interpretation says the note does not clearly record a warning discussion."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic medical-negligence review fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Patient account", "Clinical record", "Expert interpretation")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "patient_account": ["patient_account", "user_authored"],
            "clinical_record": ["clinical_record", "legal_record", "third_party_record"],
            "expert_note": ["expert_interpretation", "later_annotation"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_medical_negligence_review_treatment", statement_index=1, predicate_key="performed_action", object_text="procedure", object_type="medical_action", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_medical_negligence_review_treatment", "signal_classes": ["treatment_event"]})
    _append_observation(payload, fixture_key="synthetic_medical_negligence_review_warning", statement_index=0, predicate_key="failed_to_act", object_text="warn patient", object_type="warning", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_medical_negligence_review_warning", "signal_classes": ["warning_issue", "party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_medical_negligence_review_harm", statement_index=1, predicate_key="harm_type", object_text="post-procedure complication", object_type="harm", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_medical_negligence_review_harm", "signal_classes": ["harm_consequence"]})
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_medical_negligence_review_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_medical_negligence_review_v1"}


def _build_synthetic_professional_discipline_record_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("med-4", "complaint_digest", "reporting_note", "Public complaint digest says the practitioner is under investigation."),
        TextUnit("med-5", "board_record", "regulatory_record", "Board record shows complaint intake and formal investigation."),
        TextUnit("med-6", "tribunal_record", "tribunal_record", "Tribunal record notes findings and sanction stage."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic professional-discipline review fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Public complaint digest", "Board record", "Tribunal record")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "reporting_note": ["public_summary", "reporting_source"],
            "regulatory_record": ["regulatory_record", "third_party_record"],
            "tribunal_record": ["tribunal_record", "legal_record", "third_party_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_professional_discipline_record_complaint", statement_index=1, predicate_key="claimed", object_text="complaint stage", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_professional_discipline_record_complaint", "signal_classes": ["complaint_stage"]})
    _append_observation(payload, fixture_key="synthetic_professional_discipline_record_investigation", statement_index=1, predicate_key="sequence_marker", object_text="formal investigation", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_professional_discipline_record_investigation", "signal_classes": ["investigation_stage"]})
    _append_observation(payload, fixture_key="synthetic_professional_discipline_record_finding", statement_index=2, predicate_key="ruled", object_text="finding stage", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_professional_discipline_record_finding", "signal_classes": ["finding_stage", "structural_ambiguity"]})
    _append_observation(payload, fixture_key="synthetic_professional_discipline_record_sanction", statement_index=2, predicate_key="ordered", object_text="sanction stage", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_professional_discipline_record_sanction", "signal_classes": ["sanction_stage"]})
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_professional_discipline_record_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_professional_discipline_record_v1"}


def _build_synthetic_regulatory_public_drift_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("med-7", "headline", "reporting_note", "Headline says the doctor was effectively banned."),
        TextUnit("med-8", "board_update", "regulatory_record", "Board update says the matter is still under investigation."),
        TextUnit("med-9", "tribunal_update", "tribunal_record", "Tribunal update records a later finding on a narrower issue."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 4 synthetic regulatory/public drift fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Headline framing", "Board update", "Tribunal update")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "reporting_note": ["public_summary", "reporting_source"],
            "regulatory_record": ["regulatory_record", "third_party_record"],
            "tribunal_record": ["tribunal_record", "legal_record", "third_party_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_regulatory_public_drift_claim", statement_index=0, predicate_key="claimed", object_text="effective ban", object_type="public_claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_regulatory_public_drift_claim", "signal_classes": ["public_summary_claim", "overstatement_risk"]})
    _append_observation(payload, fixture_key="synthetic_regulatory_public_drift_investigation", statement_index=1, predicate_key="sequence_marker", object_text="still under investigation", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_regulatory_public_drift_investigation", "signal_classes": ["investigation_stage"]})
    _append_observation(payload, fixture_key="synthetic_regulatory_public_drift_finding", statement_index=2, predicate_key="ruled", object_text="narrower finding", object_type="regulatory_stage", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_regulatory_public_drift_finding", "signal_classes": ["finding_stage", "structural_ambiguity"]})
    _append_contestation(payload, fixture_key="synthetic_regulatory_public_drift_contest", fact_index=0, statement_index=1, reason_text="Public narrative overstates the current regulatory stage.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_regulatory_public_drift_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_regulatory_public_drift_v1"}


def _build_real_transcript_professional_handoff_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("rph-1", "user_journal", "personal_note", "I wrote that the panic episode happened before the GP visit, but I was still unsure of the exact day."),
        TextUnit("rph-2", "clinic_letter", "documentary_record", "The clinic letter confirms a GP visit on 2025-03-18 and records medication advice."),
        TextUnit("rph-3", "therapist_session", "professional_note", "Therapist note keeps the user wording separate and marks the earlier panic timing as unresolved."),
    ]
    workflow_run_id = "real_transcript_professional_handoff_v1"
    with _connect(db_path) as conn:
        result = run_transcript_semantic_pipeline(
            conn,
            units,
            known_participants_by_source={"user_journal": ["user"], "clinic_letter": ["gp"], "therapist_session": ["therapist", "user"]},
            run_id=workflow_run_id,
        )
        semantic_report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
        payload = build_fact_intake_payload_from_transcript_report(
            semantic_report,
            source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
            notes="Wave 5 real transcript professional handoff fixture",
        )
        labels = ("User journal account", "Clinic letter", "Therapist note")
        for row, label in zip(payload["fact_candidates"], labels):
            row["canonical_label"] = label
            row["candidate_status"] = "candidate"
        _set_source_signal_classes(
            payload,
            {
                "personal_note": ["user_authored", "client_account"],
                "documentary_record": ["documentary_record", "third_party_record"],
                "professional_note": ["professional_note", "professional_interpretation", "later_annotation"],
            },
        )
        _append_observation(payload, fixture_key="real_transcript_professional_handoff_date", statement_index=1, predicate_key="event_date", object_text="2025-03-18", object_type="date")
        _append_observation(payload, fixture_key="real_transcript_professional_handoff_gap", statement_index=2, predicate_key="sequence_marker", object_text="earlier panic timing unresolved", object_type="note", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_professional_handoff_gap", "signal_classes": ["uncertainty_preserved", "not_enough_evidence"]})
        _append_review(payload, fixture_key="real_transcript_professional_handoff_review", fact_index=2, review_status="needs_followup", note="Professional note preserves the user account and should not harden unresolved timing.")
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id=result["run_id"], payload=payload)
        bundle = build_transcript_fact_review_bundle(conn, fact_run_id=payload["run"]["run_id"], semantic_report=semantic_report)
    return {**dict(fixture), **persisted, "semantic_run_id": workflow_run_id, "bundle_version": bundle["version"]}


def _build_real_transcript_false_coherence_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("rfc-1", "user_fragment_a", "personal_note", "I think the call came before the neighbour came over, but I cannot be certain."),
        TextUnit("rfc-2", "user_fragment_b", "personal_note", "A later note says the neighbour may have arrived first."),
        TextUnit("rfc-3", "support_checkin", "professional_note", "Support worker note says not enough evidence exists to settle the order and both possibilities should be kept."),
        TextUnit("rfc-4", "phone_capture", "documentary_record", "Phone capture shows the call log but does not place the neighbour visit."),
    ]
    workflow_run_id = "real_transcript_false_coherence_v1"
    with _connect(db_path) as conn:
        result = run_transcript_semantic_pipeline(
            conn,
            units,
            known_participants_by_source={"user_fragment_a": ["user"], "user_fragment_b": ["user"], "support_checkin": ["support_worker", "user"]},
            run_id=workflow_run_id,
        )
        semantic_report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
        payload = build_fact_intake_payload_from_transcript_report(
            semantic_report,
            source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
            notes="Wave 5 real transcript false-coherence fixture",
        )
        labels = ("Fragment A", "Fragment B", "Support note", "Phone capture")
        for row, label in zip(payload["fact_candidates"], labels):
            row["canonical_label"] = label
            row["candidate_status"] = "candidate"
        _set_source_signal_classes(
            payload,
            {
                "personal_note": ["user_authored", "client_account"],
                "professional_note": ["professional_note", "later_annotation"],
                "documentary_record": ["documentary_record", "third_party_record"],
            },
        )
        _append_observation(payload, fixture_key="real_transcript_false_coherence_rel_a", statement_index=0, predicate_key="temporal_relation", object_text="call before neighbour visit", object_type="relative_time", provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_false_coherence_rel_a", "signal_classes": ["fragmentary_account", "contradiction_cluster"]})
        _append_observation(payload, fixture_key="real_transcript_false_coherence_rel_b", statement_index=1, predicate_key="temporal_relation", object_text="neighbour visit before call", object_type="relative_time", provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_false_coherence_rel_b", "signal_classes": ["fragmentary_account", "contradiction_cluster"]})
        _append_observation(payload, fixture_key="real_transcript_false_coherence_gap", statement_index=2, predicate_key="sequence_marker", object_text="not enough evidence to settle order", object_type="note", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "real_transcript_false_coherence_gap", "signal_classes": ["not_enough_evidence", "uncertainty_preserved"]})
        _append_contestation(payload, fixture_key="real_transcript_false_coherence_contest", fact_index=0, statement_index=1, reason_text="Contradictory user fragments should remain open rather than collapsing into one ordered narrative.", contestation_scope="chronology")
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id=result["run_id"], payload=payload)
        bundle = build_transcript_fact_review_bundle(conn, fact_run_id=payload["run"]["run_id"], semantic_report=semantic_report)
    return {**dict(fixture), **persisted, "semantic_run_id": workflow_run_id, "bundle_version": bundle["version"]}


def _build_synthetic_personal_professional_handoff_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("pp-1", "personal_notes", "personal_note", "I wrote down the sequence as I remembered it after the appointment."),
        TextUnit("pp-2", "documents", "documentary_record", "The discharge paper confirms the date and medication change."),
        TextUnit("pp-3", "therapist_note", "professional_note", "Therapist note keeps the account provisional and records unresolved gaps."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 5 synthetic personal-to-professional handoff fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Personal notes", "Documentary record", "Therapist note")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "personal_note": ["user_authored", "client_account"],
            "documentary_record": ["documentary_record", "third_party_record"],
            "professional_note": ["professional_note", "professional_interpretation", "later_annotation"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_personal_professional_handoff_date", statement_index=1, predicate_key="event_date", object_text="2025-07-04", object_type="date")
    _append_observation(payload, fixture_key="synthetic_personal_professional_handoff_gap", statement_index=2, predicate_key="sequence_marker", object_text="timeline still incomplete", object_type="note", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_personal_professional_handoff_gap", "signal_classes": ["uncertainty_preserved", "not_enough_evidence"]})
    _append_review(payload, fixture_key="synthetic_personal_professional_handoff_review", fact_index=2, review_status="needs_followup", note="Professional note should stay distinct from the original user-authored chronology.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_personal_professional_handoff_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_personal_professional_handoff_v1"}


def _build_synthetic_multi_professional_reopen_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("pp-4", "user_timeline", "personal_note", "My timeline says the incident happened before the hospital visit."),
        TextUnit("pp-5", "lawyer_note", "professional_note", "Lawyer note preserves the original order and identifies missing corroboration."),
        TextUnit("pp-6", "doctor_note", "professional_note", "Doctor note distinguishes symptoms from legal interpretation."),
        TextUnit("pp-7", "record", "documentary_record", "Documentary record confirms the hospital visit but not the earlier incident timing."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 5 synthetic multi-professional reopen fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("User timeline", "Lawyer note", "Doctor note", "Hospital record")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "personal_note": ["user_authored", "client_account"],
            "professional_note": ["professional_note", "professional_interpretation", "later_annotation"],
            "documentary_record": ["documentary_record", "third_party_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_multi_professional_reopen_claim", statement_index=0, predicate_key="claimed", object_text="incident before hospital visit", object_type="claim", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_multi_professional_reopen_claim", "signal_classes": ["party_assertion"]})
    _append_observation(payload, fixture_key="synthetic_multi_professional_reopen_gap", statement_index=1, predicate_key="sequence_marker", object_text="missing corroboration for incident timing", object_type="note", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_multi_professional_reopen_gap", "signal_classes": ["uncertainty_preserved", "not_enough_evidence"]})
    _append_contestation(payload, fixture_key="synthetic_multi_professional_reopen_contest", fact_index=0, statement_index=3, reason_text="The hospital record confirms the visit but not the earlier incident timing.")
    _append_review(payload, fixture_key="synthetic_multi_professional_reopen_review", fact_index=1, review_status="needs_followup", note="Keep professional notes read-only and separate from the original user chronology.")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_multi_professional_reopen_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_multi_professional_reopen_v1"}


def _build_synthetic_false_coherence_pressure_v1(db_path: Path, fixture: Mapping[str, Any]) -> dict[str, Any]:
    units = [
        TextUnit("fc-1", "fragment_a", "personal_note", "I think the meeting was before the messages, but I am not certain."),
        TextUnit("fc-2", "fragment_b", "personal_note", "Another note says the messages may have come first."),
        TextUnit("fc-3", "helper_note", "professional_note", "Helper note: not enough evidence to settle the order; keep both possibilities open."),
        TextUnit("fc-4", "screenshot", "documentary_record", "Screenshot confirms messages existed but not when the meeting occurred."),
    ]
    payload = build_fact_intake_payload_from_text_units(
        units,
        source_label=str(fixture.get("source_label") or fixture.get("fixture_id")),
        notes="Wave 5 synthetic false-coherence pressure fixture",
    )
    for row, label in zip(payload["fact_candidates"], ("Fragment A", "Fragment B", "Helper note", "Screenshot")):
        row["canonical_label"] = label
        row["candidate_status"] = "candidate"
    _set_source_signal_classes(
        payload,
        {
            "personal_note": ["user_authored", "client_account"],
            "professional_note": ["professional_note", "later_annotation"],
            "documentary_record": ["documentary_record", "third_party_record"],
        },
    )
    _append_observation(payload, fixture_key="synthetic_false_coherence_pressure_rel_a", statement_index=0, predicate_key="temporal_relation", object_text="meeting before messages", object_type="relative_time", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_false_coherence_pressure_rel_a", "signal_classes": ["fragmentary_account", "contradiction_cluster"]})
    _append_observation(payload, fixture_key="synthetic_false_coherence_pressure_rel_b", statement_index=1, predicate_key="temporal_relation", object_text="messages before meeting", object_type="relative_time", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_false_coherence_pressure_rel_b", "signal_classes": ["fragmentary_account", "contradiction_cluster"]})
    _append_observation(payload, fixture_key="synthetic_false_coherence_pressure_note", statement_index=2, predicate_key="sequence_marker", object_text="not enough evidence to settle order", object_type="note", observation_status="abstained", provenance={"source": "acceptance_fixture", "fixture_key": "synthetic_false_coherence_pressure_note", "signal_classes": ["not_enough_evidence", "uncertainty_preserved"]})
    _append_contestation(payload, fixture_key="synthetic_false_coherence_pressure_contest", fact_index=0, statement_index=1, reason_text="The two personal fragments preserve contradictory ordering and should not be merged into one settled story.", contestation_scope="chronology")
    with _connect(db_path) as conn:
        persisted = _persist_and_link(conn, workflow_kind="transcript_semantic", workflow_run_id="synthetic_false_coherence_pressure_v1", payload=payload)
    return {**dict(fixture), **persisted, "semantic_run_id": "synthetic_false_coherence_pressure_v1"}


_BUILDERS: dict[str, Callable[[Path, Mapping[str, Any]], dict[str, Any]]] = {
    "real_transcript_intake_v1": _build_real_transcript_intake_v1,
    "real_au_procedural_v1": _build_real_au_procedural_v1,
    "synthetic_sparse_dates_v1": _build_synthetic_sparse_dates_v1,
    "synthetic_assertion_outcome_v1": _build_synthetic_assertion_outcome_v1,
    "synthetic_conflict_cluster_v1": _build_synthetic_conflict_cluster_v1,
    "synthetic_personal_fragments_v1": _build_synthetic_personal_fragments_v1,
    "synthetic_investigative_reopen_v1": _build_synthetic_investigative_reopen_v1,
    "real_transcript_fragmented_support_v1": _build_real_transcript_fragmented_support_v1,
    "synthetic_trauma_fragment_cluster_v1": _build_synthetic_trauma_fragment_cluster_v1,
    "synthetic_support_worker_handoff_v1": _build_synthetic_support_worker_handoff_v1,
    "real_gwb_contested_public_figure_v1": _build_real_gwb_contested_public_figure_v1,
    "synthetic_trump_public_figure_legality_v1": _build_synthetic_trump_public_figure_legality_v1,
    "synthetic_wikipedia_defamation_review_v1": _build_synthetic_wikipedia_defamation_review_v1,
    "synthetic_wikidata_claim_worker_v1": _build_synthetic_wikidata_claim_worker_v1,
    "synthetic_wiki_legal_fidelity_v1": _build_synthetic_wiki_legal_fidelity_v1,
    "synthetic_lawyer_maintainer_conflict_v1": _build_synthetic_lawyer_maintainer_conflict_v1,
    "synthetic_family_client_circumstances_v1": _build_synthetic_family_client_circumstances_v1,
    "synthetic_family_both_sides_review_v1": _build_synthetic_family_both_sides_review_v1,
    "synthetic_child_sensitive_context_v1": _build_synthetic_child_sensitive_context_v1,
    "synthetic_cross_side_handoff_v1": _build_synthetic_cross_side_handoff_v1,
    "synthetic_medical_negligence_review_v1": _build_synthetic_medical_negligence_review_v1,
    "synthetic_professional_discipline_record_v1": _build_synthetic_professional_discipline_record_v1,
    "synthetic_regulatory_public_drift_v1": _build_synthetic_regulatory_public_drift_v1,
    "real_transcript_professional_handoff_v1": _build_real_transcript_professional_handoff_v1,
    "real_transcript_false_coherence_v1": _build_real_transcript_false_coherence_v1,
    "synthetic_personal_professional_handoff_v1": _build_synthetic_personal_professional_handoff_v1,
    "synthetic_multi_professional_reopen_v1": _build_synthetic_multi_professional_reopen_v1,
    "synthetic_false_coherence_pressure_v1": _build_synthetic_false_coherence_pressure_v1,
    "real_wiki_covid19_contested_v1": _build_real_wiki_covid19_contested_v1,
    "real_wiki_trump_contested_v1": _build_real_wiki_trump_contested_v1,
}


def build_fact_review_acceptance_fixture(
    db_path: Path,
    *,
    fixture_id: str,
    manifest_path: Path | None = None,
    wave: str = "wave1_legal",
) -> dict[str, Any]:
    fixture = next((row for row in _manifest_fixtures(manifest_path, wave=wave) if row.get("fixture_id") == fixture_id), None)
    if fixture is None:
        raise KeyError(f"unknown acceptance fixture: {fixture_id}")
    builder_key = str(fixture.get("builder_key") or "")
    builder = _BUILDERS.get(builder_key)
    if builder is None:
        raise KeyError(f"unknown acceptance fixture builder: {builder_key}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return builder(db_path, fixture)


def build_fact_review_acceptance_fixture_set(
    db_path: Path,
    *,
    manifest_path: Path | None = None,
    fixture_ids: list[str] | None = None,
    workflow_kind: str | None = None,
    wave: str = "wave1_legal",
) -> list[dict[str, Any]]:
    fixtures = _manifest_fixtures(manifest_path, wave=wave)
    if fixture_ids:
        fixture_id_set = set(fixture_ids)
        fixtures = [row for row in fixtures if str(row.get("fixture_id")) in fixture_id_set]
    if workflow_kind:
        fixtures = [row for row in fixtures if str(row.get("workflow_kind")) == workflow_kind]
    return [
        build_fact_review_acceptance_fixture(db_path, fixture_id=str(row["fixture_id"]), manifest_path=manifest_path, wave=wave)
        for row in fixtures
    ]
