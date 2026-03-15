from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from src.gwb_us_law.linkage import _pick_best_run_for_timeline_suffix
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized

_BROAD_AU_PROVENANCE_CUES = {
    "appeal",
    "new south wales",
}

_BROAD_AU_REF_TAILS = {
    "high court of australia",
    "high court",
}

_AU_REF_NORMALIZATION: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    (
        "institution_ref",
        "institution:commonwealth_of_australia",
    ): (
        ("jurisdiction_ref", "jurisdiction:commonwealth_of_australia"),
        ("organization_ref", "organization:commonwealth_of_australia"),
    ),
    (
        "institution_ref",
        "institution:state_of_new_south_wales",
    ): (
        ("jurisdiction_ref", "jurisdiction:state_of_new_south_wales"),
    ),
}


def _resolve_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path).expanduser().resolve()
    raw = (
        os.environ.get("ITIR_DB_PATH")
        or os.environ.get("SL_WIKI_TIMELINE_DB")
        or os.environ.get("SL_WIKI_TIMELINE_AOO_DB")
        or ".cache_local/itir.sqlite"
    )
    return Path(raw).expanduser().resolve()


def _stable_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def ensure_au_semantic_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_imports (
          import_name TEXT PRIMARY KEY,
          source_sha256 TEXT NOT NULL,
          generated_at TEXT,
          notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_seeds (
          seed_id TEXT PRIMARY KEY,
          import_name TEXT NOT NULL REFERENCES au_semantic_linkage_imports(import_name) ON DELETE CASCADE,
          action_summary TEXT NOT NULL,
          linkage_kind TEXT NOT NULL,
          notes TEXT,
          review_status TEXT,
          lane_tags_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_seed_authorities (
          seed_id TEXT NOT NULL REFERENCES au_semantic_linkage_seeds(seed_id) ON DELETE CASCADE,
          authority_order INTEGER NOT NULL,
          authority_title TEXT NOT NULL,
          PRIMARY KEY (seed_id, authority_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_seed_refs (
          seed_id TEXT NOT NULL REFERENCES au_semantic_linkage_seeds(seed_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_kind TEXT NOT NULL,
          canonical_ref TEXT NOT NULL,
          PRIMARY KEY (seed_id, ref_kind, ref_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_seed_cues (
          seed_id TEXT NOT NULL REFERENCES au_semantic_linkage_seeds(seed_id) ON DELETE CASCADE,
          cue_order INTEGER NOT NULL,
          cue_text TEXT NOT NULL,
          PRIMARY KEY (seed_id, cue_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_matches (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          seed_id TEXT NOT NULL REFERENCES au_semantic_linkage_seeds(seed_id) ON DELETE CASCADE,
          confidence TEXT NOT NULL,
          matched INTEGER NOT NULL,
          score INTEGER NOT NULL,
          ambiguity_group TEXT,
          PRIMARY KEY (run_id, event_id, seed_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS au_semantic_linkage_match_receipts (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          seed_id TEXT NOT NULL,
          receipt_order INTEGER NOT NULL,
          reason_kind TEXT NOT NULL,
          reason_value TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, seed_id, receipt_order),
          FOREIGN KEY (run_id, event_id, seed_id)
            REFERENCES au_semantic_linkage_matches(run_id, event_id, seed_id)
            ON DELETE CASCADE
        )
        """
    )


def import_au_semantic_seed_payload(conn: sqlite3.Connection, payload: Mapping[str, Any]) -> dict[str, Any]:
    ensure_au_semantic_schema(conn)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
    import_name = str(metadata.get("name") or "").strip()
    if not import_name:
        raise ValueError("payload.metadata.name is required")
    generated_at = str(metadata.get("generated_at") or "").strip() or None
    notes = str(metadata.get("notes") or "").strip() or None
    source_sha256 = _stable_sha256(payload)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    conn.execute(
        """
        INSERT INTO au_semantic_linkage_imports(import_name, source_sha256, generated_at, notes)
        VALUES (?,?,?,?)
        ON CONFLICT(import_name)
        DO UPDATE SET source_sha256=excluded.source_sha256, generated_at=excluded.generated_at, notes=excluded.notes
        """,
        (import_name, source_sha256, generated_at, notes),
    )
    seed_ids = [str(item.get("seed_id") or "").strip() for item in items if isinstance(item, Mapping) and str(item.get("seed_id") or "").strip()]
    if seed_ids:
        placeholders = ",".join("?" for _ in seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_match_receipts WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_matches WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_seed_authorities WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_seed_refs WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_seed_cues WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM au_semantic_linkage_seeds WHERE seed_id IN ({placeholders})", seed_ids)
    imported = 0
    for item in items:
        if not isinstance(item, Mapping):
            continue
        seed_id = str(item.get("seed_id") or "").strip()
        action_summary = str(item.get("action_summary") or "").strip()
        linkage_kind = str(item.get("linkage_kind") or "").strip()
        if not seed_id or not action_summary or not linkage_kind:
            continue
        lane_tags = item.get("lane_tags") if isinstance(item.get("lane_tags"), list) else []
        conn.execute(
            """
            INSERT INTO au_semantic_linkage_seeds(
              seed_id, import_name, action_summary, linkage_kind, notes, review_status, lane_tags_json
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                seed_id,
                import_name,
                action_summary,
                linkage_kind,
                str(item.get("notes") or "").strip() or None,
                str(item.get("review_status") or "").strip() or None,
                json.dumps([str(tag) for tag in lane_tags], ensure_ascii=True, sort_keys=True),
            ),
        )
        for idx, title in enumerate(item.get("authority_titles") if isinstance(item.get("authority_titles"), list) else [], start=1):
            authority_title = str(title).strip()
            if authority_title:
                conn.execute(
                    "INSERT INTO au_semantic_linkage_seed_authorities(seed_id, authority_order, authority_title) VALUES (?,?,?)",
                    (seed_id, idx, authority_title),
                )
        for ref_kind, field_name in (("institution_ref", "institution_refs"), ("court_ref", "court_refs")):
            ref_order = 0
            for ref in item.get(field_name) if isinstance(item.get(field_name), list) else []:
                canonical_ref = str(ref).strip()
                if canonical_ref:
                    for normalized_kind, normalized_ref in _normalized_seed_refs(ref_kind, canonical_ref):
                        ref_order += 1
                        conn.execute(
                            "INSERT INTO au_semantic_linkage_seed_refs(seed_id, ref_order, ref_kind, canonical_ref) VALUES (?,?,?,?)",
                            (seed_id, ref_order, normalized_kind, normalized_ref),
                        )
        for idx, cue in enumerate(item.get("provenance_cues") if isinstance(item.get("provenance_cues"), list) else [], start=1):
            cue_text = str(cue).strip()
            if cue_text:
                conn.execute(
                    "INSERT INTO au_semantic_linkage_seed_cues(seed_id, cue_order, cue_text) VALUES (?,?,?)",
                    (seed_id, idx, cue_text),
                )
        imported += 1
    return {"import_name": import_name, "seed_count": imported, "source_sha256": source_sha256}


def _normalize_text(text: str) -> str:
    out: list[str] = []
    previous_sep = True
    for ch in text.casefold():
        if ch.isalnum():
            out.append(ch)
            previous_sep = False
        else:
            if not previous_sep:
                out.append(" ")
            previous_sep = True
    return " ".join("".join(out).split())


def _normalized_seed_refs(ref_kind: str, canonical_ref: str) -> tuple[tuple[str, str], ...]:
    return _AU_REF_NORMALIZATION.get((ref_kind, canonical_ref), ((ref_kind, canonical_ref),))


def _contains(text_norm: str, phrase: str) -> bool:
    phrase_norm = _normalize_text(phrase)
    return bool(phrase_norm) and f" {phrase_norm} " in f" {text_norm} "


def _event_text_bundle(event: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("text", "section"):
        value = str(event.get(key) or "").strip()
        if value:
            parts.append(value)
    return "\n".join(parts)


def run_au_semantic_linkage(
    conn: sqlite3.Connection,
    *,
    timeline_suffix: str = "wiki_timeline_hca_s942025_aoo.json",
    run_id: str | None = None,
) -> dict[str, Any]:
    ensure_au_semantic_schema(conn)
    active_run_id = run_id or _pick_best_run_for_timeline_suffix(conn, timeline_suffix)
    if not active_run_id:
        raise ValueError(f"no wiki timeline run found for suffix {timeline_suffix}")
    payload = load_run_payload_from_normalized(conn, active_run_id)
    if not payload:
        raise ValueError(f"unable to load normalized payload for run_id={active_run_id}")
    conn.execute("DELETE FROM au_semantic_linkage_match_receipts WHERE run_id = ?", (active_run_id,))
    conn.execute("DELETE FROM au_semantic_linkage_matches WHERE run_id = ?", (active_run_id,))
    seeds = conn.execute(
        """
        SELECT seed_id, action_summary, linkage_kind, lane_tags_json
        FROM au_semantic_linkage_seeds
        ORDER BY seed_id
        """
    ).fetchall()
    authority_rows = conn.execute(
        "SELECT seed_id, authority_title FROM au_semantic_linkage_seed_authorities ORDER BY seed_id, authority_order"
    ).fetchall()
    ref_rows = conn.execute(
        "SELECT seed_id, ref_kind, canonical_ref FROM au_semantic_linkage_seed_refs ORDER BY seed_id, ref_kind, ref_order"
    ).fetchall()
    cue_rows = conn.execute(
        "SELECT seed_id, cue_text FROM au_semantic_linkage_seed_cues ORDER BY seed_id, cue_order"
    ).fetchall()
    authorities: dict[str, list[str]] = {}
    refs: dict[str, list[tuple[str, str]]] = {}
    cues: dict[str, list[str]] = {}
    for row in authority_rows:
        authorities.setdefault(str(row["seed_id"]), []).append(str(row["authority_title"]))
    for row in ref_rows:
        refs.setdefault(str(row["seed_id"]), []).append((str(row["ref_kind"]), str(row["canonical_ref"])))
    for row in cue_rows:
        cues.setdefault(str(row["seed_id"]), []).append(str(row["cue_text"]))
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    matched_event_count = 0
    ambiguous_event_count = 0
    for event in events:
        if not isinstance(event, Mapping) or not event.get("event_id"):
            continue
        event_id = str(event["event_id"])
        text = _event_text_bundle(event)
        text_norm = _normalize_text(text)
        scored: list[tuple[str, int, str, list[tuple[str, str]]]] = []
        for seed in seeds:
            seed_id = str(seed["seed_id"])
            score = 0
            receipts: list[tuple[str, str]] = []
            has_authority = False
            has_non_broad_ref = False
            has_non_broad_cue = False
            for title in authorities.get(seed_id, []):
                if _contains(text_norm, title):
                    score += 6
                    receipts.append(("authority_title", title))
                    has_authority = True
            for ref_kind, ref in refs.get(seed_id, []):
                ref_tail = ref.split(":", 1)[-1].replace("_", " ")
                if _contains(text_norm, ref_tail):
                    broad_ref = ref_tail in _BROAD_AU_REF_TAILS
                    score += 1 if broad_ref else 4
                    receipts.append((ref_kind, ref))
                    has_non_broad_ref = has_non_broad_ref or not broad_ref
            for cue in cues.get(seed_id, []):
                if _contains(text_norm, cue):
                    broad_cue = _normalize_text(cue) in _BROAD_AU_PROVENANCE_CUES
                    score += 1 if broad_cue else 2
                    receipts.append(("provenance_cue", cue))
                    has_non_broad_cue = has_non_broad_cue or not broad_cue
            if not has_authority and not has_non_broad_ref and not has_non_broad_cue:
                continue
            if score <= 0:
                continue
            confidence = "high" if score >= 10 else ("medium" if score >= 6 else "low")
            scored.append((seed_id, score, confidence, receipts))
        scored.sort(key=lambda item: (-item[1], item[0]))
        top_score = scored[0][1] if scored else 0
        top_count = sum(1 for _, score, _, _ in scored if score == top_score and top_score > 0)
        if top_count > 1:
            ambiguous_event_count += 1
        promoted_on_event = False
        for seed_id, score, confidence, receipts in scored:
            matched = int(score == top_score and top_count == 1 and confidence in {"high", "medium"})
            if matched:
                promoted_on_event = True
            conn.execute(
                """
                INSERT INTO au_semantic_linkage_matches(run_id, event_id, seed_id, confidence, matched, score, ambiguity_group)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    active_run_id,
                    event_id,
                    seed_id,
                    confidence if matched else ("abstain" if top_count > 1 or confidence == "low" else confidence),
                    matched,
                    score,
                    f"{active_run_id}:{event_id}:top" if top_count > 1 else None,
                ),
            )
            for idx, (kind, value) in enumerate(receipts, start=1):
                conn.execute(
                    """
                    INSERT INTO au_semantic_linkage_match_receipts(run_id, event_id, seed_id, receipt_order, reason_kind, reason_value)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (active_run_id, event_id, seed_id, idx, kind, value),
                )
        if promoted_on_event:
            matched_event_count += 1
    return {
        "run_id": active_run_id,
        "matched_event_count": matched_event_count,
        "ambiguous_event_count": ambiguous_event_count,
        "seed_count": len(seeds),
    }


def build_au_semantic_linkage_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_au_semantic_schema(conn)
    seed_ref_rows = conn.execute(
        """
        SELECT seed_id, ref_kind, canonical_ref
        FROM au_semantic_linkage_seed_refs
        ORDER BY seed_id, ref_kind, ref_order
        """
    ).fetchall()
    seed_refs: dict[str, list[dict[str, str]]] = {}
    for row in seed_ref_rows:
        seed_refs.setdefault(str(row["seed_id"]), []).append(
            {
                "ref_kind": str(row["ref_kind"]),
                "canonical_ref": str(row["canonical_ref"]),
            }
        )
    per_seed_rows = conn.execute(
        """
        SELECT s.seed_id, s.action_summary, s.linkage_kind, s.lane_tags_json,
               COUNT(m.event_id) AS candidate_count,
               SUM(CASE WHEN m.matched = 1 THEN 1 ELSE 0 END) AS matched_count
        FROM au_semantic_linkage_seeds AS s
        LEFT JOIN au_semantic_linkage_matches AS m
          ON m.seed_id = s.seed_id AND m.run_id = ?
        GROUP BY s.seed_id, s.action_summary, s.linkage_kind, s.lane_tags_json
        ORDER BY s.seed_id
        """,
        (run_id,),
    ).fetchall()
    per_seed = [
        {
            "seed_id": str(row["seed_id"]),
            "action_summary": str(row["action_summary"]),
            "linkage_kind": str(row["linkage_kind"]),
            "lane_tags": json.loads(str(row["lane_tags_json"] or "[]")),
            "seed_refs": seed_refs.get(str(row["seed_id"]), []),
            "candidate_count": int(row["candidate_count"] or 0),
            "matched_count": int(row["matched_count"] or 0),
        }
        for row in per_seed_rows
    ]
    event_rows = conn.execute(
        """
        SELECT event_id, seed_id, confidence, matched, score, ambiguity_group
        FROM au_semantic_linkage_matches
        WHERE run_id = ?
        ORDER BY event_id, score DESC, seed_id
        """,
        (run_id,),
    ).fetchall()
    receipt_rows = conn.execute(
        """
        SELECT event_id, seed_id, reason_kind, reason_value
        FROM au_semantic_linkage_match_receipts
        WHERE run_id = ?
        ORDER BY event_id, seed_id, receipt_order
        """,
        (run_id,),
    ).fetchall()
    receipts_map: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in receipt_rows:
        key = (str(row["event_id"]), str(row["seed_id"]))
        receipts_map.setdefault(key, []).append(
            {"reason_kind": str(row["reason_kind"]), "reason_value": str(row["reason_value"])}
        )
    per_event: dict[str, dict[str, Any]] = {}
    for row in event_rows:
        event_id = str(row["event_id"])
        per_event.setdefault(event_id, {"event_id": event_id, "matches": []})
        seed_id = str(row["seed_id"])
        per_event[event_id]["matches"].append(
            {
                "seed_id": seed_id,
                "confidence": str(row["confidence"]),
                "matched": bool(row["matched"]),
                "score": int(row["score"]),
                "ambiguity_group": str(row["ambiguity_group"] or ""),
                "receipts": receipts_map.get((event_id, seed_id), []),
            }
        )
    matched_seed_ids = {entry["seed_id"] for event in per_event.values() for entry in event["matches"] if entry["matched"]}
    unmatched = [row["seed_id"] for row in per_seed if row["seed_id"] not in matched_seed_ids]
    ambiguous = [event for event in per_event.values() if any(match["ambiguity_group"] for match in event["matches"])]
    return {
        "run_id": run_id,
        "per_seed": per_seed,
        "per_event": list(per_event.values()),
        "ambiguous_events": ambiguous,
        "unmatched_seeds": unmatched,
    }
