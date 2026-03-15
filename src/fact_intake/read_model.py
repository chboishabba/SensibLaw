from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.reporting.structure_report import TextUnit
from src.sensiblaw.db.dao import ensure_database

FACT_INTAKE_CONTRACT_VERSION = "fact.intake.bundle.v1"
MARY_FACT_WORKFLOW_VERSION = "mary.fact_workflow.v1"
EVENT_ASSEMBLER_VERSION = "fact_event_assembler_v1"
FACT_WORKFLOW_LINK_VERSION = "fact_workflow_link_v1"

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
_ASSERTION_PREDICATES = {"claimed", "denied", "admitted", "alleged"}
_PROCEDURAL_OUTCOME_PREDICATES = {"ordered", "ruled", "decided_by", "held_that"}
_PROCEDURAL_CONTEXT_PREDICATES = {"appealed", "challenged", "heard_by", "applied", "followed", "distinguished"}


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
        provenance = source.get("provenance")
        if not isinstance(provenance, Mapping):
            continue
        raw = provenance.get("source_signal_classes")
        if isinstance(raw, list):
            out.extend(str(value) for value in raw if str(value).strip())
            continue
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


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM fact_intake_runs WHERE run_id = ?", (run_id,))


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
    }
    if required <= existing:
        return
    migrations_dir = Path(__file__).resolve().parents[2] / "database" / "migrations"
    for filename in _FACT_INTAKE_MIGRATION_FILES:
        conn.executescript((migrations_dir / filename).read_text(encoding="utf-8"))
    conn.commit()


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


def persist_fact_intake_payload(conn: sqlite3.Connection, payload: Mapping[str, Any]) -> dict[str, Any]:
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
    source_count = 0
    for row in payload.get("sources") if isinstance(payload.get("sources"), list) else []:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
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
        )
        source_count += 1
    excerpt_count = 0
    for row in payload.get("excerpts") if isinstance(payload.get("excerpts"), list) else []:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
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
        )
        excerpt_count += 1
    statement_count = 0
    for row in payload.get("statements") if isinstance(payload.get("statements"), list) else []:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
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
        )
        statement_count += 1
    observation_count = 0
    for row in payload.get("observations") if isinstance(payload.get("observations"), list) else []:
        if not isinstance(row, Mapping):
            continue
        predicate_key = _normalize_observation_predicate_key(row.get("predicate_key"))
        predicate_family = str(row.get("predicate_family") or "").strip() or OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]
        if predicate_family != OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]:
            raise ValueError(
                f"predicate_family mismatch for {predicate_key}: expected {OBSERVATION_PREDICATE_TO_FAMILY[predicate_key]}, got {predicate_family}"
            )
        conn.execute(
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
                predicate_family,
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
        observation_count += 1
    fact_count = 0
    for row in payload.get("fact_candidates") if isinstance(payload.get("fact_candidates"), list) else []:
        if not isinstance(row, Mapping):
            continue
        fact_id = str(row.get("fact_id") or "").strip()
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
        )
        for statement_id in row.get("statement_ids") if isinstance(row.get("statement_ids"), list) else []:
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
        fact_count += 1
    contestation_count = 0
    for row in payload.get("contestations") if isinstance(payload.get("contestations"), list) else []:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
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
        )
        contestation_count += 1
    review_count = 0
    for row in payload.get("reviews") if isinstance(payload.get("reviews"), list) else []:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
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
        )
        review_count += 1
    event_summary = _assemble_event_candidates(conn, run_id=run_id)
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
    }


def _json_or_empty(text: str | None) -> Any:
    if not text:
        return {}
    return json.loads(text)


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
    }


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


def build_fact_review_run_summary(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
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
            "statement_roles": statement_roles,
            "primary_contested_reason_text": primary_contested_reason_text,
            "latest_review_status": latest_review.get("review_status") if latest_review else None,
            "latest_review_note": _latest_review_note(latest_review),
            "chronology_impacted": chronology_impacted,
            "source_ids": list(fact["source_ids"]),
            "statement_ids": list(fact["statement_ids"]),
        }
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


