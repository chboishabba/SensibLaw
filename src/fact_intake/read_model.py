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

OBSERVATION_PREDICATE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("actor_identification", ("actor", "co_actor", "actor_role", "actor_attribute", "organization")),
    ("actions_events", ("performed_action", "failed_to_act", "caused_event", "received_action", "communicated")),
    ("object_target", ("acted_on", "affected_object", "subject_matter", "document_reference")),
    ("temporal", ("event_time", "event_date", "temporal_relation", "duration", "sequence_marker")),
    ("harm_consequence", ("harm_type", "injury", "loss", "damage_amount", "causal_link")),
    ("legal_procedural", ("alleged", "denied", "admitted", "claimed", "ruled", "ordered")),
)

OBSERVATION_PREDICATE_TO_FAMILY: dict[str, str] = {
    predicate: family
    for family, predicates in OBSERVATION_PREDICATE_FAMILIES
    for predicate in predicates
}


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


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM fact_intake_runs WHERE run_id = ?", (run_id,))


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
                str(row.get("statement_status") or "captured"),
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
                str(row.get("observation_status") or "captured").strip(),
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
                str(row.get("candidate_status") or "captured"),
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
    }


def _json_or_empty(text: str | None) -> Any:
    if not text:
        return {}
    return json.loads(text)


def build_fact_intake_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_database(conn)
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
    facts: list[dict[str, Any]] = []
    for row in fact_rows:
        fact_id = str(row["fact_id"])
        refs = links_by_fact.get(fact_id, {"statement_ids": [], "excerpt_ids": [], "source_ids": [], "statement_texts": []})
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
                "statement_texts": refs["statement_texts"],
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
        },
        "summary": {
            "fact_count": len(facts),
            "contested_fact_count": sum(1 for fact in facts if fact["contestations"]),
            "reviewed_fact_count": sum(1 for fact in facts if fact["reviews"]),
        },
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
            "provenance": {
                "source_ids": fact["source_ids"],
                "excerpt_ids": fact["excerpt_ids"],
                "statement_ids": fact["statement_ids"],
            },
        }
        for fact in report["facts"]
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
        "chronology": chronology,
        "review_queue": review_queue,
    }
