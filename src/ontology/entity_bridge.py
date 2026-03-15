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
    external_url: str | None
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


_BRIDGE_SCAN_PUNCTUATION = str.maketrans({
    ".": " ",
    ",": " ",
    ";": " ",
    ":": " ",
    "(": " ",
    ")": " ",
    "[": " ",
    "]": " ",
    "{": " ",
    "}": " ",
    "!": " ",
    "?": " ",
    "\"": " ",
    "'": " ",
})


def _normalize_bridge_scan_text(text: str) -> str:
    return " ".join(text.casefold().translate(_BRIDGE_SCAN_PUNCTUATION).split())


def _stable_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _default_external_url(provider: str, external_id: str) -> str | None:
    provider_norm = provider.strip().casefold()
    external_norm = external_id.strip()
    if not provider_norm or not external_norm:
        return None
    if provider_norm == "wikidata":
        if external_norm.startswith("http://") or external_norm.startswith("https://"):
            return external_norm
        return f"https://www.wikidata.org/wiki/{external_norm}"
    if provider_norm == "dbpedia":
        if external_norm.startswith("http://") or external_norm.startswith("https://"):
            return external_norm
        return f"http://dbpedia.org/resource/{external_norm}"
    return None


def _bridge_lookup_candidates(norm_text: str, kind: str) -> list[tuple[str, str]]:
    candidates = [(norm_text, kind)]
    if kind == "act_ref" and norm_text.startswith("act:"):
        candidates.append((f"legislation:{norm_text.split(':', 1)[1]}", "legislation_ref"))
    return candidates


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
        external_url = str(entity.get("external_url") or _default_external_url(provider, external_id) or "").strip() or None
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
        SELECT provider, canonical_kind, canonical_ref, external_id, COALESCE(external_url, '') AS external_url
        FROM wikidata_bridge_entities
        WHERE slice_id = ?
        """,
        (slice_id,),
    ).fetchall()
    alias_rows = conn.execute(
        """
        SELECT a.alias_text, a.normalized_alias, e.canonical_ref
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
    entities_by_provider = {
        provider: sum(1 for row in entity_rows if str(row["provider"]) == provider)
        for provider in sorted({str(row["provider"]) for row in entity_rows})
    }
    missing_external_url_count = sum(1 for row in entity_rows if not str(row["external_url"] or "").strip())
    alias_counts: dict[str, set[str]] = {}
    for row in alias_rows:
        normalized_alias = str(row["normalized_alias"] or "").strip()
        canonical_ref = str(row["canonical_ref"] or "").strip()
        if not normalized_alias or not canonical_ref:
            continue
        alias_counts.setdefault(normalized_alias, set()).add(canonical_ref)
    duplicate_alias_count = sum(1 for refs in alias_counts.values() if len(refs) > 1)
    duplicate_external_id_reuse: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT provider, external_id, COUNT(DISTINCT canonical_ref) AS canonical_ref_count
        FROM wikidata_bridge_entities
        WHERE slice_id = ?
        GROUP BY provider, external_id
        HAVING COUNT(DISTINCT canonical_ref) > 1
        ORDER BY provider, external_id
        """,
        (slice_id,),
    ).fetchall():
        provider = str(row["provider"])
        external_id = str(row["external_id"])
        canonical_refs = [
            str(item["canonical_ref"])
            for item in conn.execute(
                """
                SELECT canonical_ref
                FROM wikidata_bridge_entities
                WHERE slice_id = ? AND provider = ? AND external_id = ?
                ORDER BY canonical_ref
                """,
                (slice_id, provider, external_id),
            ).fetchall()
        ]
        duplicate_external_id_reuse.append(
            {
                "provider": provider,
                "external_id": external_id,
                "canonical_ref_count": int(row["canonical_ref_count"]),
                "canonical_refs": canonical_refs,
            }
        )
    return {
        "slice_name": str(slice_row["slice_name"]),
        "policy_version": str(slice_row["policy_version"]),
        "entity_count": len(entity_rows),
        "alias_count": len(alias_rows),
        "entities_by_provider": entities_by_provider,
        "entities_by_kind": {
            kind: sum(1 for row in entity_rows if row["canonical_kind"] == kind)
            for kind in sorted({str(row["canonical_kind"]) for row in entity_rows})
        },
        "missing_external_url_count": missing_external_url_count,
        "duplicate_alias_count": duplicate_alias_count,
        "duplicate_external_id_reuse": duplicate_external_id_reuse,
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
        row = None
        for candidate_ref, candidate_kind in _bridge_lookup_candidates(norm_text, kind):
            row = resolved_conn.execute(
                """
                SELECT s.slice_id, s.slice_name, s.policy_version, e.provider, e.external_id, e.external_url, e.canonical_ref, e.canonical_kind
                FROM wikidata_bridge_entities AS e
                JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
                WHERE s.slice_name = ? AND e.canonical_ref = ? AND e.canonical_kind = ?
                ORDER BY e.provider, e.external_id
                LIMIT 1
                """,
                (active_slice, candidate_ref, candidate_kind),
            ).fetchone()
            if row is not None:
                break
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
            canonical_ref=str(row["canonical_ref"]),
            canonical_kind=str(row["canonical_kind"]),
            provider=str(row["provider"]),
            external_id=str(row["external_id"]),
            external_url=str(row["external_url"] or "").strip() or None,
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


def _lookup_canonical_ref_rows(
    conn: sqlite3.Connection,
    *,
    active_slice: str,
    canonical_ref: str,
    canonical_kind: str,
) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    seen: set[tuple[str, str]] = set()
    for candidate_ref, candidate_kind in _bridge_lookup_candidates(canonical_ref, canonical_kind):
        for row in conn.execute(
            """
            SELECT s.slice_id, s.slice_name, s.policy_version, e.provider, e.external_id, e.external_url, e.canonical_ref, e.canonical_kind
            FROM wikidata_bridge_entities AS e
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND e.canonical_ref = ? AND e.canonical_kind = ?
            ORDER BY e.provider, e.external_id
            """,
            (active_slice, candidate_ref, candidate_kind),
        ).fetchall():
            key = (str(row["provider"]), str(row["external_id"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


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
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        seen_occurrences: set[tuple[str, str]] = set()
        for occ in occurrences:
            occurrence_key = (occ.norm_text, occ.kind)
            if occurrence_key in seen_occurrences:
                continue
            seen_occurrences.add(occurrence_key)
            rows = _lookup_canonical_ref_rows(
                resolved_conn,
                active_slice=active_slice,
                canonical_ref=occ.norm_text,
                canonical_kind=occ.kind,
            )
            if not rows:
                if record_receipts:
                    slice_row = resolved_conn.execute(
                        "SELECT slice_id, policy_version FROM wikidata_bridge_slices WHERE slice_name = ?",
                        (active_slice,),
                    ).fetchone()
                    if slice_row is not None:
                        _record_match_receipt(
                            resolved_conn,
                            slice_id=int(slice_row["slice_id"]),
                            canonical_ref=occ.norm_text,
                            canonical_kind=occ.kind,
                            matched_alias=None,
                            provider=None,
                            external_id=None,
                            resolution_status="abstain",
                            policy_version=str(slice_row["policy_version"]),
                        )
                continue
            for row in rows:
                linked = ExternalEntityLink(
                    canonical_ref=str(row["canonical_ref"]),
                    canonical_kind=str(row["canonical_kind"]),
                    provider=str(row["provider"]),
                    external_id=str(row["external_id"]),
                    external_url=str(row["external_url"] or "").strip() or None,
                    curie=f"{row['provider']}:{row['external_id']}",
                    slice_name=str(row["slice_name"]),
                    policy_version=str(row["policy_version"]),
                )
                key = (linked.canonical_ref, linked.provider, linked.external_id)
                if key in seen:
                    continue
                seen.add(key)
                out.append(linked)
                if record_receipts:
                    _record_match_receipt(
                        resolved_conn,
                        slice_id=int(row["slice_id"]),
                        canonical_ref=linked.canonical_ref,
                        canonical_kind=linked.canonical_kind,
                        matched_alias=None,
                        provider=linked.provider,
                        external_id=linked.external_id,
                        resolution_status="resolved",
                        policy_version=linked.policy_version,
                    )
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
                external_url=None,
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


def _text_contains_normalized_alias(text: str, normalized_alias: str) -> bool:
    normalized_text = f" {_normalize_bridge_scan_text(text)} "
    alias_text = f" {_normalize_bridge_scan_text(normalized_alias)} "
    return bool(normalized_alias) and alias_text in normalized_text


def _bridge_refs_present(
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> set[str]:
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        canonical_refs = sorted({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()})
        if not canonical_refs:
            return set()
        placeholders = ",".join("?" for _ in canonical_refs)
        rows = resolved_conn.execute(
            f"""
            SELECT DISTINCT canonical_ref
            FROM wikidata_bridge_entities AS e
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND canonical_ref IN ({placeholders})
            """,
            (active_slice, *canonical_refs),
        ).fetchall()
        return {str(row["canonical_ref"]) for row in rows}
    finally:
        if should_close:
            resolved_conn.close()


def _bridge_ref_kinds(
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> dict[str, str]:
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        canonical_refs = sorted({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()})
        if not canonical_refs:
            return {}
        placeholders = ",".join("?" for _ in canonical_refs)
        rows = resolved_conn.execute(
            f"""
            SELECT canonical_ref, canonical_kind
            FROM wikidata_bridge_entities AS e
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND canonical_ref IN ({placeholders})
            ORDER BY canonical_ref, canonical_kind
            """,
            (active_slice, *canonical_refs),
        ).fetchall()
        out: dict[str, str] = {}
        for row in rows:
            canonical_ref = str(row["canonical_ref"])
            out.setdefault(canonical_ref, str(row["canonical_kind"]))
        return out
    finally:
        if should_close:
            resolved_conn.close()


def _anchor_targets(anchor: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "actor_id" in anchor:
        out["actor_id"] = int(anchor["actor_id"])
    if "concept_code" in anchor:
        out["concept_code"] = str(anchor["concept_code"])
    return out


def link_text_via_bridge_aliases(
    text: str,
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> list[ExternalEntityLink]:
    resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
    try:
        ensure_bridge_schema(resolved_conn)
        ensure_seeded_bridge_slice(resolved_conn)
        active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
        canonical_refs = sorted({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()})
        if not canonical_refs:
            return []
        placeholders = ",".join("?" for _ in canonical_refs)
        rows = resolved_conn.execute(
            f"""
            SELECT s.slice_name, s.policy_version, e.canonical_ref, e.canonical_kind,
                   e.provider, e.external_id, e.external_url, a.alias_text, a.normalized_alias
            FROM wikidata_bridge_aliases AS a
            JOIN wikidata_bridge_entities AS e ON e.bridge_entity_id = a.bridge_entity_id
            JOIN wikidata_bridge_slices AS s ON s.slice_id = e.slice_id
            WHERE s.slice_name = ? AND e.canonical_ref IN ({placeholders})
            ORDER BY LENGTH(a.normalized_alias) DESC, e.canonical_ref, e.provider, e.external_id
            """,
            (active_slice, *canonical_refs),
        ).fetchall()
        seen: set[tuple[str, str, str]] = set()
        out: list[ExternalEntityLink] = []
        for row in rows:
            normalized_alias = str(row["normalized_alias"] or "").strip()
            if not _text_contains_normalized_alias(text, normalized_alias):
                continue
            key = (str(row["canonical_ref"]), str(row["provider"]), str(row["external_id"]))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                ExternalEntityLink(
                    canonical_ref=str(row["canonical_ref"]),
                    canonical_kind=str(row["canonical_kind"]),
                    provider=str(row["provider"]),
                    external_id=str(row["external_id"]),
                    external_url=str(row["external_url"] or "").strip() or None,
                    curie=f"{row['provider']}:{row['external_id']}",
                    slice_name=str(row["slice_name"]),
                    policy_version=str(row["policy_version"]),
                    matched_alias=str(row["alias_text"] or "").strip() or None,
                )
            )
        return out
    finally:
        if should_close:
            resolved_conn.close()


def build_text_alias_match_receipts(
    text: str,
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> list[dict[str, Any]]:
    links = link_text_via_bridge_aliases(
        text,
        anchor_map,
        conn=conn,
        db_path=db_path,
        slice_name=slice_name,
    )
    bridge_backed_refs = _bridge_refs_present(anchor_map, conn=conn, db_path=db_path, slice_name=slice_name)
    bridge_ref_kinds = _bridge_ref_kinds(anchor_map, conn=conn, db_path=db_path, slice_name=slice_name)
    link_map: dict[str, list[ExternalEntityLink]] = {}
    for link in links:
        link_map.setdefault(link.canonical_ref, []).append(link)

    receipts: list[dict[str, Any]] = []
    for canonical_ref in sorted({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()}):
        anchor = anchor_map.get(canonical_ref) or {}
        anchor_targets = _anchor_targets(anchor)
        matched_links = sorted(
            link_map.get(canonical_ref, []),
            key=lambda item: (item.provider, item.external_id),
        )
        if matched_links:
            for link in matched_links:
                receipts.append(
                    {
                        "canonical_ref": link.canonical_ref,
                        "canonical_kind": link.canonical_kind,
                        "predicate": "reviewed_alias_match",
                        "resolution_status": "resolved",
                        "matched_alias": link.matched_alias,
                        "provider": link.provider,
                        "external_id": link.external_id,
                        "external_url": link.external_url or _default_external_url(link.provider, link.external_id),
                        "slice_name": link.slice_name,
                        "policy_version": link.policy_version,
                        "anchor_targets": anchor_targets,
                    }
                )
            continue
        resolution_status = "abstain_no_alias" if canonical_ref in bridge_backed_refs else "abstain_no_bridge"
        receipts.append(
            {
                "canonical_ref": canonical_ref,
                "canonical_kind": bridge_ref_kinds.get(canonical_ref, ""),
                "predicate": "reviewed_alias_match",
                "resolution_status": resolution_status,
                "matched_alias": None,
                "provider": None,
                "external_id": None,
                "external_url": None,
                "slice_name": slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME,
                "policy_version": DEFAULT_POLICY_VERSION,
                "anchor_targets": anchor_targets,
            }
        )
    return receipts


def build_external_refs_batch_from_text(
    text: str,
    anchor_map: Mapping[str, Mapping[str, Any]],
    *,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
    record_receipts: bool = False,
) -> dict[str, Any]:
    actor_external_refs: list[dict[str, Any]] = []
    concept_external_refs: list[dict[str, Any]] = []
    active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
    links = link_text_via_bridge_aliases(
        text,
        anchor_map,
        conn=conn,
        db_path=db_path,
        slice_name=active_slice,
    )
    match_receipts = build_text_alias_match_receipts(
        text,
        anchor_map,
        conn=conn,
        db_path=db_path,
        slice_name=active_slice,
    )
    resolved_bridge_refs = {link.canonical_ref for link in links}
    bridge_backed_refs = _bridge_refs_present(anchor_map, conn=conn, db_path=db_path, slice_name=active_slice)
    skipped_no_anchor = 0
    for linked in links:
        anchor = anchor_map.get(linked.canonical_ref)
        if not anchor:
            skipped_no_anchor += 1
            continue
        base = {
            "provider": linked.provider,
            "external_id": linked.external_id,
            "external_url": linked.external_url or _default_external_url(linked.provider, linked.external_id),
            "notes": (
                f"bridge canonical_ref={linked.canonical_ref} canonical_kind={linked.canonical_kind} "
                f"slice={linked.slice_name} policy={linked.policy_version}"
            ),
        }
        if "actor_id" in anchor:
            row = dict(base)
            row["actor_id"] = int(anchor["actor_id"])
            actor_external_refs.append(row)
        if "concept_code" in anchor:
            row = dict(base)
            row["concept_code"] = str(anchor["concept_code"])
            concept_external_refs.append(row)
    if record_receipts and match_receipts:
        resolved_conn, should_close = _resolve_connection(conn=conn, db_path=db_path)
        try:
            ensure_bridge_schema(resolved_conn)
            ensure_seeded_bridge_slice(resolved_conn)
            slice_row = resolved_conn.execute(
                "SELECT slice_id, policy_version FROM wikidata_bridge_slices WHERE slice_name = ?",
                (active_slice,),
            ).fetchone()
            if slice_row is not None:
                for receipt in match_receipts:
                    _record_match_receipt(
                        resolved_conn,
                        slice_id=int(slice_row["slice_id"]),
                        canonical_ref=str(receipt["canonical_ref"]),
                        canonical_kind=str(receipt["canonical_kind"]),
                        matched_alias=(str(receipt["matched_alias"]) if receipt["matched_alias"] else None),
                        provider=(str(receipt["provider"]) if receipt["provider"] else None),
                        external_id=(str(receipt["external_id"]) if receipt["external_id"] else None),
                        resolution_status=str(receipt["resolution_status"]),
                        policy_version=str(slice_row["policy_version"]),
                    )
                resolved_conn.commit()
        finally:
            if should_close:
                resolved_conn.close()
    return {
        "meta": {
            "source": "entity_bridge_alias_scan",
            "slice_name": (links[0].slice_name if links else active_slice),
            "bridge_refs": [link.canonical_ref for link in links],
            "match_receipts": match_receipts,
            "coverage": {
                "total_candidate_refs": len({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()}),
                "resolved_bridge_refs": len(resolved_bridge_refs),
                "skipped_no_bridge_match": len({str(ref).strip() for ref in anchor_map.keys() if str(ref).strip()}) - len(bridge_backed_refs),
                "skipped_no_anchor": skipped_no_anchor,
                "emitted_actor_rows": len(actor_external_refs),
                "emitted_concept_rows": len(concept_external_refs),
            },
        },
        "concept_external_refs": concept_external_refs,
        "actor_external_refs": actor_external_refs,
    }


def bridge_match_receipt_summary(
    conn: sqlite3.Connection,
    *,
    slice_name: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    ensure_bridge_schema(conn)
    ensure_seeded_bridge_slice(conn)
    active_slice = slice_name or os.getenv("ITIR_WIKIDATA_BRIDGE_SLICE") or SEEDED_SLICE_NAME
    slice_row = conn.execute(
        "SELECT slice_id, slice_name, policy_version FROM wikidata_bridge_slices WHERE slice_name = ?",
        (active_slice,),
    ).fetchone()
    if slice_row is None:
        raise ValueError(f"Unknown bridge slice: {active_slice}")
    rows = conn.execute(
        """
        SELECT canonical_ref, canonical_kind, matched_alias, provider, external_id, resolution_status, policy_version
        FROM wikidata_bridge_match_receipts
        WHERE slice_id = ?
        ORDER BY canonical_ref, canonical_kind, matched_alias, provider, external_id, resolution_status
        LIMIT ?
        """,
        (int(slice_row["slice_id"]), int(limit)),
    ).fetchall()
    status_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    canonical_ref_counts: dict[str, int] = {}
    for row in rows:
        resolution_status = str(row["resolution_status"])
        status_counts[resolution_status] = status_counts.get(resolution_status, 0) + 1
        provider = str(row["provider"] or "").strip()
        if provider:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        canonical_ref = str(row["canonical_ref"])
        canonical_ref_counts[canonical_ref] = canonical_ref_counts.get(canonical_ref, 0) + 1
    return {
        "slice_name": str(slice_row["slice_name"]),
        "policy_version": str(slice_row["policy_version"]),
        "receipt_count": len(rows),
        "counts_by_status": status_counts,
        "counts_by_provider": provider_counts,
        "counts_by_canonical_ref": canonical_ref_counts,
        "receipts": [
            {
                "canonical_ref": str(row["canonical_ref"]),
                "canonical_kind": str(row["canonical_kind"]),
                "matched_alias": str(row["matched_alias"] or "").strip() or None,
                "provider": provider or None,
                "external_id": str(row["external_id"] or "").strip() or None,
                "resolution_status": str(row["resolution_status"]),
                "policy_version": str(row["policy_version"]),
            }
            for row in rows
            for provider in [str(row["provider"] or "").strip()]
        ],
    }


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
    occurrence_list = list(occurrences)
    unique_occurrences = {
        (occ.norm_text, occ.kind)
        for occ in occurrence_list
        if occ.kind.endswith("_ref")
    }
    links = link_lexeme_occurrences(
        [occ for occ in occurrence_list if occ.kind.endswith("_ref")],
        conn=conn,
        db_path=db_path,
        slice_name=slice_name,
        record_receipts=record_receipts,
    )
    resolved_bridge_refs = {link.canonical_ref for link in links}
    resolved_occurrence_keys = {
        (norm_text, kind)
        for norm_text, kind in unique_occurrences
        if any(candidate_ref in resolved_bridge_refs for candidate_ref, _ in _bridge_lookup_candidates(norm_text, kind))
    }
    skipped_no_anchor = 0
    for linked in links:
        anchor = anchor_map.get(linked.canonical_ref)
        if not anchor:
            skipped_no_anchor += 1
            continue
        base = {
            "provider": linked.provider,
            "external_id": linked.external_id,
            "external_url": linked.external_url or _default_external_url(linked.provider, linked.external_id),
            "notes": (
                f"bridge canonical_ref={linked.canonical_ref} canonical_kind={linked.canonical_kind} "
                f"slice={linked.slice_name} policy={linked.policy_version}"
            ),
        }
        if "actor_id" in anchor:
            row = dict(base)
            row["actor_id"] = int(anchor["actor_id"])
            actor_external_refs.append(row)
        if "concept_code" in anchor:
            row = dict(base)
            row["concept_code"] = str(anchor["concept_code"])
            concept_external_refs.append(row)
    unmatched_bridge_count = len(unique_occurrences) - len(resolved_occurrence_keys)
    return {
        "meta": {
            "source": "entity_bridge",
            "slice_name": (links[0].slice_name if links else (slice_name or SEEDED_SLICE_NAME)),
            "bridge_refs": [link.canonical_ref for link in links],
            "coverage": {
                "total_unique_occurrences": len(unique_occurrences),
                "resolved_bridge_refs": len(resolved_bridge_refs),
                "skipped_no_bridge_match": unmatched_bridge_count,
                "skipped_no_anchor": skipped_no_anchor,
                "emitted_actor_rows": len(actor_external_refs),
                "emitted_concept_rows": len(concept_external_refs),
            },
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
    "build_external_refs_batch_from_text",
    "ensure_bridge_schema",
    "ensure_seeded_bridge_slice",
    "import_bridge_payload",
    "link_canonical_ref",
    "link_lexeme_occurrences",
    "link_text_via_bridge_aliases",
    "lookup_bridge_alias",
]
