from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import statistics
import time
from typing import Any, Iterable, Mapping

from src.reporting.structure_report import TextUnit
from src.sensiblaw.db.dao import ensure_database
from src.zelph_bridge import enrich_workbench_with_zelph, load_zelph_rules
from .control_plane import FOLLOW_CONTROL_PLANE_VERSION, build_follow_control_plane, summarize_follow_queue
from .operator_views import (
    build_contested_control_items,
    build_review_queue_control_items,
)

FACT_INTAKE_CONTRACT_VERSION = "fact.intake.bundle.v1"
MARY_FACT_WORKFLOW_VERSION = "mary.fact_workflow.v1"
EVENT_ASSEMBLER_VERSION = "fact_event_assembler_v1"
FACT_WORKFLOW_LINK_VERSION = "fact_workflow_link_v1"
AUTHORITY_INGEST_VERSION = "authority.ingest.v1"
FEEDBACK_RECEIPT_VERSION = "feedback.receipt.v1"

OBSERVATION_PREDICATE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("actor_identification", ("actor", "co_actor", "actor_role", "actor_attribute", "organization")),
    ("actions_events", ("performed_action", "failed_to_act", "caused_event", "received_action", "communicated")),
    ("object_target", ("acted_on", "affected_object", "subject_matter", "document_reference")),
    ("temporal", ("event_time", "event_date", "temporal_relation", "duration", "sequence_marker")),
    ("harm_consequence", ("harm_type", "injury", "loss", "damage_amount", "causal_link")),
    (
        "legal_procedural",
        (
            "alleged",
            "denied",
            "admitted",
            "claimed",
            "ruled",
            "ordered",
            "appealed",
            "challenged",
            "heard_by",
            "decided_by",
            "applied",
            "followed",
            "distinguished",
            "held_that",
        ),
    ),
    ("wiki_events", ("is_reversion", "is_archival", "is_administrative")),
)

OBSERVATION_PREDICATE_TO_FAMILY: dict[str, str] = {
    predicate: family
    for family, predicates in OBSERVATION_PREDICATE_FAMILIES
    for predicate in predicates
}

EVENT_TRIGGER_PREDICATES = {
    "performed_action",
    "failed_to_act",
    "caused_event",
    "received_action",
    "communicated",
}

EVENT_ATTRIBUTE_PREDICATES = {
    "temporal_relation",
    "duration",
    "sequence_marker",
    "harm_type",
    "injury",
    "loss",
    "damage_amount",
    "causal_link",
    "alleged",
    "denied",
    "admitted",
    "claimed",
    "ruled",
    "ordered",
}

STATEMENT_STATUS_VALUES = {"captured", "abstained"}
OBSERVATION_STATUS_VALUES = {"captured", "uncertain", "abstained"}
FACT_STATUS_VALUES = {"captured", "candidate", "reviewed", "uncertain", "abstained", "no_fact"}
EVENT_STATUS_VALUES = {"candidate", "reviewed", "abstained"}
_FACT_INTAKE_MIGRATION_FILES = (
    "005_fact_intake_read_model.sql",
    "006_fact_observation_records.sql",
    "007_event_candidate_assembler.sql",
    "008_fact_workflow_links.sql",
    "009_fact_semantic_layer.sql",
    "010_fact_semantic_materialization.sql",
    "011_fact_semantic_refresh_progress.sql",
    "012_contested_affidavit_review.sql",
    "013_authority_ingest.sql",
    "014_feedback_receipts.sql",
    "015_contested_affidavit_relation_fields.sql",
)

REVIEW_REASON_LABELS: dict[str, str] = {
    "unreviewed": "Unreviewed",
    "contested": "Contested",
    "candidate_uncertain": "Candidate is uncertain",
    "candidate_abstained": "Candidate is abstained",
    "event_missing": "No assembled event",
    "event_undated": "Assembled event is undated",
    "chronology_undated": "Chronology is undated",
    "review_followup": "Review requires follow-up",
    "missing_date": "Missing date",
    "missing_actor": "Missing actor",
    "contradictory_chronology": "Contradictory chronology",
    "statement_only_fact": "Statement-only fact",
    "source_conflict": "Source conflict",
    "procedural_significance": "Procedural significance",
}

FACT_REVIEW_OPERATOR_VIEW_KINDS = (
    "intake_triage",
    "chronology_prep",
    "procedural_posture",
    "contested_items",
    "trauma_handoff",
    "professional_handoff",
    "false_coherence_review",
    "public_claim_review",
    "wiki_fidelity",
    "claim_alignment",
)

FACT_REVIEW_WORKBENCH_VERSION = "fact.review.workbench.v1"
FACT_REVIEW_ZELPH_RULESET_VERSION = "fact.review.workbench.zelph.v2"
FACT_SEMANTIC_LAYER_VERSION = "fact.semantic.layer.v1"
_ASSERTION_PREDICATES = {"claimed", "denied", "admitted", "alleged"}
_PROCEDURAL_OUTCOME_PREDICATES = {"ordered", "ruled", "decided_by", "held_that"}
_PROCEDURAL_CONTEXT_PREDICATES = {"appealed", "challenged", "heard_by", "applied", "followed", "distinguished"}

_SEMANTIC_CLASS_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("public_summary", "source_authority", "source", "Public summary source."),
    ("wiki_article", "source_authority", "source", "Wiki article source."),
    ("wikidata_claim", "source_authority", "source", "Wikidata claim source."),
    ("legal_record", "source_authority", "source", "Legal record source."),
    ("procedural_record", "source_authority", "source", "Procedural record source."),
    ("strong_legal_source", "source_authority", "source", "Strong legal source."),
    ("reporting_source", "source_authority", "source", "Reporting-style summary source."),
    ("ocr_capture", "source_authority", "source", "OCR capture source."),
    ("later_annotation", "source_authority", "source", "Later annotation source."),
    ("agent_summary", "role_boundary", "source", "Agent-generated summary source."),
    ("system_summary", "role_boundary", "source", "System-generated summary source."),
    ("agent_action_log", "role_boundary", "source", "Agent execution/activity log source."),
    ("professional_note", "role_boundary", "source", "Professional note source."),
    ("professional_interpretation", "role_boundary", "source", "Professional interpretation source."),
    ("support_worker_note", "role_boundary", "source", "Support-worker note source."),
    ("third_party_record", "source_authority", "source", "Third-party record source."),
    ("documentary_record", "source_authority", "source", "Documentary record source."),
    ("user_authored", "role_boundary", "source", "User-authored source."),
    ("client_account", "role_boundary", "source", "Client account source."),
    ("patient_account", "role_boundary", "source", "Patient account source."),
    ("party_assertion", "claim_status", "observation", "Party-level assertion."),
    ("procedural_outcome", "claim_status", "observation", "Procedural outcome."),
    ("procedural_context", "claim_status", "observation", "Procedural context."),
    ("uncertainty_preserved", "epistemic", "fact", "Uncertainty must be preserved."),
    ("sequence_signal", "epistemic", "fact", "Sequence-bearing signal."),
    ("execution_handoff_signal", "workflow", "fact", "Execution or handoff signal."),
    ("self_correction_signal", "epistemic", "fact", "Self-correction signal."),
    ("handoff_context_signal", "workflow", "fact", "Handoff context signal."),
    ("professional_handoff_signal", "workflow", "fact", "Professional handoff signal."),
    ("appeal_stage_signal", "claim_status", "fact", "Appeal-stage signal."),
    ("volatility_signal", "epistemic", "fact", "Volatility or contested-edit signal."),
    ("authority_transfer_risk", "epistemic", "fact", "Authority transfer risk."),
    ("public_knowledge_not_authority", "epistemic", "fact", "Public knowledge is not authority."),
    ("wiki_wikidata_claim_alignment", "epistemic", "fact", "Wiki/Wikidata alignment signal."),
)

_SEMANTIC_RELATION_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("contextualizes", "source", "source", "Source contextualizes another source."),
    ("cannot_upgrade_authority_of", "source", "source", "Source cannot upgrade authority of another source."),
    ("corroborates", "fact", "fact", "Fact corroborates another fact."),
    ("contradicts", "fact", "fact", "Fact contradicts another fact."),
)

_SEMANTIC_RULE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("legacy_source_metadata", "manual", "Source/adapter metadata projection."),
    ("legacy_observation_metadata", "manual", "Observation metadata projection."),
    ("native_signal_projection", "native_rule", "Native review-signal projection."),
    ("zelph_signal_projection", "zelph", "Zelph workbench inference projection."),
    ("policy_projection", "native_rule", "Policy outcome projection."),
)

_POLICY_SPECS: tuple[tuple[str, str, str], ...] = (
    ("review_required", "fact", "Fact requires review."),
    ("do_not_promote_to_primary", "fact", "Fact must not be promoted to a primary-authority claim."),
    ("preserve_source_boundary", "fact", "Source boundary must be preserved."),
    ("manual_resolution_required", "fact", "Manual resolution is required."),
    ("bounded_context_required", "fact", "Downstream agents must receive bounded context only."),
)


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_payload(payload: object) -> str:
    return _sha256_text(_stable_json(payload))


def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except Exception:
            loaded = {"raw": value}
        return _stable_json(loaded)
    if value is None:
        return "{}"
    return _stable_json(value)


def _stable_id(prefix: str, payload: object) -> str:
    return f"{prefix}:{_sha256_payload(payload)[:16]}"


def _coalesce_rule_key(assertion_origin: str, rule_key: str | None) -> str:
    return _normalize_opt_text(rule_key) or assertion_origin


def _normalize_observation_predicate_key(value: Any) -> str:
    predicate_key = str(value or "").strip()
    if not predicate_key:
        raise ValueError("observation predicate_key is required")
    if predicate_key not in OBSERVATION_PREDICATE_TO_FAMILY:
        raise ValueError(f"unsupported observation predicate_key: {predicate_key}")
    return predicate_key


def _normalize_event_field(value: Any) -> str | None:
    text = _normalize_opt_text(value)
    return text.casefold() if text else None


def _normalize_status(value: Any, *, allowed: set[str], label: str, default: str) -> str:
    status = str(value or default).strip()
    if status not in allowed:
        raise ValueError(f"unsupported {label}: {status}")
    return status


def _latest_review_note(row: Mapping[str, Any] | None) -> str | None:
    if not isinstance(row, Mapping):
        return None
    return _normalize_opt_text(row.get("note"))


def _latest_contestation_reason(rows: list[Mapping[str, Any]]) -> str | None:
    if not rows:
        return None
    return _normalize_opt_text(rows[-1].get("reason_text"))


def _event_confidence_for_roles(roles: set[str]) -> float:
    score = 0.35
    if "event_type" in roles:
        score += 0.25
    if "primary_actor" in roles:
        score += 0.2
    if "object_text" in roles:
        score += 0.1
    if "time_start" in roles:
        score += 0.1
    return min(score, 0.99)