def build_fact_review_operator_views(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    summary = build_fact_review_run_summary(conn, run_id=run_id)
    review_queue = list(summary["review_queue"])
    chronology_groups = dict(summary["chronology_groups"])
    contested_summary = dict(summary["contested_summary"])
    return {
        "intake_triage": {
            "title": "Intake triage",
            "summary": {
                "review_queue_count": summary["summary"]["review_queue_count"],
                "needs_followup_count": summary["summary"]["needs_followup_count"],
                "missing_date_review_queue_count": summary["summary"]["missing_date_review_queue_count"],
                "missing_actor_review_queue_count": summary["summary"]["missing_actor_review_queue_count"],
                "statement_only_review_queue_count": summary["summary"]["statement_only_review_queue_count"],
            },
            "groups": {
                "missing_date": [row for row in review_queue if "missing_date" in row["reason_codes"]],
                "missing_actor": [row for row in review_queue if "missing_actor" in row["reason_codes"]],
                "chronology_conflict": [row for row in review_queue if "contradictory_chronology" in row["reason_codes"]],
                "procedural_significance": [row for row in review_queue if "procedural_significance" in row["reason_codes"]],
            },
            "items": review_queue,
        },
        "chronology_prep": {
            "title": "Chronology prep",
            "summary": dict(summary["chronology_summary"]),
            "groups": chronology_groups,
        },
        "procedural_posture": {
            "title": "Procedural posture",
            "summary": {
                "legal_procedural_review_queue_count": summary["summary"]["legal_procedural_review_queue_count"],
                "contested_item_count": summary["summary"]["contested_item_count"],
            },
            "items": [row for row in review_queue if row["has_legal_procedural_observations"]],
        },
        "contested_items": {
            "title": "Contested items",
            "summary": {
                "count": contested_summary["count"],
                "needs_followup_count": contested_summary["needs_followup_count"],
                "chronology_impacted_count": contested_summary["chronology_impacted_count"],
            },
            "items": list(contested_summary["items"]),
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


def build_fact_review_workbench_payload(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    report = build_fact_intake_report(conn, run_id=run_id)
    summary = build_fact_review_run_summary(conn, run_id=run_id)
    operator_views = build_fact_review_operator_views(conn, run_id=run_id)
    summary_by_fact_id = {row["fact_id"]: row for row in summary["facts"]}
    facts = []
    for fact in report["facts"]:
        queue_row = summary_by_fact_id.get(fact["fact_id"])
        facts.append(
            {
                **fact,
                "signal_classes": list(queue_row.get("signal_classes", [])) if queue_row else [],
                "source_signal_classes": list(queue_row.get("source_signal_classes", [])) if queue_row else [],
                "source_types": list(queue_row.get("source_types", [])) if queue_row else [],
                "statement_roles": list(queue_row.get("statement_roles", [])) if queue_row else [],
                "legal_procedural_predicates": list(queue_row.get("legal_procedural_predicates", [])) if queue_row else [],
                "latest_review_status": queue_row.get("latest_review_status") if queue_row else None,
                "latest_review_note": queue_row.get("latest_review_note") if queue_row else None,
            }
        )
    default_fact_id = summary["review_queue"][0]["fact_id"] if summary["review_queue"] else (report["facts"][0]["fact_id"] if report["facts"] else None)
    return {
        "version": FACT_REVIEW_WORKBENCH_VERSION,
        "run": report["run"],
        "summary": summary["summary"],
        "review_queue": summary["review_queue"],
        "contested_summary": summary["contested_summary"],
        "chronology_summary": summary["chronology_summary"],
        "chronology": summary["chronology"],
        "chronology_groups": summary["chronology_groups"],
        "operator_views": operator_views,
        "sources": report["sources"],
        "excerpts": report["excerpts"],
        "statements": report["statements"],
        "observations": report["observations"],
        "events": report["events"],
        "facts": facts,
        "inspector_defaults": {
            "selected_fact_id": default_fact_id,
            "default_view": "intake_triage",
        },
    }
