from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.au_semantic.linkage import run_au_semantic_linkage
from src.ingestion.citation_follow import extract_citations
from src.gwb_us_law.linkage import _pick_best_run_for_timeline_suffix
from src.gwb_us_law.semantic import (
    PIPELINE_VERSION,
    EntitySeed,
    _ensure_predicates,
    _ensure_promotion_policies,
    _entity_for_key,
    _insert_cluster_and_resolution,
    _insert_event_role,
    _insert_relation_candidate,
    _normalize_phrase,
    _policy_adjusted_confidence,
    _text_contains_phrase,
    _upsert_seed_entity,
    build_gwb_semantic_report,
    ensure_gwb_semantic_schema,
    load_run_payload_from_normalized,
    _delete_run_rows,
)


_AU_PREDICATES = (
    ("appealed", "appealed", "procedural_review"),
    ("challenged", "challenged", "adjudicative_review"),
    ("heard_by", "heard by", "procedural_review"),
    ("decided_by", "decided by", "adjudicative_review"),
    ("applied", "applied", "adjudicative_reasoning"),
    ("followed", "followed", "adjudicative_reasoning"),
    ("distinguished", "distinguished", "adjudicative_reasoning"),
    ("held_that", "held that", "adjudicative_reasoning"),
)


_AU_ENTITY_SEEDS: tuple[EntitySeed, ...] = (
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:high_court_of_australia",
        canonical_label="High Court of Australia",
        actor_kind="institution_actor",
        classification_tag="court",
        aliases=("High Court of Australia", "High Court"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:commonwealth_of_australia",
        canonical_label="Commonwealth of Australia",
        actor_kind="institution_actor",
        aliases=("Commonwealth", "Commonwealth of Australia"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:state_of_new_south_wales",
        canonical_label="State of New South Wales",
        actor_kind="institution_actor",
        aliases=("New South Wales", "State of New South Wales", "NSW"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:mabo_v_queensland_no_2",
        canonical_label="Mabo v Queensland (No 2)",
        ref_kind="case_ref",
        source_title="Mabo v Queensland (No 2)",
        aliases=("Mabo v Queensland (No 2)", "Mabo [No 2]", "Mabo"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:house_v_the_king",
        canonical_label="House v The King",
        ref_kind="case_ref",
        source_title="House v The King",
        aliases=("House v The King",),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:plaintiff_s157_2002_v_commonwealth",
        canonical_label="Plaintiff S157/2002 v Commonwealth",
        ref_kind="case_ref",
        source_title="Plaintiff S157/2002 v Commonwealth",
        aliases=("Plaintiff S157/2002 v Commonwealth", "Plaintiff S157"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:native_title_new_south_wales_act_1994",
        canonical_label="Native Title (New South Wales) Act 1994",
        ref_kind="act_ref",
        source_title="Native Title (New South Wales) Act 1994",
        aliases=("Native Title (New South Wales) Act 1994", "Native Title (NSW) Act 1994"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:new_south_wales_v_lepore",
        canonical_label="New South Wales v Lepore",
        ref_kind="case_ref",
        source_title="New South Wales v Lepore",
        aliases=("New South Wales v Lepore", "Lepore"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:commonwealth_v_introvigne",
        canonical_label="Commonwealth v Introvigne",
        ref_kind="case_ref",
        source_title="Commonwealth v Introvigne",
        aliases=("Commonwealth v Introvigne", "Introvigne"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:nationwide_news_pty_ltd_v_naidu",
        canonical_label="Nationwide News Pty Ltd v Naidu",
        ref_kind="case_ref",
        source_title="Nationwide News Pty Ltd v Naidu",
        aliases=("Nationwide News Pty Ltd v Naidu", "Naidu"),
    ),
    EntitySeed(
        entity_kind="legal_ref",
        canonical_key="legal_ref:civil_liability_act_2002_nsw",
        canonical_label="Civil Liability Act 2002 (NSW)",
        ref_kind="act_ref",
        source_title="Civil Liability Act 2002 (NSW)",
        aliases=("Civil Liability Act 2002 (NSW)", "Civil Liability Act"),
    ),
    EntitySeed(
        entity_kind="office",
        canonical_key="office:attorney_general",
        canonical_label="Attorney-General",
        office_kind="office",
        aliases=("Attorney-General",),
    ),
    EntitySeed(
        entity_kind="office",
        canonical_key="office:registrar",
        canonical_label="Registrar",
        office_kind="office",
        aliases=("Registrar",),
    ),
)

_ROLE_SURFACES = {
    "appellant": "party_appellant",
    "respondent": "party_respondent",
    "plaintiff": "party_plaintiff",
    "defendant": "party_defendant",
    "accused": "party_accused",
    "applicant": "party_applicant",
}

_ABSTAINED_SURFACES = ("the Court", "the Minister")

_JUDGE_SUFFIXES = (" CJ", " J", " JA", " ACJ")
_TITLE_PREFIXES = ("Mr ", "Ms ", "Mrs ", "Dr ", "Professor ")
_LEGAL_REP_SUFFIXES = (" SC", " KC", " QC")
_OFFICE_SURFACES = {
    "Attorney-General": "office:attorney_general",
    "Registrar": "office:registrar",
}
_TITLE_TOKEN_NORMALIZED = tuple(prefix.strip().replace(".", "").casefold() for prefix in _TITLE_PREFIXES)
_LEGAL_REP_SUFFIX_NORMALIZED = tuple(suffix.strip().replace(".", "").casefold() for suffix in _LEGAL_REP_SUFFIXES)
_CLAUSE_BREAK_TOKENS = {"and", "but", "while"}
_AUTHORITY_TERM_STOPWORDS = {
    "and",
    "the",
    "v",
    "of",
    "no",
    "act",
    "pty",
    "ltd",
    "state",
    "commonwealth",
}


def _au_legal_representation_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "semantic" / "au_legal_representation_cues_v1.json"


@lru_cache(maxsize=1)
def _load_au_legal_representation_cues() -> tuple[dict[str, str], ...]:
    payload = json.loads(_au_legal_representation_catalog_path().read_text(encoding="utf-8"))
    party_roles = payload.get("party_roles") if isinstance(payload.get("party_roles"), list) else []
    cue_templates = payload.get("cue_templates") if isinstance(payload.get("cue_templates"), list) else []
    expanded: list[dict[str, str]] = []
    for role in party_roles:
        if not isinstance(role, Mapping):
            continue
        role_key = str(role.get("key") or "").strip()
        role_title = str(role.get("title") or "").strip()
        if not role_key or not role_title:
            continue
        for cue in cue_templates:
            if not isinstance(cue, Mapping):
                continue
            surface_template = str(cue.get("surface_template") or "").strip()
            role_label_template = str(cue.get("role_label_template") or "").strip()
            if not surface_template or not role_label_template:
                continue
            expanded.append(
                {
                    "surface": surface_template.format(party_role=role_key),
                    "cue_template": surface_template,
                    "party_role": role_key,
                    "role_label": role_label_template.format(party_role_title=role_title),
                }
            )
    return tuple(expanded)


def _normalize_authority_text(text: str | None) -> str:
    return " ".join(str(text or "").casefold().split())


def _au_doc_actor_key(run_id: str, surface: str) -> str:
    slug = "_".join(surface.casefold().replace("/", " ").replace("-", " ").split())
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in slug).strip("_")
    return f"actor:doc:{run_id}:{cleaned}"


def _is_legal_rep_suffix_surface(text: str) -> bool:
    compact = " ".join(str(text or "").replace(".", "").split())
    return any(compact.endswith(suffix.strip()) for suffix in _LEGAL_REP_SUFFIXES)


def _normalized_surface_token(text: str) -> str:
    return "".join(ch.casefold() for ch in str(text or "") if ch.isalnum())


def _surface_tokens(text: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    start: int | None = None
    for index, ch in enumerate(text):
        if ch.isspace():
            if start is not None:
                raw = text[start:index]
                tokens.append({"raw": raw, "norm": _normalized_surface_token(raw), "start": start, "end": index})
                start = None
            continue
        if start is None:
            start = index
    if start is not None:
        raw = text[start:]
        tokens.append({"raw": raw, "norm": _normalized_surface_token(raw), "start": start, "end": len(text)})
    return [token for token in tokens if token["norm"]]


def _join_token_surface(tokens: list[dict[str, Any]], start: int, end: int) -> str:
    return " ".join(str(token["raw"]).strip(" ,;:()[]") for token in tokens[start:end]).strip()


def _clause_ranges(tokens: list[dict[str, Any]]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for index, token in enumerate(tokens):
        raw = str(token["raw"])
        split_here = token["norm"] in _CLAUSE_BREAK_TOKENS or any(mark in raw for mark in ";:.")
        if not split_here:
            continue
        if start < index:
            ranges.append((start, index))
        start = index + 1
    if start < len(tokens):
        ranges.append((start, len(tokens)))
    return ranges


def _find_phrase_matches(tokens: list[dict[str, Any]], phrase: str) -> list[tuple[int, int]]:
    phrase_parts = [_normalized_surface_token(part) for part in phrase.split() if _normalized_surface_token(part)]
    if not phrase_parts or len(phrase_parts) > len(tokens):
        return []
    matches: list[tuple[int, int]] = []
    for start in range(0, len(tokens) - len(phrase_parts) + 1):
        if [tokens[start + offset]["norm"] for offset in range(len(phrase_parts))] == phrase_parts:
            matches.append((start, start + len(phrase_parts)))
    return matches


def _is_title_token(token: str) -> bool:
    return _normalized_surface_token(token) in _TITLE_TOKEN_NORMALIZED


def _is_legal_rep_suffix_token(token: str) -> bool:
    return _normalized_surface_token(token) in _LEGAL_REP_SUFFIX_NORMALIZED


def _looks_like_named_token(token: str) -> bool:
    for ch in str(token or "").lstrip("([{\"'"):
        if ch.isalpha():
            return ch.isupper()
    return False


def _insert_event_role_once(
    conn,
    *,
    seen: set[tuple[str, str, int | None, int | None, str | None]],
    run_id: str,
    event_id: str,
    role_kind: str,
    entity_id: int | None = None,
    cluster_id: int | None = None,
    note: str | None = None,
) -> None:
    key = (event_id, role_kind, entity_id, cluster_id, note)
    if key in seen:
        return
    seen.add(key)
    _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind=role_kind, entity_id=entity_id, cluster_id=cluster_id, note=note)


def _ensure_au_predicates(conn) -> dict[str, int]:
    predicate_ids = _ensure_predicates(conn)
    for key, label, family in _AU_PREDICATES:
        conn.execute(
            """
            INSERT INTO semantic_predicate_vocab(
              predicate_key, display_label, predicate_family, is_directed, inverse_predicate_key, promotion_rule_key, active_v1
            ) VALUES (?,?,?,?,?,?,1)
            ON CONFLICT(predicate_key)
            DO UPDATE SET display_label=excluded.display_label,
                          predicate_family=excluded.predicate_family,
                          is_directed=excluded.is_directed,
                          inverse_predicate_key=excluded.inverse_predicate_key,
                          promotion_rule_key=excluded.promotion_rule_key,
                          active_v1=excluded.active_v1
            """,
            (key, label, family, 1, None, f"au_{key}_v1"),
        )
    _ensure_promotion_policies(conn)
    rows = conn.execute("SELECT predicate_id, predicate_key FROM semantic_predicate_vocab").fetchall()
    return {str(row["predicate_key"]): int(row["predicate_id"]) for row in rows}


def _seed_au_entities(conn) -> dict[str, int]:
    return {seed.canonical_key: _upsert_seed_entity(conn, seed) for seed in _AU_ENTITY_SEEDS}


def _ensure_doc_actor(
    conn,
    *,
    run_id: str,
    label: str,
    source_rule: str,
    classification_tag: str | None = None,
) -> int:
    key = _au_doc_actor_key(run_id, label)
    entity_id = _entity_for_key(conn, key)
    if entity_id is not None:
        if classification_tag:
            conn.execute(
                "UPDATE semantic_entity_actors SET classification_tag = COALESCE(classification_tag, ?) WHERE entity_id = ?",
                (classification_tag, entity_id),
            )
        return entity_id
    return _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="actor",
            canonical_key=key,
            canonical_label=label,
            actor_kind="person_actor",
            classification_tag=classification_tag,
            aliases=(label,),
        ),
    )


def _detect_au_mentions_for_event(conn, *, run_id: str, event_id: str, event: Mapping[str, Any], entity_ids: dict[str, int]) -> dict[str, list[int]]:
    text = str(event.get("text") or "")
    found: dict[str, list[int]] = defaultdict(list)
    role_insertions: set[tuple[str, str, int | None, int | None, str | None]] = set()
    for surface in _ABSTAINED_SURFACES:
        if _text_contains_phrase(text, surface):
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=None,
                surface_text=surface,
                source_rule="au_ambiguous_surface_v1",
                resolved_entity_id=None,
                resolution_status="abstained",
                resolution_rule="title_requires_stronger_context_v1",
                receipts=[("surface", surface), ("reason", "ambiguous_forum_or_office")],
            )
            found["abstained"].append(cluster_id)
    for seed in _AU_ENTITY_SEEDS:
        for alias in seed.aliases:
            if _text_contains_phrase(text, alias):
                cluster_id, _ = _insert_cluster_and_resolution(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    mention_kind="actor" if seed.entity_kind == "actor" else seed.entity_kind,
                    canonical_key_hint=seed.canonical_key,
                    surface_text=alias,
                    source_rule="au_seed_alias_v1",
                    resolved_entity_id=entity_ids[seed.canonical_key],
                    resolution_status="resolved",
                    resolution_rule="seed_alias_exact_v1",
                    receipts=[("alias", alias), ("canonical_key", seed.canonical_key)],
                )
                found[seed.canonical_key].append(cluster_id)
    for surface, office_key in _OFFICE_SURFACES.items():
        if _text_contains_phrase(text, surface):
            office_id = entity_ids[office_key]
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="office",
                canonical_key_hint=office_key,
                surface_text=surface,
                source_rule="au_office_surface_v1",
                resolved_entity_id=office_id,
                resolution_status="resolved",
                resolution_rule="office_surface_exact_v1",
                receipts=[("office_surface", surface), ("canonical_key", office_key)],
            )
            found[office_key].append(cluster_id)
            _insert_event_role_once(
                conn,
                seen=role_insertions,
                run_id=run_id,
                event_id=event_id,
                role_kind="office_context",
                entity_id=office_id,
                note="au_office_surface_v1",
            )
    text_lines = [part.strip(" .,;:()") for part in text.split()]
    for surface, role_kind in _ROLE_SURFACES.items():
        if _text_contains_phrase(text, f"the {surface}") or _text_contains_phrase(text, surface):
            label = surface.title()
            entity_id = _ensure_doc_actor(conn, run_id=run_id, label=label, source_rule="au_case_role_v1")
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=f"actor:doc:{run_id}:{surface}",
                surface_text=f"the {surface}",
                source_rule="au_case_role_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="document_local_case_role_v1",
                receipts=[("role_pattern", surface), ("scope", "document_local_actor")],
            )
            found[f"doc_role:{surface}"].append(cluster_id)
            _insert_event_role_once(
                conn,
                seen=role_insertions,
                run_id=run_id,
                event_id=event_id,
                role_kind=role_kind,
                entity_id=entity_id,
                note="au_case_role_v1",
            )
    tokens = _surface_tokens(text)
    representative_mentions: list[dict[str, Any]] = []
    seen_representative_keys: set[tuple[str, int, int]] = set()

    def register_representative(
        *,
        label: str,
        start_index: int,
        end_index: int,
        source_rule: str,
        resolution_rule: str,
        receipts: list[tuple[str, str]],
        classification_tag: str | None = None,
        insert_role: bool = False,
    ) -> dict[str, Any]:
        canonical_key = _au_doc_actor_key(run_id, label)
        entity_id = _ensure_doc_actor(
            conn,
            run_id=run_id,
            label=label,
            source_rule=source_rule,
            classification_tag=classification_tag,
        )
        dedupe_key = (canonical_key, start_index, end_index)
        if dedupe_key in seen_representative_keys:
            return {
                "entity_id": entity_id,
                "canonical_key": canonical_key,
                "label": label,
                "start_index": start_index,
                "end_index": end_index,
            }
        seen_representative_keys.add(dedupe_key)
        cluster_id, _ = _insert_cluster_and_resolution(
            conn,
            run_id=run_id,
            event_id=event_id,
            mention_kind="actor",
            canonical_key_hint=canonical_key,
            surface_text=label,
            source_rule=source_rule,
            resolved_entity_id=entity_id,
            resolution_status="resolved",
            resolution_rule=resolution_rule,
            receipts=receipts,
        )
        found[canonical_key].append(cluster_id)
        if insert_role:
            _insert_event_role_once(
                conn,
                seen=role_insertions,
                run_id=run_id,
                event_id=event_id,
                role_kind="legal_representative",
                entity_id=entity_id,
                cluster_id=cluster_id,
                note=source_rule,
            )
        mention = {
            "entity_id": entity_id,
            "canonical_key": canonical_key,
            "label": label,
            "cluster_id": cluster_id,
            "start_index": start_index,
            "end_index": end_index,
        }
        representative_mentions.append(mention)
        return mention

    for token_index in range(len(tokens) - 1):
        first = str(tokens[token_index]["raw"]).strip(" ,;:()[]")
        second = str(tokens[token_index + 1]["raw"]).strip(" ,;:()[]")
        candidate = f"{first} {second}".strip()
        candidate_three = ""
        if token_index + 2 < len(tokens):
            third = str(tokens[token_index + 2]["raw"]).strip(" ,;:()[]")
            candidate_three = f"{first} {second} {third}".strip()
        title_and_suffix = (
            token_index + 2 < len(tokens)
            and _is_title_token(first)
            and _looks_like_named_token(second)
            and _is_legal_rep_suffix_token(third)
        )
        if title_and_suffix:
            register_representative(
                label=candidate_three,
                start_index=token_index,
                end_index=token_index + 3,
                source_rule="au_named_legal_representative_v1",
                resolution_rule="document_local_named_legal_representative_v1",
                receipts=[("title_suffix_pattern", candidate_three), ("scope", "document_local_actor")],
                classification_tag="legal_representative",
                insert_role=True,
            )
        elif _is_title_token(first) and _looks_like_named_token(second):
            register_representative(
                label=candidate,
                start_index=token_index,
                end_index=token_index + 2,
                source_rule="au_titled_person_v1",
                resolution_rule="document_local_titled_person_v1",
                receipts=[("title_pattern", candidate), ("scope", "document_local_actor")],
            )
        if _is_legal_rep_suffix_token(second) and _looks_like_named_token(first) and not (token_index > 0 and _is_title_token(str(tokens[token_index - 1]["raw"]))):
            register_representative(
                label=candidate,
                start_index=token_index,
                end_index=token_index + 2,
                source_rule="au_suffix_legal_representative_v1",
                resolution_rule="document_local_suffix_legal_representative_v1",
                receipts=[("suffix_pattern", candidate), ("scope", "document_local_actor")],
                classification_tag="legal_representative",
                insert_role=True,
            )
        if any(candidate.endswith(suffix.strip()) for suffix in _JUDGE_SUFFIXES):
            entity_id = _ensure_doc_actor(conn, run_id=run_id, label=candidate, source_rule="au_judge_surface_v1", classification_tag="judge")
            conn.execute(
                "UPDATE semantic_entity_actors SET classification_tag = ? WHERE entity_id = ?",
                ("judge", entity_id),
            )
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_au_doc_actor_key(run_id, candidate),
                surface_text=candidate,
                source_rule="au_judge_surface_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="judge_title_globalish_v1",
                receipts=[("judge_surface", candidate), ("scope", "global_judge_v1")],
            )
            found[_au_doc_actor_key(run_id, candidate)].append(cluster_id)
    for clause_start, clause_end in _clause_ranges(tokens):
        clause_tokens = tokens[clause_start:clause_end]
        clause_reps = [
            mention
            for mention in representative_mentions
            if mention["start_index"] >= clause_start and mention["end_index"] <= clause_end
        ]
        for cue in _load_au_legal_representation_cues():
            for start_offset, end_offset in _find_phrase_matches(clause_tokens, cue["surface"]):
                start_index = clause_start + start_offset
                end_index = clause_start + end_offset
                matched_surface = _join_token_surface(tokens, start_index, end_index)
                bound_rep = None
                preceding = [mention for mention in clause_reps if mention["end_index"] <= start_index]
                following = [mention for mention in clause_reps if mention["start_index"] >= end_index]
                if preceding:
                    bound_rep = max(preceding, key=lambda mention: int(mention["end_index"]))
                elif following:
                    bound_rep = min(following, key=lambda mention: int(mention["start_index"]))
                if bound_rep is None:
                    cluster_id, _ = _insert_cluster_and_resolution(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        mention_kind="actor",
                        canonical_key_hint=None,
                        surface_text=matched_surface,
                        source_rule="au_legal_representation_cue_v1",
                        resolved_entity_id=None,
                        resolution_status="abstained",
                        resolution_rule="legal_representation_requires_named_representative_v1",
                        receipts=[
                            ("cue_surface", matched_surface),
                            ("cue_template", cue["cue_template"]),
                            ("party_role", cue["party_role"]),
                            ("reason", "missing_named_representative_signal"),
                        ],
                    )
                    found["abstained"].append(cluster_id)
                    continue
                cluster_id, _ = _insert_cluster_and_resolution(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    mention_kind="actor",
                    canonical_key_hint=bound_rep["canonical_key"],
                    surface_text=matched_surface,
                    source_rule="au_legal_representation_cue_v1",
                    resolved_entity_id=bound_rep["entity_id"],
                    resolution_status="resolved",
                    resolution_rule="clause_local_named_representative_v1",
                    receipts=[
                        ("cue_surface", matched_surface),
                        ("cue_template", cue["cue_template"]),
                        ("party_role", cue["party_role"]),
                        ("role_label", cue["role_label"]),
                        ("representative_surface", bound_rep["label"]),
                    ],
                )
                found[bound_rep["canonical_key"]].append(cluster_id)
                _insert_event_role_once(
                    conn,
                    seen=role_insertions,
                    run_id=run_id,
                    event_id=event_id,
                    role_kind="legal_representative",
                    entity_id=bound_rep["entity_id"],
                    cluster_id=cluster_id,
                    note=f"au_legal_representation_cue_v1:{cue['role_label']}",
                )
    return found


def _predicate_confidence(conn, predicate_key: str, receipts: list[tuple[str, str]]) -> str:
    kinds = {kind for kind, _ in receipts}
    if predicate_key in {"appealed", "challenged"} and {"subject", "verb", "object"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="high")
    if predicate_key in {"heard_by", "decided_by", "applied", "followed", "distinguished", "held_that"} and {"subject", "verb", "object"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="medium")
    if {"subject", "verb"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="low")
    return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="abstain")


