from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized


_BROAD_PROVENANCE_CUES = {
    "congress",
    "iraq",
    "veto",
    "supreme court",
    "u.s. supreme court",
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
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def ensure_gwb_us_law_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_imports (
          import_name TEXT PRIMARY KEY,
          source_sha256 TEXT NOT NULL,
          generated_at TEXT,
          notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_seeds (
          seed_id TEXT PRIMARY KEY,
          import_name TEXT NOT NULL REFERENCES gwb_us_law_linkage_imports(import_name) ON DELETE CASCADE,
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
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_seed_authorities (
          seed_id TEXT NOT NULL REFERENCES gwb_us_law_linkage_seeds(seed_id) ON DELETE CASCADE,
          authority_order INTEGER NOT NULL,
          authority_title TEXT NOT NULL,
          PRIMARY KEY (seed_id, authority_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_seed_refs (
          seed_id TEXT NOT NULL REFERENCES gwb_us_law_linkage_seeds(seed_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_kind TEXT NOT NULL,
          canonical_ref TEXT NOT NULL,
          PRIMARY KEY (seed_id, ref_kind, ref_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_seed_cues (
          seed_id TEXT NOT NULL REFERENCES gwb_us_law_linkage_seeds(seed_id) ON DELETE CASCADE,
          cue_order INTEGER NOT NULL,
          cue_text TEXT NOT NULL,
          PRIMARY KEY (seed_id, cue_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_matches (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          seed_id TEXT NOT NULL REFERENCES gwb_us_law_linkage_seeds(seed_id) ON DELETE CASCADE,
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
        CREATE TABLE IF NOT EXISTS gwb_us_law_linkage_match_receipts (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          seed_id TEXT NOT NULL,
          receipt_order INTEGER NOT NULL,
          reason_kind TEXT NOT NULL,
          reason_value TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, seed_id, receipt_order),
          FOREIGN KEY (run_id, event_id, seed_id)
            REFERENCES gwb_us_law_linkage_matches(run_id, event_id, seed_id)
            ON DELETE CASCADE
        )
        """
    )


def import_gwb_us_law_seed_payload(conn: sqlite3.Connection, payload: Mapping[str, Any]) -> dict[str, Any]:
    ensure_gwb_us_law_schema(conn)
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
        INSERT INTO gwb_us_law_linkage_imports(import_name, source_sha256, generated_at, notes)
        VALUES (?,?,?,?)
        ON CONFLICT(import_name)
        DO UPDATE SET source_sha256=excluded.source_sha256, generated_at=excluded.generated_at, notes=excluded.notes
        """,
        (import_name, source_sha256, generated_at, notes),
    )
    seed_ids = [str(item.get("seed_id") or "").strip() for item in items if isinstance(item, Mapping) and str(item.get("seed_id") or "").strip()]
    if seed_ids:
        placeholders = ",".join("?" for _ in seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_match_receipts WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_matches WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_seed_authorities WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_seed_refs WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_seed_cues WHERE seed_id IN ({placeholders})", seed_ids)
        conn.execute(f"DELETE FROM gwb_us_law_linkage_seeds WHERE seed_id IN ({placeholders})", seed_ids)
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
            INSERT INTO gwb_us_law_linkage_seeds(
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
                    "INSERT INTO gwb_us_law_linkage_seed_authorities(seed_id, authority_order, authority_title) VALUES (?,?,?)",
                    (seed_id, idx, authority_title),
                )
        for ref_kind, field_name in (("institution_ref", "institution_refs"), ("court_ref", "court_refs")):
            for idx, ref in enumerate(item.get(field_name) if isinstance(item.get(field_name), list) else [], start=1):
                canonical_ref = str(ref).strip()
                if canonical_ref:
                    conn.execute(
                        "INSERT INTO gwb_us_law_linkage_seed_refs(seed_id, ref_order, ref_kind, canonical_ref) VALUES (?,?,?,?)",
                        (seed_id, idx, ref_kind, canonical_ref),
                    )
        for idx, cue in enumerate(item.get("provenance_cues") if isinstance(item.get("provenance_cues"), list) else [], start=1):
            cue_text = str(cue).strip()
            if cue_text:
                conn.execute(
                    "INSERT INTO gwb_us_law_linkage_seed_cues(seed_id, cue_order, cue_text) VALUES (?,?,?)",
                    (seed_id, idx, cue_text),
                )
        imported += 1
    return {"import_name": import_name, "seed_count": imported, "source_sha256": source_sha256}


def _pick_best_run_for_timeline_suffix(conn: sqlite3.Connection, suffix: str) -> str | None:
    row = conn.execute(
        """
        SELECT run_id
        FROM wiki_timeline_aoo_runs
        WHERE timeline_path LIKE ?
        ORDER BY generated_at DESC, n_events DESC, run_id ASC
        LIMIT 1
        """,
        (f"%{suffix}",),
    ).fetchone()
    return str(row["run_id"]) if row else None


def _bridge_aliases_for_ref(conn: sqlite3.Connection, canonical_ref: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT e.canonical_label, a.alias_text
        FROM wikidata_bridge_entities AS e
        LEFT JOIN wikidata_bridge_aliases AS a ON a.bridge_entity_id = e.bridge_entity_id
        WHERE e.canonical_ref = ?
        ORDER BY a.alias_order
        """,
        (canonical_ref,),
    ).fetchall()
    out: list[str] = []
    for row in rows:
        for raw in (row["canonical_label"], row["alias_text"]):
            text = str(raw or "").strip()
            if text and text not in out:
                out.append(text)
    return out


def _collect_event_strings(event: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, str):
            txt = value.strip()
            if txt:
                out.append(txt)
        elif isinstance(value, Mapping):
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)
    walk(event)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in out:
        low = item.casefold()
        if low in seen:
            continue
        seen.add(low)
        deduped.append(item)
    return deduped


def _compute_match(authorities: list[str], refs: list[tuple[str, str]], cues: list[str], event: Mapping[str, Any], ref_aliases: Mapping[str, list[str]]) -> tuple[int, list[tuple[str, str]]]:
    haystacks = _collect_event_strings(event)
    score = 0
    receipts: list[tuple[str, str]] = []
    folded_haystacks = [text.casefold() for text in haystacks]
    for title in authorities:
        title_fold = title.casefold()
        if any(title_fold in text for text in folded_haystacks):
            score += 5
            receipts.append(("authority_title", title))
    for ref_kind, canonical_ref in refs:
        matched = False
        for alias in ref_aliases.get(canonical_ref, []):
            alias_fold = alias.casefold()
            if any(alias_fold in text for text in folded_haystacks):
                matched = True
                receipts.append((ref_kind, alias))
                break
        if matched:
            score += 4
    strong_cue_hits = 0
    broad_cue_hits = 0
    for cue in cues:
        cue_fold = cue.casefold()
        if any(cue_fold in text for text in folded_haystacks):
            if cue_fold in _BROAD_PROVENANCE_CUES:
                broad_cue_hits += 1
                receipts.append(("provenance_cue_broad", cue))
            else:
                strong_cue_hits += 1
                receipts.append(("provenance_cue", cue))
    if strong_cue_hits:
        score += strong_cue_hits
    non_cue_signal = any(kind in {"authority_title", "institution_ref", "court_ref"} for kind, _ in receipts)
    if broad_cue_hits and not non_cue_signal and not strong_cue_hits:
        score += 1
    elif broad_cue_hits and non_cue_signal:
        score += min(1, broad_cue_hits)
    return score, receipts


def _confidence_from_score(score: int, receipts: list[tuple[str, str]]) -> str:
    kinds = {kind for kind, _ in receipts}
    if score >= 7 or "authority_title" in kinds:
        return "high"
    if score >= 4 and (
        "authority_title" in kinds
        or ("institution_ref" in kinds and "provenance_cue" in kinds)
        or ("court_ref" in kinds and "provenance_cue" in kinds)
        or ("institution_ref" in kinds and "court_ref" in kinds)
    ):
        return "medium"
    if score >= 3 and (
        "provenance_cue" in kinds
        or "authority_title" in kinds
        or "provenance_cue_broad" in kinds
        or ("institution_ref" in kinds and "provenance_cue_broad" in kinds)
        or ("court_ref" in kinds and "provenance_cue_broad" in kinds)
        or ("institution_ref" in kinds and "court_ref" in kinds)
    ):
        return "low"
    if score >= 1 and "provenance_cue_broad" in kinds:
        return "low"
    return "abstain"


def run_gwb_us_law_linkage(
    conn: sqlite3.Connection,
    *,
    timeline_suffix: str = "wiki_timeline_gwb.json",
    run_id: str | None = None,
) -> dict[str, Any]:
    ensure_gwb_us_law_schema(conn)
    active_run_id = run_id or _pick_best_run_for_timeline_suffix(conn, timeline_suffix)
    if not active_run_id:
        raise ValueError(f"no wiki timeline run found for suffix {timeline_suffix}")
    payload = load_run_payload_from_normalized(conn, active_run_id)
    if not payload:
        raise ValueError(f"unable to load normalized payload for run_id={active_run_id}")
    seed_rows = conn.execute(
        "SELECT seed_id, action_summary, linkage_kind, lane_tags_json FROM gwb_us_law_linkage_seeds ORDER BY seed_id"
    ).fetchall()
    seeds: list[dict[str, Any]] = []
    all_refs: set[str] = set()
    for row in seed_rows:
        seed_id = str(row["seed_id"])
        authorities = [
            str(r["authority_title"])
            for r in conn.execute(
                "SELECT authority_title FROM gwb_us_law_linkage_seed_authorities WHERE seed_id = ? ORDER BY authority_order",
                (seed_id,),
            ).fetchall()
        ]
        refs = [
            (str(r["ref_kind"]), str(r["canonical_ref"]))
            for r in conn.execute(
                "SELECT ref_kind, canonical_ref FROM gwb_us_law_linkage_seed_refs WHERE seed_id = ? ORDER BY ref_kind, ref_order",
                (seed_id,),
            ).fetchall()
        ]
        cues = [
            str(r["cue_text"])
            for r in conn.execute(
                "SELECT cue_text FROM gwb_us_law_linkage_seed_cues WHERE seed_id = ? ORDER BY cue_order",
                (seed_id,),
            ).fetchall()
        ]
        for _, canonical_ref in refs:
            all_refs.add(canonical_ref)
        seeds.append(
            {
                "seed_id": seed_id,
                "action_summary": str(row["action_summary"]),
                "linkage_kind": str(row["linkage_kind"]),
                "lane_tags": json.loads(str(row["lane_tags_json"] or "[]")),
                "authority_titles": authorities,
                "refs": refs,
                "provenance_cues": cues,
            }
        )
    ref_aliases = {canonical_ref: _bridge_aliases_for_ref(conn, canonical_ref) for canonical_ref in sorted(all_refs)}
    conn.execute("DELETE FROM gwb_us_law_linkage_match_receipts WHERE run_id = ?", (active_run_id,))
    conn.execute("DELETE FROM gwb_us_law_linkage_matches WHERE run_id = ?", (active_run_id,))
    matched_event_count = 0
    ambiguous_event_count = 0
    per_seed_counts: Counter[str] = Counter()
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("event_id") or "")
        if not event_id:
            continue
        candidates: list[tuple[dict[str, Any], int, list[tuple[str, str]], str]] = []
        for seed in seeds:
            score, receipts = _compute_match(seed["authority_titles"], seed["refs"], seed["provenance_cues"], event, ref_aliases)
            if score <= 0:
                continue
            confidence = _confidence_from_score(score, receipts)
            candidates.append((seed, score, receipts, confidence))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (-item[1], item[0]["seed_id"]))
        top_score = candidates[0][1]
        promotable = [item for item in candidates if item[1] == top_score]
        ambiguity_group = None
        if len(promotable) > 1:
            ambiguity_group = "|".join(seed["seed_id"] for seed, _, _, _ in promotable)
            ambiguous_event_count += 1
        else:
            if promotable[0][3] != "abstain":
                matched_event_count += 1
        for seed, score, receipts, confidence in candidates:
            matched = 1 if score == top_score and len(promotable) == 1 and confidence != "abstain" else 0
            if matched:
                per_seed_counts[seed["seed_id"]] += 1
            elif confidence != "abstain" and score == top_score:
                confidence = "low"
            conn.execute(
                """
                INSERT INTO gwb_us_law_linkage_matches(run_id, event_id, seed_id, confidence, matched, score, ambiguity_group)
                VALUES (?,?,?,?,?,?,?)
                """,
                (active_run_id, event_id, seed["seed_id"], confidence, matched, score, ambiguity_group),
            )
            for receipt_order, (reason_kind, reason_value) in enumerate(receipts, start=1):
                conn.execute(
                    """
                    INSERT INTO gwb_us_law_linkage_match_receipts(run_id, event_id, seed_id, receipt_order, reason_kind, reason_value)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (active_run_id, event_id, seed["seed_id"], receipt_order, reason_kind, reason_value),
                )
    return {
        "run_id": active_run_id,
        "event_count": len(events),
        "matched_event_count": matched_event_count,
        "ambiguous_event_count": ambiguous_event_count,
        "seed_match_counts": dict(sorted(per_seed_counts.items())),
    }


def build_gwb_us_law_linkage_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_gwb_us_law_schema(conn)
    match_rows = conn.execute(
        """
        SELECT m.event_id, m.seed_id, m.confidence, m.matched, m.score, m.ambiguity_group,
               s.action_summary, s.linkage_kind
        FROM gwb_us_law_linkage_matches AS m
        JOIN gwb_us_law_linkage_seeds AS s ON s.seed_id = m.seed_id
        WHERE m.run_id = ?
        ORDER BY m.event_id, m.score DESC, m.seed_id
        """,
        (run_id,),
    ).fetchall()
    payload = load_run_payload_from_normalized(conn, run_id) or {}
    event_map = {
        str(event.get("event_id")): event
        for event in (payload.get("events") if isinstance(payload.get("events"), list) else [])
        if isinstance(event, Mapping) and event.get("event_id")
    }
    per_seed: dict[str, dict[str, Any]] = {}
    per_event: dict[str, dict[str, Any]] = {}
    ambiguous: list[dict[str, Any]] = []
    confidence_counter: Counter[str] = Counter()
    for row in match_rows:
        event_id = str(row["event_id"])
        seed_id = str(row["seed_id"])
        confidence = str(row["confidence"])
        confidence_counter[confidence] += 1
        receipts = [
            {"kind": str(r["reason_kind"]), "value": str(r["reason_value"])}
            for r in conn.execute(
                """
                SELECT reason_kind, reason_value
                FROM gwb_us_law_linkage_match_receipts
                WHERE run_id = ? AND event_id = ? AND seed_id = ?
                ORDER BY receipt_order
                """,
                (run_id, event_id, seed_id),
            ).fetchall()
        ]
        event = event_map.get(event_id, {})
        seed_bucket = per_seed.setdefault(
            seed_id,
            {
                "seed_id": seed_id,
                "action_summary": str(row["action_summary"]),
                "linkage_kind": str(row["linkage_kind"]),
                "matched_event_count": 0,
                "candidate_event_count": 0,
                "confidence_counts": Counter(),
                "events": [],
            },
        )
        seed_bucket["candidate_event_count"] += 1
        seed_bucket["confidence_counts"][confidence] += 1
        if int(row["matched"] or 0):
            seed_bucket["matched_event_count"] += 1
        entry = {
            "event_id": event_id,
            "confidence": confidence,
            "matched": bool(row["matched"]),
            "score": int(row["score"] or 0),
            "anchor": event.get("anchor"),
            "text": str(event.get("text") or ""),
            "receipts": receipts,
        }
        seed_bucket["events"].append(entry)
        event_bucket = per_event.setdefault(
            event_id,
            {
                "event_id": event_id,
                "anchor": event.get("anchor"),
                "text": str(event.get("text") or ""),
                "matches": [],
            },
        )
        event_bucket["matches"].append(
            {
                "seed_id": seed_id,
                "action_summary": str(row["action_summary"]),
                "confidence": confidence,
                "matched": bool(row["matched"]),
                "score": int(row["score"] or 0),
                "receipts": receipts,
            }
        )
        if row["ambiguity_group"]:
            ambiguous.append(
                {
                    "event_id": event_id,
                    "ambiguity_group": str(row["ambiguity_group"]),
                    "seed_id": seed_id,
                    "confidence": confidence,
                    "score": int(row["score"] or 0),
                }
            )
    all_seed_ids = [
        str(row["seed_id"])
        for row in conn.execute("SELECT seed_id FROM gwb_us_law_linkage_seeds ORDER BY seed_id").fetchall()
    ]
    unmatched_seeds = [seed_id for seed_id in all_seed_ids if seed_id not in per_seed]
    for bucket in per_seed.values():
        bucket["confidence_counts"] = dict(sorted(bucket["confidence_counts"].items()))
        bucket["events"].sort(key=lambda row: (-int(row["matched"]), -int(row["score"]), row["event_id"]))
    for bucket in per_event.values():
        bucket["matches"].sort(key=lambda row: (-int(row["matched"]), -int(row["score"]), row["seed_id"]))
    ambiguous_unique = []
    seen_ambiguity: set[tuple[str, str]] = set()
    for row in ambiguous:
        key = (row["event_id"], row["ambiguity_group"])
        if key in seen_ambiguity:
            continue
        seen_ambiguity.add(key)
        ambiguous_unique.append(row)
    return {
        "run_id": run_id,
        "confidence_counts": dict(sorted(confidence_counter.items())),
        "per_seed": [per_seed[seed_id] for seed_id in sorted(per_seed)],
        "per_event": [per_event[event_id] for event_id in sorted(per_event)],
        "ambiguous_events": ambiguous_unique,
        "unmatched_seed_ids": unmatched_seeds,
    }
