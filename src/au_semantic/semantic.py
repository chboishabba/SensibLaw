from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from src.au_semantic.linkage import run_au_semantic_linkage
from src.gwb_us_law.linkage import _pick_best_run_for_timeline_suffix
from src.gwb_us_law.semantic import (
    PIPELINE_VERSION,
    EntitySeed,
    _ensure_predicates,
    _entity_for_key,
    _insert_cluster_and_resolution,
    _insert_event_role,
    _insert_relation_candidate,
    _normalize_phrase,
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
_LEGAL_REP_ROLE_SURFACES = {
    "counsel for the appellant": "Counsel for Appellant",
    "counsel for the respondent": "Counsel for Respondent",
    "counsel for the applicant": "Counsel for Applicant",
    "counsel for the plaintiff": "Counsel for Plaintiff",
    "counsel for the defendant": "Counsel for Defendant",
    "senior counsel for the appellant": "Senior Counsel for Appellant",
    "senior counsel for the respondent": "Senior Counsel for Respondent",
    "senior counsel for the applicant": "Senior Counsel for Applicant",
    "senior counsel for the plaintiff": "Senior Counsel for Plaintiff",
    "senior counsel for the defendant": "Senior Counsel for Defendant",
    "junior counsel for the appellant": "Junior Counsel for Appellant",
    "junior counsel for the respondent": "Junior Counsel for Respondent",
    "appeared for the appellant": "Counsel for Appellant",
    "appeared for the respondent": "Counsel for Respondent",
    "appeared for the applicant": "Counsel for Applicant",
    "appeared for the plaintiff": "Counsel for Plaintiff",
    "appeared for the defendant": "Counsel for Defendant",
}


def _au_doc_actor_key(run_id: str, surface: str) -> str:
    slug = "_".join(surface.casefold().replace("/", " ").replace("-", " ").split())
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in slug).strip("_")
    return f"actor:doc:{run_id}:{cleaned}"


def _is_legal_rep_suffix_surface(text: str) -> bool:
    compact = " ".join(str(text or "").replace(".", "").split())
    return any(compact.endswith(suffix.strip()) for suffix in _LEGAL_REP_SUFFIXES)


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
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="office_context", entity_id=office_id, note="au_office_surface_v1")
    for surface, label in _LEGAL_REP_ROLE_SURFACES.items():
        if _text_contains_phrase(text, surface):
            entity_id = _ensure_doc_actor(
                conn,
                run_id=run_id,
                label=label,
                source_rule="au_legal_representative_v1",
                classification_tag="legal_representative",
            )
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_au_doc_actor_key(run_id, label),
                surface_text=surface,
                source_rule="au_legal_representative_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="document_local_legal_representative_v1",
                receipts=[("representative_surface", surface), ("scope", "document_local_actor")],
            )
            found[_au_doc_actor_key(run_id, label)].append(cluster_id)
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="legal_representative", entity_id=entity_id, note="au_legal_representative_v1")
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
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind=role_kind, entity_id=entity_id, note="au_case_role_v1")
    for token_index in range(len(text_lines) - 1):
        first = text_lines[token_index]
        second = text_lines[token_index + 1]
        candidate = f"{first} {second}".strip()
        candidate_three = ""
        if token_index + 2 < len(text_lines):
            candidate_three = f"{first} {second} {text_lines[token_index + 2]}".strip()
        if any(candidate.startswith(prefix) for prefix in _TITLE_PREFIXES):
            entity_id = _ensure_doc_actor(conn, run_id=run_id, label=candidate, source_rule="au_titled_person_v1")
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_au_doc_actor_key(run_id, candidate),
                surface_text=candidate,
                source_rule="au_titled_person_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="document_local_titled_person_v1",
                receipts=[("title_pattern", candidate), ("scope", "document_local_actor")],
            )
            found[_au_doc_actor_key(run_id, candidate)].append(cluster_id)
        if candidate_three and any(candidate_three.startswith(prefix) for prefix in _TITLE_PREFIXES) and _is_legal_rep_suffix_surface(candidate_three):
            entity_id = _ensure_doc_actor(
                conn,
                run_id=run_id,
                label=candidate_three,
                source_rule="au_named_legal_representative_v1",
                classification_tag="legal_representative",
            )
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_au_doc_actor_key(run_id, candidate_three),
                surface_text=candidate_three,
                source_rule="au_named_legal_representative_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="document_local_named_legal_representative_v1",
                receipts=[("title_suffix_pattern", candidate_three), ("scope", "document_local_actor")],
            )
            found[_au_doc_actor_key(run_id, candidate_three)].append(cluster_id)
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="legal_representative", entity_id=entity_id, note="au_named_legal_representative_v1")
        if _is_legal_rep_suffix_surface(candidate) and first[:1].isupper():
            entity_id = _ensure_doc_actor(
                conn,
                run_id=run_id,
                label=candidate,
                source_rule="au_suffix_legal_representative_v1",
                classification_tag="legal_representative",
            )
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_au_doc_actor_key(run_id, candidate),
                surface_text=candidate,
                source_rule="au_suffix_legal_representative_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="document_local_suffix_legal_representative_v1",
                receipts=[("suffix_pattern", candidate), ("scope", "document_local_actor")],
            )
            found[_au_doc_actor_key(run_id, candidate)].append(cluster_id)
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="legal_representative", entity_id=entity_id, note="au_suffix_legal_representative_v1")
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
    return found


def _predicate_confidence(predicate_key: str, receipts: list[tuple[str, str]]) -> str:
    kinds = {kind for kind, _ in receipts}
    if predicate_key in {"appealed", "challenged"} and {"subject", "verb", "object"} <= kinds:
        return "high"
    if predicate_key in {"heard_by", "decided_by", "applied", "followed", "distinguished", "held_that"} and {"subject", "verb", "object"} <= kinds:
        return "medium"
    if {"subject", "verb"} <= kinds:
        return "low"
    return "abstain"


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
                confidence_tier=_predicate_confidence("appealed", receipts),
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
                    confidence_tier=_predicate_confidence("challenged", receipts),
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
                confidence_tier=_predicate_confidence("heard_by", receipts),
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
                confidence_tier=_predicate_confidence(predicate, receipts),
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
                        confidence_tier=_predicate_confidence("applied", receipts),
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
                        confidence_tier=_predicate_confidence(predicate, receipts),
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


def build_au_semantic_report(conn, *, run_id: str) -> dict[str, Any]:
    report = build_gwb_semantic_report(conn, run_id=run_id)
    report["au_linkage"] = __import__("src.au_semantic.linkage", fromlist=["build_au_semantic_linkage_report"]).build_au_semantic_linkage_report(conn, run_id=run_id)
    return report