def _extract_au_relations(conn, *, run_id: str, event_id: str, event: Mapping[str, Any], mention_clusters: Mapping[str, list[int]], entity_ids: dict[str, int], predicate_ids: Mapping[str, int]) -> None:
    text = str(event.get("text") or "")
    text_fold = text.casefold()
    court_id = entity_ids.get("actor:high_court_of_australia")
    legal_ref_keys = [key for key in mention_clusters if key.startswith("legal_ref:")]
    act_keys = [key for key in legal_ref_keys if "_act_" in key or key.endswith("_act")]
    case_keys = [key for key in legal_ref_keys if key not in act_keys]
    subject_entity_ids: list[int] = []
    for role_surface in _ROLE_SURFACES:
        doc_key = f"doc_role:{role_surface}"
        if mention_clusters.get(doc_key):
            subject_entity_ids.append(_ensure_doc_actor(conn, run_id=run_id, label=role_surface.title(), source_rule="au_case_role_v1"))
    if not subject_entity_ids and case_keys:
        subject_entity_ids.extend(entity_ids.get(key) or _entity_for_key(conn, key) for key in case_keys if (entity_ids.get(key) or _entity_for_key(conn, key)))
    if "appeal" in text_fold:
        for subject_id in subject_entity_ids:
            if court_id is None:
                continue
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="forum", entity_id=court_id, note="au_appeal_v1")
            receipts = [("subject", str(subject_id)), ("verb", "appeal"), ("object", "actor:high_court_of_australia")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=subject_id,
                predicate_id=predicate_ids["appealed"],
                object_entity_id=court_id,
                confidence_tier=_predicate_confidence(conn, "appealed", receipts),
                receipts=receipts,
            )
    if "challeng" in text_fold:
        objects = []
        if court_id is not None:
            objects.append(court_id)
        objects.extend(entity_ids.get(key) or _entity_for_key(conn, key) for key in act_keys if (entity_ids.get(key) or _entity_for_key(conn, key)))
        for subject_id in subject_entity_ids:
            for object_id in objects:
                receipts = [("subject", str(subject_id)), ("verb", "challenged"), ("object", str(object_id))]
                _insert_relation_candidate(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    subject_entity_id=subject_id,
                    predicate_id=predicate_ids["challenged"],
                    object_entity_id=object_id,
                    confidence_tier=_predicate_confidence(conn, "challenged", receipts),
                    receipts=receipts,
                )
    subject_candidates: list[tuple[int, str]] = []
    for case_key in case_keys:
        case_id = entity_ids.get(case_key) or _entity_for_key(conn, case_key)
        if case_id is not None:
            subject_candidates.append((case_id, case_key))
    for subject_id in subject_entity_ids:
        subject_candidates.append((subject_id, str(subject_id)))
    seen_subjects: set[int] = set()
    normalized_subjects: list[tuple[int, str]] = []
    for sid, skey in subject_candidates:
        if sid in seen_subjects:
            continue
        seen_subjects.add(sid)
        normalized_subjects.append((sid, skey))

    if court_id is not None and ("heard by" in text_fold or "heard in" in text_fold or "before the high court" in text_fold):
        for subject_id, subject_key in normalized_subjects:
            receipts = [("subject", subject_key), ("verb", "heard_by"), ("object", "actor:high_court_of_australia")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=subject_id,
                predicate_id=predicate_ids["heard_by"],
                object_entity_id=court_id,
                confidence_tier=_predicate_confidence(conn, "heard_by", receipts),
                receipts=receipts,
            )
    if court_id is not None and ("held that" in text_fold or "held" in text_fold or "decided" in text_fold):
        for subject_id, subject_key in normalized_subjects:
            predicate = "held_that" if "held" in text_fold else "decided_by"
            receipts = [("subject", subject_key), ("verb", predicate), ("object", "actor:high_court_of_australia")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=subject_id,
                predicate_id=predicate_ids[predicate],
                object_entity_id=court_id,
                confidence_tier=_predicate_confidence(conn, predicate, receipts),
                receipts=receipts,
            )
            if predicate == "held_that":
                _insert_relation_candidate(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    subject_entity_id=subject_id,
                    predicate_id=predicate_ids["decided_by"],
                    object_entity_id=court_id,
                    confidence_tier="low",
                    receipts=[("subject", subject_key), ("verb", "decided_by"), ("object", "actor:high_court_of_australia"), ("support", "held_surface_proxy")],
                )
    if normalized_subjects:
        for subject_id, subject_key in normalized_subjects:
            if "applied" in text_fold:
                applied_targets = [key for key in legal_ref_keys if key != subject_key] + (["actor:high_court_of_australia"] if court_id is not None else [])
                for target_key in applied_targets:
                    target_id = entity_ids.get(target_key) or _entity_for_key(conn, target_key)
                    if target_id is None:
                        continue
                    receipts = [("subject", subject_key), ("verb", "applied"), ("object", target_key)]
                    _insert_relation_candidate(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        subject_entity_id=subject_id,
                        predicate_id=predicate_ids["applied"],
                        object_entity_id=target_id,
                        confidence_tier=_predicate_confidence(conn, "applied", receipts),
                        receipts=receipts,
                    )
            for predicate, cue in (("followed", "followed"), ("distinguished", "distinguished")):
                if cue not in text_fold:
                    continue
                target_case_keys = [key for key in case_keys if key != subject_key]
                for target_key in target_case_keys:
                    target_id = entity_ids.get(target_key) or _entity_for_key(conn, target_key)
                    if target_id is None:
                        continue
                    receipts = [("subject", subject_key), ("verb", predicate), ("object", target_key)]
                    _insert_relation_candidate(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        subject_entity_id=subject_id,
                        predicate_id=predicate_ids[predicate],
                        object_entity_id=target_id,
                        confidence_tier=_predicate_confidence(conn, predicate, receipts),
                        receipts=receipts,
                    )