def _source_signal_classes(sources: Iterable[Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for source in sources:
        out.extend(_derived_source_classes(source))
    return list(dict.fromkeys(out))


def _source_projection_modes(sources: Iterable[Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for source in sources:
        provenance = source.get("provenance")
        if not isinstance(provenance, Mapping):
            continue
        raw = provenance.get("lexical_projection_modes")
        if isinstance(raw, list):
            out.extend(str(value) for value in raw if str(value).strip())
            continue
        single = _normalize_opt_text(provenance.get("lexical_projection_mode"))
        if single:
            out.append(single)
    return list(dict.fromkeys(out))


def _derived_source_classes(source: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    source_type = str(source.get("source_type") or "").strip()
    provenance = source.get("provenance") if isinstance(source.get("provenance"), Mapping) else {}
    if source_type == "wiki_article":
        out.extend(["public_summary", "wiki_article"])
    if source_type == "wikidata_claim_sheet":
        out.append("wikidata_claim")
    if source_type == "legal_record":
        out.append("legal_record")
    if source_type == "timeline_payload":
        out.append("procedural_record")
    if source_type == "openrecall_capture":
        out.extend(["ocr_capture", "agent_action_log"])
    if source_type == "annotation_note":
        out.append("later_annotation")
    if source_type == "professional_note":
        out.append("professional_note")
    if source_type == "professional_interpretation":
        out.extend(["professional_interpretation", "agent_summary"])
    if source_type == "support_worker_note":
        out.append("support_worker_note")
    if source_type in {"chat_archive_sample", "facebook_messages_archive_sample"}:
        out.append("documentary_record")
    raw = provenance.get("source_signal_classes")
    if isinstance(raw, list):
        out.extend(str(value) for value in raw if str(value).strip())
    else:
        single = _normalize_opt_text(provenance.get("source_signal_class"))
        if single:
            out.append(single)
    return list(dict.fromkeys(out))


def _explicit_signal_classes(observations: Iterable[Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for observation in observations:
        provenance = observation.get("provenance")
        if not isinstance(provenance, Mapping):
            continue
        raw = provenance.get("signal_classes")
        if isinstance(raw, list):
            out.extend(str(value) for value in raw if str(value).strip())
            continue
        single = _normalize_opt_text(provenance.get("signal_class"))
        if single:
            out.append(single)
    return list(dict.fromkeys(out))


def _observation_signal_classes(predicates: Iterable[str]) -> list[str]:
    out: list[str] = []
    predicate_set = set(predicates)
    if predicate_set & _ASSERTION_PREDICATES:
        out.append("party_assertion")
    if predicate_set & _PROCEDURAL_OUTCOME_PREDICATES:
        out.append("procedural_outcome")
    if predicate_set & _PROCEDURAL_CONTEXT_PREDICATES:
        out.append("procedural_context")
    return out


def _has_legal_procedural_visibility(
    legal_procedural_predicates: Iterable[str],
    signal_classes: Iterable[str],
    source_signal_classes: Iterable[str],
) -> bool:
    signal_set = set(signal_classes)
    source_signal_set = set(source_signal_classes)
    return bool(
        set(legal_procedural_predicates)
        or signal_set & {"party_assertion", "procedural_outcome", "procedural_context"}
        or source_signal_set & {"party_material", "procedural_record"}
    )


def _event_time_precision(event: Mapping[str, Any], observations_by_id: Mapping[str, Mapping[str, Any]]) -> str:
    if not _normalize_opt_text(event.get("time_start")):
        return "undated"
    for evidence in event.get("evidence", []):
        if not isinstance(evidence, Mapping) or str(evidence.get("role")) != "time_start":
            continue
        observation = observations_by_id.get(str(evidence.get("observation_id")))
        if not isinstance(observation, Mapping):
            continue
        object_type = _normalize_opt_text(observation.get("object_type"))
        provenance = observation.get("provenance")
        if isinstance(provenance, Mapping):
            provenance_precision = _normalize_opt_text(provenance.get("time_precision"))
            if provenance_precision in {"dated", "approximate", "undated"}:
                return provenance_precision
        if object_type in {"date", "datetime"}:
            return "dated"
        if object_type in {"date_hint", "temporal_phrase"}:
            return "approximate"
    return "approximate"


FACT_INT_ROLLBACK_TABLES = [
    "fact_sources",
    "fact_excerpts",
    "fact_statements",
    "fact_observations",
    "fact_candidates",
    "fact_intake_runs",
]


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    fact_ids = [
        str(row[0])
        for row in conn.execute("SELECT fact_id FROM fact_candidates WHERE run_id = ?", (run_id,))
        if row and row[0]
    ]
    if fact_ids:
        placeholders = ",".join("?" for _ in fact_ids)
        for table in ("fact_candidate_statements", "fact_reviews", "fact_contestations"):
            conn.execute(f"DELETE FROM {table} WHERE fact_id IN ({placeholders})", fact_ids)
    for table in FACT_INT_ROLLBACK_TABLES:
        conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def _delete_contested_review_run(conn: sqlite3.Connection, review_run_id: str) -> None:
    conn.execute("DELETE FROM contested_review_runs WHERE review_run_id = ?", (review_run_id,))


def _ensure_fact_intake_tables(conn: sqlite3.Connection) -> None:
    existing = {
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        if row and row[0]
    }
    required = {
        "fact_intake_runs",
        "fact_sources",
        "fact_excerpts",
        "fact_statements",
        "fact_candidates",
        "fact_candidate_statements",
        "fact_contestations",
        "fact_reviews",
        "fact_observations",
        "event_candidates",
        "event_attributes",
        "event_evidence",
        "fact_workflow_links",
        "semantic_class_vocab",
        "semantic_relation_vocab",
        "semantic_rule_vocab",
        "policy_vocab",
        "entity_class_assertions",
        "entity_relations",
        "policy_outcomes",
        "semantic_refresh_runs",
        "contested_review_runs",
        "contested_review_affidavit_rows",
        "contested_review_source_rows",
        "contested_review_zelph_facts",
        "authority_ingest_runs",
        "authority_ingest_segments",
        "feedback_receipts",
    }
    if required <= existing:
        _ensure_semantic_refresh_progress_columns(conn)
        _seed_fact_semantic_vocab(conn)
        return
    migrations_dir = Path(__file__).resolve().parents[2] / "database" / "migrations"
    for filename in _FACT_INTAKE_MIGRATION_FILES:
        conn.executescript((migrations_dir / filename).read_text(encoding="utf-8"))
    _ensure_semantic_refresh_progress_columns(conn)
    _seed_fact_semantic_vocab(conn)
    conn.commit()


def _ensure_semantic_refresh_progress_columns(conn: sqlite3.Connection) -> None:
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(semantic_refresh_runs)").fetchall()
        if row and row[1]
    }
    if not columns:
        return
    wanted = {
        "started_at": "TEXT",
        "updated_at": "TEXT",
        "current_stage": "TEXT",
        "status_message": "TEXT",
    }
    for column, column_type in wanted.items():
        if column in columns:
            continue
        conn.execute(f"ALTER TABLE semantic_refresh_runs ADD COLUMN {column} {column_type}")


def _seed_fact_semantic_vocab(conn: sqlite3.Connection) -> None:
    for class_key, dimension, applies_to, description in _SEMANTIC_CLASS_SPECS:
        conn.execute(
            """
            INSERT OR IGNORE INTO semantic_class_vocab(
              class_key, dimension, applies_to, class_status, description, introduced_in_version
            ) VALUES (?,?,?,?,?,?)
            """,
            (class_key, dimension, applies_to, "active", description, FACT_SEMANTIC_LAYER_VERSION),
        )
    for relation_key, subject_kind, object_kind, description in _SEMANTIC_RELATION_SPECS:
        conn.execute(
            """
            INSERT OR IGNORE INTO semantic_relation_vocab(
              relation_key, subject_kind, object_kind, relation_status, description, introduced_in_version
            ) VALUES (?,?,?,?,?,?)
            """,
            (relation_key, subject_kind, object_kind, "active", description, FACT_SEMANTIC_LAYER_VERSION),
        )
    for rule_key, engine_kind, description in _SEMANTIC_RULE_SPECS:
        conn.execute(
            """
            INSERT OR IGNORE INTO semantic_rule_vocab(
              rule_key, engine_kind, ruleset_version, description
            ) VALUES (?,?,?,?)
            """,
            (rule_key, engine_kind, FACT_REVIEW_ZELPH_RULESET_VERSION, description),
        )
    for policy_key, applies_to, description in _POLICY_SPECS:
        conn.execute(
            """
            INSERT OR IGNORE INTO policy_vocab(
              policy_key, applies_to, policy_status, description
            ) VALUES (?,?,?,?)
            """,
            (policy_key, applies_to, "active", description),
        )


def _assemble_event_candidates(conn: sqlite3.Connection, *, run_id: str) -> dict[str, int]:
    """Assemble derived events from normalized observation predicates only.

    Language/jurisdiction-specific variation must have already been normalized
    into the observation layer before this function runs.
    """

    conn.execute("DELETE FROM event_evidence WHERE event_id IN (SELECT event_id FROM event_candidates WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM event_attributes WHERE event_id IN (SELECT event_id FROM event_candidates WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM event_candidates WHERE run_id = ?", (run_id,))

    rows = conn.execute(
        """
        SELECT observation_id, statement_id, excerpt_id, source_id, observation_order,
               predicate_key, object_text, subject_text, observation_status
        FROM fact_observations
        WHERE run_id = ?
        ORDER BY statement_id, observation_order, observation_id
        """,
        (run_id,),
    ).fetchall()

    statement_buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        predicate_key = str(row["predicate_key"])
        object_text = _normalize_opt_text(row["object_text"])
        statement_id = str(row["statement_id"])
        observation_status = _normalize_status(
            row["observation_status"],
            allowed=OBSERVATION_STATUS_VALUES,
            label="observation_status",
            default="captured",
        )
        if observation_status == "abstained":
            continue
        bucket = statement_buckets.setdefault(
            statement_id,
            {
                "statement_ids": {statement_id},
                "event_type": None,
                "primary_actor": None,
                "secondary_actor": None,
                "object_text": None,
                "location_text": None,
                "instrument_text": None,
                "time_start": None,
                "time_end": None,
                "roles": [],
                "attributes": [],
            },
        )

        if predicate_key in EVENT_TRIGGER_PREDICATES:
            if bucket["event_type"] is None:
                bucket["event_type"] = object_text
            bucket["roles"].append((str(row["observation_id"]), "event_type", predicate_key, object_text))
            continue

        role: str | None = None
        if predicate_key == "actor":
            if bucket["primary_actor"] is None:
                bucket["primary_actor"] = object_text
                role = "primary_actor"
            elif bucket["secondary_actor"] is None and object_text != bucket["primary_actor"]:
                bucket["secondary_actor"] = object_text
                role = "secondary_actor"
        elif predicate_key in {"co_actor", "organization"}:
            if bucket["secondary_actor"] is None:
                bucket["secondary_actor"] = object_text
                role = "secondary_actor"
        elif predicate_key in {"acted_on", "affected_object", "subject_matter", "document_reference"}:
            if bucket["object_text"] is None:
                bucket["object_text"] = object_text
                role = "object_text"
        elif predicate_key in {"event_time", "event_date"}:
            if bucket["time_start"] is None:
                bucket["time_start"] = object_text
                role = "time_start"
        elif predicate_key in EVENT_ATTRIBUTE_PREDICATES:
            bucket["attributes"].append((str(row["observation_id"]), predicate_key, object_text))
            role = "attribute"

        if role:
            bucket["roles"].append((str(row["observation_id"]), role, predicate_key, object_text))

    grouped: dict[tuple[str | None, str | None, str | None, str | None], dict[str, Any]] = {}
    pending_attribute_buckets: list[dict[str, Any]] = []
    for bucket in statement_buckets.values():
        if not bucket["event_type"]:
            if bucket["attributes"] or bucket["roles"]:
                pending_attribute_buckets.append(bucket)
            continue
        signature = (
            _normalize_event_field(bucket["event_type"]),
            _normalize_event_field(bucket["primary_actor"]),
            _normalize_event_field(bucket["object_text"]),
            _normalize_event_field(bucket["time_start"]),
        )
        grouped_bucket = grouped.setdefault(
            signature,
            {
                "statement_ids": set(),
                "event_type": bucket["event_type"],
                "primary_actor": bucket["primary_actor"],
                "secondary_actor": bucket["secondary_actor"],
                "object_text": bucket["object_text"],
                "location_text": bucket["location_text"],
                "instrument_text": bucket["instrument_text"],
                "time_start": bucket["time_start"],
                "time_end": bucket["time_end"],
                "roles": [],
                "attributes": [],
            },
        )
        grouped_bucket["statement_ids"].update(bucket["statement_ids"])
        if grouped_bucket["secondary_actor"] is None:
            grouped_bucket["secondary_actor"] = bucket["secondary_actor"]
        grouped_bucket["roles"].extend(bucket["roles"])
        grouped_bucket["attributes"].extend(bucket["attributes"])

    if len(grouped) == 1:
        sole_bucket = next(iter(grouped.values()))
        for bucket in pending_attribute_buckets:
            sole_bucket["statement_ids"].update(bucket["statement_ids"])
            sole_bucket["roles"].extend(bucket["roles"])
            sole_bucket["attributes"].extend(bucket["attributes"])

    event_count = 0
    attribute_count = 0
    evidence_count = 0
    for index, bucket in enumerate(grouped.values(), start=1):
        if not bucket["event_type"]:
            continue
        role_names = {role for _, role, _, _ in bucket["roles"]}
        if "primary_actor" not in role_names and "secondary_actor" not in role_names:
            continue
        signature_payload = {
            "run_id": run_id,
            "event_type": bucket["event_type"],
            "primary_actor": bucket["primary_actor"],
            "secondary_actor": bucket["secondary_actor"],
            "object_text": bucket["object_text"],
            "time_start": bucket["time_start"],
            "index": index,
        }
        event_id = "event:" + _sha256_payload(signature_payload)[:16]
        confidence = _event_confidence_for_roles(role_names)
        conn.execute(
            """
            INSERT INTO event_candidates(
              event_id, run_id, event_type, primary_actor, secondary_actor, object_text,
              location_text, instrument_text, time_start, time_end, confidence, status, assembler_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                run_id,
                bucket["event_type"],
                bucket["primary_actor"],
                bucket["secondary_actor"],
                bucket["object_text"],
                bucket["location_text"],
                bucket["instrument_text"],
                bucket["time_start"],
                bucket["time_end"],
                confidence,
                _normalize_status("candidate", allowed=EVENT_STATUS_VALUES, label="event_status", default="candidate"),
                EVENT_ASSEMBLER_VERSION,
            ),
        )
        event_count += 1
        for observation_id, role, _predicate_key, _value in bucket["roles"]:
            conn.execute(
                """
                INSERT INTO event_evidence(event_id, observation_id, role, confidence)
                VALUES (?,?,?,?)
                """,
                (event_id, observation_id, role, confidence),
            )
            evidence_count += 1
        for observation_id, attribute_type, attribute_value in bucket["attributes"]:
            conn.execute(
                """
                INSERT INTO event_attributes(event_id, attribute_type, attribute_value, source_observation_id, confidence)
                VALUES (?,?,?,?,?)
                """,
                (event_id, attribute_type, attribute_value or "", observation_id, confidence),
            )
            attribute_count += 1
    return {
        "event_count": event_count,
        "event_attribute_count": attribute_count,
        "event_evidence_count": evidence_count,
    }


def build_fact_intake_payload_from_text_units(
    units: Iterable[TextUnit],
    *,
    source_label: str,
    notes: str | None = None,
) -> dict[str, Any]:
    unit_list = list(units)
    run_basis = {
        "kind": "fact_intake_run",
        "source_label": source_label,
        "units": [
            {
                "unit_id": unit.unit_id,
                "source_id": unit.source_id,
                "source_type": unit.source_type,
                "text": unit.text,
            }
            for unit in unit_list
        ],
    }
    # `run_id` identifies one execution context; structural IDs below remain
    # content-derived within that context and are kept distinct from timestamps.
    run_id = "factrun:" + _sha256_payload(run_basis)
    sources: list[dict[str, Any]] = []
    excerpts: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    seen_sources: dict[tuple[str, str], str] = {}
    source_order = 0
    excerpt_order_by_source: dict[str, int] = {}
    for unit in unit_list:
        source_key = (unit.source_id, unit.source_type)
        source_id = seen_sources.get(source_key)
        if source_id is None:
            source_order += 1
            source_id = f"src:{_sha256_text(f'{run_id}:{unit.source_id}:{unit.source_type}')[:16]}"
            seen_sources[source_key] = source_id
            sources.append(
                {
                    "source_id": source_id,
                    "source_order": source_order,
                    "source_type": unit.source_type,
                    "source_label": unit.source_id,
                    "source_ref": unit.unit_id,
                    "content_sha256": _sha256_text(unit.text),
                    "provenance": {
                        "source_id": unit.source_id,
                        "source_type": unit.source_type,
                    },
                }
            )
            excerpt_order_by_source[source_id] = 0
        excerpt_order_by_source[source_id] += 1
        excerpt_order = excerpt_order_by_source[source_id]
        excerpt_id = f"excerpt:{_sha256_text(f'{run_id}:{unit.unit_id}:excerpt')[:16]}"
        statement_id = f"statement:{_sha256_text(f'{run_id}:{unit.unit_id}:statement')[:16]}"
        fact_id = f"fact:{_sha256_text(f'{run_id}:{unit.unit_id}:fact')[:16]}"
        excerpts.append(
            {
                "excerpt_id": excerpt_id,
                "source_id": source_id,
                "excerpt_order": excerpt_order,
                "excerpt_text": unit.text,
                "char_start": 0,
                "char_end": len(unit.text),
                "anchor_label": unit.unit_id,
                "provenance": {"unit_id": unit.unit_id},
            }
        )
        statements.append(
            {
                "statement_id": statement_id,
                "excerpt_id": excerpt_id,
                "statement_order": 1,
                "statement_text": unit.text,
                "statement_role": "captured_statement",
                "statement_status": "captured",
                "chronology_hint": None,
                "provenance": {"unit_id": unit.unit_id, "sender": "TextUnit"},
            }
        )
        facts.append(
            {
                "fact_id": fact_id,
                "canonical_label": unit.text[:80],
                "fact_text": unit.text,
                "fact_type": "statement_capture",
                "candidate_status": "captured",
                "chronology_sort_key": None,
                "chronology_label": None,
                "primary_statement_id": statement_id,
                "statement_ids": [statement_id],
                "provenance": {"sender": "build_fact_intake_payload_from_text_units"},
            }
        )
    return {
        "run": {
            "run_id": run_id,
            "contract_version": FACT_INTAKE_CONTRACT_VERSION,
            "source_label": source_label,
            "mary_projection_version": MARY_FACT_WORKFLOW_VERSION,
            "notes": notes,
        },
        "sources": sources,
        "excerpts": excerpts,
        "statements": statements,
        "observations": observations,
        "fact_candidates": facts,
        "contestations": [],
        "reviews": [],
    }


def persist_fact_intake_payload(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    deferred_refresh: bool = False,
    progress_callback: Any | None = None,
) -> dict[str, Any]:

    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    run = payload.get("run") if isinstance(payload.get("run"), Mapping) else {}
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("payload.run.run_id is required")
    contract_version = str(run.get("contract_version") or FACT_INTAKE_CONTRACT_VERSION).strip()
    source_label = str(run.get("source_label") or "").strip()
    if not source_label:
        raise ValueError("payload.run.source_label is required")
    mary_projection_version = str(run.get("mary_projection_version") or MARY_FACT_WORKFLOW_VERSION).strip()

    def emit_progress(
        stage: str,
        *,
        status: str,
        section: str | None = None,
        completed: int | None = None,
        total: int | None = None,
        started_at: float | None = None,
        message: str | None = None,
        **extra: Any,
    ) -> None:
        if not callable(progress_callback):
            return
        elapsed_seconds = None if started_at is None else max(time.monotonic() - started_at, 0.0)
        items_per_second = None
        if elapsed_seconds and completed is not None and elapsed_seconds > 0:
            items_per_second = round(completed / elapsed_seconds, 2)
        progress_callback(
            {
                "run_id": run_id,
                "stage": stage,
                "status": status,
                "section": section,
                "completed": completed,
                "total": total,
                "elapsed_seconds": None if elapsed_seconds is None else round(elapsed_seconds, 3),
                "items_per_second": items_per_second,
                "message": message,
                **extra,
            }
        )

    def persist_section(
        stage_prefix: str,
        rows: list[Any],
        *,
        total_label: str,
        insert_row: Any,
        chunk_size: int = 250,
    ) -> int:
        total = len(rows)
        section_started_at = time.monotonic()
        rate_samples: list[float] = []

        def eta_fields(completed: int) -> dict[str, Any]:
            if completed <= 0 or total <= 0:
                return {
                    "eta_seconds_remaining": None,
                    "eta_finish_utc": None,
                    "eta_confidence_interval_seconds": None,
                    "eta_confidence": "none",
                }
            elapsed = max(time.monotonic() - section_started_at, 0.0)
            if elapsed <= 0:
                return {
                    "eta_seconds_remaining": None,
                    "eta_finish_utc": None,
                    "eta_confidence_interval_seconds": None,
                    "eta_confidence": "none",
                }
            current_rate = completed / elapsed
            if current_rate <= 0:
                return {
                    "eta_seconds_remaining": None,
                    "eta_finish_utc": None,
                    "eta_confidence_interval_seconds": None,
                    "eta_confidence": "none",
                }
            rate_samples.append(current_rate)
            remaining = max(total - completed, 0)
            eta_seconds = remaining / current_rate
            finish_at = datetime.now(timezone.utc).timestamp() + eta_seconds
            eta_finish_utc = datetime.fromtimestamp(finish_at, tz=timezone.utc).isoformat()
            if len(rate_samples) >= 2:
                mean_rate = statistics.fmean(rate_samples)
                rate_std = statistics.pstdev(rate_samples) if len(rate_samples) > 1 else 0.0
                low_rate = max(mean_rate - rate_std, 0.001)
                high_rate = max(mean_rate + rate_std, low_rate)
                lower_eta = remaining / high_rate
                upper_eta = remaining / low_rate
                eta_interval = [round(lower_eta, 3), round(upper_eta, 3)]
                eta_confidence = "heuristic_1sigma_rate_band"
            else:
                eta_interval = [round(eta_seconds * 0.5, 3), round(eta_seconds * 1.5, 3)]
                eta_confidence = "heuristic_single_sample_low_confidence"
            return {
                "eta_seconds_remaining": round(eta_seconds, 3),
                "eta_finish_utc": eta_finish_utc,
                "eta_confidence_interval_seconds": eta_interval,
                "eta_confidence": eta_confidence,
            }

        emit_progress(
            f"{stage_prefix}_started",
            status="running",
            section=stage_prefix,
            completed=0,
            total=total,
            started_at=section_started_at,
            message=f"Persisting {total_label}.",
        )
        count = 0
        next_chunk_mark = chunk_size
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            insert_row(row)
            count += 1
            if count >= next_chunk_mark or count == total:
                emit_progress(
                    f"{stage_prefix}_progress",
                    status="running",
                    section=stage_prefix,
                    completed=count,
                    total=total,
                    started_at=section_started_at,
                    message=f"Persisted {count}/{total} {total_label}.",
                    **eta_fields(count),
                )
                next_chunk_mark += chunk_size
        emit_progress(
            f"{stage_prefix}_finished",
            status="ok",
            section=stage_prefix,
            completed=count,
            total=total,
            started_at=section_started_at,
            message=f"Finished persisting {count} {total_label}.",
            eta_seconds_remaining=0.0,
            eta_finish_utc=datetime.now(timezone.utc).isoformat(),
            eta_confidence_interval_seconds=[0.0, 0.0],
            eta_confidence="complete",
        )
        return count

    _delete_run(conn, run_id)
    conn.execute(
        """
        INSERT INTO fact_intake_runs(run_id, contract_version, source_label, mary_projection_version, notes)
        VALUES (?,?,?,?,?)
        """,
        (
            run_id,
            contract_version,
            source_label,
            mary_projection_version,
            _normalize_opt_text(run.get("notes")),
        ),
    )
    source_rows = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    source_count = persist_section(
        "sources",
        list(source_rows),
        total_label="sources",
        insert_row=lambda row: conn.execute(
            """
            INSERT INTO fact_sources(
              source_id, run_id, source_order, source_type, source_label, source_ref, content_sha256, provenance_json
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                str(row.get("source_id") or "").strip(),
                run_id,
                int(row.get("source_order") or 0),
                str(row.get("source_type") or "").strip(),
                str(row.get("source_label") or "").strip(),
                _normalize_opt_text(row.get("source_ref")),
                _normalize_opt_text(row.get("content_sha256")),
                _normalize_json(row.get("provenance")),
            ),
        ),
    )
    excerpt_rows = payload.get("excerpts") if isinstance(payload.get("excerpts"), list) else []
    excerpt_count = persist_section(
        "excerpts",
        list(excerpt_rows),
        total_label="excerpts",
        insert_row=lambda row: conn.execute(
            """
            INSERT INTO fact_excerpts(
              excerpt_id, run_id, source_id, excerpt_order, excerpt_text, char_start, char_end, anchor_label, provenance_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                str(row.get("excerpt_id") or "").strip(),
                run_id,
                str(row.get("source_id") or "").strip(),
                int(row.get("excerpt_order") or 0),
                str(row.get("excerpt_text") or ""),
                row.get("char_start"),
                row.get("char_end"),
                _normalize_opt_text(row.get("anchor_label")),
                _normalize_json(row.get("provenance")),
            ),
        ),
    )
    statement_rows = payload.get("statements") if isinstance(payload.get("statements"), list) else []
    statement_count = persist_section(
        "statements",
        list(statement_rows),
        total_label="statements",
        insert_row=lambda row: conn.execute(
            """
            INSERT INTO fact_statements(
              statement_id, run_id, excerpt_id, statement_order, statement_text, speaker_label,
              statement_role, statement_status, chronology_hint, provenance_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(row.get("statement_id") or "").strip(),
                run_id,
                str(row.get("excerpt_id") or "").strip(),
                int(row.get("statement_order") or 0),
                str(row.get("statement_text") or ""),
                _normalize_opt_text(row.get("speaker_label")),
                _normalize_opt_text(row.get("statement_role")),
                _normalize_status(
                    row.get("statement_status"),
                    allowed=STATEMENT_STATUS_VALUES,
                    label="statement_status",
                    default="captured",
                ),
                _normalize_opt_text(row.get("chronology_hint")),
                _normalize_json(row.get("provenance")),
            ),
        ),
    )
    observation_rows = payload.get("observations") if isinstance(payload.get("observations"), list) else []
    observation_count = persist_section(
        "observations",
        list(observation_rows),
        total_label="observations",
        insert_row=lambda row: (
            lambda predicate_key: conn.execute(
                """
                INSERT INTO fact_observations(
                  observation_id, run_id, statement_id, excerpt_id, source_id, observation_order,
                  predicate_key, predicate_family, object_text, object_type, object_ref, subject_text,
                  observation_status, provenance_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(row.get("observation_id") or "").strip(),
                    run_id,
                    str(row.get("statement_id") or "").strip(),
                    _normalize_opt_text(row.get("excerpt_id")),
                    _normalize_opt_text(row.get("source_id")),
                    int(row.get("observation_order") or 1),
                    predicate_key,
                    (
                        lambda predicate_family: (
                            predicate_family
                            if predicate_family == OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]
                            else (_ for _ in ()).throw(
                                ValueError(
                                    f"predicate_family mismatch for {predicate_key}: expected {OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]}, got {predicate_family}"
                                )
                            )
                        )
                    )(str(row.get("predicate_family") or "").strip() or OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]),
                    str(row.get("object_text") or "").strip(),
                    _normalize_opt_text(row.get("object_type")),
                    _normalize_opt_text(row.get("object_ref")),
                    _normalize_opt_text(row.get("subject_text")),
                    _normalize_status(
                        row.get("observation_status"),
                        allowed=OBSERVATION_STATUS_VALUES,
                        label="observation_status",
                        default="captured",
                    ),
                    _normalize_json(row.get("provenance")),
                ),
            )
        )(_normalize_observation_predicate_key(row.get("predicate_key"))),
    )
    fact_rows = payload.get("fact_candidates") if isinstance(payload.get("fact_candidates"), list) else []
    fact_count = persist_section(
        "facts",
        list(fact_rows),
        total_label="fact candidates",
        insert_row=lambda row: (
            lambda fact_id: (
                conn.execute(
                    """
                    INSERT INTO fact_candidates(
                      fact_id, run_id, canonical_label, fact_text, fact_type, candidate_status,
                      chronology_sort_key, chronology_label, primary_statement_id, provenance_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        fact_id,
                        run_id,
                        _normalize_opt_text(row.get("canonical_label")),
                        str(row.get("fact_text") or ""),
                        str(row.get("fact_type") or ""),
                        _normalize_status(
                            row.get("candidate_status"),
                            allowed=FACT_STATUS_VALUES,
                            label="candidate_status",
                            default="captured",
                        ),
                        _normalize_opt_text(row.get("chronology_sort_key")),
                        _normalize_opt_text(row.get("chronology_label")),
                        _normalize_opt_text(row.get("primary_statement_id")),
                        _normalize_json(row.get("provenance")),
                    ),
                ),
                [
                    conn.execute(
                        """
                        INSERT INTO fact_candidate_statements(fact_id, statement_id, link_kind)
                        VALUES (?,?,?)
                        """,
                        (
                            fact_id,
                            str(statement_id),
                            str(row.get("link_kind") or "supporting_statement"),
                        ),
                    )
                    for statement_id in row.get("statement_ids")
                    if isinstance(row.get("statement_ids"), list)
                ],
            )
        )(str(row.get("fact_id") or "").strip()),
    )
    contestation_rows = payload.get("contestations") if isinstance(payload.get("contestations"), list) else []
    contestation_count = persist_section(
        "contestations",
        list(contestation_rows),
        total_label="contestations",
        insert_row=lambda row: conn.execute(
            """
            INSERT INTO fact_contestations(
              contestation_id, fact_id, statement_id, contestation_status, reason_text, author, provenance_json
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                str(row.get("contestation_id") or "").strip(),
                str(row.get("fact_id") or "").strip(),
                _normalize_opt_text(row.get("statement_id")),
                str(row.get("contestation_status") or "").strip(),
                str(row.get("reason_text") or "").strip(),
                _normalize_opt_text(row.get("author")),
                _normalize_json(row.get("provenance")),
            ),
        ),
    )
    review_rows = payload.get("reviews") if isinstance(payload.get("reviews"), list) else []
    review_count = persist_section(
        "reviews",
        list(review_rows),
        total_label="reviews",
        insert_row=lambda row: conn.execute(
            """
            INSERT INTO fact_reviews(
              review_id, fact_id, review_status, reviewer, note, provenance_json
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                str(row.get("review_id") or "").strip(),
                str(row.get("fact_id") or "").strip(),
                str(row.get("review_status") or "").strip(),
                str(row.get("reviewer") or "").strip(),
                _normalize_opt_text(row.get("note")),
                _normalize_json(row.get("provenance")),
            ),
        ),
    )
    emit_progress("event_assembly_started", status="running", section="event_assembly", message="Assembling event candidates.")
    event_summary = _assemble_event_candidates(conn, run_id=run_id)
    emit_progress(
        "event_assembly_finished",
        status="ok",
        section="event_assembly",
        completed=int(event_summary.get("event_count") or 0),
        total=int(fact_count),
        message="Event candidate assembly finished.",
    )
    conn.commit()
    semantic_summary: dict[str, Any] = {"assertion_count": 0, "relation_count": 0, "policy_count": 0}
    if not deferred_refresh:
        semantic_summary = persist_fact_semantic_materialization(
            conn,
            run_id=run_id,
            include_zelph=True,
            refresh_kind="dual_write",
            progress_callback=progress_callback,
        )
    else:
        refresh_id = _stable_id(
            "semrefresh",
            {
                "run_id": run_id,
                "ruleset_version": FACT_REVIEW_ZELPH_RULESET_VERSION,
                "refresh_kind": "dual_write",
                "include_zelph": True,
            },
        )
        _upsert_semantic_refresh_run(
            conn,
            refresh_id=refresh_id,
            run_id=run_id,
            refresh_kind="dual_write",
            refresh_status="pending",
            current_stage="deferred",
            status_message="Fact intake complete; semantic refresh deferred to background.",
            facts_serialized_count=0,
            assertion_count=0,
            relation_count=0,
            policy_count=0,
        )

    conn.commit()
    return {
        "run_id": run_id,
        "source_count": source_count,
        "excerpt_count": excerpt_count,
        "statement_count": statement_count,
        "observation_count": observation_count,
        "fact_count": fact_count,
        "contestation_count": contestation_count,
        "review_count": review_count,
        **event_summary,
        "semantic_assertion_count": semantic_summary["assertion_count"],
        "semantic_relation_count": semantic_summary["relation_count"],
        "semantic_policy_count": semantic_summary["policy_count"],
        "refresh_status": "deferred" if deferred_refresh else "ok",
    }



def _json_or_empty(text: str | None) -> Any:
    if not text:
        return {}
    return json.loads(text)


def _json_or_list(text: str | None) -> list[Any]:
    if not text:
        return []
    loaded = json.loads(text)
    return loaded if isinstance(loaded, list) else []


def _json_or_dict(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    loaded = json.loads(text)
    return loaded if isinstance(loaded, dict) else {}


def _build_contested_review_run_id(payload: Mapping[str, Any]) -> str:
    source_input = payload.get("source_input") if isinstance(payload.get("source_input"), Mapping) else {}
    affidavit_input = payload.get("affidavit_input") if isinstance(payload.get("affidavit_input"), Mapping) else {}
    affidavit_rows = payload.get("affidavit_rows") if isinstance(payload.get("affidavit_rows"), list) else []
    source_review_rows = payload.get("source_review_rows") if isinstance(payload.get("source_review_rows"), list) else []
    identity = {
        "version": payload.get("version"),
        "fixture_kind": payload.get("fixture_kind"),
        "source_input": {
            "path": source_input.get("path"),
            "source_kind": source_input.get("source_kind"),
            "source_label": source_input.get("source_label"),
        },
        "affidavit_input": {
            "path": affidavit_input.get("path"),
            "character_count": affidavit_input.get("character_count"),
        },
        "affidavit_rows": [
            {
                "proposition_id": row.get("proposition_id"),
                "text": row.get("text"),
                "coverage_status": row.get("coverage_status"),
                "best_source_row_id": row.get("best_source_row_id"),
                "promotion_status": row.get("promotion_status"),
                "support_direction": row.get("support_direction"),
                "conflict_state": row.get("conflict_state"),
                "evidentiary_state": row.get("evidentiary_state"),
                "operational_status": row.get("operational_status"),
            }
            for row in affidavit_rows
            if isinstance(row, Mapping)
        ],
        "source_review_rows": [
            {
                "source_row_id": row.get("source_row_id"),
                "review_status": row.get("review_status"),
                "best_affidavit_proposition_id": row.get("best_affidavit_proposition_id"),
            }
            for row in source_review_rows
            if isinstance(row, Mapping)
        ],
    }
    return _stable_id("contested_review", identity)


def persist_contested_affidavit_review(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row

    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError("payload.version is required")
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    source_input = payload.get("source_input") if isinstance(payload.get("source_input"), Mapping) else {}
    affidavit_input = payload.get("affidavit_input") if isinstance(payload.get("affidavit_input"), Mapping) else {}
    affidavit_rows = payload.get("affidavit_rows") if isinstance(payload.get("affidavit_rows"), list) else []
    source_review_rows = payload.get("source_review_rows") if isinstance(payload.get("source_review_rows"), list) else []
    zelph_facts = payload.get("zelph_claim_state_facts") if isinstance(payload.get("zelph_claim_state_facts"), list) else []

    review_run_id = _build_contested_review_run_id(payload)
    payload_sha256 = _sha256_payload(payload)
    _delete_contested_review_run(conn, review_run_id)
    conn.execute(
        """
        INSERT INTO contested_review_runs(
          review_run_id, artifact_version, fixture_kind, source_kind, source_label,
          source_input_path, affidavit_input_path, source_row_count, affidavit_proposition_count,
          covered_count, partial_count, contested_affidavit_count, unsupported_affidavit_count,
          missing_review_count, contested_source_count, abstained_source_count,
          semantic_basis_counts_json, promotion_status_counts_json, support_direction_counts_json,
          conflict_state_counts_json, evidentiary_state_counts_json, operational_status_counts_json,
          payload_sha256
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            review_run_id,
            version,
            _normalize_opt_text(payload.get("fixture_kind")),
            _normalize_opt_text(source_input.get("source_kind")),
            _normalize_opt_text(source_input.get("source_label")),
            _normalize_opt_text(source_input.get("path")),
            _normalize_opt_text(affidavit_input.get("path")),
            int(summary.get("source_row_count") or 0),
            int(summary.get("affidavit_proposition_count") or 0),
            int(summary.get("covered_count") or 0),
            int(summary.get("partial_count") or 0),
            int(summary.get("contested_affidavit_count") or 0),
            int(summary.get("unsupported_affidavit_count") or 0),
            int(summary.get("missing_review_count") or 0),
            int(summary.get("contested_source_count") or 0),
            int(summary.get("abstained_source_count") or 0),
            _normalize_json(summary.get("semantic_basis_counts")),
            _normalize_json(summary.get("promotion_status_counts")),
            _normalize_json(summary.get("support_direction_counts")),
            _normalize_json(summary.get("conflict_state_counts")),
            _normalize_json(summary.get("evidentiary_state_counts")),
            _normalize_json(summary.get("operational_status_counts")),
            payload_sha256,
        ),
    )

    for row in affidavit_rows:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO contested_review_affidavit_rows(
              review_run_id, proposition_id, paragraph_id, paragraph_order, sentence_order,
              proposition_text, coverage_status, best_source_row_id, best_match_score,
              best_adjusted_match_score, best_match_basis, best_match_excerpt,
              duplicate_match_excerpt, best_response_role, support_status, semantic_basis,
              promotion_status, promotion_basis, promotion_reason, support_direction,
              conflict_state, evidentiary_state, operational_status, relation_root,
              relation_leaf, primary_target_component, explanation_json,
              missing_dimensions_json, semantic_candidate_json, claim_json,
              response_json, justifications_json, matched_source_rows_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                review_run_id,
                str(row.get("proposition_id") or "").strip(),
                _normalize_opt_text(row.get("paragraph_id")),
                int(row.get("paragraph_order") or 0),
                int(row.get("sentence_order") or 0),
                str(row.get("text") or ""),
                _normalize_opt_text(row.get("coverage_status")),
                _normalize_opt_text(row.get("best_source_row_id")),
                row.get("best_match_score"),
                row.get("best_adjusted_match_score"),
                _normalize_opt_text(row.get("best_match_basis")),
                _normalize_opt_text(row.get("best_match_excerpt")),
                _normalize_opt_text(row.get("duplicate_match_excerpt")),
                _normalize_opt_text(row.get("best_response_role")),
                _normalize_opt_text(row.get("support_status")),
                _normalize_opt_text(row.get("semantic_basis")),
                _normalize_opt_text(row.get("promotion_status")),
                _normalize_opt_text(row.get("promotion_basis")),
                _normalize_opt_text(row.get("promotion_reason")),
                _normalize_opt_text(row.get("support_direction")),
                _normalize_opt_text(row.get("conflict_state")),
                _normalize_opt_text(row.get("evidentiary_state")),
                _normalize_opt_text(row.get("operational_status")),
                _normalize_opt_text(row.get("relation_root")),
                _normalize_opt_text(row.get("relation_leaf")),
                _normalize_opt_text(row.get("primary_target_component")),
                _normalize_json(row.get("explanation")),
                _normalize_json(row.get("missing_dimensions")),
                _normalize_json(row.get("semantic_candidate")),
                _normalize_json(row.get("claim")),
                _normalize_json(row.get("response")),
                _normalize_json(row.get("justifications")),
                _normalize_json(row.get("matched_source_rows")),
            ),
        )

    for row in source_review_rows:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO contested_review_source_rows(
              review_run_id, source_row_id, source_kind, source_text, candidate_status, review_status,
              best_affidavit_proposition_id, best_match_score, best_adjusted_match_score,
              best_match_basis, best_match_excerpt, best_response_role,
              matched_affidavit_proposition_ids_json, related_affidavit_proposition_ids_json,
              reason_codes_json, workload_classes_json, candidate_anchors_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                review_run_id,
                str(row.get("source_row_id") or "").strip(),
                _normalize_opt_text(row.get("source_kind")),
                str(row.get("text") or ""),
                _normalize_opt_text(row.get("candidate_status")),
                _normalize_opt_text(row.get("review_status")),
                _normalize_opt_text(row.get("best_affidavit_proposition_id")),
                row.get("best_match_score"),
                row.get("best_adjusted_match_score"),
                _normalize_opt_text(row.get("best_match_basis")),
                _normalize_opt_text(row.get("best_match_excerpt")),
                _normalize_opt_text(row.get("best_response_role")),
                _normalize_json(row.get("matched_affidavit_proposition_ids")),
                _normalize_json(row.get("related_affidavit_proposition_ids")),
                _normalize_json(row.get("reason_codes")),
                _normalize_json(row.get("workload_classes")),
                _normalize_json(row.get("candidate_anchors")),
            ),
        )

    for row in zelph_facts:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO contested_review_zelph_facts(
              review_run_id, fact_id, proposition_id, best_source_row_id, fact_kind,
              semantic_basis, promotion_status, promotion_basis, support_direction,
              conflict_state, evidentiary_state, operational_status, fact_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                review_run_id,
                str(row.get("fact_id") or "").strip(),
                _normalize_opt_text(row.get("proposition_id")),
                _normalize_opt_text(row.get("best_source_row_id")),
                _normalize_opt_text(row.get("fact_kind")),
                _normalize_opt_text(row.get("semantic_basis")),
                _normalize_opt_text(row.get("promotion_status")),
                _normalize_opt_text(row.get("promotion_basis")),
                _normalize_opt_text(row.get("support_direction")),
                _normalize_opt_text(row.get("conflict_state")),
                _normalize_opt_text(row.get("evidentiary_state")),
                _normalize_opt_text(row.get("operational_status")),
                _normalize_json(row),
            ),
        )

    conn.commit()
    return {
        "review_run_id": review_run_id,
        "artifact_version": version,
        "affidavit_row_count": len([row for row in affidavit_rows if isinstance(row, Mapping)]),
        "source_row_count": len([row for row in source_review_rows if isinstance(row, Mapping)]),
        "zelph_fact_count": len([row for row in zelph_facts if isinstance(row, Mapping)]),
        "payload_sha256": payload_sha256,
    }


def list_contested_affidavit_review_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    source_kind: str | None = None,
    source_label: str | None = None,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where: list[str] = []
    params: list[Any] = []
    if source_kind:
        where.append("source_kind = ?")
        params.append(str(source_kind))
    if source_label:
        where.append("source_label = ?")
        params.append(str(source_label))
    sql = """
        SELECT review_run_id, artifact_version, fixture_kind, source_kind, source_label,
               source_input_path, affidavit_input_path, source_row_count, affidavit_proposition_count,
               covered_count, partial_count, contested_affidavit_count, unsupported_affidavit_count,
               missing_review_count, contested_source_count, abstained_source_count,
               semantic_basis_counts_json, promotion_status_counts_json, created_at
        FROM contested_review_runs
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, review_run_id DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [
        {
            "review_run_id": str(row["review_run_id"]),
            "artifact_version": str(row["artifact_version"]),
            "fixture_kind": _normalize_opt_text(row["fixture_kind"]),
            "source_kind": _normalize_opt_text(row["source_kind"]),
            "source_label": _normalize_opt_text(row["source_label"]),
            "source_input_path": _normalize_opt_text(row["source_input_path"]),
            "affidavit_input_path": _normalize_opt_text(row["affidavit_input_path"]),
            "source_row_count": int(row["source_row_count"] or 0),
            "affidavit_proposition_count": int(row["affidavit_proposition_count"] or 0),
            "covered_count": int(row["covered_count"] or 0),
            "partial_count": int(row["partial_count"] or 0),
            "contested_affidavit_count": int(row["contested_affidavit_count"] or 0),
            "unsupported_affidavit_count": int(row["unsupported_affidavit_count"] or 0),
            "missing_review_count": int(row["missing_review_count"] or 0),
            "contested_source_count": int(row["contested_source_count"] or 0),
            "abstained_source_count": int(row["abstained_source_count"] or 0),
            "semantic_basis_counts": _json_or_dict(row["semantic_basis_counts_json"]),
            "promotion_status_counts": _json_or_dict(row["promotion_status_counts_json"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def build_contested_affidavit_review_summary(
    conn: sqlite3.Connection,
    *,
    review_run_id: str,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    run_row = conn.execute(
        """
        SELECT *
        FROM contested_review_runs
        WHERE review_run_id = ?
        """,
        (str(review_run_id or "").strip(),),
    ).fetchone()
    if run_row is None:
        raise ValueError(f"Unknown contested review run: {review_run_id}")
    affidavit_rows = conn.execute(
        """
        SELECT proposition_id, paragraph_id, paragraph_order, sentence_order, proposition_text,
               coverage_status, best_source_row_id, best_match_score, best_adjusted_match_score,
               best_match_basis, best_match_excerpt, duplicate_match_excerpt, best_response_role,
               support_status, semantic_basis, promotion_status, promotion_basis, promotion_reason,
               support_direction, conflict_state, evidentiary_state, operational_status,
               relation_root, relation_leaf, primary_target_component, explanation_json,
               missing_dimensions_json, semantic_candidate_json, claim_json, response_json,
               justifications_json, matched_source_rows_json
        FROM contested_review_affidavit_rows
        WHERE review_run_id = ?
        ORDER BY paragraph_order ASC, sentence_order ASC, proposition_id ASC
        """,
        (review_run_id,),
    ).fetchall()
    source_rows = conn.execute(
        """
        SELECT source_row_id, source_kind, source_text, candidate_status, review_status,
               best_affidavit_proposition_id, best_match_score, best_adjusted_match_score,
               best_match_basis, best_match_excerpt, best_response_role,
               matched_affidavit_proposition_ids_json, related_affidavit_proposition_ids_json,
               reason_codes_json, workload_classes_json, candidate_anchors_json
        FROM contested_review_source_rows
        WHERE review_run_id = ?
        ORDER BY source_row_id ASC
        """,
        (review_run_id,),
    ).fetchall()
    zelph_rows = conn.execute(
        """
        SELECT fact_id, proposition_id, best_source_row_id, fact_kind, semantic_basis,
               promotion_status, promotion_basis, support_direction, conflict_state,
               evidentiary_state, operational_status, fact_json
        FROM contested_review_zelph_facts
        WHERE review_run_id = ?
        ORDER BY fact_id ASC
        """,
        (review_run_id,),
    ).fetchall()
    run = {
        "review_run_id": str(run_row["review_run_id"]),
        "artifact_version": str(run_row["artifact_version"]),
        "fixture_kind": _normalize_opt_text(run_row["fixture_kind"]),
        "source_kind": _normalize_opt_text(run_row["source_kind"]),
        "source_label": _normalize_opt_text(run_row["source_label"]),
        "source_input_path": _normalize_opt_text(run_row["source_input_path"]),
        "affidavit_input_path": _normalize_opt_text(run_row["affidavit_input_path"]),
        "created_at": str(run_row["created_at"]),
    }
    summary = {
        "source_row_count": int(run_row["source_row_count"] or 0),
        "affidavit_proposition_count": int(run_row["affidavit_proposition_count"] or 0),
        "covered_count": int(run_row["covered_count"] or 0),
        "partial_count": int(run_row["partial_count"] or 0),
        "contested_affidavit_count": int(run_row["contested_affidavit_count"] or 0),
        "unsupported_affidavit_count": int(run_row["unsupported_affidavit_count"] or 0),
        "missing_review_count": int(run_row["missing_review_count"] or 0),
        "contested_source_count": int(run_row["contested_source_count"] or 0),
        "abstained_source_count": int(run_row["abstained_source_count"] or 0),
        "semantic_basis_counts": _json_or_dict(run_row["semantic_basis_counts_json"]),
        "promotion_status_counts": _json_or_dict(run_row["promotion_status_counts_json"]),
        "support_direction_counts": _json_or_dict(run_row["support_direction_counts_json"]),
        "conflict_state_counts": _json_or_dict(run_row["conflict_state_counts_json"]),
        "evidentiary_state_counts": _json_or_dict(run_row["evidentiary_state_counts_json"]),
        "operational_status_counts": _json_or_dict(run_row["operational_status_counts_json"]),
    }
    return {
        "run": run,
        "summary": summary,
        "affidavit_rows": [
            (
                lambda affidavit_row: {
                **affidavit_row,
                "status_explanation": _build_affidavit_status_explanation(affidavit_row),
            }
            )(
                {
                "proposition_id": str(row["proposition_id"]),
                "paragraph_id": _normalize_opt_text(row["paragraph_id"]),
                "paragraph_order": int(row["paragraph_order"] or 0),
                "sentence_order": int(row["sentence_order"] or 0),
                "text": str(row["proposition_text"] or ""),
                "coverage_status": _normalize_opt_text(row["coverage_status"]),
                "best_source_row_id": _normalize_opt_text(row["best_source_row_id"]),
                "best_match_score": row["best_match_score"],
                "best_adjusted_match_score": row["best_adjusted_match_score"],
                "best_match_basis": _normalize_opt_text(row["best_match_basis"]),
                "best_match_excerpt": _normalize_opt_text(row["best_match_excerpt"]),
                "duplicate_match_excerpt": _normalize_opt_text(row["duplicate_match_excerpt"]),
                "best_response_role": _normalize_opt_text(row["best_response_role"]),
                "support_status": _normalize_opt_text(row["support_status"]),
                "semantic_basis": _normalize_opt_text(row["semantic_basis"]),
                "promotion_status": _normalize_opt_text(row["promotion_status"]),
                "promotion_basis": _normalize_opt_text(row["promotion_basis"]),
                "promotion_reason": _normalize_opt_text(row["promotion_reason"]),
                "support_direction": _normalize_opt_text(row["support_direction"]),
                "conflict_state": _normalize_opt_text(row["conflict_state"]),
                "evidentiary_state": _normalize_opt_text(row["evidentiary_state"]),
                "operational_status": _normalize_opt_text(row["operational_status"]),
                "relation_root": _normalize_opt_text(row["relation_root"]),
                "relation_leaf": _normalize_opt_text(row["relation_leaf"]),
                "primary_target_component": _normalize_opt_text(row["primary_target_component"]),
                "explanation": _json_or_dict(row["explanation_json"]),
                "missing_dimensions": _json_or_list(row["missing_dimensions_json"]),
                "semantic_candidate": _json_or_dict(row["semantic_candidate_json"]),
                "claim": _json_or_dict(row["claim_json"]),
                "response": _json_or_dict(row["response_json"]),
                "justifications": _json_or_list(row["justifications_json"]),
                "matched_source_rows": _json_or_list(row["matched_source_rows_json"]),
            }
            )
            for row in affidavit_rows
        ],
        "source_review_rows": [
            (
                lambda source_row: {
                **source_row,
                "status_explanation": _build_source_status_explanation(source_row),
            }
            )(
                {
                "source_row_id": str(row["source_row_id"]),
                "source_kind": _normalize_opt_text(row["source_kind"]),
                "text": str(row["source_text"] or ""),
                "candidate_status": _normalize_opt_text(row["candidate_status"]),
                "review_status": _normalize_opt_text(row["review_status"]),
                "best_affidavit_proposition_id": _normalize_opt_text(row["best_affidavit_proposition_id"]),
                "best_match_score": row["best_match_score"],
                "best_adjusted_match_score": row["best_adjusted_match_score"],
                "best_match_basis": _normalize_opt_text(row["best_match_basis"]),
                "best_match_excerpt": _normalize_opt_text(row["best_match_excerpt"]),
                "best_response_role": _normalize_opt_text(row["best_response_role"]),
                "matched_affidavit_proposition_ids": _json_or_list(row["matched_affidavit_proposition_ids_json"]),
                "related_affidavit_proposition_ids": _json_or_list(row["related_affidavit_proposition_ids_json"]),
                "reason_codes": _json_or_list(row["reason_codes_json"]),
                "workload_classes": _json_or_list(row["workload_classes_json"]),
                "candidate_anchors": _json_or_list(row["candidate_anchors_json"]),
            }
            )
            for row in source_rows
        ],
        "zelph_claim_state_facts": [
            {
                **_json_or_dict(row["fact_json"]),
                "fact_id": str(row["fact_id"]),
                "proposition_id": _normalize_opt_text(row["proposition_id"]),
                "best_source_row_id": _normalize_opt_text(row["best_source_row_id"]),
                "fact_kind": _normalize_opt_text(row["fact_kind"]),
                "semantic_basis": _normalize_opt_text(row["semantic_basis"]),
                "promotion_status": _normalize_opt_text(row["promotion_status"]),
                "promotion_basis": _normalize_opt_text(row["promotion_basis"]),
                "support_direction": _normalize_opt_text(row["support_direction"]),
                "conflict_state": _normalize_opt_text(row["conflict_state"]),
                "evidentiary_state": _normalize_opt_text(row["evidentiary_state"]),
                "operational_status": _normalize_opt_text(row["operational_status"]),
            }
            for row in zelph_rows
        ],
    }


_SUPPORTED_AFFIDAVIT_STATUSES = {"covered"}
_DISPUTED_AFFIDAVIT_STATUSES = {"contested_source", "contested_affidavit"}
_MISSING_AFFIDAVIT_STATUSES = {"unsupported_affidavit"}
_CLARIFY_AFFIDAVIT_STATUSES = {"partial"}
_DISPUTED_SOURCE_REVIEW_STATUSES = {"contested_source"}
_CLARIFY_SOURCE_REVIEW_STATUSES = {"missing_review", "abstained_source"}


def _status_label(code: str | None) -> str | None:
    normalized = str(code or "").strip()
    if not normalized:
        return None
    if normalized in REVIEW_REASON_LABELS:
        return REVIEW_REASON_LABELS[normalized]
    return normalized.replace("_", " ").title()


def _next_action_for_stage(stage: str) -> str:
    if stage == "resolved":
        return "record_state"
    if stage == "clarify":
        return "clarify_match"
    if stage == "review_source":
        return "review_source_rows"
    if stage == "adjudicate":
        return "adjudicate_conflict"
    return "inspect_row"


def _stringify_reason_details(values: Iterable[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        items.append(text)
    return list(dict.fromkeys(items))


def _render_reason_summary(
    *,
    reason_labels: Iterable[str],
    detail_labels: Iterable[str],
) -> str | None:
    parts: list[str] = []
    seen_keys: set[str] = set()
    for value in [*_stringify_reason_details(reason_labels), *_stringify_reason_details(detail_labels)]:
        key = value.casefold()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        parts.append(value)
    return "; ".join(parts) if parts else None


def _detail_label(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return normalized.replace("_", " ")


def _is_low_information_detail(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold()
    return normalized in {"captured", "candidate", "unknown", "other"}


def _build_status_explanation_base(
    *,
    status_scope: str,
    status_value: str | None,
    status_bucket: str,
    why: str | None,
    reason_codes: list[str],
    related_record_id: str | None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_codes = [str(value).strip() for value in reason_codes if str(value).strip()]
    normalized_bucket = str(status_bucket).strip() or "inspect"
    normalized_details = dict(details or {})
    normalized_labels = [label for label in (_status_label(code) for code in normalized_codes) if label]
    return {
        "status_scope": str(status_scope).strip(),
        "status_value": _normalize_opt_text(status_value) or "unknown",
        "status_bucket": normalized_bucket,
        "why": _normalize_opt_text(why),
        "next_action": _next_action_for_stage(normalized_bucket),
        "primary_reason_code": normalized_codes[0] if normalized_codes else None,
        "reason_codes": normalized_codes,
        "reason_labels": normalized_labels,
        "related_record_id": _normalize_opt_text(related_record_id),
        "details": normalized_details,
    }


def _build_affidavit_status_explanation(row: Mapping[str, Any]) -> dict[str, Any]:
    coverage_status = str(row.get("coverage_status") or "").strip()
    support_status = str(row.get("support_status") or "").strip()
    relation_root = str(row.get("relation_root") or "").strip()
    relation_leaf = str(row.get("relation_leaf") or "").strip()
    best_source_row_id = _normalize_opt_text(row.get("best_source_row_id"))
    explanation = row.get("explanation") if isinstance(row.get("explanation"), Mapping) else {}
    missing_dimensions = [str(value) for value in row.get("missing_dimensions", []) if str(value).strip()]
    rendered_reason = _normalize_opt_text(explanation.get("reason"))
    matched_response = _normalize_opt_text(explanation.get("matched_response"))
    if coverage_status == "covered":
        status_bucket = "resolved"
    elif coverage_status == "partial":
        status_bucket = "clarify"
    elif coverage_status in {"unsupported_affidavit", "missing_review"}:
        status_bucket = "review_source"
    elif coverage_status in {"contested_affidavit", "contested_source", "abstained_source"}:
        status_bucket = "adjudicate"
    else:
        status_bucket = "inspect"
    reason_codes = [relation_leaf or support_status or coverage_status or "unknown"]
    details = {
        "support_status": support_status or None,
        "relation_root": relation_root or None,
        "relation_leaf": relation_leaf or None,
        "matched_response": matched_response,
        "missing_dimensions": missing_dimensions,
        "legacy_reason": rendered_reason,
    }
    status_explanation = _build_status_explanation_base(
        status_scope="coverage",
        status_value=coverage_status,
        status_bucket=status_bucket,
        why=None,
        reason_codes=reason_codes,
        related_record_id=best_source_row_id,
        details=details,
    )
    detail_labels = [
        _detail_label(relation_leaf),
        *(f"missing {value.replace('_', ' ')}" for value in missing_dimensions),
    ]
    status_explanation["why"] = _render_reason_summary(
        reason_labels=status_explanation["reason_labels"],
        detail_labels=detail_labels,
    ) or rendered_reason
    return status_explanation


def _build_source_status_explanation(row: Mapping[str, Any]) -> dict[str, Any]:
    review_status = str(row.get("review_status") or "").strip()
    candidate_status = str(row.get("candidate_status") or "").strip()
    best_match_basis = _normalize_opt_text(row.get("best_match_basis"))
    best_response_role = _normalize_opt_text(row.get("best_response_role"))
    reason_codes = [str(value) for value in row.get("reason_codes", []) if str(value).strip()]
    workload_classes = [str(value) for value in row.get("workload_classes", []) if str(value).strip()]
    best_affidavit_proposition_id = _normalize_opt_text(row.get("best_affidavit_proposition_id"))
    matched_affidavit_proposition_ids = [
        str(value) for value in row.get("matched_affidavit_proposition_ids", []) if str(value).strip()
    ]
    related_affidavit_proposition_ids = [
        str(value) for value in row.get("related_affidavit_proposition_ids", []) if str(value).strip()
    ]
    if review_status in _DISPUTED_SOURCE_REVIEW_STATUSES:
        status_bucket = "adjudicate"
    elif review_status in _CLARIFY_SOURCE_REVIEW_STATUSES:
        status_bucket = "review_source"
    elif review_status == "covered":
        status_bucket = "resolved"
    else:
        status_bucket = "inspect"
    details = {
        "candidate_status": candidate_status or None,
        "best_match_basis": best_match_basis,
        "best_response_role": best_response_role,
        "workload_classes": workload_classes,
        "matched_affidavit_proposition_ids": matched_affidavit_proposition_ids,
        "related_affidavit_proposition_ids": related_affidavit_proposition_ids,
    }
    status_explanation = _build_status_explanation_base(
        status_scope="review",
        status_value=review_status,
        status_bucket=status_bucket,
        why=None,
        reason_codes=reason_codes or [review_status or candidate_status or "unknown"],
        related_record_id=best_affidavit_proposition_id,
        details=details,
    )
    proposition_count = len(related_affidavit_proposition_ids or matched_affidavit_proposition_ids)
    proposition_label = (
        f"linked proposition set ({proposition_count} row{'s' if proposition_count != 1 else ''})"
        if proposition_count
        else None
    )
    detail_labels = [
        *(value.replace("_", " ") for value in workload_classes),
        None if _is_low_information_detail(candidate_status) else _detail_label(candidate_status),
        None if _is_low_information_detail(best_match_basis) else _detail_label(best_match_basis),
        None if _is_low_information_detail(best_response_role) else _detail_label(best_response_role),
        proposition_label,
    ]
    status_explanation["why"] = _render_reason_summary(
        reason_labels=status_explanation["reason_labels"],
        detail_labels=detail_labels,
    )
    return status_explanation


def _build_review_queue_status_explanation(row: Mapping[str, Any]) -> dict[str, Any]:
    latest_review_status = str(row.get("latest_review_status") or "").strip()
    candidate_status = str(row.get("candidate_status") or "").strip()
    reason_codes = [str(value) for value in row.get("reason_codes", []) if str(value).strip()]
    source_signal_classes = [str(value) for value in row.get("source_signal_classes", []) if str(value).strip()]
    primary_contested_reason_text = _normalize_opt_text(row.get("primary_contested_reason_text"))
    if latest_review_status in {"contested", "disputed"} or bool(row.get("contestation_count")):
        status_bucket = "adjudicate"
    elif latest_review_status == "needs_followup":
        status_bucket = "clarify"
    elif latest_review_status in {"reviewed", "resolved"}:
        status_bucket = "resolved"
    elif latest_review_status in {"review_queue", "open"} or not latest_review_status:
        status_bucket = "review_source"
    else:
        status_bucket = "inspect"
    details = {
        "candidate_status": candidate_status or None,
        "chronology_bucket": _normalize_opt_text(row.get("chronology_bucket")),
        "chronology_impacted": bool(row.get("chronology_impacted")),
        "primary_contested_reason_text": primary_contested_reason_text,
        "source_signal_classes": source_signal_classes,
        "event_ids": [str(value) for value in row.get("event_ids", []) if str(value).strip()],
    }
    status_explanation = _build_status_explanation_base(
        status_scope="review",
        status_value=latest_review_status or ("needs_review" if bool(row.get("needs_review")) else candidate_status),
        status_bucket=status_bucket,
        why=None,
        reason_codes=reason_codes or [latest_review_status or candidate_status or "review_pending"],
        related_record_id=_normalize_opt_text(row.get("fact_id")),
        details=details,
    )
    detail_labels = [
        None if _is_low_information_detail(candidate_status) else _detail_label(candidate_status),
        _detail_label(row.get("chronology_bucket")),
        "chronology impacted" if bool(row.get("chronology_impacted")) else None,
        primary_contested_reason_text,
        *(value.replace("_", " ") for value in source_signal_classes),
    ]
    status_explanation["why"] = _render_reason_summary(
        reason_labels=status_explanation["reason_labels"],
        detail_labels=detail_labels,
    )
    return status_explanation


def _extract_interrogative_labels_from_relation_graph(
    relation_graph: Mapping[str, Any] | None,
    *,
    node_kind: str,
) -> list[str]:
    if not isinstance(relation_graph, Mapping):
        return []
    nodes = relation_graph.get("nodes")
    if not isinstance(nodes, list):
        return []
    values: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        if _normalize_opt_text(node.get("node_kind")) != node_kind:
            continue
        label = _normalize_opt_text(node.get("label")) or _normalize_opt_text(node.get("value"))
        if label:
            values.append(label)
    return list(dict.fromkeys(values))


def _claim_component_texts(claim: Mapping[str, Any] | None, key: str) -> list[str]:
    if not isinstance(claim, Mapping):
        return []
    components = claim.get("components")
    if not isinstance(components, Mapping):
        return []
    value = components.get(key)
    if isinstance(value, str):
        text = _normalize_opt_text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        values: list[str] = []
        for candidate_key in ("text", "text_span", "label", "value"):
            text = _normalize_opt_text(value.get(candidate_key))
            if text:
                values.append(text)
        return list(dict.fromkeys(values))
    if isinstance(value, list):
        values = []
        for item in value:
            if isinstance(item, str):
                text = _normalize_opt_text(item)
                if text:
                    values.append(text)
            elif isinstance(item, Mapping):
                for candidate_key in ("text", "text_span", "label", "value"):
                    text = _normalize_opt_text(item.get(candidate_key))
                    if text:
                        values.append(text)
        return list(dict.fromkeys(values))
    return []


def build_interrogative_view(
    record: Mapping[str, Any],
    *,
    relation_graph: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status_explanation = record.get("status_explanation") if isinstance(record.get("status_explanation"), Mapping) else {}
    details = status_explanation.get("details") if isinstance(status_explanation.get("details"), Mapping) else {}
    claim = record.get("claim") if isinstance(record.get("claim"), Mapping) else {}
    response = record.get("response") if isinstance(record.get("response"), Mapping) else {}

    who = _extract_interrogative_labels_from_relation_graph(relation_graph, node_kind="actor")
    if not who:
        who = _claim_component_texts(claim, "actor")

    what = _extract_interrogative_labels_from_relation_graph(relation_graph, node_kind="object")
    if not what:
        what = _claim_component_texts(claim, "predicate_text")
    if not what:
        primary_target_component = _normalize_opt_text(record.get("primary_target_component"))
        if primary_target_component:
            what = [primary_target_component]

    how = _extract_interrogative_labels_from_relation_graph(relation_graph, node_kind="action")
    if not how:
        response_acts = response.get("acts") if isinstance(response.get("acts"), list) else []
        how = [str(value) for value in response_acts if str(value).strip()]
    if not how:
        best_response_role = _normalize_opt_text(record.get("best_response_role"))
        if best_response_role:
            how = [best_response_role]

    when = _claim_component_texts(claim, "time")
    paragraph_order = record.get("paragraph_order")
    sentence_order = record.get("sentence_order")
    if paragraph_order not in (None, ""):
        when.append(f"paragraph:{int(paragraph_order)}")
    if sentence_order not in (None, ""):
        when.append(f"sentence:{int(sentence_order)}")
    when = list(dict.fromkeys(when))

    where_values: list[str] = []
    for key in ("source_row_id", "best_source_row_id", "related_record_id", "paragraph_id"):
        text = _normalize_opt_text(record.get(key))
        if text:
            where_values.append(f"{key}:{text}")
    text_ref = record.get("text_ref")
    if isinstance(text_ref, Mapping):
        for key in ("text_id", "segment_id", "unit_id", "envelope_id"):
            text = _normalize_opt_text(text_ref.get(key))
            if text:
                where_values.append(f"{key}:{text}")
    where_values = list(dict.fromkeys(where_values))

    why = _normalize_opt_text(status_explanation.get("why"))
    if not why:
        why = _render_reason_summary(
            reason_labels=status_explanation.get("reason_labels", []),
            detail_labels=[
                _detail_label(details.get("relation_leaf")),
                *(
                    f"missing {str(value).replace('_', ' ')}"
                    for value in details.get("missing_dimensions", [])
                    if str(value).strip()
                ),
            ],
        )

    return {
        "who": who,
        "what": what,
        "when": when,
        "where": where_values,
        "why": why,
        "how": list(dict.fromkeys(how)),
    }
_WEAKLY_ADDRESSED_SUPPORT_STATUSES = {
    "textually_addressed",
    "responsive_but_non_substantive",
    "evidentially_grounded_response",
}
_RELATION_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "with",
    "you",
    "your",
}
_RELATION_SUBJECT_TOKENS = {
    "applicant",
    "claimant",
    "complainant",
    "landlord",
    "respondent",
    "tenant",
    "witness",
}
_RELATION_BUCKET_BY_TYPE = {
    "exact_support": "supported",
    "equivalent_support": "supported",
    "explicit_dispute": "disputed",
    "implicit_dispute": "disputed",
    "partial_overlap": "partial_support",
    "adjacent_event": "adjacent_event",
    "substitution": "substitution",
    "procedural_nonanswer": "non_substantive_response",
    "unrelated": "missing",
}


def _classify_contested_affidavit_proving_bucket(row: Mapping[str, Any]) -> str:
    return _derive_contested_affidavit_relation(row)["legacy_bucket"]


def _relation_tokens(text: str) -> set[str]:
    normalized = (
        str(text or "")
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("\r", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(";", " ")
        .replace(":", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace("{", " ")
        .replace("}", " ")
        .replace("'", " ")
        .replace('"', " ")
    )
    return {
        token
        for token in normalized.split()
        if token and token not in _RELATION_TOKEN_STOPWORDS and len(token) > 2
    }


def _subject_alignment(proposition_text: str, matched_response: str) -> bool:
    proposition_tokens = _relation_tokens(proposition_text)
    response_tokens = _relation_tokens(matched_response)
    if not proposition_tokens or not response_tokens:
        return False
    proposition_subjects = proposition_tokens & _RELATION_SUBJECT_TOKENS
    response_subjects = response_tokens & _RELATION_SUBJECT_TOKENS
    if proposition_subjects and response_subjects:
        return bool(proposition_subjects & response_subjects)
    pronoun_tokens = {"i", "me", "my", "we", "our", "he", "she", "they", "them", "their"}
    proposition_pronouns = set(str(proposition_text or "").lower().split()) & pronoun_tokens
    response_pronouns = set(str(matched_response or "").lower().split()) & pronoun_tokens
    if proposition_pronouns and response_pronouns:
        return bool(proposition_pronouns & response_pronouns)
    return bool(proposition_tokens & response_tokens)


def _action_alignment(proposition_text: str, matched_response: str) -> bool:
    proposition_tokens = _relation_tokens(proposition_text)
    response_tokens = _relation_tokens(matched_response)
    if not proposition_tokens or not response_tokens:
        return False
    overlap = proposition_tokens & response_tokens
    return len(overlap) >= 2


def _polarity_alignment(row: Mapping[str, Any]) -> bool:
    response = row.get("response")
    polarity = (
        str(response.get("polarity") or "").strip().lower()
        if isinstance(response, Mapping)
        else ""
    )
    support_direction = str(row.get("support_direction") or "").strip().lower()
    conflict_state = str(row.get("conflict_state") or "").strip().lower()
    best_response_role = str(row.get("best_response_role") or "").strip().lower()
    if best_response_role in {"dispute", "hedged_denial"} or conflict_state == "disputed" or support_direction == "against":
        return polarity in {"negative", "qualified", "neutral", ""}
    if support_direction in {"for", "supports"}:
        return polarity in {"positive", "qualified", "neutral", ""}
    return polarity in {"", "neutral", "qualified", "positive"}


def _normalize_missing_dimensions(row: Mapping[str, Any]) -> list[str]:
    dimensions: list[str] = []
    primary_target_component = str(row.get("primary_target_component") or "").strip()
    support_status = str(row.get("support_status") or "").strip()
    best_match_excerpt = _normalize_opt_text(row.get("best_match_excerpt"))
    duplicate_match_excerpt = _normalize_opt_text(row.get("duplicate_match_excerpt"))
    coverage_status = str(row.get("coverage_status") or "").strip()

    if primary_target_component == "time":
        dimensions.append("time")
    elif primary_target_component == "characterization":
        dimensions.append("direct_response")
    elif primary_target_component == "predicate_text":
        dimensions.append("action")

    if support_status in {"responsive_but_non_substantive", "unresolved"}:
        dimensions.append("direct_response")
    if support_status == "textually_addressed" and not duplicate_match_excerpt:
        dimensions.append("object")
    if coverage_status == "unsupported_affidavit" and not best_match_excerpt:
        dimensions.append("direct_response")

    deduped: list[str] = []
    for dimension in dimensions:
        if dimension and dimension not in deduped:
            deduped.append(dimension)
    proposition_text = str(row.get("text") or "").strip()
    matched_response = _normalize_opt_text(row.get("best_match_excerpt")) or ""
    if not _subject_alignment(proposition_text, matched_response):
        deduped.append("subject")
    if not _action_alignment(proposition_text, matched_response):
        deduped.append("action")
    if not _polarity_alignment(row):
        deduped.append("direct_response")
    final_dimensions: list[str] = []
    for dimension in deduped:
        if dimension and dimension not in final_dimensions:
            final_dimensions.append(dimension)
    return final_dimensions or ["direct_response"]


def _derive_contested_affidavit_relation(row: Mapping[str, Any]) -> dict[str, Any]:
    coverage_status = str(row.get("coverage_status") or "").strip()
    support_status = str(row.get("support_status") or "").strip()
    conflict_state = str(row.get("conflict_state") or "").strip()
    support_direction = str(row.get("support_direction") or "").strip()
    best_response_role = str(row.get("best_response_role") or "").strip()
    primary_target_component = str(row.get("primary_target_component") or "").strip()
    best_match_excerpt = _normalize_opt_text(row.get("best_match_excerpt"))
    proposition_text = str(row.get("text") or "").strip()
    missing_dimensions = _normalize_missing_dimensions(row)
    subject_aligned = _subject_alignment(proposition_text, best_match_excerpt or "")
    action_aligned = _action_alignment(proposition_text, best_match_excerpt or "")
    polarity_aligned = _polarity_alignment(row)

    relation_type = "procedural_nonanswer"
    relation_root = "non_resolving"
    relation_leaf = "non_substantive_response"
    bucket = _RELATION_BUCKET_BY_TYPE[relation_type]
    reason = "The response engages the proposition, but the current match remains unresolved."

    if not best_match_excerpt:
        relation_type = "unrelated"
        reason = "No adequately aligned response row was found for this proposition."
    elif best_response_role in {"dispute", "hedged_denial"} and subject_aligned:
        relation_type = "explicit_dispute"
        reason = "The matched response explicitly disputes the proposition with aligned subject and action."
    elif coverage_status in _DISPUTED_AFFIDAVIT_STATUSES:
        relation_type = "implicit_dispute"
        reason = "The proposition is marked contested and is treated as a dispute until a stronger support relation is established."
    elif conflict_state == "disputed" or support_direction == "against":
        relation_type = "implicit_dispute"
        reason = "The matched response materially opposes the proposition under the current conflict/support state."
    elif coverage_status in _SUPPORTED_AFFIDAVIT_STATUSES and subject_aligned and action_aligned:
        relation_type = "exact_support" if support_status == "substantively_addressed" else "equivalent_support"
        reason = "The matched response aligns on the same proposition with substantive support."
    elif coverage_status in _MISSING_AFFIDAVIT_STATUSES:
        relation_type = "unrelated"
        reason = "No adequately aligned response row was found for this proposition."
    elif primary_target_component == "time":
        relation_type = "adjacent_event"
        reason = "The matched response appears to concern a nearby event or timing slice rather than the exact proposition."
    elif best_response_role in {"explanation", "procedural_frame", "restatement_only", "non_response"}:
        relation_type = "procedural_nonanswer"
        reason = "The matched response is procedural, explanatory, or otherwise non-substantive for this proposition."
    elif action_aligned and subject_aligned and polarity_aligned:
        relation_type = "partial_overlap"
        reason = "The matched response partially overlaps the proposition but leaves key dimensions unresolved."
    elif support_status == "textually_addressed" and action_aligned and not subject_aligned:
        relation_type = "substitution"
        reason = "The matched response overlaps lexically, but substitutes a different actor or incident."
    elif support_status == "textually_addressed":
        relation_type = "partial_overlap"
        reason = "The matched response overlaps textually with the proposition but does not fully resolve it."
    elif support_status in _WEAKLY_ADDRESSED_SUPPORT_STATUSES:
        relation_type = "procedural_nonanswer"
        reason = "The matched response is procedural, explanatory, or otherwise non-substantive for this proposition."
    elif coverage_status in _CLARIFY_AFFIDAVIT_STATUSES:
        relation_type = "partial_overlap"
        reason = "The matched response partially overlaps the proposition but leaves key dimensions unresolved."

    bucket = _RELATION_BUCKET_BY_TYPE[relation_type]
    if relation_type in {"exact_support", "equivalent_support"}:
        relation_root = "supports"
        relation_leaf = relation_type
    elif relation_type in {"explicit_dispute", "implicit_dispute"}:
        relation_root = "invalidates"
        relation_leaf = relation_type
    elif relation_type == "unrelated":
        relation_root = "unanswered"
        relation_leaf = "missing"
    elif relation_type == "partial_overlap":
        relation_root = "supports"
        relation_leaf = "partial_support"
    elif relation_type == "adjacent_event":
        relation_root = "non_resolving"
        relation_leaf = "adjacent_event"
    elif relation_type == "substitution":
        relation_root = "non_resolving"
        relation_leaf = "substitution"
    else:
        relation_root = "non_resolving"
        relation_leaf = "non_substantive_response"

    explanation = {
        "classification": bucket,
        "matched_response": best_match_excerpt,
        "reason": reason,
        "missing_dimension": missing_dimensions,
    }
    return {
        "relation_type": relation_type,
        "relation_root": relation_root,
        "relation_leaf": relation_leaf,
        "bucket": bucket,
        "legacy_bucket": "needs_clarification" if bucket in {"partial_support", "adjacent_event", "substitution", "non_substantive_response"} else bucket,
        "explanation": explanation,
        "matched_response": best_match_excerpt,
        "missing_dimensions": missing_dimensions,
    }


def _build_contested_affidavit_next_steps(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    next_steps: list[dict[str, Any]] = []
    if int(summary.get("unsupported_affidavit_count") or 0) > 0:
        next_steps.append(
            {
                "step_id": "review_unsupported_affidavit",
                "priority": "high",
                "reason": "unsupported_affidavit_count",
                "text": "Review unsupported affidavit propositions against source-grounded material before treating the draft as complete.",
            }
        )
    if int(summary.get("missing_review_count") or 0) > 0:
        next_steps.append(
            {
                "step_id": "resolve_missing_review_rows",
                "priority": "high",
                "reason": "missing_review_count",
                "text": "Resolve source rows that are still absent from the affidavit and awaiting review before making omission claims.",
            }
        )
    contested_total = int(summary.get("contested_source_count") or 0) + int(summary.get("contested_affidavit_count") or 0)
    if contested_total > 0:
        next_steps.append(
            {
                "step_id": "inspect_contested_material",
                "priority": "medium",
                "reason": "contested_material",
                "text": "Inspect contested source or affidavit material before promoting contradiction or omission conclusions.",
            }
        )
    clarification_total = int(summary.get("partial_count") or 0) + int(summary.get("abstained_source_count") or 0)
    if clarification_total > 0:
        next_steps.append(
            {
                "step_id": "clarify_partial_or_abstained_rows",
                "priority": "medium",
                "reason": "clarification_needed",
                "text": "Clarify partial matches and abstained source rows with stronger anchors or narrower wording.",
            }
        )
    return next_steps[:3]


def build_contested_affidavit_proving_slice(
    conn: sqlite3.Connection,
    *,
    review_run_id: str,
) -> dict[str, Any]:
    review = build_contested_affidavit_review_summary(conn, review_run_id=review_run_id)
    affidavit_rows = review.get("affidavit_rows") if isinstance(review.get("affidavit_rows"), list) else []
    source_rows = review.get("source_review_rows") if isinstance(review.get("source_review_rows"), list) else []
    summary = review.get("summary") if isinstance(review.get("summary"), Mapping) else {}

    bucketed_rows: dict[str, list[dict[str, Any]]] = {
        "supported": [],
        "disputed": [],
        "partial_support": [],
        "adjacent_event": [],
        "substitution": [],
        "non_substantive_response": [],
        "non_resolving": [],
        "missing": [],
        "needs_clarification": [],
    }
    for row in affidavit_rows:
        persisted_explanation = row.get("explanation") if isinstance(row.get("explanation"), Mapping) else None
        persisted_classification = (
            str(persisted_explanation.get("classification") or "").strip()
            if isinstance(persisted_explanation, Mapping)
            else ""
        )
        persisted_relation_type = _normalize_opt_text(row.get("relation_type"))
        relation = (
            {
                "relation_type": persisted_relation_type,
                "relation_root": _normalize_opt_text(row.get("relation_root")),
                "relation_leaf": _normalize_opt_text(row.get("relation_leaf")),
                "bucket": persisted_classification or _classify_contested_affidavit_proving_bucket(row),
                "matched_response": _normalize_opt_text(row.get("best_match_excerpt")),
                "explanation": persisted_explanation,
                "missing_dimensions": row.get("missing_dimensions") if isinstance(row.get("missing_dimensions"), list) else None,
            }
            if (
                _normalize_opt_text(row.get("relation_root"))
                and _normalize_opt_text(row.get("relation_leaf"))
                and persisted_relation_type
            )
            else _derive_contested_affidavit_relation(row)
        )
        if (
            relation.get("explanation") is None
            or relation.get("missing_dimensions") is None
            or not relation.get("relation_type")
        ):
            relation = _derive_contested_affidavit_relation(row)
        enriched_row = {
            **row,
            "relation_type": relation["relation_type"],
            "relation_root": relation["relation_root"],
            "relation_leaf": relation["relation_leaf"],
            "matched_response": relation["matched_response"],
            "explanation": relation["explanation"],
            "missing_dimensions": relation["missing_dimensions"],
        }
        bucketed_rows[relation["bucket"]].append(enriched_row)
        if relation["relation_root"] == "non_resolving":
            bucketed_rows["non_resolving"].append(enriched_row)
            bucketed_rows["needs_clarification"].append(enriched_row)

    supported = bucketed_rows["supported"]
    disputed = bucketed_rows["disputed"]
    partial_support = bucketed_rows["partial_support"]
    adjacent_event = bucketed_rows["adjacent_event"]
    substitution = bucketed_rows["substitution"]
    non_substantive_response = bucketed_rows["non_substantive_response"]
    non_resolving = bucketed_rows["non_resolving"]
    missing = bucketed_rows["missing"]
    needs_clarification = bucketed_rows["needs_clarification"]

    disputed_source_rows = [
        row for row in source_rows if str(row.get("review_status") or "") in _DISPUTED_SOURCE_REVIEW_STATUSES
    ]
    clarification_source_rows = [
        row for row in source_rows if str(row.get("review_status") or "") in _CLARIFY_SOURCE_REVIEW_STATUSES
    ]

    return {
        "run": review.get("run"),
        "summary": {
            **summary,
            "supported_affidavit_count": len(supported),
            "disputed_affidavit_count": len(disputed),
            "partial_support_affidavit_count": len(partial_support),
            "adjacent_event_affidavit_count": len(adjacent_event),
            "substitution_affidavit_count": len(substitution),
            "non_substantive_response_affidavit_count": len(non_substantive_response),
            "non_resolving_affidavit_count": len(non_resolving),
            "weakly_addressed_affidavit_count": 0,
            "missing_affidavit_count": len(missing),
            "needs_clarification_affidavit_count": len(needs_clarification),
            "disputed_source_row_count": len(disputed_source_rows),
            "needs_clarification_source_row_count": len(clarification_source_rows),
        },
        "sections": {
            "supported": supported,
            "disputed": disputed,
            "partial_support": partial_support,
            "adjacent_event": adjacent_event,
            "substitution": substitution,
            "non_substantive_response": non_substantive_response,
            "non_resolving": non_resolving,
            "missing": missing,
            "needs_clarification": needs_clarification,
        },
        "source_attention": {
            "disputed": disputed_source_rows,
            "needs_clarification": clarification_source_rows,
        },
        "next_steps": _build_contested_affidavit_next_steps(summary),
    }


def _workflow_link_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "workflow_kind": str(row["workflow_kind"]),
        "workflow_run_id": str(row["workflow_run_id"]),
        "fact_run_id": str(row["fact_run_id"]),
        "source_label": _normalize_opt_text(row["source_label"]),
        "adapter_version": str(row["adapter_version"]),
        "created_at": str(row["created_at"]),
    }


def record_fact_workflow_link(
    conn: sqlite3.Connection,
    *,
    workflow_kind: str,
    workflow_run_id: str,
    fact_run_id: str,
    source_label: str | None = None,
    adapter_version: str = FACT_WORKFLOW_LINK_VERSION,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    workflow_kind = str(workflow_kind or "").strip()
    workflow_run_id = str(workflow_run_id or "").strip()
    fact_run_id = str(fact_run_id or "").strip()
    if not workflow_kind:
        raise ValueError("workflow_kind is required")
    if not workflow_run_id:
        raise ValueError("workflow_run_id is required")
    if not fact_run_id:
        raise ValueError("fact_run_id is required")
    conn.execute(
        """
        INSERT INTO fact_workflow_links(
          workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(workflow_kind, workflow_run_id)
        DO UPDATE SET
          fact_run_id = excluded.fact_run_id,
          source_label = excluded.source_label,
          adapter_version = excluded.adapter_version
        """,
        (
            workflow_kind,
            workflow_run_id,
            fact_run_id,
            _normalize_opt_text(source_label),
            str(adapter_version or FACT_WORKFLOW_LINK_VERSION).strip(),
        ),
    )
    conn.commit()
    return resolve_fact_run_link(
        conn,
        workflow_kind=workflow_kind,
        workflow_run_id=workflow_run_id,
    )


def resolve_fact_run_link(
    conn: sqlite3.Connection,
    *,
    workflow_kind: str,
    workflow_run_id: str,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version, created_at
        FROM fact_workflow_links
        WHERE workflow_kind = ? AND workflow_run_id = ?
        """,
        (str(workflow_kind or "").strip(), str(workflow_run_id or "").strip()),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown fact workflow link: {workflow_kind}:{workflow_run_id}")
    return _workflow_link_row_to_dict(row) or {}


def find_latest_fact_workflow_link(
    conn: sqlite3.Connection,
    *,
    workflow_kind: str,
    source_label: str | None = None,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where = ["workflow_kind = ?"]
    params: list[Any] = [str(workflow_kind or "").strip()]
    if source_label:
        where.append("source_label = ?")
        params.append(str(source_label))
    row = conn.execute(
        f"""
        SELECT workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version, created_at
        FROM fact_workflow_links
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC, workflow_run_id DESC
        LIMIT 1
        """,
        tuple(params),
    ).fetchone()
    if row is None:
        label_suffix = f" source_label={source_label}" if source_label else ""
        raise ValueError(f"No fact workflow link found for {workflow_kind}{label_suffix}")
    return _workflow_link_row_to_dict(row) or {}


def _resolve_fact_run_id(
    conn: sqlite3.Connection,
    *,
    run_id: str | None = None,
    workflow_kind: str | None = None,
    workflow_run_id: str | None = None,
    source_label: str | None = None,
) -> str:
    direct_run_id = _normalize_opt_text(run_id)
    if direct_run_id:
        return direct_run_id
    resolved_kind = _normalize_opt_text(workflow_kind)
    resolved_workflow_run_id = _normalize_opt_text(workflow_run_id)
    if resolved_kind and resolved_workflow_run_id:
        return resolve_fact_run_link(
            conn,
            workflow_kind=resolved_kind,
            workflow_run_id=resolved_workflow_run_id,
        )["fact_run_id"]
    if resolved_kind:
        return find_latest_fact_workflow_link(
            conn,
            workflow_kind=resolved_kind,
            source_label=_normalize_opt_text(source_label),
        )["fact_run_id"]
    raise ValueError("Provide run_id or workflow_kind + workflow_run_id")


def resolve_fact_run_id(
    conn: sqlite3.Connection,
    *,
    run_id: str | None = None,
    workflow_kind: str | None = None,
    workflow_run_id: str | None = None,
    source_label: str | None = None,
) -> str:
    return _resolve_fact_run_id(
        conn,
        run_id=run_id,
        workflow_kind=workflow_kind,
        workflow_run_id=workflow_run_id,
        source_label=source_label,
    )


def build_fact_intake_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    run = conn.execute(
        """
        SELECT run_id, contract_version, source_label, mary_projection_version, notes, created_at
        FROM fact_intake_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if run is None:
        raise ValueError(f"Unknown fact intake run: {run_id}")
    workflow_link = _workflow_link_row_to_dict(
        conn.execute(
            """
            SELECT workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version, created_at
            FROM fact_workflow_links
            WHERE fact_run_id = ?
            """,
            (run_id,),
        ).fetchone()
    )
    source_rows = conn.execute(
        """
        SELECT source_id, source_order, source_type, source_label, source_ref, content_sha256, provenance_json
        FROM fact_sources
        WHERE run_id = ?
        ORDER BY source_order, source_id
        """,
        (run_id,),
    ).fetchall()
    excerpt_rows = conn.execute(
        """
        SELECT excerpt_id, source_id, excerpt_order, excerpt_text, char_start, char_end, anchor_label, provenance_json
        FROM fact_excerpts
        WHERE run_id = ?
        ORDER BY source_id, excerpt_order, excerpt_id
        """,
        (run_id,),
    ).fetchall()
    statement_rows = conn.execute(
        """
        SELECT statement_id, excerpt_id, statement_order, statement_text, speaker_label,
               statement_role, statement_status, chronology_hint, provenance_json
        FROM fact_statements
        WHERE run_id = ?
        ORDER BY excerpt_id, statement_order, statement_id
        """,
        (run_id,),
    ).fetchall()
    fact_rows = conn.execute(
        """
        SELECT fact_id, canonical_label, fact_text, fact_type, candidate_status,
               chronology_sort_key, chronology_label, primary_statement_id, provenance_json
        FROM fact_candidates
        WHERE run_id = ?
        ORDER BY chronology_sort_key IS NULL, chronology_sort_key, fact_id
        """,
        (run_id,),
    ).fetchall()
    contestation_rows = conn.execute(
        """
        SELECT contestation_id, fact_id, statement_id, contestation_status, reason_text, author, provenance_json, created_at
        FROM fact_contestations
        WHERE fact_id IN (SELECT fact_id FROM fact_candidates WHERE run_id = ?)
        ORDER BY fact_id, created_at, contestation_id
        """,
        (run_id,),
    ).fetchall()
    review_rows = conn.execute(
        """
        SELECT review_id, fact_id, review_status, reviewer, note, provenance_json, created_at
        FROM fact_reviews
        WHERE fact_id IN (SELECT fact_id FROM fact_candidates WHERE run_id = ?)
        ORDER BY fact_id, created_at, review_id
        """,
        (run_id,),
    ).fetchall()
    observation_rows = conn.execute(
        """
        SELECT observation_id, statement_id, excerpt_id, source_id, observation_order,
               predicate_key, predicate_family, object_text, object_type, object_ref, subject_text,
               observation_status, provenance_json, created_at
        FROM fact_observations
        WHERE run_id = ?
        ORDER BY statement_id, observation_order, observation_id
        """,
        (run_id,),
    ).fetchall()
    event_rows = conn.execute(
        """
        SELECT event_id, event_type, primary_actor, secondary_actor, object_text,
               location_text, instrument_text, time_start, time_end, confidence,
               status, assembler_version, created_at
        FROM event_candidates
        WHERE run_id = ?
        ORDER BY time_start IS NULL, time_start, event_id
        """,
        (run_id,),
    ).fetchall()
    event_attribute_rows = conn.execute(
        """
        SELECT event_id, attribute_type, attribute_value, source_observation_id, confidence
        FROM event_attributes
        WHERE event_id IN (SELECT event_id FROM event_candidates WHERE run_id = ?)
        ORDER BY event_id, attribute_type, attribute_value
        """,
        (run_id,),
    ).fetchall()
    event_evidence_rows = conn.execute(
        """
        SELECT event_id, observation_id, role, confidence
        FROM event_evidence
        WHERE event_id IN (SELECT event_id FROM event_candidates WHERE run_id = ?)
        ORDER BY event_id, observation_id, role
        """,
        (run_id,),
    ).fetchall()
    rule_atoms: list[dict[str, Any]] = []
    try:
        rule_atom_rows = conn.execute(
            """
            SELECT doc_id, stable_id, party, role, modality, action, scope
            FROM rule_atoms
            WHERE doc_id IN (SELECT source_label FROM fact_sources WHERE run_id = ?)
            """,
            (run_id,),
        ).fetchall()
        rule_atoms = [dict(row) for row in rule_atom_rows]
    except sqlite3.OperationalError:
        pass
    link_rows = conn.execute(
        """
        SELECT fcs.fact_id, fs.statement_id, fs.statement_text, fs.excerpt_id, fe.source_id
        FROM fact_candidate_statements AS fcs
        JOIN fact_statements AS fs ON fs.statement_id = fcs.statement_id
        JOIN fact_excerpts AS fe ON fe.excerpt_id = fs.excerpt_id
        WHERE fcs.fact_id IN (SELECT fact_id FROM fact_candidates WHERE run_id = ?)
        ORDER BY fcs.fact_id, fs.statement_id
        """,
        (run_id,),
    ).fetchall()
    links_by_fact: dict[str, dict[str, list[str]]] = {}
    for row in link_rows:
        bucket = links_by_fact.setdefault(
            str(row["fact_id"]),
            {"statement_ids": [], "excerpt_ids": [], "source_ids": [], "statement_texts": []},
        )
        for field, value in (
            ("statement_ids", str(row["statement_id"])),
            ("excerpt_ids", str(row["excerpt_id"])),
            ("source_ids", str(row["source_id"])),
            ("statement_texts", str(row["statement_text"])),
        ):
            if value not in bucket[field]:
                bucket[field].append(value)
    contestations_by_fact: dict[str, list[dict[str, Any]]] = {}
    for row in contestation_rows:
        contestations_by_fact.setdefault(str(row["fact_id"]), []).append(
            {
                "contestation_id": str(row["contestation_id"]),
                "statement_id": _normalize_opt_text(row["statement_id"]),
                "contestation_status": str(row["contestation_status"]),
                "reason_text": str(row["reason_text"]),
                "author": _normalize_opt_text(row["author"]),
                "provenance": _json_or_empty(row["provenance_json"]),
                "created_at": str(row["created_at"]),
            }
        )
    reviews_by_fact: dict[str, list[dict[str, Any]]] = {}
    for row in review_rows:
        reviews_by_fact.setdefault(str(row["fact_id"]), []).append(
            {
                "review_id": str(row["review_id"]),
                "review_status": str(row["review_status"]),
                "reviewer": str(row["reviewer"]),
                "note": _normalize_opt_text(row["note"]),
                "provenance": _json_or_empty(row["provenance_json"]),
                "created_at": str(row["created_at"]),
            }
        )
    observations_by_statement: dict[str, list[dict[str, Any]]] = {}
    for row in observation_rows:
        observations_by_statement.setdefault(str(row["statement_id"]), []).append(
            {
                "observation_id": str(row["observation_id"]),
                "statement_id": str(row["statement_id"]),
                "excerpt_id": _normalize_opt_text(row["excerpt_id"]),
                "source_id": _normalize_opt_text(row["source_id"]),
                "observation_order": int(row["observation_order"]),
                "predicate_key": str(row["predicate_key"]),
                "predicate_family": str(row["predicate_family"]),
                "object_text": str(row["object_text"]),
                "object_type": _normalize_opt_text(row["object_type"]),
                "object_ref": _normalize_opt_text(row["object_ref"]),
                "subject_text": _normalize_opt_text(row["subject_text"]),
                "observation_status": str(row["observation_status"]),
                "provenance": _json_or_empty(row["provenance_json"]),
                "created_at": str(row["created_at"]),
            }
        )
    all_observations: list[dict[str, Any]] = []
    for statement_id in sorted(observations_by_statement):
        all_observations.extend(observations_by_statement[statement_id])
    event_attributes_by_event: dict[str, list[dict[str, Any]]] = {}
    for row in event_attribute_rows:
        event_attributes_by_event.setdefault(str(row["event_id"]), []).append(
            {
                "attribute_type": str(row["attribute_type"]),
                "attribute_value": str(row["attribute_value"]),
                "source_observation_id": _normalize_opt_text(row["source_observation_id"]),
                "confidence": float(row["confidence"]),
            }
        )
    event_evidence_by_event: dict[str, list[dict[str, Any]]] = {}
    event_statement_ids_by_event: dict[str, list[str]] = {}
    event_source_ids_by_event: dict[str, list[str]] = {}
    event_source_event_ids_by_event: dict[str, list[str]] = {}
    for row in event_evidence_rows:
        event_id = str(row["event_id"])
        evidence = {
            "observation_id": str(row["observation_id"]),
            "role": str(row["role"]),
            "confidence": float(row["confidence"]),
        }
        event_evidence_by_event.setdefault(event_id, []).append(evidence)
        observation_row = next((obs for obs in all_observations if obs["observation_id"] == evidence["observation_id"]), None)
        if observation_row is not None:
            statement_id = str(observation_row["statement_id"])
            source_id = _normalize_opt_text(observation_row["source_id"])
            observation_provenance = observation_row.get("provenance")
            source_event_id = None
            if isinstance(observation_provenance, dict):
                source_event_id = _normalize_opt_text(observation_provenance.get("source_event_id"))
            event_statement_ids_by_event.setdefault(event_id, [])
            if statement_id not in event_statement_ids_by_event[event_id]:
                event_statement_ids_by_event[event_id].append(statement_id)
            if source_id:
                event_source_ids_by_event.setdefault(event_id, [])
                if source_id not in event_source_ids_by_event[event_id]:
                    event_source_ids_by_event[event_id].append(source_id)
            if source_event_id:
                event_source_event_ids_by_event.setdefault(event_id, [])
                if source_event_id not in event_source_event_ids_by_event[event_id]:
                    event_source_event_ids_by_event[event_id].append(source_event_id)
    sources = [
        {
            "source_id": str(row["source_id"]),
            "source_order": int(row["source_order"]),
            "source_type": str(row["source_type"]),
            "source_label": str(row["source_label"]),
            "source_ref": _normalize_opt_text(row["source_ref"]),
            "content_sha256": _normalize_opt_text(row["content_sha256"]),
            "provenance": _json_or_empty(row["provenance_json"]),
        }
        for row in source_rows
    ]
    excerpts = [
        {
            "excerpt_id": str(row["excerpt_id"]),
            "source_id": str(row["source_id"]),
            "excerpt_order": int(row["excerpt_order"]),
            "excerpt_text": str(row["excerpt_text"]),
            "char_start": row["char_start"],
            "char_end": row["char_end"],
            "anchor_label": _normalize_opt_text(row["anchor_label"]),
            "provenance": _json_or_empty(row["provenance_json"]),
        }
        for row in excerpt_rows
    ]
    statements = [
        {
            "statement_id": str(row["statement_id"]),
            "excerpt_id": str(row["excerpt_id"]),
            "statement_order": int(row["statement_order"]),
            "statement_text": str(row["statement_text"]),
            "speaker_label": _normalize_opt_text(row["speaker_label"]),
            "statement_role": _normalize_opt_text(row["statement_role"]),
            "statement_status": str(row["statement_status"]),
            "chronology_hint": _normalize_opt_text(row["chronology_hint"]),
            "provenance": _json_or_empty(row["provenance_json"]),
        }
        for row in statement_rows
    ]
    events: list[dict[str, Any]] = []
    event_ids_by_statement: dict[str, list[str]] = {}
    for row in event_rows:
        event_id = str(row["event_id"])
        for statement_id in event_statement_ids_by_event.get(event_id, []):
            event_ids_by_statement.setdefault(statement_id, [])
            if event_id not in event_ids_by_statement[statement_id]:
                event_ids_by_statement[statement_id].append(event_id)
        events.append(
            {
                "event_id": event_id,
                "event_type": str(row["event_type"]),
                "primary_actor": _normalize_opt_text(row["primary_actor"]),
                "secondary_actor": _normalize_opt_text(row["secondary_actor"]),
                "object_text": _normalize_opt_text(row["object_text"]),
                "location_text": _normalize_opt_text(row["location_text"]),
                "instrument_text": _normalize_opt_text(row["instrument_text"]),
                "time_start": _normalize_opt_text(row["time_start"]),
                "time_end": _normalize_opt_text(row["time_end"]),
                "confidence": float(row["confidence"]),
                "status": str(row["status"]),
                "assembler_version": str(row["assembler_version"]),
                "attributes": event_attributes_by_event.get(event_id, []),
                "evidence": event_evidence_by_event.get(event_id, []),
                "statement_ids": event_statement_ids_by_event.get(event_id, []),
                "source_ids": event_source_ids_by_event.get(event_id, []),
                "source_event_ids": event_source_event_ids_by_event.get(event_id, []),
                "created_at": str(row["created_at"]),
            }
        )
    facts: list[dict[str, Any]] = []
    for row in fact_rows:
        fact_id = str(row["fact_id"])
        refs = links_by_fact.get(fact_id, {"statement_ids": [], "excerpt_ids": [], "source_ids": [], "statement_texts": []})
        fact_observations: list[dict[str, Any]] = []
        seen_observation_ids: set[str] = set()
        for statement_id in refs["statement_ids"]:
            for observation in observations_by_statement.get(statement_id, []):
                if observation["observation_id"] in seen_observation_ids:
                    continue
                seen_observation_ids.add(observation["observation_id"])
                fact_observations.append(observation)
        fact_event_ids: list[str] = []
        for statement_id in refs["statement_ids"]:
            for event_id in event_ids_by_statement.get(statement_id, []):
                if event_id not in fact_event_ids:
                    fact_event_ids.append(event_id)
        facts.append(
            {
                "fact_id": fact_id,
                "canonical_label": _normalize_opt_text(row["canonical_label"]),
                "fact_text": str(row["fact_text"]),
                "fact_type": str(row["fact_type"]),
                "candidate_status": str(row["candidate_status"]),
                "chronology_sort_key": _normalize_opt_text(row["chronology_sort_key"]),
                "chronology_label": _normalize_opt_text(row["chronology_label"]),
                "primary_statement_id": _normalize_opt_text(row["primary_statement_id"]),
                "provenance": _json_or_empty(row["provenance_json"]),
                "statement_ids": refs["statement_ids"],
                "excerpt_ids": refs["excerpt_ids"],
                "source_ids": refs["source_ids"],
                "event_ids": fact_event_ids,
                "statement_texts": refs["statement_texts"],
                "observations": fact_observations,
                "contestations": contestations_by_fact.get(fact_id, []),
                "reviews": reviews_by_fact.get(fact_id, []),
            }
        )
    return {
        "run": {
            "run_id": str(run["run_id"]),
            "contract_version": str(run["contract_version"]),
            "source_label": str(run["source_label"]),
            "mary_projection_version": str(run["mary_projection_version"]),
            "notes": _normalize_opt_text(run["notes"]),
            "created_at": str(run["created_at"]),
            "workflow_link": workflow_link,
        },
        "summary": {
            "observation_count": len(all_observations),
            "event_count": len(events),
            "fact_count": len(facts),
            "contested_fact_count": sum(1 for fact in facts if fact["contestations"]),
            "reviewed_fact_count": sum(1 for fact in facts if fact["reviews"]),
        },
        "sources": sources,
        "excerpts": excerpts,
        "statements": statements,
        "observations": all_observations,
        "events": events,
        "facts": facts,
        "rule_atoms": rule_atoms,
    }


def _has_semantic_materialization(conn: sqlite3.Connection, *, run_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM semantic_refresh_runs
        WHERE run_id = ? AND refresh_status = 'ok'
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    return row is not None


def _load_entity_class_map(conn: sqlite3.Connection, *, run_id: str, target_kind: str) -> dict[str, list[str]]:
    rows = conn.execute(
        """
        SELECT target_id, class_key
        FROM entity_class_assertions
        WHERE run_id = ? AND target_kind = ? AND assertion_status = 'active'
        ORDER BY target_id, class_key
        """,
        (run_id, target_kind),
    ).fetchall()
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row["target_id"]), [])
        value = str(row["class_key"])
        if value not in out[str(row["target_id"])]:
            out[str(row["target_id"])].append(value)
    return out


def _load_policy_map(conn: sqlite3.Connection, *, run_id: str, target_kind: str) -> dict[str, list[str]]:
    rows = conn.execute(
        """
        SELECT target_id, policy_key
        FROM policy_outcomes
        WHERE run_id = ? AND target_kind = ? AND outcome_status = 'active'
        ORDER BY target_id, policy_key
        """,
        (run_id, target_kind),
    ).fetchall()
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row["target_id"]), [])
        value = str(row["policy_key"])
        if value not in out[str(row["target_id"])]:
            out[str(row["target_id"])].append(value)
    return out


def list_semantic_refresh_runs(
    conn: sqlite3.Connection,
    *,
    run_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where = "WHERE run_id = ?" if run_id else ""
    params: tuple[Any, ...] = ((run_id, max(int(limit), 1)) if run_id else (max(int(limit), 1),))
    rows = conn.execute(
        f"""
        SELECT refresh_id, run_id, bridge_version, ruleset_version, refresh_kind, refresh_status,
               facts_serialized_count, assertion_count, relation_count, policy_count,
               started_at, updated_at, current_stage, status_message, created_at
        FROM semantic_refresh_runs
        {where}
        ORDER BY COALESCE(updated_at, created_at) DESC, refresh_id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "refresh_id": str(row["refresh_id"]),
            "run_id": str(row["run_id"]),
            "bridge_version": str(row["bridge_version"]),
            "ruleset_version": str(row["ruleset_version"]),
            "refresh_kind": str(row["refresh_kind"]),
            "refresh_status": str(row["refresh_status"]),
            "facts_serialized_count": int(row["facts_serialized_count"]),
            "assertion_count": int(row["assertion_count"]),
            "relation_count": int(row["relation_count"]),
            "policy_count": int(row["policy_count"]),
            "started_at": _normalize_opt_text(row["started_at"]),
            "updated_at": _normalize_opt_text(row["updated_at"]),
            "current_stage": _normalize_opt_text(row["current_stage"]),
            "status_message": _normalize_opt_text(row["status_message"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def build_fact_semantic_status_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    report = build_fact_intake_report(conn, run_id=run_id)
    refreshes = list_semantic_refresh_runs(conn, run_id=run_id, limit=20)
    assertion_rows = conn.execute(
        """
        SELECT target_kind, assertion_origin, COUNT(*) AS row_count
        FROM entity_class_assertions
        WHERE run_id = ? AND assertion_status = 'active'
        GROUP BY target_kind, assertion_origin
        ORDER BY target_kind, assertion_origin
        """,
        (run_id,),
    ).fetchall()
    relation_rows = conn.execute(
        """
        SELECT relation_key, assertion_origin, COUNT(*) AS row_count
        FROM entity_relations
        WHERE run_id = ? AND relation_status = 'active'
        GROUP BY relation_key, assertion_origin
        ORDER BY relation_key, assertion_origin
        """,
        (run_id,),
    ).fetchall()
    policy_rows = conn.execute(
        """
        SELECT policy_key, outcome_status, COUNT(*) AS row_count
        FROM policy_outcomes
        WHERE run_id = ?
        GROUP BY policy_key, outcome_status
        ORDER BY policy_key, outcome_status
        """,
        (run_id,),
    ).fetchall()
    return {
        "run": report["run"],
        "materialized": _has_semantic_materialization(conn, run_id=run_id),
        "latest_refresh": refreshes[0] if refreshes else None,
        "refresh_history": refreshes,
        "assertions": [
            {
                "target_kind": str(row["target_kind"]),
                "assertion_origin": str(row["assertion_origin"]),
                "row_count": int(row["row_count"]),
            }
            for row in assertion_rows
        ],
        "relations": [
            {
                "relation_key": str(row["relation_key"]),
                "assertion_origin": str(row["assertion_origin"]),
                "row_count": int(row["row_count"]),
            }
            for row in relation_rows
        ],
        "policies": [
            {
                "policy_key": str(row["policy_key"]),
                "outcome_status": str(row["outcome_status"]),
                "row_count": int(row["row_count"]),
            }
            for row in policy_rows
        ],
    }


def _policy_message(policy_key: str) -> str:
    return {
        "review_required": "Human review required before relying on this fact.",
        "do_not_promote_to_primary": "Do not elevate this fact to primary-authority status.",
        "preserve_source_boundary": "Preserve the original source boundary in any summary or handoff.",
        "manual_resolution_required": "Manual resolution is required before downstream automation.",
        "bounded_context_required": "Only bounded, source-linked context may be shown to downstream agents.",
    }.get(policy_key, f"Policy active: {policy_key}")


def build_fact_agent_feedback_payload(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    workbench = build_fact_review_workbench_payload(conn, run_id=run_id)
    items: list[dict[str, Any]] = []
    active_policy_count = 0
    for fact in workbench.get("facts", []):
        if not isinstance(fact, Mapping):
            continue
        policies = [str(value) for value in fact.get("policy_outcomes", []) if str(value).strip()]
        if not policies:
            continue
        active_policy_count += len(policies)
        items.append(
            {
                "fact_id": str(fact.get("fact_id")),
                "label": str(fact.get("canonical_label") or fact.get("fact_text") or "")[:120],
                "policy_outcomes": policies,
                "messages": [_policy_message(policy_key) for policy_key in policies],
                "signal_classes": list(fact.get("signal_classes", [])),
                "source_signal_classes": list(fact.get("source_signal_classes", [])),
                "source_ids": list(fact.get("source_ids", [])),
                "statement_ids": list(fact.get("statement_ids", [])),
            }
        )
    return {
        "run": workbench["run"],
        "summary": {
            "fact_count": len(workbench.get("facts", [])),
            "constrained_fact_count": len(items),
            "active_policy_count": active_policy_count,
        },
        "global_messages": list(
            dict.fromkeys(
                message
                for item in items
                for message in item["messages"]
            )
        ),
        "items": items,
    }


def _record_class_assertion(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    target_kind: str,
    target_id: str,
    class_key: str,
    assertion_origin: str,
    rule_key: str | None = None,
    confidence: float | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> str:
    conn.execute(
        """
        INSERT OR IGNORE INTO semantic_class_vocab(
          class_key, dimension, applies_to, class_status, description, introduced_in_version
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            class_key,
            "other",
            target_kind,
            "active",
            f"Auto-seeded semantic class for {target_kind}.",
            FACT_SEMANTIC_LAYER_VERSION,
        ),
    )
    assertion_id = _stable_id(
        "classassert",
        {
            "run_id": run_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "class_key": class_key,
            "assertion_origin": assertion_origin,
            "rule_key": _coalesce_rule_key(assertion_origin, rule_key),
        },
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO entity_class_assertions(
          assertion_id, run_id, target_kind, target_id, class_key, assertion_origin,
          assertion_status, rule_key, confidence, provenance_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            assertion_id,
            run_id,
            target_kind,
            target_id,
            class_key,
            assertion_origin,
            "active",
            _normalize_opt_text(rule_key),
            confidence,
            _normalize_json(provenance),
        ),
    )
    return assertion_id


def _record_relation(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    subject_kind: str,
    subject_id: str,
    relation_key: str,
    object_kind: str,
    object_id: str,
    assertion_origin: str,
    rule_key: str | None = None,
    confidence: float | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> str:
    relation_id = _stable_id(
        "relation",
        {
            "run_id": run_id,
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "relation_key": relation_key,
            "object_kind": object_kind,
            "object_id": object_id,
            "assertion_origin": assertion_origin,
            "rule_key": _coalesce_rule_key(assertion_origin, rule_key),
        },
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO entity_relations(
          relation_id, run_id, subject_kind, subject_id, relation_key, object_kind, object_id,
          assertion_origin, relation_status, rule_key, confidence, provenance_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            relation_id,
            run_id,
            subject_kind,
            subject_id,
            relation_key,
            object_kind,
            object_id,
            assertion_origin,
            "active",
            _normalize_opt_text(rule_key),
            confidence,
            _normalize_json(provenance),
        ),
    )
    return relation_id


def _record_policy_outcome(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    target_kind: str,
    target_id: str,
    policy_key: str,
    rule_key: str | None = None,
    trigger_assertion_id: str | None = None,
    trigger_relation_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> str:
    outcome_id = _stable_id(
        "policy",
        {
            "run_id": run_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "policy_key": policy_key,
            "rule_key": _coalesce_rule_key("policy_projection", rule_key),
        },
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO policy_outcomes(
          outcome_id, run_id, target_kind, target_id, policy_key, outcome_status,
          trigger_assertion_id, trigger_relation_id, rule_key, provenance_json, reviewer, note
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            outcome_id,
            run_id,
            target_kind,
            target_id,
            policy_key,
            "active",
            _normalize_opt_text(trigger_assertion_id),
            _normalize_opt_text(trigger_relation_id),
            _normalize_opt_text(rule_key),
            _normalize_json(provenance),
            None,
            None,
        ),
    )
    return outcome_id


def _upsert_semantic_refresh_run(
    conn: sqlite3.Connection,
    *,
    refresh_id: str,
    run_id: str,
    refresh_kind: str,
    refresh_status: str,
    current_stage: str,
    status_message: str,
    facts_serialized_count: int = 0,
    assertion_count: int = 0,
    relation_count: int = 0,
    policy_count: int = 0,
) -> None:
    existing = conn.execute(
        "SELECT refresh_id FROM semantic_refresh_runs WHERE refresh_id = ?",
        (refresh_id,),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO semantic_refresh_runs(
              refresh_id, run_id, bridge_version, ruleset_version, refresh_kind, refresh_status,
              facts_serialized_count, assertion_count, relation_count, policy_count,
              started_at, updated_at, current_stage, status_message
            ) VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?,?)
            """,
            (
                refresh_id,
                run_id,
                "fact_intake.zelph_bridge.v1",
                FACT_REVIEW_ZELPH_RULESET_VERSION,
                refresh_kind,
                refresh_status,
                facts_serialized_count,
                assertion_count,
                relation_count,
                policy_count,
                current_stage,
                status_message,
            ),
        )
        return
    conn.execute(
        """
        UPDATE semantic_refresh_runs
        SET refresh_status = ?,
            facts_serialized_count = ?,
            assertion_count = ?,
            relation_count = ?,
            policy_count = ?,
            updated_at = CURRENT_TIMESTAMP,
            current_stage = ?,
            status_message = ?
        WHERE refresh_id = ?
        """,
        (
            refresh_status,
            facts_serialized_count,
            assertion_count,
            relation_count,
            policy_count,
            current_stage,
            status_message,
            refresh_id,
        ),
    )


def build_mary_fact_workflow_projection(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    report = build_fact_intake_report(conn, run_id=run_id)
    chronology: list[dict[str, Any]] = []
    for index, fact in enumerate(report["facts"], start=1):
        chronology.append(
            {
                "order": index,
                "chronology_sort_key": fact["chronology_sort_key"],
                "chronology_label": fact["chronology_label"] or fact["canonical_label"] or fact["fact_text"][:80],
                "fact_id": fact["fact_id"],
                "candidate_status": fact["candidate_status"],
            }
        )
    workflow_facts = [
        {
            "fact_id": fact["fact_id"],
            "label": fact["canonical_label"] or fact["fact_text"][:80],
            "fact_text": fact["fact_text"],
            "status": fact["candidate_status"],
            "contested": bool(fact["contestations"]),
            "review_statuses": [row["review_status"] for row in fact["reviews"]],
            "observation_predicates": [row["predicate_key"] for row in fact["observations"]],
            "provenance": {
                "source_ids": fact["source_ids"],
                "excerpt_ids": fact["excerpt_ids"],
                "statement_ids": fact["statement_ids"],
            },
            "event_ids": list(fact["event_ids"]),
        }
        for fact in report["facts"]
    ]
    chronology_events = [
        {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "primary_actor": event["primary_actor"],
            "object_text": event["object_text"],
            "time_start": event["time_start"],
            "status": event["status"],
            "confidence": event["confidence"],
        }
        for event in report["events"]
    ]
    review_queue = [
        {
            "fact_id": fact["fact_id"],
            "label": fact["canonical_label"] or fact["fact_text"][:80],
            "needs_review": not fact["reviews"] or bool(fact["contestations"]),
            "contestation_count": len(fact["contestations"]),
        }
        for fact in report["facts"]
        if not fact["reviews"] or fact["contestations"]
    ]
    return {
        "version": MARY_FACT_WORKFLOW_VERSION,
        "run_id": report["run"]["run_id"],
        "source_label": report["run"]["source_label"],
        "summary": report["summary"],
        "facts": workflow_facts,
        "events": chronology_events,
        "chronology": chronology,
        "review_queue": review_queue,
    }


def list_fact_intake_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    source_label: str | None = None,
    workflow_kind: str | None = None,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where_parts: list[str] = []
    params: list[Any] = []
    if source_label:
        where_parts.append("fr.source_label = ?")
        params.append(source_label)
    if workflow_kind:
        where_parts.append(
            """
            EXISTS (
              SELECT 1
              FROM fact_workflow_links AS fwl
              WHERE fwl.fact_run_id = fr.run_id
                AND fwl.workflow_kind = ?
            )
            """.strip()
        )
        params.append(workflow_kind)
    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    params.append(max(int(limit), 1))
    rows = conn.execute(
        f"""
        SELECT fr.run_id, fr.contract_version, fr.source_label, fr.mary_projection_version, fr.notes, fr.created_at
        FROM fact_intake_runs AS fr
        {where}
        ORDER BY fr.created_at DESC, fr.run_id DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        run_id = str(row["run_id"])
        out.append(
            {
                "run_id": run_id,
                "contract_version": str(row["contract_version"]),
                "source_label": str(row["source_label"]),
                "mary_projection_version": str(row["mary_projection_version"]),
                "notes": _normalize_opt_text(row["notes"]),
                "created_at": str(row["created_at"]),
                "source_count": int(conn.execute("SELECT COUNT(*) FROM fact_sources WHERE run_id = ?", (run_id,)).fetchone()[0]),
                "statement_count": int(conn.execute("SELECT COUNT(*) FROM fact_statements WHERE run_id = ?", (run_id,)).fetchone()[0]),
                "observation_count": int(conn.execute("SELECT COUNT(*) FROM fact_observations WHERE run_id = ?", (run_id,)).fetchone()[0]),
                "fact_count": int(conn.execute("SELECT COUNT(*) FROM fact_candidates WHERE run_id = ?", (run_id,)).fetchone()[0]),
                "event_count": int(conn.execute("SELECT COUNT(*) FROM event_candidates WHERE run_id = ?", (run_id,)).fetchone()[0]),
                "contestation_count": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM fact_contestations
                        WHERE fact_id IN (SELECT fact_id FROM fact_candidates WHERE run_id = ?)
                        """,
                        (run_id,),
                    ).fetchone()[0]
                ),
                "review_count": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM fact_reviews
                        WHERE fact_id IN (SELECT fact_id FROM fact_candidates WHERE run_id = ?)
                        """,
                        (run_id,),
                    ).fetchone()[0]
                ),
                "workflow_link": _workflow_link_row_to_dict(
                    conn.execute(
                        """
                        SELECT workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version, created_at
                        FROM fact_workflow_links
                        WHERE fact_run_id = ?
                        """,
                        (run_id,),
                    ).fetchone()
                ),
            }
        )
    return out


def list_fact_review_sources(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    workflow_kind: str | None = None,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where_parts: list[str] = []
    params: list[Any] = []
    if workflow_kind:
        where_parts.append("workflow_kind = ?")
        params.append(str(workflow_kind))
    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    params.append(max(int(limit), 1))
    rows = conn.execute(
        f"""
        SELECT
          COALESCE(source_label, '') AS source_label,
          COUNT(*) AS linked_run_count,
          MAX(created_at) AS latest_created_at
        FROM fact_workflow_links
        {where}
        GROUP BY COALESCE(source_label, '')
        ORDER BY latest_created_at DESC, source_label DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        source_label_value = _normalize_opt_text(row["source_label"])
        latest_link = None
        if source_label_value:
            latest_link = find_latest_fact_workflow_link(
                conn,
                workflow_kind=workflow_kind or "transcript_semantic",
                source_label=source_label_value,
            ) if workflow_kind else _workflow_link_row_to_dict(
                conn.execute(
                    """
                    SELECT workflow_kind, workflow_run_id, fact_run_id, source_label, adapter_version, created_at
                    FROM fact_workflow_links
                    WHERE source_label = ?
                    ORDER BY created_at DESC, workflow_kind, workflow_run_id DESC
                    LIMIT 1
                    """,
                    (source_label_value,),
                ).fetchone()
            )
        out.append(
            {
                "source_label": source_label_value,
                "linked_run_count": int(row["linked_run_count"]),
                "latest_created_at": str(row["latest_created_at"]),
                "latest_workflow_link": latest_link,
            }
        )
    return out


def _build_fact_review_run_summary_legacy(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    report = build_fact_intake_report(conn, run_id=run_id)
    projection = build_mary_fact_workflow_projection(conn, run_id=run_id)
    events_by_id = {str(event["event_id"]): event for event in report["events"]}
    observations_by_id = {str(observation["observation_id"]): observation for observation in report["observations"]}
    sources_by_id = {str(source["source_id"]): source for source in report["sources"]}
    statements_by_id = {str(statement["statement_id"]): statement for statement in report["statements"]}
    fact_rows: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for fact in report["facts"]:
        review_statuses = [row["review_status"] for row in fact["reviews"]]
        latest_review = fact["reviews"][-1] if fact["reviews"] else None
        primary_contested_reason_text = _latest_contestation_reason(fact["contestations"])
        reason_codes: list[str] = []
        if not fact["reviews"]:
            reason_codes.append("unreviewed")
        if fact["contestations"]:
            reason_codes.append("contested")
        if fact["candidate_status"] in {"abstained", "uncertain"}:
            reason_codes.append(f"candidate_{fact['candidate_status']}")
        if any(status == "needs_followup" for status in review_statuses):
            reason_codes.append("review_followup")
        fact_events = [events_by_id[event_id] for event_id in fact["event_ids"] if event_id in events_by_id]
        if not fact_events:
            chronology_bucket = "no_event"
            reason_codes.append("event_missing")
        elif any(event.get("time_start") for event in fact_events):
            chronology_bucket = (
                "dated"
                if any(_event_time_precision(event, observations_by_id) == "dated" for event in fact_events)
                else "approximate"
            )
        else:
            chronology_bucket = "undated"
            reason_codes.append("event_undated")
        if not fact["chronology_sort_key"]:
            reason_codes.append("chronology_undated")
        observation_families = sorted({str(row["predicate_family"]) for row in fact["observations"]})
        observation_predicates = [str(row["predicate_key"]) for row in fact["observations"]]
        signal_classes = list(
            dict.fromkeys(
                _observation_signal_classes(observation_predicates) + _explicit_signal_classes(fact["observations"])
            )
        )
        legal_procedural_predicates = [
            str(row["predicate_key"])
            for row in fact["observations"]
            if str(row["predicate_family"]) == "legal_procedural"
        ]
        source_types = sorted(
            {
                str((sources_by_id.get(source_id) or {}).get("source_type"))
                for source_id in fact["source_ids"]
                if (sources_by_id.get(source_id) or {}).get("source_type")
            }
        )
        source_rows = [sources_by_id[source_id] for source_id in fact["source_ids"] if source_id in sources_by_id]
        source_signal_classes = _source_signal_classes(source_rows)
        source_projection_modes = _source_projection_modes(source_rows)
        has_legal_procedural_observations = _has_legal_procedural_visibility(
            legal_procedural_predicates,
            signal_classes,
            source_signal_classes,
        )
        statement_roles = sorted(
            {
                str((statements_by_id.get(statement_id) or {}).get("statement_role"))
                for statement_id in fact["statement_ids"]
                if (statements_by_id.get(statement_id) or {}).get("statement_role")
            }
        )
        actorish_predicates = {"actor", "co_actor", "organization"}
        if not any(predicate in actorish_predicates for predicate in observation_predicates):
            reason_codes.append("missing_actor")
        if not any(predicate in {"event_time", "event_date"} for predicate in observation_predicates) and chronology_bucket != "dated":
            reason_codes.append("missing_date")
        if not fact["observations"] or (not fact["event_ids"] and fact["candidate_status"] in {"captured", "candidate", "uncertain"}):
            reason_codes.append("statement_only_fact")
        if has_legal_procedural_observations:
            reason_codes.append("procedural_significance")
        chronology_contested = any(
            isinstance(row.get("provenance"), Mapping)
            and _normalize_opt_text(row["provenance"].get("contestation_scope")) == "chronology"
            for row in fact["contestations"]
        )
        if chronology_impacted := bool(fact["chronology_sort_key"]) or any(
            events_by_id[event_id].get("time_start") for event_id in fact["event_ids"] if event_id in events_by_id
        ):
            if chronology_contested:
                reason_codes.append("contradictory_chronology")
        if len(set(fact["source_ids"])) > 1 and fact["contestations"]:
            reason_codes.append("source_conflict")
        reason_codes = list(dict.fromkeys(reason_codes))
        fact_row = {
            "fact_id": fact["fact_id"],
            "label": fact["canonical_label"] or fact["fact_text"][:80],
            "needs_review": not fact["reviews"] or bool(fact["contestations"]),
            "candidate_status": fact["candidate_status"],
            "contestation_count": len(fact["contestations"]),
            "review_statuses": review_statuses,
            "chronology_label": fact["chronology_label"],
            "reason_codes": reason_codes,
            "reason_labels": [REVIEW_REASON_LABELS[code] for code in reason_codes if code in REVIEW_REASON_LABELS],
            "chronology_bucket": chronology_bucket,
            "event_ids": list(fact["event_ids"]),
            "observation_families": observation_families,
            "signal_classes": signal_classes,
            "legal_procedural_predicates": legal_procedural_predicates,
            "has_legal_procedural_observations": has_legal_procedural_observations,
            "legal_procedural_observation_count": len(legal_procedural_predicates),
            "source_types": source_types,
            "source_signal_classes": source_signal_classes,
            "source_projection_modes": source_projection_modes,
            "statement_roles": statement_roles,
            "primary_contested_reason_text": primary_contested_reason_text,
            "latest_review_status": latest_review.get("review_status") if latest_review else None,
            "latest_review_note": _latest_review_note(latest_review),
            "chronology_impacted": chronology_impacted,
            "source_ids": list(fact["source_ids"]),
            "statement_ids": list(fact["statement_ids"]),
        }
        fact_row["status_explanation"] = _build_review_queue_status_explanation(fact_row)
        fact_rows.append(fact_row)
        review_queue.append(fact_row)
    review_queue = [row for row in review_queue if row["needs_review"]]
    review_queue.sort(
        key=lambda row: (
            0 if row["contestation_count"] else 1,
            0 if row["latest_review_status"] == "needs_followup" else 1,
            0 if row["chronology_impacted"] else 1,
            0 if row["has_legal_procedural_observations"] else 1,
            row["label"].casefold(),
            row["fact_id"],
        )
    )
    contested_items = [
        {
            "fact_id": fact["fact_id"],
            "label": fact["canonical_label"] or fact["fact_text"][:80],
            "contestation_count": len(fact["contestations"]),
            "contestation_statuses": [row["contestation_status"] for row in fact["contestations"]],
            "reason_texts": [row["reason_text"] for row in fact["contestations"]],
            "review_statuses": [row["review_status"] for row in fact["reviews"]],
            "chronology_sort_key": fact["chronology_sort_key"],
            "event_ids": list(fact["event_ids"]),
            "chronology_impacted": bool(fact["chronology_sort_key"]) or any(
                events_by_id[event_id].get("time_start") for event_id in fact["event_ids"] if event_id in events_by_id
            ),
        }
        for fact in report["facts"]
        if fact["contestations"]
    ]
    chronology_events = [
        {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "primary_actor": event["primary_actor"],
            "object_text": event["object_text"],
            "time_start": event["time_start"],
            "time_precision": _event_time_precision(event, observations_by_id),
            "status": event["status"],
            "source_event_ids": event["source_event_ids"],
        }
        for event in report["events"]
    ]
    chronology_facts = list(projection["chronology"])
    chronology_summary = {
        "event_count": len(chronology_events),
        "dated_event_count": sum(1 for row in chronology_events if row["time_precision"] == "dated"),
        "approximate_event_count": sum(1 for row in chronology_events if row["time_precision"] == "approximate"),
        "undated_event_count": sum(1 for row in chronology_events if row["time_precision"] == "undated"),
        "fact_count": len(chronology_facts),
        "dated_fact_count": sum(1 for row in chronology_facts if row["chronology_sort_key"]),
        "undated_fact_count": sum(1 for row in chronology_facts if not row["chronology_sort_key"]),
        "no_event_fact_count": sum(1 for fact in report["facts"] if not fact["event_ids"]),
        "contested_chronology_item_count": sum(1 for row in contested_items if row["chronology_impacted"]),
    }
    summary = {
        **report["summary"],
        "source_count": len(report["sources"]),
        "excerpt_count": len(report["excerpts"]),
        "statement_count": len(report["statements"]),
        "review_queue_count": len(review_queue),
        "needs_followup_count": sum(1 for row in review_queue if row["latest_review_status"] == "needs_followup"),
        "chronology_impacted_review_queue_count": sum(1 for row in review_queue if row["chronology_impacted"]),
        "legal_procedural_review_queue_count": sum(1 for row in review_queue if row["has_legal_procedural_observations"]),
        "missing_date_review_queue_count": sum(1 for row in review_queue if "missing_date" in row["reason_codes"]),
        "missing_actor_review_queue_count": sum(1 for row in review_queue if "missing_actor" in row["reason_codes"]),
        "statement_only_review_queue_count": sum(1 for row in review_queue if "statement_only_fact" in row["reason_codes"]),
        "contradictory_chronology_review_queue_count": sum(1 for row in review_queue if "contradictory_chronology" in row["reason_codes"]),
        "contested_item_count": len(contested_items),
        "abstained_fact_count": sum(1 for fact in report["facts"] if fact["candidate_status"] == "abstained"),
        **chronology_summary,
    }
    chronology_groups = {
        "dated_events": [row for row in chronology_events if row["time_precision"] == "dated"],
        "approximate_events": [row for row in chronology_events if row["time_precision"] == "approximate"],
        "undated_events": [row for row in chronology_events if row["time_precision"] == "undated"],
        "facts_with_no_event": [
            {
                "fact_id": fact["fact_id"],
                "label": fact["canonical_label"] or fact["fact_text"][:80],
                "candidate_status": fact["candidate_status"],
                "chronology_label": fact["chronology_label"],
                "source_ids": list(fact["source_ids"]),
                "statement_ids": list(fact["statement_ids"]),
            }
            for fact in report["facts"]
            if not fact["event_ids"]
        ],
        "contested_chronology_items": [row for row in contested_items if row["chronology_impacted"]],
    }
    return {
        "run": report["run"],
        "summary": summary,
        "facts": fact_rows,
        "review_queue": review_queue,
        "contested_summary": {
            "count": len(contested_items),
            "items": contested_items,
            "needs_followup_count": sum(1 for row in contested_items if "needs_followup" in row["review_statuses"]),
            "reviewed_count": sum(1 for row in contested_items if row["review_statuses"]),
            "chronology_impacted_count": sum(1 for row in contested_items if row["chronology_impacted"]),
            "needs_followup_items": [row for row in contested_items if "needs_followup" in row["review_statuses"]],
            "reviewed_items": [row for row in contested_items if row["review_statuses"]],
            "chronology_impacted_items": [row for row in contested_items if row["chronology_impacted"]],
        },
        "chronology_summary": chronology_summary,
        "chronology": {
            "events": chronology_events,
            "facts": chronology_facts,
        },
        "chronology_groups": chronology_groups,
    }


def build_fact_review_run_summary(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    if not _has_semantic_materialization(conn, run_id=run_id):
        return _build_fact_review_run_summary_legacy(conn, run_id=run_id)
    report = build_fact_intake_report(conn, run_id=run_id)
    legacy = _build_fact_review_run_summary_legacy(conn, run_id=run_id)
    fact_class_map = _load_entity_class_map(conn, run_id=run_id, target_kind="fact")
    source_class_map = _load_entity_class_map(conn, run_id=run_id, target_kind="source")
    policy_map = _load_policy_map(conn, run_id=run_id, target_kind="fact")
    sources_by_id = {str(source["source_id"]): source for source in report["sources"]}
    updated_facts: list[dict[str, Any]] = []
    updated_by_fact_id: dict[str, dict[str, Any]] = {}
    for row in legacy["facts"]:
        source_signal_classes: list[str] = []
        for source_id in row.get("source_ids", []):
            for value in source_class_map.get(str(source_id), []):
                if value not in source_signal_classes:
                    source_signal_classes.append(value)
        signal_classes = list(fact_class_map.get(str(row["fact_id"]), []))
        new_row = {
            **row,
            "signal_classes": signal_classes,
            "source_signal_classes": source_signal_classes,
            "policy_outcomes": list(policy_map.get(str(row["fact_id"]), [])),
        }
        updated_facts.append(new_row)
        updated_by_fact_id[str(row["fact_id"])] = new_row
    updated_review_queue = [
        updated_by_fact_id[str(row["fact_id"])]
        for row in legacy["review_queue"]
        if str(row["fact_id"]) in updated_by_fact_id
    ]
    updated_summary = dict(legacy["summary"])
    updated_summary["policy_review_required_count"] = sum(
        1 for row in updated_facts if "review_required" in set(row.get("policy_outcomes", []))
    )
    return {
        **legacy,
        "summary": updated_summary,
        "facts": updated_facts,
        "review_queue": updated_review_queue,
    }


def _build_fact_review_workbench_payload_legacy(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    include_zelph: bool = True,
) -> dict[str, Any]:
    report = build_fact_intake_report(conn, run_id=run_id)
    summary = _build_fact_review_run_summary_legacy(conn, run_id=run_id)
    operator_views = build_fact_review_operator_views(conn, run_id=run_id)
    workflow_link = report["run"].get("workflow_link") if isinstance(report["run"].get("workflow_link"), Mapping) else {}
    recent_sources = list_fact_review_sources(
        conn,
        workflow_kind=_normalize_opt_text(workflow_link.get("workflow_kind")),
        limit=20,
    )
    summary_by_fact_id = {row["fact_id"]: row for row in summary["facts"]}
    review_queue_by_fact_id = {row["fact_id"]: row for row in summary["review_queue"]}
    facts = []
    for fact in report["facts"]:
        queue_row = summary_by_fact_id.get(fact["fact_id"])
        review_queue_row = review_queue_by_fact_id.get(fact["fact_id"])
        facts.append(
            {
                **fact,
                "signal_classes": list(queue_row.get("signal_classes", [])) if queue_row else [],
                "source_signal_classes": list(queue_row.get("source_signal_classes", [])) if queue_row else [],
                "lexical_projection_mode": (list(queue_row.get("source_projection_modes", []))[0] if queue_row and queue_row.get("source_projection_modes") else None),
                "source_types": list(queue_row.get("source_types", [])) if queue_row else [],
                "statement_roles": list(queue_row.get("statement_roles", [])) if queue_row else [],
                "legal_procedural_predicates": list(queue_row.get("legal_procedural_predicates", [])) if queue_row else [],
                "latest_review_status": queue_row.get("latest_review_status") if queue_row else None,
                "latest_review_note": queue_row.get("latest_review_note") if queue_row else None,
                "status_explanation": dict(review_queue_row.get("status_explanation", {})) if review_queue_row else None,
                "inspector_classification": _inspector_classification_for_fact_row(queue_row or {}),
            }
        )
    default_fact_id = summary["review_queue"][0]["fact_id"] if summary["review_queue"] else (report["facts"][0]["fact_id"] if report["facts"] else None)
    workbench = {
        "version": FACT_REVIEW_WORKBENCH_VERSION,
        "zelph_ruleset_version": FACT_REVIEW_ZELPH_RULESET_VERSION,
        "run": report["run"],
        "summary": summary["summary"],
        "review_queue": summary["review_queue"],
        "contested_summary": summary["contested_summary"],
        "chronology_summary": summary["chronology_summary"],
        "chronology": summary["chronology"],
        "chronology_groups": summary["chronology_groups"],
        "operator_views": operator_views,
        "reopen_navigation": _build_reopen_navigation(report["run"], recent_sources),
        "issue_filters": _build_issue_filters(summary, operator_views),
        "sources": report["sources"],
        "excerpts": report["excerpts"],
        "statements": report["statements"],
        "observations": report["observations"],
        "events": report["events"],
        "facts": facts,
        "rule_atoms": report.get("rule_atoms", []),
        "semantic_context": report.get("semantic_context", {}),
        "workflow_summary": _build_fact_review_workflow_summary(
            report=report,
            summary=summary,
            operator_views=operator_views,
            default_fact_id=default_fact_id,
        ),
        "inspector_classification": {
            "status_order": ["party_assertion", "procedural_outcome", "later_annotation"],
            "selected_fact_id": default_fact_id,
            "facts": {row["fact_id"]: row["inspector_classification"] for row in facts},
        },
        "inspector_defaults": {
            "selected_fact_id": default_fact_id,
            "default_view": "intake_triage",
        },
    }
    if not include_zelph:
        return workbench
    return enrich_workbench_with_zelph(workbench, rules=_fact_review_zelph_rules())


def persist_authority_ingest_receipt(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row

    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError("payload.version is required")
    authority_kind = str(payload.get("authority_kind") or "").strip()
    if not authority_kind:
        raise ValueError("payload.authority_kind is required")
    ingest_mode = str(payload.get("ingest_mode") or "").strip()
    if not ingest_mode:
        raise ValueError("payload.ingest_mode is required")
    resolved_url = _normalize_opt_text(payload.get("resolved_url"))
    if not resolved_url:
        raise ValueError("payload.resolved_url is required")

    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    normalized_segments = [segment for segment in segments if isinstance(segment, Mapping)]
    content_sha256 = _normalize_opt_text(payload.get("content_sha256"))
    if not content_sha256:
        raise ValueError("payload.content_sha256 is required")

    ingest_run_id = _stable_id(
        "authingest",
        {
            "authority_kind": authority_kind,
            "ingest_mode": ingest_mode,
            "citation": _normalize_opt_text(payload.get("citation")),
            "query_text": _normalize_opt_text(payload.get("query_text")),
            "selection_reason": _normalize_opt_text(payload.get("selection_reason")),
            "resolved_url": resolved_url,
            "content_sha256": content_sha256,
            "paragraph_request": payload.get("paragraph_request") if isinstance(payload.get("paragraph_request"), list) else [],
            "paragraph_window": int(payload.get("paragraph_window") or 0),
            "segments": [
                {
                    "paragraph_number": segment.get("paragraph_number"),
                    "segment_kind": _normalize_opt_text(segment.get("segment_kind")) or "paragraph",
                    "segment_text": str(segment.get("segment_text") or ""),
                }
                for segment in normalized_segments
            ],
        },
    )
    payload_sha256 = _sha256_payload(payload)

    conn.execute("DELETE FROM authority_ingest_runs WHERE ingest_run_id = ?", (ingest_run_id,))
    conn.execute(
        """
        INSERT INTO authority_ingest_runs(
          ingest_run_id, ingest_version, authority_kind, ingest_mode, citation, query_text,
          selection_reason, resolved_url, content_type, content_length, content_sha256,
          paragraph_request_json, paragraph_window, segment_count, body_preview_text,
          fetch_metadata_json, payload_sha256
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ingest_run_id,
            version,
            authority_kind,
            ingest_mode,
            _normalize_opt_text(payload.get("citation")),
            _normalize_opt_text(payload.get("query_text")),
            _normalize_opt_text(payload.get("selection_reason")),
            resolved_url,
            _normalize_opt_text(payload.get("content_type")),
            int(payload.get("content_length") or 0),
            content_sha256,
            _normalize_json(payload.get("paragraph_request")),
            int(payload.get("paragraph_window") or 0),
            len(normalized_segments),
            _normalize_opt_text(payload.get("body_preview_text")),
            _normalize_json(payload.get("fetch_metadata")),
            payload_sha256,
        ),
    )

    for order, segment in enumerate(normalized_segments, start=1):
        segment_text = str(segment.get("segment_text") or "")
        paragraph_number = segment.get("paragraph_number")
        conn.execute(
            """
            INSERT INTO authority_ingest_segments(
              ingest_run_id, segment_id, segment_order, segment_kind, paragraph_number, segment_text, char_count
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                ingest_run_id,
                _stable_id("authseg", {"ingest_run_id": ingest_run_id, "order": order, "paragraph_number": paragraph_number, "segment_text": segment_text}),
                order,
                _normalize_opt_text(segment.get("segment_kind")) or "paragraph",
                int(paragraph_number) if paragraph_number is not None else None,
                segment_text,
                len(segment_text),
            ),
        )

    conn.commit()
    return {
        "ingest_run_id": ingest_run_id,
        "authority_kind": authority_kind,
        "ingest_mode": ingest_mode,
        "segment_count": len(normalized_segments),
        "payload_sha256": payload_sha256,
    }


def list_authority_ingest_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    authority_kind: str | None = None,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where: list[str] = []
    params: list[Any] = []
    if authority_kind:
        where.append("authority_kind = ?")
        params.append(str(authority_kind))
    sql = """
        SELECT ingest_run_id, ingest_version, authority_kind, ingest_mode, citation, query_text,
               selection_reason, resolved_url, content_type, content_length, paragraph_request_json,
               paragraph_window, segment_count, body_preview_text, created_at
        FROM authority_ingest_runs
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, ingest_run_id DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [
        {
            "ingest_run_id": str(row["ingest_run_id"]),
            "ingest_version": str(row["ingest_version"]),
            "authority_kind": str(row["authority_kind"]),
            "ingest_mode": str(row["ingest_mode"]),
            "citation": _normalize_opt_text(row["citation"]),
            "query_text": _normalize_opt_text(row["query_text"]),
            "selection_reason": _normalize_opt_text(row["selection_reason"]),
            "resolved_url": str(row["resolved_url"]),
            "content_type": _normalize_opt_text(row["content_type"]),
            "content_length": int(row["content_length"] or 0),
            "paragraph_request": _json_or_list(row["paragraph_request_json"]),
            "paragraph_window": int(row["paragraph_window"] or 0),
            "segment_count": int(row["segment_count"] or 0),
            "body_preview_text": _normalize_opt_text(row["body_preview_text"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def build_authority_ingest_summary(
    conn: sqlite3.Connection,
    *,
    ingest_run_id: str,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    run_row = conn.execute(
        """
        SELECT *
        FROM authority_ingest_runs
        WHERE ingest_run_id = ?
        """,
        (str(ingest_run_id or "").strip(),),
    ).fetchone()
    if run_row is None:
        raise ValueError(f"Unknown authority ingest run: {ingest_run_id}")
    segment_rows = conn.execute(
        """
        SELECT segment_id, segment_order, segment_kind, paragraph_number, segment_text, char_count
        FROM authority_ingest_segments
        WHERE ingest_run_id = ?
        ORDER BY segment_order ASC, segment_id ASC
        """,
        (str(ingest_run_id),),
    ).fetchall()
    return {
        "run": {
            "ingest_run_id": str(run_row["ingest_run_id"]),
            "ingest_version": str(run_row["ingest_version"]),
            "authority_kind": str(run_row["authority_kind"]),
            "ingest_mode": str(run_row["ingest_mode"]),
            "citation": _normalize_opt_text(run_row["citation"]),
            "query_text": _normalize_opt_text(run_row["query_text"]),
            "selection_reason": _normalize_opt_text(run_row["selection_reason"]),
            "resolved_url": str(run_row["resolved_url"]),
            "content_type": _normalize_opt_text(run_row["content_type"]),
            "content_length": int(run_row["content_length"] or 0),
            "content_sha256": str(run_row["content_sha256"]),
            "paragraph_request": _json_or_list(run_row["paragraph_request_json"]),
            "paragraph_window": int(run_row["paragraph_window"] or 0),
            "segment_count": int(run_row["segment_count"] or 0),
            "body_preview_text": _normalize_opt_text(run_row["body_preview_text"]),
            "fetch_metadata": _json_or_dict(run_row["fetch_metadata_json"]),
            "created_at": str(run_row["created_at"]),
        },
        "segments": [
            {
                "segment_id": str(row["segment_id"]),
                "segment_order": int(row["segment_order"] or 0),
                "segment_kind": str(row["segment_kind"]),
                "paragraph_number": int(row["paragraph_number"]) if row["paragraph_number"] is not None else None,
                "segment_text": str(row["segment_text"]),
                "char_count": int(row["char_count"] or 0),
            }
            for row in segment_rows
        ],
    }


def persist_feedback_receipt(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row

    schema_version = str(payload.get("schema_version") or "").strip()
    if not schema_version:
        raise ValueError("payload.schema_version is required")
    feedback_class = str(payload.get("feedback_class") or "").strip()
    if not feedback_class:
        raise ValueError("payload.feedback_class is required")
    role_label = str(payload.get("role_label") or "").strip()
    if not role_label:
        raise ValueError("payload.role_label is required")
    task_label = str(payload.get("task_label") or "").strip()
    if not task_label:
        raise ValueError("payload.task_label is required")
    source_kind = str(payload.get("source_kind") or "").strip()
    if not source_kind:
        raise ValueError("payload.source_kind is required")
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise ValueError("payload.summary is required")
    quote_text = str(payload.get("quote_text") or "").strip()
    if not quote_text:
        raise ValueError("payload.quote_text is required")
    severity = str(payload.get("severity") or "").strip()
    if not severity:
        raise ValueError("payload.severity is required")
    captured_at = str(payload.get("captured_at") or "").strip()
    if not captured_at:
        raise ValueError("payload.captured_at is required")

    receipt_id = _stable_id(
        "feedback",
        {
            "schema_version": schema_version,
            "feedback_class": feedback_class,
            "role_label": role_label,
            "task_label": task_label,
            "target_product": _normalize_opt_text(payload.get("target_product")),
            "target_surface": _normalize_opt_text(payload.get("target_surface")),
            "workflow_label": _normalize_opt_text(payload.get("workflow_label")),
            "source_kind": source_kind,
            "summary": summary,
            "quote_text": quote_text,
            "severity": severity,
            "desired_outcome": _normalize_opt_text(payload.get("desired_outcome")),
            "captured_at": captured_at,
        },
    )
    payload_sha256 = _sha256_payload(payload)
    conn.execute("DELETE FROM feedback_receipts WHERE receipt_id = ?", (receipt_id,))
    conn.execute(
        """
        INSERT INTO feedback_receipts(
          receipt_id, schema_version, feedback_class, role_label, task_label,
          target_product, target_surface, workflow_label, source_kind, summary,
          quote_text, severity, desired_outcome, sentiment, captured_at,
          tags_json, provenance_json, payload_sha256
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            receipt_id,
            schema_version,
            feedback_class,
            role_label,
            task_label,
            _normalize_opt_text(payload.get("target_product")),
            _normalize_opt_text(payload.get("target_surface")),
            _normalize_opt_text(payload.get("workflow_label")),
            source_kind,
            summary,
            quote_text,
            severity,
            _normalize_opt_text(payload.get("desired_outcome")),
            _normalize_opt_text(payload.get("sentiment")),
            captured_at,
            _normalize_json(payload.get("tags")),
            _normalize_json(payload.get("provenance")),
            payload_sha256,
        ),
    )
    conn.commit()
    return {
        "receipt_id": receipt_id,
        "schema_version": schema_version,
        "feedback_class": feedback_class,
        "source_kind": source_kind,
        "payload_sha256": payload_sha256,
    }


def list_feedback_receipts(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    feedback_class: str | None = None,
    source_kind: str | None = None,
    target_product: str | None = None,
) -> list[dict[str, Any]]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    where: list[str] = []
    params: list[Any] = []
    if feedback_class:
        where.append("feedback_class = ?")
        params.append(str(feedback_class))
    if source_kind:
        where.append("source_kind = ?")
        params.append(str(source_kind))
    if target_product:
        where.append("target_product = ?")
        params.append(str(target_product))
    sql = """
        SELECT receipt_id, schema_version, feedback_class, role_label, task_label,
               target_product, target_surface, workflow_label, source_kind, summary,
               quote_text, severity, desired_outcome, sentiment, captured_at,
               tags_json, provenance_json, created_at
        FROM feedback_receipts
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY captured_at DESC, receipt_id DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [
        {
            "receipt_id": str(row["receipt_id"]),
            "schema_version": str(row["schema_version"]),
            "feedback_class": str(row["feedback_class"]),
            "role_label": str(row["role_label"]),
            "task_label": str(row["task_label"]),
            "target_product": _normalize_opt_text(row["target_product"]),
            "target_surface": _normalize_opt_text(row["target_surface"]),
            "workflow_label": _normalize_opt_text(row["workflow_label"]),
            "source_kind": str(row["source_kind"]),
            "summary": str(row["summary"]),
            "quote_text": str(row["quote_text"]),
            "severity": str(row["severity"]),
            "desired_outcome": _normalize_opt_text(row["desired_outcome"]),
            "sentiment": _normalize_opt_text(row["sentiment"]),
            "captured_at": str(row["captured_at"]),
            "tags": _json_or_list(row["tags_json"]),
            "provenance": _json_or_dict(row["provenance_json"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def build_feedback_receipt_summary(
    conn: sqlite3.Connection,
    *,
    receipt_id: str,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT *
        FROM feedback_receipts
        WHERE receipt_id = ?
        """,
        (str(receipt_id or "").strip(),),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown feedback receipt: {receipt_id}")
    return {
        "receipt": {
            "receipt_id": str(row["receipt_id"]),
            "schema_version": str(row["schema_version"]),
            "feedback_class": str(row["feedback_class"]),
            "role_label": str(row["role_label"]),
            "task_label": str(row["task_label"]),
            "target_product": _normalize_opt_text(row["target_product"]),
            "target_surface": _normalize_opt_text(row["target_surface"]),
            "workflow_label": _normalize_opt_text(row["workflow_label"]),
            "source_kind": str(row["source_kind"]),
            "summary": str(row["summary"]),
            "quote_text": str(row["quote_text"]),
            "severity": str(row["severity"]),
            "desired_outcome": _normalize_opt_text(row["desired_outcome"]),
            "sentiment": _normalize_opt_text(row["sentiment"]),
            "captured_at": str(row["captured_at"]),
            "tags": _json_or_list(row["tags_json"]),
            "provenance": _json_or_dict(row["provenance_json"]),
            "created_at": str(row["created_at"]),
        }
    }


def persist_fact_semantic_materialization(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    include_zelph: bool = True,
    refresh_kind: str = "dual_write",
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    ensure_database(conn)
    _ensure_fact_intake_tables(conn)
    conn.row_factory = sqlite3.Row
    refresh_id = _stable_id(
        "semrefresh",
        {
            "run_id": run_id,
            "ruleset_version": FACT_REVIEW_ZELPH_RULESET_VERSION,
            "refresh_kind": refresh_kind,
            "include_zelph": include_zelph,
        },
    )

    def emit(stage: str, message: str, *, status: str = "running", facts_serialized_count: int = 0, assertion_count: int = 0, relation_count: int = 0, policy_count: int = 0) -> None:
        _upsert_semantic_refresh_run(
            conn,
            refresh_id=refresh_id,
            run_id=run_id,
            refresh_kind=refresh_kind,
            refresh_status=status,
            current_stage=stage,
            status_message=message,
            facts_serialized_count=facts_serialized_count,
            assertion_count=assertion_count,
            relation_count=relation_count,
            policy_count=policy_count,
        )
        conn.commit()
        if callable(progress_callback):
            progress_callback(
                {
                    "run_id": run_id,
                    "refresh_id": refresh_id,
                    "status": status,
                    "stage": stage,
                    "message": message,
                    "facts_serialized_count": facts_serialized_count,
                    "assertion_count": assertion_count,
                    "relation_count": relation_count,
                    "policy_count": policy_count,
                }
            )

    assertion_count = 0
    relation_count = 0
    policy_count = 0
    workbench_facts_serialized_count = 0
    emit("load_report", "Loading persisted fact-intake report.", status="pending")
    try:
        report = build_fact_intake_report(conn, run_id=run_id)
        emit("build_workbench", "Building legacy workbench for semantic projection.")
        workbench = _build_fact_review_workbench_payload_legacy(conn, run_id=run_id, include_zelph=include_zelph)
        workbench_facts_serialized_count = int(workbench.get("zelph", {}).get("facts_serialized_count", 0))
        emit("clear_previous", "Clearing previous semantic materialization rows.", facts_serialized_count=workbench_facts_serialized_count)
        conn.execute("DELETE FROM policy_outcomes WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM entity_relations WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM entity_class_assertions WHERE run_id = ?", (run_id,))

        emit("materialize_sources", f"Writing source semantic assertions for {len(report['sources'])} sources.", facts_serialized_count=workbench_facts_serialized_count)
        source_signal_by_id = {str(source["source_id"]): _derived_source_classes(source) for source in report["sources"]}
        for source in report["sources"]:
            source_id = str(source["source_id"])
            for class_key in source_signal_by_id.get(source_id, []):
                _record_class_assertion(
                    conn,
                    run_id=run_id,
                    target_kind="source",
                    target_id=source_id,
                    class_key=class_key,
                    assertion_origin="ingest",
                    rule_key="legacy_source_metadata",
                    provenance={"source_id": source_id},
                )
                assertion_count += 1

        emit("materialize_observations", f"Writing observation semantic assertions for {len(report['observations'])} observations.", facts_serialized_count=workbench_facts_serialized_count, assertion_count=assertion_count)
        for observation in report["observations"]:
            observation_id = str(observation["observation_id"])
            predicate_classes = _observation_signal_classes([str(observation["predicate_key"])])
            explicit_classes = _explicit_signal_classes([observation])
            for class_key in list(dict.fromkeys(predicate_classes + explicit_classes)):
                _record_class_assertion(
                    conn,
                    run_id=run_id,
                    target_kind="observation",
                    target_id=observation_id,
                    class_key=class_key,
                    assertion_origin="ingest" if class_key in explicit_classes else "native_rule",
                    rule_key="legacy_observation_metadata" if class_key in explicit_classes else "native_signal_projection",
                    provenance={"observation_id": observation_id},
                )
                assertion_count += 1

        emit("materialize_facts", f"Writing fact assertions/policies for {len(report['facts'])} facts.", facts_serialized_count=workbench_facts_serialized_count, assertion_count=assertion_count)
        fact_rows_by_id = {str(row["fact_id"]): row for row in workbench["facts"]}
        for fact in report["facts"]:
            fact_id = str(fact["fact_id"])
            fact_row = fact_rows_by_id.get(fact_id, {})
            for class_key in fact_row.get("signal_classes", []):
                origin = "zelph" if class_key in set(fact_row.get("inferred_signal_classes", [])) else "native_rule"
                rule_key = "zelph_signal_projection" if origin == "zelph" else "native_signal_projection"
                _record_class_assertion(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    class_key=str(class_key),
                    assertion_origin=origin,
                    rule_key=rule_key,
                    provenance={"fact_id": fact_id},
                )
                assertion_count += 1
            for policy_key in (
                ["review_required"] if any(row["fact_id"] == fact_id for row in workbench["review_queue"]) else []
            ):
                _record_policy_outcome(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    policy_key=policy_key,
                    rule_key="policy_projection",
                    provenance={"fact_id": fact_id, "reason": "review_queue"},
                )
                policy_count += 1
            fact_signal_set = set(fact_row.get("signal_classes", []))
            if {"authority_transfer_risk", "public_knowledge_not_authority"} & fact_signal_set:
                _record_policy_outcome(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    policy_key="do_not_promote_to_primary",
                    rule_key="policy_projection",
                    provenance={"fact_id": fact_id, "signals": sorted({"authority_transfer_risk", "public_knowledge_not_authority"} & fact_signal_set)},
                )
                policy_count += 1
            if {"uncertainty_preserved", "self_correction_signal"} & fact_signal_set:
                _record_policy_outcome(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    policy_key="preserve_source_boundary",
                    rule_key="policy_projection",
                    provenance={"fact_id": fact_id},
                )
                policy_count += 1
            if {"ocr_capture", "agent_summary", "system_summary", "later_annotation"} & {
                signal
                for source_id in fact.get("source_ids", [])
                for signal in source_signal_by_id.get(str(source_id), [])
            }:
                _record_policy_outcome(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    policy_key="bounded_context_required",
                    rule_key="policy_projection",
                    provenance={"fact_id": fact_id},
                )
                policy_count += 1
            if {"volatility_signal", "authority_transfer_risk"} & fact_signal_set:
                _record_policy_outcome(
                    conn,
                    run_id=run_id,
                    target_kind="fact",
                    target_id=fact_id,
                    policy_key="manual_resolution_required",
                    rule_key="policy_projection",
                    provenance={"fact_id": fact_id},
                )
                policy_count += 1

            source_ids = list(fact.get("source_ids", []))
            public_source_ids = [
                source_id
                for source_id in source_ids
                if {"public_summary", "wiki_article", "reporting_source"} & set(source_signal_by_id.get(str(source_id), []))
            ]
            record_source_ids = [
                source_id
                for source_id in source_ids
                if {"legal_record", "procedural_record", "strong_legal_source"} & set(source_signal_by_id.get(str(source_id), []))
            ]
            for public_source_id in public_source_ids:
                for record_source_id in record_source_ids:
                    _record_relation(
                        conn,
                        run_id=run_id,
                        subject_kind="source",
                        subject_id=str(public_source_id),
                        relation_key="contextualizes",
                        object_kind="source",
                        object_id=str(record_source_id),
                        assertion_origin="native_rule",
                        rule_key="native_signal_projection",
                        provenance={"fact_id": fact_id},
                    )
                    relation_count += 1
                    _record_relation(
                        conn,
                        run_id=run_id,
                        subject_kind="source",
                        subject_id=str(public_source_id),
                        relation_key="cannot_upgrade_authority_of",
                        object_kind="source",
                        object_id=str(record_source_id),
                        assertion_origin="zelph" if "public_knowledge_not_authority" in fact_signal_set else "native_rule",
                        rule_key="zelph_signal_projection" if "public_knowledge_not_authority" in fact_signal_set else "native_signal_projection",
                        provenance={"fact_id": fact_id},
                    )
                    relation_count += 1

        for idx, fact in enumerate(report["facts"]):
            fact_id = str(fact["fact_id"])
            fact_signal_set = set(fact_rows_by_id.get(fact_id, {}).get("signal_classes", []))
            for other in report["facts"][idx + 1 :]:
                other_id = str(other["fact_id"])
                other_signal_set = set(fact_rows_by_id.get(other_id, {}).get("signal_classes", []))
                if fact.get("contestations") and other.get("contestations"):
                    _record_relation(
                        conn,
                        run_id=run_id,
                        subject_kind="fact",
                        subject_id=fact_id,
                        relation_key="contradicts",
                        object_kind="fact",
                        object_id=other_id,
                        assertion_origin="native_rule",
                        rule_key="native_signal_projection",
                        provenance={"reason": "mutual_contestation"},
                    )
                    relation_count += 1
                if fact_signal_set & {"procedural_outcome", "public_knowledge_not_authority"} and other_signal_set & {"party_assertion", "uncertainty_preserved"}:
                    _record_relation(
                        conn,
                        run_id=run_id,
                        subject_kind="fact",
                        subject_id=fact_id,
                        relation_key="corroborates",
                        object_kind="fact",
                        object_id=other_id,
                        assertion_origin="native_rule",
                        rule_key="native_signal_projection",
                        provenance={"reason": "complementary_semantics"},
                    )
                    relation_count += 1

        emit("finalize", "Semantic materialization complete.", status="ok", facts_serialized_count=workbench_facts_serialized_count, assertion_count=assertion_count, relation_count=relation_count, policy_count=policy_count)
    except Exception as exc:
        emit(
            "error",
            f"Semantic materialization failed: {exc}",
            status="error",
            facts_serialized_count=workbench_facts_serialized_count,
            assertion_count=assertion_count,
            relation_count=relation_count,
            policy_count=policy_count,
        )
        raise

    return {
        "refresh_id": refresh_id,
        "run_id": run_id,
        "assertion_count": assertion_count,
        "relation_count": relation_count,
        "policy_count": policy_count,
        "refresh_kind": refresh_kind,
        "refresh_status": "ok",
    }


def build_fact_review_operator_views(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    summary = build_fact_review_run_summary(conn, run_id=run_id)
    review_queue = list(summary["review_queue"])
    chronology_groups = dict(summary["chronology_groups"])
    contested_summary = dict(summary["contested_summary"])
    review_queue_control_items = build_review_queue_control_items(review_queue)
    review_queue_control_summary = summarize_follow_queue(review_queue_control_items)
    contested_control_items = build_contested_control_items(contested_summary["items"])
    contested_control_summary = summarize_follow_queue(contested_control_items)
    intake_groups = {
        "missing_date": [row for row in review_queue if "missing_date" in row["reason_codes"]],
        "missing_actor": [row for row in review_queue if "missing_actor" in row["reason_codes"]],
        "contradictory_chronology": [row for row in review_queue if "contradictory_chronology" in row["reason_codes"]],
        "procedural_significance": [row for row in review_queue if "procedural_significance" in row["reason_codes"]],
    }
    return {
        "intake_triage": {
            "title": "Intake triage",
            "control_plane": build_follow_control_plane(
                source_family="fact_review",
                hint_kind="fact_review_signal",
                receipt_kind="fact_observation_record",
                substrate_kind="fact_review_workbench",
                conjecture_kind="review_queue_item",
                route_targets=list(review_queue_control_summary["route_target_counts"].keys()),
                resolution_statuses=list(review_queue_control_summary["resolution_status_counts"].keys()),
            ),
            "summary": {
                "review_queue_count": summary["summary"]["review_queue_count"],
                "needs_followup_count": summary["summary"]["needs_followup_count"],
                "missing_date_review_queue_count": summary["summary"]["missing_date_review_queue_count"],
                "missing_actor_review_queue_count": summary["summary"]["missing_actor_review_queue_count"],
                "statement_only_review_queue_count": summary["summary"]["statement_only_review_queue_count"],
                "queue_count": review_queue_control_summary["queue_count"],
                "route_target_counts": review_queue_control_summary["route_target_counts"],
                "resolution_status_counts": review_queue_control_summary["resolution_status_counts"],
            },
            "groups": {
                **intake_groups,
                "chronology_conflict": list(intake_groups["contradictory_chronology"]),
            },
            "items": review_queue,
            "queue": review_queue_control_items,
        },
        "chronology_prep": {
            "title": "Chronology prep",
            "summary": dict(summary["chronology_summary"]),
            "groups": chronology_groups,
            "items": list(summary.get("chronology", [])),
        },
        "procedural_posture": {
            "title": "Procedural posture",
            "summary": {
                "legal_procedural_review_queue_count": summary["summary"]["legal_procedural_review_queue_count"],
                "contested_item_count": summary["summary"]["contested_item_count"],
            },
            "groups": {},
            "items": [row for row in review_queue if row["has_legal_procedural_observations"]],
        },
        "contested_items": {
            "title": "Contested items",
            "control_plane": build_follow_control_plane(
                source_family="fact_review",
                hint_kind="contestation_signal",
                receipt_kind="fact_contestation_record",
                substrate_kind="fact_review_workbench",
                conjecture_kind="contested_fact_item",
                route_targets=list(contested_control_summary["route_target_counts"].keys()),
                resolution_statuses=list(contested_control_summary["resolution_status_counts"].keys()),
            ),
            "summary": {
                "count": contested_summary["count"],
                "needs_followup_count": contested_summary["needs_followup_count"],
                "chronology_impacted_count": contested_summary["chronology_impacted_count"],
                "queue_count": contested_control_summary["queue_count"],
                "route_target_counts": contested_control_summary["route_target_counts"],
                "resolution_status_counts": contested_control_summary["resolution_status_counts"],
            },
            "groups": {},
            "items": list(contested_summary["items"]),
            "queue": contested_control_items,
        },
        "trauma_handoff": {
            "title": "Trauma handoff",
            "summary": {
                "support_handoff_count": sum(
                    1 for row in review_queue if {"user_authored", "support_worker_note", "third_party_record"} & set(row["source_signal_classes"])
                ),
                "abstained_count": summary["summary"]["abstained_fact_count"],
            },
            "items": [
                row
                for row in review_queue
                if {"user_authored", "support_worker_note", "third_party_record", "later_annotation"} & set(row["source_signal_classes"])
            ],
        },
        "professional_handoff": {
            "title": "Professional handoff",
            "summary": {
                "user_authored_count": sum(
                    1 for row in review_queue if {"user_authored", "client_account", "patient_account"} & set(row["source_signal_classes"])
                ),
                "professional_note_count": sum(
                    1 for row in review_queue if {"professional_note", "professional_interpretation"} & set(row["source_signal_classes"])
                ),
                "documentary_count": sum(
                    1 for row in review_queue if {"documentary_record", "third_party_record", "legal_record"} & set(row["source_signal_classes"])
                ),
            },
            "items": [
                row
                for row in review_queue
                if {"user_authored", "client_account", "patient_account", "professional_note", "professional_interpretation", "documentary_record", "third_party_record"} & set(row["source_signal_classes"])
            ],
        },
        "false_coherence_review": {
            "title": "False-coherence review",
            "summary": {
                "abstained_count": summary["summary"]["abstained_fact_count"],
                "contested_count": summary["summary"]["contested_item_count"],
                "no_event_fact_count": summary["chronology_summary"]["no_event_fact_count"],
            },
            "items": [
                row
                for row in review_queue
                if {"fragmentary_account", "contradiction_cluster", "not_enough_evidence", "uncertainty_preserved"} & set(row["signal_classes"])
                or {"candidate_abstained", "statement_only_fact", "source_conflict"} & set(row["reason_codes"])
            ],
        },
        "public_claim_review": {
            "title": "Public claim review",
            "summary": {
                "public_claim_count": sum(
                    1
                    for row in review_queue
                    if {"public_summary", "wiki_article", "reporting_source", "wikidata_claim"} & set(row["source_signal_classes"])
                ),
                "procedural_record_count": sum(
                    1 for row in review_queue if {"legal_record", "procedural_record"} & set(row["source_signal_classes"])
                ),
            },
            "items": [
                row
                for row in review_queue
                if {"public_summary", "wiki_article", "reporting_source", "wikidata_claim"} & set(row["source_signal_classes"])
                or {"public_summary_claim", "overstatement_risk", "source_shopping_risk"} & set(row["signal_classes"])
            ],
        },
        "wiki_fidelity": {
            "title": "Wiki fidelity",
            "summary": {
                "wiki_fidelity_count": sum(
                    1
                    for row in review_queue
                    if {"wiki_article", "public_summary"} & set(row["source_signal_classes"])
                    and {"legal_record", "procedural_record"} & set(row["source_signal_classes"])
                ),
            },
            "items": [
                row
                for row in review_queue
                if {"wiki_article", "public_summary"} & set(row["source_signal_classes"])
                and {"legal_record", "procedural_record"} & set(row["source_signal_classes"])
            ],
        },
        "claim_alignment": {
            "title": "Claim alignment",
            "summary": {
                "wikidata_claim_count": sum(1 for row in review_queue if "wikidata_claim" in set(row["source_signal_classes"])),
                "structural_boundary_count": sum(
                    1 for row in review_queue if {"structural_ambiguity", "identity_claim", "institutional_boundary"} & set(row["signal_classes"])
                ),
            },
            "items": [
                row
                for row in review_queue
                if "wikidata_claim" in set(row["source_signal_classes"])
                or {"structural_ambiguity", "identity_claim", "institutional_boundary", "office_holder_role"} & set(row["signal_classes"])
            ],
        },
    }


def _inspector_classification_for_fact_row(fact_row: Mapping[str, Any]) -> dict[str, Any]:
    signal_classes = [str(value) for value in fact_row.get("signal_classes", []) if str(value).strip()]
    source_signal_classes = [str(value) for value in fact_row.get("source_signal_classes", []) if str(value).strip()]
    status_keys = {
        "party_assertion": "party_assertion" in signal_classes,
        "procedural_outcome": "procedural_outcome" in signal_classes,
        "later_annotation": "later_annotation" in source_signal_classes,
    }
    dominant_label = next((key for key in ("procedural_outcome", "party_assertion", "later_annotation") if status_keys[key]), "unclassified")
    return {
        "status_keys": status_keys,
        "dominant_label": dominant_label,
        "display_labels": [
            label.replace("_", " ")
            for label, enabled in status_keys.items()
            if enabled
        ] or ["unclassified"],
    }


def _build_issue_filters(summary: Mapping[str, Any], operator_views: Mapping[str, Any]) -> dict[str, Any]:
    intake_triage = operator_views.get("intake_triage") if isinstance(operator_views, Mapping) else None
    triage_groups = intake_triage.get("groups") if isinstance(intake_triage, Mapping) else {}
    filters: list[dict[str, Any]] = []
    for key in ("missing_date", "missing_actor", "contradictory_chronology", "procedural_significance"):
        items = triage_groups.get(key, []) if isinstance(triage_groups, Mapping) else []
        filters.append(
            {
                "filter_key": key,
                "label": REVIEW_REASON_LABELS.get(key, key.replace("_", " ").title()),
                "count": len(items) if isinstance(items, list) else 0,
                "fact_ids": [row["fact_id"] for row in items if isinstance(row, Mapping) and row.get("fact_id")],
            }
        )
    return {
        "default_filter": "all",
        "available_filters": ["all", *[row["filter_key"] for row in filters if row["count"] > 0]],
        "filters": filters,
        "summary": {
            "missing_date_review_queue_count": summary["summary"]["missing_date_review_queue_count"],
            "missing_actor_review_queue_count": summary["summary"]["missing_actor_review_queue_count"],
            "contradictory_chronology_review_queue_count": summary["summary"]["contradictory_chronology_review_queue_count"],
            "procedural_significance_review_queue_count": summary["summary"]["legal_procedural_review_queue_count"],
        },
    }



def _build_reopen_navigation(run: Mapping[str, Any], sources: list[Mapping[str, Any]]) -> dict[str, Any]:
    workflow_link = run.get("workflow_link") if isinstance(run.get("workflow_link"), Mapping) else {}
    workflow_kind = _normalize_opt_text(workflow_link.get("workflow_kind"))
    workflow_run_id = _normalize_opt_text(workflow_link.get("workflow_run_id"))
    source_label = _normalize_opt_text(run.get("source_label"))
    return {
        "current": {
            "run_id": run.get("run_id"),
            "source_label": source_label,
            "workflow_kind": workflow_kind,
            "workflow_run_id": workflow_run_id,
        },
        "query": {
            "workflow_kind": workflow_kind,
            "workflow_run_id": workflow_run_id,
            "source_label": source_label,
        },
        "recent_sources": [
            {
                "source_label": row.get("source_label"),
                "workflow_kind": ((row.get("latest_workflow_link") or {}).get("workflow_kind") if isinstance(row.get("latest_workflow_link"), Mapping) else None),
                "workflow_run_id": ((row.get("latest_workflow_link") or {}).get("workflow_run_id") if isinstance(row.get("latest_workflow_link"), Mapping) else None),
                "fact_run_id": ((row.get("latest_workflow_link") or {}).get("fact_run_id") if isinstance(row.get("latest_workflow_link"), Mapping) else None),
                "run_count": row.get("run_count"),
            }
            for row in sources
        ],
    }


def _build_fact_review_workflow_summary(
    *,
    report: Mapping[str, Any],
    summary: Mapping[str, Any],
    operator_views: Mapping[str, Any],
    default_fact_id: str | None,
) -> dict[str, Any]:
    semantic_context = (
        report.get("semantic_context") if isinstance(report.get("semantic_context"), Mapping) else {}
    )
    promotion_gate = (
        semantic_context.get("promotion_gate")
        if isinstance(semantic_context.get("promotion_gate"), Mapping)
        else None
    )
    summary_counts = summary.get("summary") if isinstance(summary.get("summary"), Mapping) else {}
    chronology_summary = (
        summary.get("chronology_summary") if isinstance(summary.get("chronology_summary"), Mapping) else {}
    )
    contested_summary = (
        summary.get("contested_summary") if isinstance(summary.get("contested_summary"), Mapping) else {}
    )
    authority_follow = (
        operator_views.get("authority_follow") if isinstance(operator_views.get("authority_follow"), Mapping) else {}
    )
    authority_follow_summary = (
        authority_follow.get("summary") if isinstance(authority_follow.get("summary"), Mapping) else {}
    )
    authority_follow_queue = (
        authority_follow.get("queue") if isinstance(authority_follow.get("queue"), list) else []
    )
    intake_triage = (
        operator_views.get("intake_triage") if isinstance(operator_views.get("intake_triage"), Mapping) else {}
    )
    intake_groups = (
        intake_triage.get("groups") if isinstance(intake_triage.get("groups"), Mapping) else {}
    )
    review_filters = [
        str(key)
        for key, rows in intake_groups.items()
        if str(key).strip() and str(key) != "all" and isinstance(rows, list) and rows
    ]

    review_queue_count = int(summary_counts.get("review_queue_count") or 0)
    contested_followup_count = int(contested_summary.get("needs_followup_count") or 0)
    authority_follow_queue_count = int(authority_follow_summary.get("queue_count") or len(authority_follow_queue))
    undated_event_count = int(chronology_summary.get("undated_event_count") or 0)
    no_event_fact_count = int(chronology_summary.get("no_event_fact_count") or 0)
    gate_decision = str(promotion_gate.get("decision") or "").strip() if isinstance(promotion_gate, Mapping) else None

    counts = {
        "review_queue_count": review_queue_count,
        "contested_followup_count": contested_followup_count,
        "authority_follow_queue_count": authority_follow_queue_count,
        "undated_event_count": undated_event_count,
        "no_event_fact_count": no_event_fact_count,
    }

    if authority_follow_queue_count > 0:
        return {
            "stage": "follow_up",
            "title": "Resolve authority follow-up items",
            "recommended_view": "authority_follow",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": f"{authority_follow_queue_count} authority follow-up item(s) remain open.",
            "counts": counts,
            "promotion_gate": promotion_gate,
        }
    if contested_followup_count > 0:
        return {
            "stage": "follow_up",
            "title": "Resolve contested review items",
            "recommended_view": "contested_items",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": f"{contested_followup_count} contested item(s) still need follow-up.",
            "counts": counts,
            "promotion_gate": promotion_gate,
        }
    if review_queue_count > 0:
        gate_note = " The current promotion gate is audit." if gate_decision == "audit" else ""
        return {
            "stage": "decide",
            "title": "Review unresolved facts",
            "recommended_view": "intake_triage",
            "recommended_filter": review_filters[0] if review_filters else "all",
            "focus_fact_id": default_fact_id,
            "reason": f"{review_queue_count} fact(s) remain in the review queue.{gate_note}",
            "counts": counts,
            "promotion_gate": promotion_gate,
        }
    if undated_event_count > 0 or no_event_fact_count > 0:
        return {
            "stage": "inspect",
            "title": "Inspect chronology pressure before handoff",
            "recommended_view": "chronology_prep",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": (
                f"Chronology still has {undated_event_count} undated event(s) and "
                f"{no_event_fact_count} no-event fact(s)."
            ),
            "counts": counts,
            "promotion_gate": promotion_gate,
        }
    return {
        "stage": "record",
        "title": "Record and hand off the bounded review state",
        "recommended_view": "professional_handoff",
        "recommended_filter": None,
        "focus_fact_id": default_fact_id,
        "reason": "No open follow-up, review-queue, or chronology pressure is blocking the current bundle.",
        "counts": counts,
        "promotion_gate": promotion_gate,
    }


def _fact_review_zelph_rules() -> str:
    base_dir = Path(__file__).resolve().parent
    return load_zelph_rules(
        base_dir / "zelph_invariants.zlp",
        base_dir / "zelph_workbench_rules.zlp",
    )


def build_fact_review_workbench_payload(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    include_zelph: bool = True,
) -> dict[str, Any]:
    if not _has_semantic_materialization(conn, run_id=run_id):
        return _build_fact_review_workbench_payload_legacy(conn, run_id=run_id, include_zelph=include_zelph)
    report = build_fact_intake_report(conn, run_id=run_id)
    summary = build_fact_review_run_summary(conn, run_id=run_id)
    operator_views = build_fact_review_operator_views(conn, run_id=run_id)
    workflow_link = report["run"].get("workflow_link") if isinstance(report["run"].get("workflow_link"), Mapping) else {}
    recent_sources = list_fact_review_sources(
        conn,
        workflow_kind=_normalize_opt_text(workflow_link.get("workflow_kind")),
        limit=20,
    )
    summary_by_fact_id = {row["fact_id"]: row for row in summary["facts"]}
    review_queue_by_fact_id = {row["fact_id"]: row for row in summary["review_queue"]}
    facts = []
    for fact in report["facts"]:
        queue_row = summary_by_fact_id.get(fact["fact_id"])
        review_queue_row = review_queue_by_fact_id.get(fact["fact_id"])
        facts.append(
            {
                **fact,
                "signal_classes": list(queue_row.get("signal_classes", [])) if queue_row else [],
                "source_signal_classes": list(queue_row.get("source_signal_classes", [])) if queue_row else [],
                "lexical_projection_mode": (list(queue_row.get("source_projection_modes", []))[0] if queue_row and queue_row.get("source_projection_modes") else None),
                "source_types": list(queue_row.get("source_types", [])) if queue_row else [],
                "statement_roles": list(queue_row.get("statement_roles", [])) if queue_row else [],
                "legal_procedural_predicates": list(queue_row.get("legal_procedural_predicates", [])) if queue_row else [],
                "policy_outcomes": list(queue_row.get("policy_outcomes", [])) if queue_row else [],
                "latest_review_status": queue_row.get("latest_review_status") if queue_row else None,
                "latest_review_note": queue_row.get("latest_review_note") if queue_row else None,
                "status_explanation": dict(review_queue_row.get("status_explanation", {})) if review_queue_row else None,
                "inspector_classification": _inspector_classification_for_fact_row(queue_row or {}),
            }
        )
    default_fact_id = summary["review_queue"][0]["fact_id"] if summary["review_queue"] else (report["facts"][0]["fact_id"] if report["facts"] else None)
    workbench = {
        "version": FACT_REVIEW_WORKBENCH_VERSION,
        "zelph_ruleset_version": FACT_REVIEW_ZELPH_RULESET_VERSION,
        "run": report["run"],
        "summary": summary["summary"],
        "review_queue": summary["review_queue"],
        "contested_summary": summary["contested_summary"],
        "chronology_summary": summary["chronology_summary"],
        "chronology": summary["chronology"],
        "chronology_groups": summary["chronology_groups"],
        "operator_views": operator_views,
        "reopen_navigation": _build_reopen_navigation(report["run"], recent_sources),
        "issue_filters": _build_issue_filters(summary, operator_views),
        "sources": report["sources"],
        "excerpts": report["excerpts"],
        "statements": report["statements"],
        "observations": report["observations"],
        "events": report["events"],
        "facts": facts,
        "rule_atoms": report.get("rule_atoms", []),
        "semantic_context": report.get("semantic_context", {}),
        "workflow_summary": _build_fact_review_workflow_summary(
            report=report,
            summary=summary,
            operator_views=operator_views,
            default_fact_id=default_fact_id,
        ),
        "inspector_classification": {
            "status_order": ["party_assertion", "procedural_outcome", "later_annotation"],
            "selected_fact_id": default_fact_id,
            "facts": {row["fact_id"]: row["inspector_classification"] for row in facts},
        },
        "inspector_defaults": {
            "selected_fact_id": default_fact_id,
            "default_view": "intake_triage",
        },
    }
    if not include_zelph:
        return workbench
    return enrich_workbench_with_zelph(workbench, rules=_fact_review_zelph_rules())
