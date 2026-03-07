from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping, Any

from src.text.lexeme_index import LexemeOccurrence


SEEDED_SLICE_NAME = "seeded_body_refs_v1"
DEFAULT_POLICY_VERSION = "entity_bridge_v1"

_SEEDED_BRIDGE_PAYLOAD = {
    "slice": {
        "name": SEEDED_SLICE_NAME,
        "source_version": "seeded_local_v1",
        "policy_version": DEFAULT_POLICY_VERSION,
        "notes": "Deterministic reviewed body/court bridge seeds for canonical runs.",
    },
    "entities": [
        {
            "canonical_ref": "institution:united_nations",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q1065",
            "canonical_label": "United Nations",
            "aliases": ["UN", "U.N.", "UNO", "United Nations", "United Nations Organization"],
        },
        {
            "canonical_ref": "institution:united_nations_security_council",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q37470",
            "canonical_label": "United Nations Security Council",
            "aliases": [
                "UN Security Council",
                "U.N. Security Council",
                "UNSC",
                "Security Council",
                "United Nations Security Council",
            ],
        },
        {
            "canonical_ref": "court:international_criminal_court",
            "canonical_kind": "court_ref",
            "provider": "wikidata",
            "external_id": "Q47488",
            "canonical_label": "International Criminal Court",
            "aliases": ["ICC", "ICCt", "International Criminal Court"],
        },
        {
            "canonical_ref": "court:international_court_of_justice",
            "canonical_kind": "court_ref",
            "provider": "wikidata",
            "external_id": "Q7801",
            "canonical_label": "International Court of Justice",
            "aliases": ["ICJ", "World Court", "International Court of Justice"],
        },
        {
            "canonical_ref": "court:u_s_supreme_court",
            "canonical_kind": "court_ref",
            "provider": "wikidata",
            "external_id": "Q11201",
            "canonical_label": "Supreme Court of the United States",
            "aliases": ["U.S. Supreme Court", "United States Supreme Court", "US Supreme Court", "SCOTUS"],
        },
        {
            "canonical_ref": "court:united_states_district_court",
            "canonical_kind": "court_ref",
            "provider": "wikidata",
            "external_id": "Q1614849",
            "canonical_label": "United States district court",
            "aliases": [
                "U.S. district court",
                "US district court",
                "United States district court",
                "federal district court",
                "U.S. federal district court",
                "U.S. district courts",
                "US district courts",
                "United States district courts",
                "federal district courts",
                "federal trial court",
            ],
        },
        {
            "canonical_ref": "court:united_states_court_of_appeals_for_the_sixth_circuit",
            "canonical_kind": "court_ref",
            "provider": "wikidata",
            "external_id": "Q250472",
            "canonical_label": "United States Court of Appeals for the Sixth Circuit",
            "aliases": [
                "United States Court of Appeals for the Sixth Circuit",
                "U.S. Court of Appeals for the Sixth Circuit",
                "US Court of Appeals for the Sixth Circuit",
                "Sixth Circuit",
                "6th Circuit",
            ],
        },
        {
            "canonical_ref": "institution:united_states_department_of_defense",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q11209",
            "canonical_label": "United States Department of Defense",
            "aliases": [
                "United States Department of Defense",
                "U.S. Department of Defense",
                "US Department of Defense",
                "Department of Defense",
                "Defense Department",
                "DoD",
            ],
        },
        {
            "canonical_ref": "institution:u_s_senate",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q66096",
            "canonical_label": "United States Senate",
            "aliases": ["U.S. Senate", "US Senate", "United States Senate", "Senate of the United States"],
        },
        {
            "canonical_ref": "institution:u_s_house_of_representatives",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q11701",
            "canonical_label": "United States House of Representatives",
            "aliases": [
                "House of Representatives",
                "U.S. House of Representatives",
                "US House of Representatives",
                "United States House of Representatives",
            ],
        },
        {
            "canonical_ref": "institution:central_intelligence_agency",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q37230",
            "canonical_label": "Central Intelligence Agency",
            "aliases": ["CIA", "Central Intelligence Agency"],
        },
        {
            "canonical_ref": "institution:federal_bureau_of_investigation",
            "canonical_kind": "institution_ref",
            "provider": "wikidata",
            "external_id": "Q8333",
            "canonical_label": "Federal Bureau of Investigation",
            "aliases": ["FBI", "F.B.I.", "Federal Bureau of Investigation"],
        },
    ],
}