def run_au_semantic_pipeline(conn, *, timeline_suffix: str = "wiki_timeline_hca_s942025_aoo.json", run_id: str | None = None) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    active_run_id = run_id or _pick_best_run_for_timeline_suffix(conn, timeline_suffix)
    if not active_run_id:
        raise ValueError(f"no wiki timeline run found for suffix {timeline_suffix}")
    run_au_semantic_linkage(conn, timeline_suffix=timeline_suffix, run_id=active_run_id)
    payload = load_run_payload_from_normalized(conn, active_run_id)
    if not payload:
        raise ValueError(f"unable to load normalized payload for run_id={active_run_id}")
    _delete_run_rows(conn, active_run_id)
    entity_ids = _seed_au_entities(conn)
    predicate_ids = _ensure_au_predicates(conn)
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    for event in events:
        if not isinstance(event, Mapping) or not event.get("event_id"):
            continue
        event_id = str(event["event_id"])
        mention_clusters = _detect_au_mentions_for_event(
            conn,
            run_id=active_run_id,
            event_id=event_id,
            event=event,
            entity_ids=entity_ids,
        )
        _extract_au_relations(
            conn,
            run_id=active_run_id,
            event_id=event_id,
            event=event,
            mention_clusters=mention_clusters,
            entity_ids=entity_ids,
            predicate_ids=predicate_ids,
        )
    entity_count = int(conn.execute("SELECT COUNT(*) FROM semantic_entities").fetchone()[0])
    candidate_count = int(conn.execute("SELECT COUNT(*) FROM semantic_relation_candidates WHERE run_id = ?", (active_run_id,)).fetchone()[0])
    promoted_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_relations
            WHERE candidate_id IN (SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?)
            """,
            (active_run_id,),
        ).fetchone()[0]
    )
    abstained_resolutions = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_mention_resolutions
            WHERE cluster_id IN (SELECT cluster_id FROM semantic_mention_clusters WHERE run_id = ?)
              AND resolution_status = 'abstained'
            """,
            (active_run_id,),
        ).fetchone()[0]
    )
    return {
        "run_id": active_run_id,
        "entity_count": entity_count,
        "relation_candidate_count": candidate_count,
        "promoted_relation_count": promoted_count,
        "abstained_resolution_count": abstained_resolutions,
    }


def _event_authority_hints(event: Mapping[str, Any], matches: list[Mapping[str, Any]]) -> dict[str, Any]:
    authority_titles: set[str] = set()
    legal_refs: set[str] = set()
    for match in matches:
        if not isinstance(match, Mapping):
            continue
        for receipt in match.get("receipts", []):
            if not isinstance(receipt, Mapping):
                continue
            reason_kind = str(receipt.get("reason_kind") or "")
            reason_value = str(receipt.get("reason_value") or "").strip()
            if not reason_value:
                continue
            if reason_kind == "authority_title":
                authority_titles.add(reason_value)
            elif reason_kind:
                legal_refs.add(reason_value)
    event_text = str(event.get("text") or "").strip()
    event_section = str(event.get("section") or "").strip()
    parts = [event_text, event_section]
    return {
        "text": "\n".join(part for part in parts if part),
        "event_text": event_text,
        "event_section": event_section,
        "authority_titles": sorted(authority_titles),
        "legal_refs": sorted(legal_refs),
    }


def _authority_term_tokens(authority_titles: Iterable[str], legal_refs: Iterable[str]) -> list[str]:
    tokens: set[str] = set()
    for raw in list(authority_titles) + [ref.split(":", 1)[-1].replace("_", " ") for ref in legal_refs]:
        for token in str(raw or "").replace("/", " ").replace("-", " ").split():
            normalized = "".join(ch for ch in token.casefold() if ch.isalnum())
            if len(normalized) < 4 or normalized in _AUTHORITY_TERM_STOPWORDS:
                continue
            tokens.add(normalized)
    return sorted(tokens)