@dataclass(frozen=True, slots=True)
class ExternalEntityLink:
    canonical_ref: str
    canonical_kind: str
    provider: str
    external_id: str
    curie: str
    slice_name: str
    policy_version: str
    matched_alias: str | None = None
    resolution_status: str = "resolved"


def _default_db_path() -> Path:
    raw = (os.getenv("ITIR_DB_PATH") or ".cache_local/itir.sqlite").strip()
    return Path(raw).expanduser()


def _normalize_alias(text: str) -> str:
    return " ".join(text.casefold().split())


def _stable_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def ensure_bridge_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wikidata_bridge_slices (
          slice_id INTEGER PRIMARY KEY,
          slice_name TEXT NOT NULL UNIQUE,
          source_version TEXT,
          source_sha256 TEXT,
          policy_version TEXT NOT NULL,
          notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wikidata_bridge_entities (
          bridge_entity_id INTEGER PRIMARY KEY,
          slice_id INTEGER NOT NULL REFERENCES wikidata_bridge_slices(slice_id) ON DELETE CASCADE,
          canonical_ref TEXT NOT NULL,
          canonical_kind TEXT NOT NULL,
          canonical_label TEXT,
          provider TEXT NOT NULL,
          external_id TEXT NOT NULL,
          external_url TEXT,
          ambiguity_policy TEXT NOT NULL DEFAULT 'exact_only',
          UNIQUE (slice_id, canonical_ref, canonical_kind, provider, external_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wikidata_bridge_aliases (
          alias_id INTEGER PRIMARY KEY,
          bridge_entity_id INTEGER NOT NULL REFERENCES wikidata_bridge_entities(bridge_entity_id) ON DELETE CASCADE,
          alias_text TEXT NOT NULL,
          normalized_alias TEXT NOT NULL,
          alias_kind TEXT,
          alias_order INTEGER NOT NULL DEFAULT 0,
          UNIQUE (bridge_entity_id, normalized_alias)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wikidata_bridge_match_receipts (
          receipt_id INTEGER PRIMARY KEY,
          slice_id INTEGER NOT NULL REFERENCES wikidata_bridge_slices(slice_id) ON DELETE CASCADE,
          canonical_ref TEXT NOT NULL,
          canonical_kind TEXT NOT NULL,
          matched_alias TEXT NOT NULL DEFAULT '',
          provider TEXT NOT NULL DEFAULT '',
          external_id TEXT NOT NULL DEFAULT '',
          resolution_status TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          UNIQUE (
            slice_id,
            canonical_ref,
            canonical_kind,
            matched_alias,
            provider,
            external_id,
            resolution_status,
            policy_version
          )
        )
        """
    )


def import_bridge_payload(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    replace_slice: bool = False,
) -> dict[str, Any]:
    ensure_bridge_schema(conn)
    slice_meta = payload.get("slice") if isinstance(payload.get("slice"), Mapping) else {}
    entities = payload.get("entities") if isinstance(payload.get("entities"), list) else []
    slice_name = str(slice_meta.get("name") or "").strip()
    if not slice_name:
        raise ValueError("bridge payload requires slice.name")
    source_version = str(slice_meta.get("source_version") or "").strip() or None
    policy_version = str(slice_meta.get("policy_version") or DEFAULT_POLICY_VERSION).strip()
    notes = str(slice_meta.get("notes") or "").strip() or None
    source_sha256 = _stable_sha256(payload)

    existing = conn.execute(
        "SELECT slice_id FROM wikidata_bridge_slices WHERE slice_name = ?",
        (slice_name,),
    ).fetchone()
    if existing and replace_slice:
        slice_id = int(existing["slice_id"])
        conn.execute("DELETE FROM wikidata_bridge_match_receipts WHERE slice_id = ?", (slice_id,))
        entity_ids = [
            int(row["bridge_entity_id"])
            for row in conn.execute(
                "SELECT bridge_entity_id FROM wikidata_bridge_entities WHERE slice_id = ?",
                (slice_id,),
            ).fetchall()
        ]
        for bridge_entity_id in entity_ids:
            conn.execute("DELETE FROM wikidata_bridge_aliases WHERE bridge_entity_id = ?", (bridge_entity_id,))
        conn.execute("DELETE FROM wikidata_bridge_entities WHERE slice_id = ?", (slice_id,))
        conn.execute(
            """
            UPDATE wikidata_bridge_slices
            SET source_version = ?, source_sha256 = ?, policy_version = ?, notes = ?
            WHERE slice_id = ?
            """,
            (source_version, source_sha256, policy_version, notes, slice_id),
        )
    elif existing:
        slice_id = int(existing["slice_id"])
    else:
        cur = conn.execute(
            """
            INSERT INTO wikidata_bridge_slices(slice_name, source_version, source_sha256, policy_version, notes)
            VALUES (?,?,?,?,?)
            """,
            (slice_name, source_version, source_sha256, policy_version, notes),
        )
        slice_id = int(cur.lastrowid)

    imported_entities = 0
    imported_aliases = 0
    for entity in entities:
        if not isinstance(entity, Mapping):
            continue
        canonical_ref = str(entity.get("canonical_ref") or "").strip()
        canonical_kind = str(entity.get("canonical_kind") or "").strip()
        provider = str(entity.get("provider") or "").strip()
        external_id = str(entity.get("external_id") or "").strip()
        if not canonical_ref or not canonical_kind or not provider or not external_id:
            continue
        label = str(entity.get("canonical_label") or "").strip() or None
        external_url = str(entity.get("external_url") or f"https://www.wikidata.org/wiki/{external_id}" if provider == "wikidata" else "").strip() or None
        ambiguity_policy = str(entity.get("ambiguity_policy") or "exact_only").strip()
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO wikidata_bridge_entities(
              bridge_entity_id, slice_id, canonical_ref, canonical_kind, canonical_label,
              provider, external_id, external_url, ambiguity_policy
            )
            VALUES (
              COALESCE(
                (SELECT bridge_entity_id FROM wikidata_bridge_entities
                 WHERE slice_id = ? AND canonical_ref = ? AND canonical_kind = ? AND provider = ? AND external_id = ?),
                NULL
              ),
              ?,?,?,?,?,?,?,?
            )
            """,
            (
                slice_id,
                canonical_ref,
                canonical_kind,
                provider,
                external_id,
                slice_id,
                canonical_ref,
                canonical_kind,
                label,
                provider,
                external_id,
                external_url,
                ambiguity_policy,
            ),
        )
        bridge_entity_id = int(
            conn.execute(
                """
                SELECT bridge_entity_id FROM wikidata_bridge_entities
                WHERE slice_id = ? AND canonical_ref = ? AND canonical_kind = ? AND provider = ? AND external_id = ?
                """,
                (slice_id, canonical_ref, canonical_kind, provider, external_id),
            ).fetchone()["bridge_entity_id"]
        )
        imported_entities += 1
        aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
        for alias_order, alias in enumerate(aliases):
            alias_text = str(alias).strip()
            if not alias_text:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO wikidata_bridge_aliases(
                  bridge_entity_id, alias_text, normalized_alias, alias_kind, alias_order
                ) VALUES (?,?,?,?,?)
                """,
                (bridge_entity_id, alias_text, _normalize_alias(alias_text), "surface", alias_order),
            )
            imported_aliases += 1
    return {
        "slice_name": slice_name,
        "slice_id": slice_id,
        "entity_count": imported_entities,
        "alias_count": imported_aliases,
        "policy_version": policy_version,
    }


def ensure_seeded_bridge_slice(conn: sqlite3.Connection) -> None:
    existing = conn.execute(
        "SELECT source_sha256 FROM wikidata_bridge_slices WHERE slice_name = ?",
        (SEEDED_SLICE_NAME,),
    ).fetchone()
    expected_sha = _stable_sha256(_SEEDED_BRIDGE_PAYLOAD)
    if existing is None:
        import_bridge_payload(conn, _SEEDED_BRIDGE_PAYLOAD, replace_slice=False)
        return
    current_sha = str(existing["source_sha256"] or "").strip()
    if current_sha != expected_sha:
        import_bridge_payload(conn, _SEEDED_BRIDGE_PAYLOAD, replace_slice=True)


def bridge_storage_summary(conn: sqlite3.Connection, *, slice_name: str | None = None) -> dict[str, Any]:
    ensure_bridge_schema(conn)
    ensure_seeded_bridge_slice(conn)
    selected_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
    slice_row = conn.execute(
        "SELECT slice_id, slice_name, policy_version FROM wikidata_bridge_slices WHERE slice_name = ?",
        (selected_slice,),
    ).fetchone()
    if slice_row is None:
        return {"slice_name": selected_slice, "missing": True}
    slice_id = int(slice_row["slice_id"])
    entity_rows = conn.execute(
        """
        SELECT canonical_kind, canonical_ref, external_id, COALESCE(external_url, '') AS external_url
        FROM wikidata_bridge_entities
        WHERE slice_id = ?
        """,
        (slice_id,),
    ).fetchall()
    alias_rows = conn.execute(
        """
        SELECT a.alias_text
        FROM wikidata_bridge_aliases AS a
        JOIN wikidata_bridge_entities AS e ON e.bridge_entity_id = a.bridge_entity_id
        WHERE e.slice_id = ?
        """,
        (slice_id,),
    ).fetchall()
    url_counts: dict[str, int] = {}
    notes_counts: dict[str, int] = {}
    if _table_exists(conn, "actor_external_refs") and _table_exists(conn, "concept_external_refs"):
        for row in conn.execute(
            """
            SELECT external_url, notes FROM actor_external_refs
            UNION ALL
            SELECT external_url, notes FROM concept_external_refs
            """
        ).fetchall():
            url = str(row["external_url"] or "").strip()
            notes = str(row["notes"] or "").strip()
            if url:
                url_counts[url] = url_counts.get(url, 0) + 1
            if notes:
                notes_counts[notes] = notes_counts.get(notes, 0) + 1
    duplicate_url_bytes = sum((count - 1) * len(url) for url, count in url_counts.items() if count > 1)
    duplicate_notes_bytes = sum((count - 1) * len(notes) for notes, count in notes_counts.items() if count > 1)
    return {
        "slice_name": str(slice_row["slice_name"]),
        "policy_version": str(slice_row["policy_version"]),
        "entity_count": len(entity_rows),
        "alias_count": len(alias_rows),
        "entities_by_kind": {
            kind: sum(1 for row in entity_rows if row["canonical_kind"] == kind)
            for kind in sorted({str(row["canonical_kind"]) for row in entity_rows})
        },
        "bridge_string_bytes": {
            "canonical_ref_bytes": sum(len(str(row["canonical_ref"])) for row in entity_rows),
            "alias_bytes": sum(len(str(row["alias_text"])) for row in alias_rows),
            "external_url_bytes": sum(len(str(row["external_url"])) for row in entity_rows),
        },
        "external_ref_duplicate_bytes_estimate": {
            "external_url": duplicate_url_bytes,
            "notes": duplicate_notes_bytes,
        },
    }


def _resolve_connection(
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
) -> tuple[sqlite3.Connection, bool]:
    if conn is not None:
        return conn, False
    resolved_path = Path(db_path) if db_path is not None else _default_db_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    opened = sqlite3.connect(str(resolved_path))
    opened.row_factory = sqlite3.Row
    return opened, True


def _record_match_receipt(
    conn: sqlite3.Connection,
    *,
    slice_id: int,
    canonical_ref: str,
    canonical_kind: str,
    matched_alias: str | None,
    provider: str | None,
    external_id: str | None,
    resolution_status: str,
    policy_version: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO wikidata_bridge_match_receipts(
          slice_id, canonical_ref, canonical_kind, matched_alias, provider, external_id, resolution_status, policy_version
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            slice_id,
            canonical_ref,
            canonical_kind,
            matched_alias or "",
            provider or "",
            external_id or "",
            resolution_status,
            policy_version,
        ),
    )


def link_canonical_ref(
    norm_text: str,
    kind: str,
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
    record_receipt: bool = False,
) -> ExternalEntityLink | None:
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        row = resolved_conn.execute(
            """
            SELECT s.slice_id, s.slice_name, s.policy_version, e.provider, e.external_id
            FROM wikidata_bridge_entities AS e
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND e.canonical_ref = ? AND e.canonical_kind = ?
            LIMIT 1
            """,
            (active_slice, norm_text, kind),
        ).fetchone()
        if row is None:
            if record_receipt:
                slice_row = resolved_conn.execute(
                    "SELECT slice_id, policy_version FROM wikidata_bridge_slices WHERE slice_name = ?",
                    (active_slice,),
                ).fetchone()
                if slice_row is not None:
                    _record_match_receipt(
                        resolved_conn,
                        slice_id=int(slice_row["slice_id"]),
                        canonical_ref=norm_text,
                        canonical_kind=kind,
                        matched_alias=None,
                        provider=None,
                        external_id=None,
                        resolution_status="abstain",
                        policy_version=str(slice_row["policy_version"]),
                    )
                    resolved_conn.commit()
            return None
        link = ExternalEntityLink(
            canonical_ref=norm_text,
            canonical_kind=kind,
            provider=str(row["provider"]),
            external_id=str(row["external_id"]),
            curie=f"{row['provider']}:{row['external_id']}",
            slice_name=str(row["slice_name"]),
            policy_version=str(row["policy_version"]),
        )
        if record_receipt:
            _record_match_receipt(
                resolved_conn,
                slice_id=int(row["slice_id"]),
                canonical_ref=norm_text,
                canonical_kind=kind,
                matched_alias=None,
                provider=link.provider,
                external_id=link.external_id,
                resolution_status="resolved",
                policy_version=link.policy_version,
            )
            resolved_conn.commit()
        return link
    finally:
        if should_close:
            resolved_conn.close()


def link_lexeme_occurrences(
    occurrences: Iterable[LexemeOccurrence],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
    record_receipts: bool = False,
) -> list[ExternalEntityLink]:
    out: list[ExternalEntityLink] = []
    seen: set[tuple[str, str, str]] = set()
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        for occ in occurrences:
            linked = link_canonical_ref(
                occ.norm_text,
                occ.kind,
                conn=resolved_conn,
                slice_name=slice_name,
                record_receipt=record_receipts,
            )
            if linked is None:
                continue
            key = (linked.canonical_ref, linked.provider, linked.external_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(linked)
        if record_receipts:
            resolved_conn.commit()
        return out
    finally:
        if should_close:
            resolved_conn.close()


def lookup_bridge_alias(
    alias_text: str,
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> list[ExternalEntityLink]:
    normalized = _normalize_alias(alias_text)
    if not normalized:
        return []
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        rows = resolved_conn.execute(
            """
            SELECT s.slice_name, s.policy_version, e.canonical_ref, e.canonical_kind, e.provider, e.external_id, a.alias_text
            FROM wikidata_bridge_aliases AS a
            JOIN wikidata_bridge_entities AS e ON e.bridge_entity_id = a.bridge_entity_id
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND a.normalized_alias = ?
            ORDER BY e.canonical_kind, e.canonical_ref, e.provider, e.external_id
            """,
            (active_slice, normalized),
        ).fetchall()
        return [
            ExternalEntityLink(
                canonical_ref=str(row["canonical_ref"]),
                canonical_kind=str(row["canonical_kind"]),
                provider=str(row["provider"]),
                external_id=str(row["external_id"]),
                curie=f"{row['provider']}:{row['external_id']}",
                slice_name=str(row["slice_name"]),
                policy_version=str(row["policy_version"]),
                matched_alias=str(row["alias_text"]),
            )
            for row in rows
        ]
    finally:
        if should_close:
            resolved_conn.close()


def build_external_refs_batch(
    occurrences: Iterable[LexemeOccurrence],
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
    record_receipts: bool = False,
) -> dict[str, Any]:
    actor_external_refs: list[dict[str, Any]] = []
    concept_external_refs: list[dict[str, Any]] = []
    links = link_lexeme_occurrences(
        occurrences,
        conn=conn,
        db_path=db_path,
        slice_name=slice_name,
        record_receipts=record_receipts,
    )
    for linked in links:
        anchor = anchor_map.get(linked.canonical_ref)
        if not anchor:
            continue
        base = {
            "provider": linked.provider,
            "external_id": linked.external_id,
            "external_url": f"https://www.wikidata.org/wiki/{linked.external_id}" if linked.provider == "wikidata" else None,
            "notes": (
                f"bridge canonical_ref={linked.canonical_ref} canonical_kind={linked.canonical_kind} "
                f"slice={linked.slice_name} policy={linked.policy_version}"
            ),
        }
        if "actor_id" in anchor:
            row = dict(base)
            row["actor_id"] = int(anchor["actor_id"])
            actor_external_refs.append(row)
        elif "concept_code" in anchor:
            row = dict(base)
            row["concept_code"] = str(anchor["concept_code"])
            concept_external_refs.append(row)
    return {
        "meta": {
            "source": "entity_bridge",
            "slice_name": (links[0].slice_name if links else (slice_name or SEEDED_SLICE_NAME)),
            "bridge_refs": [link.canonical_ref for link in links],
        },
        "concept_external_refs": concept_external_refs,
        "actor_external_refs": actor_external_refs,
    }


__all__ = [
    "DEFAULT_POLICY_VERSION",
    "ExternalEntityLink",
    "SEEDED_SLICE_NAME",
    "bridge_storage_summary",
    "build_external_refs_batch",
    "ensure_bridge_schema",
    "ensure_seeded_bridge_slice",
    "import_bridge_payload",
    "link_canonical_ref",
    "link_lexeme_occurrences",
    "lookup_bridge_alias",
]