def _conjecture_route_target(*, authority_titles: list[str], legal_refs: list[str], candidate_citations: list[str]) -> str:
    if candidate_citations and authority_titles:
        return "known_authority_fetch"
    if authority_titles:
        return "authority_title_resolution"
    if candidate_citations or legal_refs:
        return "citation_follow"
    return "manual_review"


def build_au_authority_receipt_context(
    conn,
    *,
    run_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    from src.fact_intake.read_model import build_authority_ingest_summary, list_authority_ingest_runs

    payload = load_run_payload_from_normalized(conn, run_id) or {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    linkage_report = __import__("src.au_semantic.linkage", fromlist=["build_au_semantic_linkage_report"]).build_au_semantic_linkage_report(conn, run_id=run_id)
    per_event_matches = {
        str(event.get("event_id") or ""): list(event.get("matches") or [])
        for event in linkage_report.get("per_event", [])
        if isinstance(event, Mapping) and event.get("event_id")
    }
    event_map = {
        str(event.get("event_id") or ""): event
        for event in events
        if isinstance(event, Mapping) and event.get("event_id")
    }
    event_hints = {
        event_id: _event_authority_hints(event_map[event_id], matches)
        for event_id, matches in per_event_matches.items()
        if event_id in event_map
    }
    for hints in event_hints.values():
        hint_text = str(hints.get("text") or "")
        hints["candidate_citations"] = [ref.raw_text for ref in extract_citations(hint_text)]
        hints["authority_term_tokens"] = _authority_term_tokens(
            hints.get("authority_titles", []),
            hints.get("legal_refs", []),
        )

    authority_runs = list_authority_ingest_runs(conn, limit=max(int(limit or 0), 0))
    items: list[dict[str, Any]] = []
    linked_event_ids_seen: set[str] = set()
    authority_kind_counts: Counter[str] = Counter()
    for run in authority_runs:
        summary = build_authority_ingest_summary(conn, ingest_run_id=str(run["ingest_run_id"]))
        run_payload = summary.get("run") if isinstance(summary.get("run"), Mapping) else {}
        segments = [segment for segment in summary.get("segments", []) if isinstance(segment, Mapping)]
        searchable_parts = [
            str(run_payload.get("citation") or ""),
            str(run_payload.get("query_text") or ""),
            str(run_payload.get("selection_reason") or ""),
            str(run_payload.get("resolved_url") or ""),
            str(run_payload.get("body_preview_text") or ""),
        ]
        for segment in segments:
            searchable_parts.append(str(segment.get("segment_text") or ""))
        searchable_text = _normalize_authority_text("\n".join(part for part in searchable_parts if part))
        detected_citations = sorted({ref.raw_text for ref in extract_citations("\n".join(part for part in searchable_parts if part))})

        linked_event_ids: list[str] = []
        matched_titles: set[str] = set()
        matched_refs: set[str] = set()
        for event_id, hints in event_hints.items():
            event_text = _normalize_authority_text(str(hints.get("text") or ""))
            titles = [str(title) for title in hints.get("authority_titles", [])]
            refs = [str(ref) for ref in hints.get("legal_refs", [])]
            title_hit = any(
                _normalize_authority_text(title) and _normalize_authority_text(title) in searchable_text
                for title in titles
            )
            ref_hit = any(
                (_normalize_authority_text(ref.split(":", 1)[-1].replace("_", " "))) in searchable_text
                for ref in refs
                if _normalize_authority_text(ref.split(":", 1)[-1].replace("_", " "))
            )
            citation_hit = bool(run_payload.get("citation")) and _normalize_authority_text(str(run_payload.get("citation"))) in event_text
            if title_hit or ref_hit or citation_hit:
                linked_event_ids.append(event_id)
                matched_titles.update(title for title in titles if _normalize_authority_text(title) in searchable_text)
                matched_refs.update(
                    ref
                    for ref in refs
                    if _normalize_authority_text(ref.split(":", 1)[-1].replace("_", " ")) in searchable_text
                )
        linked_event_ids = sorted(set(linked_event_ids))
        linked_event_ids_seen.update(linked_event_ids)
        authority_kind = str(run_payload.get("authority_kind") or "")
        if authority_kind:
            authority_kind_counts[authority_kind] += 1
        paragraph_numbers = [
            int(segment["paragraph_number"])
            for segment in segments
            if segment.get("paragraph_number") is not None
        ]
        segment_kinds = sorted(
            {
                str(segment.get("segment_kind") or "").strip()
                for segment in segments
                if str(segment.get("segment_kind") or "").strip()
            }
        )
        segment_previews = [
            {
                "segment_kind": str(segment.get("segment_kind") or ""),
                "paragraph_number": segment.get("paragraph_number"),
                "preview_text": str(segment.get("segment_text") or "")[:240],
            }
            for segment in segments[:3]
        ]
        linked_event_sections = sorted(
            {
                str(event_hints[event_id].get("event_section") or "").strip()
                for event_id in linked_event_ids
                if str(event_hints[event_id].get("event_section") or "").strip()
            }
        )
        route_targets = sorted(
            {
                _conjecture_route_target(
                    authority_titles=list(event_hints[event_id].get("authority_titles") or []),
                    legal_refs=list(event_hints[event_id].get("legal_refs") or []),
                    candidate_citations=sorted(
                        set(list(event_hints[event_id].get("candidate_citations") or []) + list(detected_citations))
                    ),
                )
                for event_id in linked_event_ids
            }
        )
        structured_summary = {
            "source_identity": {
                "authority_kind": authority_kind,
                "citation": run_payload.get("citation"),
                "resolved_url": str(run_payload.get("resolved_url") or ""),
                "ingest_mode": str(run_payload.get("ingest_mode") or ""),
            },
            "selected_paragraph_numbers": paragraph_numbers,
            "selected_paragraph_count": len(paragraph_numbers),
            "segment_count": len(segments),
            "selected_segment_kinds": segment_kinds,
            "selected_segment_previews": segment_previews,
            "linked_authority_signals": {
                "authority_titles": sorted(matched_titles),
                "legal_refs": sorted(matched_refs),
            },
            "linked_event_sections": linked_event_sections,
            "detected_neutral_citations": detected_citations,
            "authority_term_tokens": _authority_term_tokens(sorted(matched_titles), sorted(matched_refs)),
            "route_targets": route_targets,
            "body_preview_text": run_payload.get("body_preview_text"),
        }
        items.append(
            {
                "ingest_run_id": str(run_payload.get("ingest_run_id") or run["ingest_run_id"]),
                "authority_kind": authority_kind,
                "ingest_mode": str(run_payload.get("ingest_mode") or ""),
                "citation": run_payload.get("citation"),
                "query_text": run_payload.get("query_text"),
                "selection_reason": run_payload.get("selection_reason"),
                "resolved_url": str(run_payload.get("resolved_url") or ""),
                "segment_count": int(run_payload.get("segment_count") or 0),
                "linked_event_ids": linked_event_ids,
                "matched_authority_titles": sorted(matched_titles),
                "matched_legal_refs": sorted(matched_refs),
                "link_status": "linked" if linked_event_ids else "unlinked",
                "storage_basis": "sqlite",
                "created_at": str(run_payload.get("created_at") or ""),
                "structured_summary": structured_summary,
            }
        )

    follow_needed_events = [
        {
            "event_id": event_id,
            "event_section": str(hints.get("event_section") or ""),
            "event_text": str(hints.get("event_text") or "")[:240],
            "authority_titles": list(hints.get("authority_titles") or []),
            "legal_refs": list(hints.get("legal_refs") or []),
            "candidate_citations": list(hints.get("candidate_citations") or []),
            "authority_term_tokens": list(hints.get("authority_term_tokens") or []),
        }
        for event_id, hints in event_hints.items()
        if (hints.get("authority_titles") or hints.get("legal_refs")) and event_id not in linked_event_ids_seen
    ]
    follow_needed_conjectures: list[dict[str, Any]] = []
    for row in follow_needed_events:
        route_target = _conjecture_route_target(
            authority_titles=row["authority_titles"],
            legal_refs=row["legal_refs"],
            candidate_citations=row["candidate_citations"],
        )
        if row["authority_titles"]:
            follow_needed_conjectures.append(
                {
                    "conjecture_kind": "missing_authority_receipt_for_authority_title",
                    "event_id": row["event_id"],
                    "event_section": row["event_section"],
                    "event_text": row["event_text"],
                    "authority_titles": row["authority_titles"],
                    "legal_refs": row["legal_refs"],
                    "candidate_citations": row["candidate_citations"],
                    "authority_term_tokens": row["authority_term_tokens"],
                    "route_target": route_target,
                    "resolution_hint": (
                        "persist_or_link_known_authority_receipt"
                        if route_target == "known_authority_fetch"
                        else "resolve_authority_title_then_persist_receipt"
                    ),
                }
            )
        if row["legal_refs"]:
            follow_needed_conjectures.append(
                {
                    "conjecture_kind": "missing_authority_receipt_for_legal_ref",
                    "event_id": row["event_id"],
                    "event_section": row["event_section"],
                    "event_text": row["event_text"],
                    "authority_titles": row["authority_titles"],
                    "legal_refs": row["legal_refs"],
                    "candidate_citations": row["candidate_citations"],
                    "authority_term_tokens": row["authority_term_tokens"],
                    "route_target": route_target,
                    "resolution_hint": "follow_citation_or_link_authority_receipt",
                }
            )
    return {
        "summary": {
            "authority_receipt_count": len(items),
            "linked_receipt_count": sum(1 for item in items if item["linked_event_ids"]),
            "follow_needed_event_count": len(follow_needed_events),
            "conjecture_count": len(follow_needed_conjectures),
            "authority_kind_counts": dict(authority_kind_counts),
        },
        "items": items,
        "follow_needed_events": follow_needed_events,
        "follow_needed_conjectures": follow_needed_conjectures,
    }


def build_au_semantic_report(
    conn,
    *,
    run_id: str,
    include_authority_receipts: bool = True,
    authority_receipt_limit: int = 20,
) -> dict[str, Any]:
    report = build_gwb_semantic_report(conn, run_id=run_id)
    report["au_linkage"] = __import__("src.au_semantic.linkage", fromlist=["build_au_semantic_linkage_report"]).build_au_semantic_linkage_report(conn, run_id=run_id)
    if include_authority_receipts:
        report["authority_receipts"] = build_au_authority_receipt_context(
            conn,
            run_id=run_id,
            limit=authority_receipt_limit,
        )
    return report
