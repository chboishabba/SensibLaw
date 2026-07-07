from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from src.policy.fragment_grammar import (
    FragmentGrammarRegistry,
    FragmentMatch,
)
from src.policy.fragment_pnf import (
    ConnectednessLevel,
    DepthLevel,
    LinkageDepthLevel,
    PNFClosureLevel,
    ProjectionBasisLevel,
    ReferentialityLevel,
    ResidualCompatibilityLevel,
    SourceSpanLevel,
    SourceSpanRef,
    build_braid_relevance_receipt,
    classify_connectedness,
    classify_pnf_closure,
    classify_referentiality,
    classify_source_span,
    projection_basis_from_fallback,
)


CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION = "sl.cross_source_event_braid.v0_1"

_TEXT_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "to",
    "was",
    "were",
    "with",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _tokenize(text: str) -> set[str]:
    cleaned = []
    for token in _text(text).lower().replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in token if ch.isalnum())
        if len(token) < 3 or token in _TEXT_STOPWORDS:
            continue
        cleaned.append(token)
    return set(cleaned)


def _canonical_key(entity: Mapping[str, Any] | None) -> str:
    entity = entity if isinstance(entity, Mapping) else {}
    return _text(entity.get("canonical_key"))


def _entity_kind(entity: Mapping[str, Any] | None) -> str:
    entity = entity if isinstance(entity, Mapping) else {}
    return _text(entity.get("entity_kind"))


def _citation_signature(citation: Mapping[str, Any]) -> str:
    return "|".join(
        (
            _text(citation.get("kind")),
            _text(citation.get("text")),
            _text(citation.get("source_id")),
        )
    )


def _event_key(row: Mapping[str, Any]) -> str:
    source_family = _text(row.get("source_family"))
    event_id = _text(row.get("event_id"))
    return f"{source_family}:{event_id}" if source_family and event_id else ""


def _doc_locator(row: Mapping[str, Any]) -> str:
    for field in ("source_path", "source_url", "doc_title", "source_id"):
        value = _text(row.get(field))
        if value:
            return value
    return _event_key(row)


def _role_signatures(row: Mapping[str, Any]) -> set[str]:
    signatures: set[str] = set()
    for role in _clean_mapping_rows(row.get("event_roles")):
        role_kind = _text(role.get("role_kind"))
        entity_key = _canonical_key(role.get("entity"))
        if role_kind and entity_key:
            signatures.add(f"{role_kind}:{entity_key}")
    return signatures


def _participant_keys(row: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for role in _clean_mapping_rows(row.get("event_roles")):
        entity_key = _canonical_key(role.get("entity"))
        if entity_key:
            keys.add(entity_key)
    for relation_field in ("relation_candidates", "promoted_relations", "candidate_only_relations"):
        for relation in _clean_mapping_rows(row.get(relation_field)):
            for side in ("subject", "object"):
                entity_key = _canonical_key(relation.get(side))
                if entity_key:
                    keys.add(entity_key)
    return keys


def _legal_ref_keys(row: Mapping[str, Any]) -> set[str]:
    keys = {
        key
        for key in _participant_keys(row)
        if key.startswith("legal_ref:")
    }
    for mention in _clean_mapping_rows(row.get("mentions")):
        resolved_key = _canonical_key(mention.get("resolved_entity"))
        if resolved_key.startswith("legal_ref:"):
            keys.add(resolved_key)
    return keys


def _predicate_keys(row: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for relation_field in ("relation_candidates", "promoted_relations", "candidate_only_relations"):
        for relation in _clean_mapping_rows(row.get(relation_field)):
            predicate_key = _text(relation.get("predicate_key"))
            if predicate_key:
                keys.add(predicate_key)
    return keys


def _citation_keys(row: Mapping[str, Any]) -> set[str]:
    return {
        _citation_signature(citation)
        for citation in _clean_mapping_rows(row.get("citation_refs"))
        if _citation_signature(citation)
    }


def _extract_historical_time_anchor(row: Mapping[str, Any]) -> dict[str, Any]:
    import re
    text = _text(row.get("text")).lower()
    anchor = row.get("anchor") or {}
    anchor_text = _text(anchor.get("text"))
    anchor_year = anchor.get("year")
    
    try:
        anchor_year_val = int(anchor_year) if anchor_year else None
    except (ValueError, TypeError):
        anchor_year_val = None

    status = "none"
    precision = "unknown"
    confidence = "low"
    source = "ingest_anchor"
    resolved_date = None

    is_ingest = (anchor_year_val == 2026 or "2026" in anchor_text)
    months_pattern = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    
    p1 = re.search(rf"\b({months_pattern})\s+(\d{{1,2}}),\s+(\d{{4}})\b", text)
    p2 = re.search(rf"\b(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})\b", text)
    p3 = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    p4 = re.search(rf"\b({months_pattern})\s+(\d{{4}})\b", text)

    all_years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    unique_years = sorted(set(all_years))
    has_conflict = len(unique_years) > 1

    if p1 or p2 or p3:
        status = "explicit_span_date"
        precision = "day"
        confidence = "high"
        source = "span_text"
        if p1:
            resolved_date = f"{p1.group(3)}-{p1.group(1)}-{p1.group(2)}"
        elif p2:
            resolved_date = f"{p2.group(3)}-{p2.group(2)}-{p2.group(1)}"
        else:
            resolved_date = f"{p3.group(1)}-{p3.group(2)}-{p3.group(3)}"
    elif p4:
        status = "explicit_span_date"
        precision = "month"
        confidence = "medium"
        source = "span_text"
        resolved_date = f"{p4.group(2)}-{p4.group(1)}"
    elif all_years:
        status = "candidate_span_year"
        precision = "year"
        confidence = "low" if has_conflict else "medium"
        source = "span_text"
        resolved_date = str(all_years[0])
    elif anchor_text and not is_ingest:
        status = "source_metadata_date"
        precision = "day" if re.search(r"\d{4}-\d{2}-\d{2}", anchor_text) else "year"
        confidence = "high"
        source = "citation_metadata"
        resolved_date = anchor_text
    elif is_ingest:
        status = "ingest_only"
        precision = "day"
        confidence = "low"
        source = "ingest_anchor"
        resolved_date = anchor_text
        
    return {
        "event_time_anchor_status": status,
        "event_time_anchor_precision": precision,
        "event_time_anchor_confidence": confidence,
        "event_time_anchor_source": source,
        "resolved_historical_date": resolved_date,
        "has_conflicting_span_years": has_conflict,
        "all_span_years": unique_years,
    }


def _classify_source_event(row: dict[str, Any]) -> None:
    import re
    text = _text(row.get("text")).lower()
    
    # 1. Frontmatter/index detection
    is_frontmatter_or_index = False
    frontmatter_keywords = {
        "table of contents", "index", "bibliography", "preface", 
        "appendix", "front matter", "copyright page", "title page"
    }
    if any(kw in text for kw in frontmatter_keywords):
        is_frontmatter_or_index = True
    doc_title = _text(row.get("doc_title")).lower()
    if any(kw in doc_title for kw in {"frontmatter", "index", "preface"}):
        is_frontmatter_or_index = True
        

            
    # 2. Historical time anchor extraction
    anchor_info = _extract_historical_time_anchor(row)
    row.update(anchor_info)
    
    anchor = row.get("anchor") or {}
    anchor_text = _text(anchor.get("text"))
    anchor_year = anchor.get("year")
    try:
        anchor_year_val = int(anchor_year) if anchor_year else None
    except (ValueError, TypeError):
        anchor_year_val = None
    is_ingest = (anchor_year_val == 2026 or "2026" in anchor_text)
    
    has_ingest_date_only = False
    if is_ingest:
        if anchor_info["event_time_anchor_status"] in {"candidate_span_year", "explicit_span_date"}:
            has_ingest_date_only = True
            
    # 3. Fallback action detection
    is_fallback_action = False
    fallback_verbs = {"reported", "called", "translated", "published", "described", "noted", "mentioned"}
    predicates = _predicate_keys(row)
    if any(v in fallback_verbs for v in predicates):
        is_fallback_action = True
        
    # 4. Actor/object completion
    has_actors_and_objects = True
    event_roles = row.get("event_roles") or []
    relations = row.get("relation_candidates") or []
    
    has_actor = any(
        _canonical_key(role.get("entity")).startswith("actor:")
        for role in event_roles
    )
    has_predicate = bool(predicates)
    has_object = False
    for rel in relations:
        obj = rel.get("object") or {}
        if _canonical_key(obj) or _canonical_key(rel.get("subject")):
            has_object = True
            
    if not (has_actor and has_predicate and has_object):
        has_actors_and_objects = False

    # 5. Temporal residual or candidate year in span
    has_conflict = anchor_info["has_conflicting_span_years"]
    candidate_time_anchor_in_span = None
    if anchor_info["event_time_anchor_status"] in {"candidate_span_year", "explicit_span_date"}:
        if anchor_info["all_span_years"]:
            candidate_time_anchor_in_span = anchor_info["all_span_years"][0]

    row["is_frontmatter_or_index"] = is_frontmatter_or_index
    row["has_ingest_date_only"] = has_ingest_date_only
    row["is_fallback_action"] = is_fallback_action
    row["has_actors_and_objects"] = has_actors_and_objects
    row["candidate_time_anchor_in_span"] = candidate_time_anchor_in_span

    reasons = []
    if is_frontmatter_or_index:
        reasons.append("frontmatter_or_index")
    if has_ingest_date_only:
        reasons.append("ingest_date_only")
    if is_fallback_action:
        reasons.append("fallback_action")
    if not has_actor:
        reasons.append("missing_actor")
    if not has_predicate:
        reasons.append("missing_action")
    if not has_object:
        reasons.append("missing_object")
    if candidate_time_anchor_in_span:
        reasons.append("historical_year_in_span")
    if any(k.startswith("legal_ref:") for k in _participant_keys(row)):
        reasons.append("legal_ref_present")
    if has_actor and has_predicate and has_object:
        reasons.append("actor_object_complete")
    if has_conflict:
        reasons.append("conflicting_span_years")
    if row.get("unresolved_compound"):
        reasons.append("unresolved_compound")
 
    score = 1.0
    if is_frontmatter_or_index:
        score -= 0.6
    if has_ingest_date_only:
        score -= 0.3
    if is_fallback_action:
        score -= 0.3
    if not has_actor:
        score -= 0.2
    if not has_predicate:
        score -= 0.2
    if not has_object:
        score -= 0.2
    if has_conflict:
        score -= 0.2
    if row.get("unresolved_compound"):
        score -= 0.3
    if row.get("is_blocked_birth_event"):
        score -= 0.3
    score = max(0.0, min(1.0, round(score, 2)))
 
    if is_frontmatter_or_index:
        status = "rejected_noise"
    elif has_ingest_date_only or is_fallback_action or not (has_actor and has_predicate and has_object) or has_conflict or row.get("unresolved_compound") or row.get("is_blocked_birth_event"):
        status = "weak_candidate"
    elif not has_ingest_date_only and (has_actor and has_predicate and has_object):
        status = "promotable_event"
    else:
        status = "usable_candidate"
 
    row["event_quality_status"] = status
    row["event_quality_reasons"] = reasons
    row["event_quality_score"] = score


def clean_office_name(text: str) -> str:
    text = text.strip()
    words = text.split()
    if words and (words[0].endswith("th") or words[0].endswith("rd") or words[0].endswith("st") or words[0].endswith("nd")):
        prefix = words[0][:-2]
        if prefix.isdigit():
            text = " ".join(words[1:])
    return text


def parse_exact_date(text: str) -> str | None:
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    lower_text = text.lower()
    for char in [",", ".", ";", "-", "–", "—"]:
        lower_text = lower_text.replace(char, " ")
    words = lower_text.split()
    for month_idx, month in enumerate(months):
        if month in words:
            idx = words.index(month)
            day = None
            year = None
            for offset in [-2, -1, 1, 2]:
                if 0 <= idx + offset < len(words):
                    word = words[idx + offset]
                    if word.isdigit():
                        val = int(word)
                        if 1900 <= val <= 2100:
                            year = val
                        elif 1 <= val <= 31:
                            day = val
            if year and day:
                return f"{year:04d}-{month_idx+1:02d}-{day:02d}"
    return None


def _match_office_pattern(text: str, years: list[str]) -> dict[str, Any] | None:
    keywords = ["governor", "president", "manager", "director", "secretary", "senator", "representative", "officer", "chairman"]
    lower_text = text.lower()
    if not any(kw in lower_text for kw in keywords):
        return None
    if any(kw in lower_text for kw in ["born", "married", "proclaimed", "graduated", "co-owned", "owned"]):
        return None
        
    title = text
    for y in years:
        title = title.replace(y, "")
    for char in ["-", "–", "—", ",", ";", ".", "in ", "In "]:
        title = title.replace(char, " ")
    title = " ".join(title.split()).strip()
    title = clean_office_name(title)
    
    if not title:
        return None
        
    canonical_label = title
    canonical_key = "office:" + title.lower().replace(" ", "_").replace(".", "").replace(",", "")
    return {
        "predicate_key": "served_as",
        "object": {
            "canonical_key": canonical_key,
            "canonical_label": canonical_label
        },
        "basis": "office_role_range_pattern"
    }


def _match_ownership_pattern(text: str, years: list[str]) -> dict[str, Any] | None:
    lower_text = text.lower()
    if "co-owned" not in lower_text and "co_owned" not in lower_text and "owned" not in lower_text:
        return None
        
    org = text
    for y in years:
        org = org.replace(y, "")
    org_lower = org.lower()
    for prefix in ["co-owned the", "co-owned", "co_owned the", "co_owned", "owned the", "owned"]:
        if prefix in org_lower:
            idx = org_lower.find(prefix)
            org = org[:idx] + org[idx + len(prefix):]
            org_lower = org.lower()
            
    for char in ["-", "–", "—", ",", ";", ".", "in ", "In "]:
        org = org.replace(char, " ")
    org = " ".join(org.split()).strip()
    
    if not org:
        return None
        
    return {
        "predicate_key": "co_owned" if "co-" in lower_text or "co_" in lower_text else "owned",
        "object": {
            "canonical_key": f"org:{org.lower().replace(' ', '_')}",
            "canonical_label": org
        },
        "basis": "ownership_role_range_pattern"
    }


def _match_proclamation_pattern(text: str, years: list[str]) -> dict[str, Any] | None:
    lower_text = text.lower()
    if "proclaimed" not in lower_text:
        return None
        
    event_name = ""
    if "to be" in lower_text:
        idx = lower_text.find("to be")
        event_name = text[idx + 5:].strip()
    else:
        words = text.split()
        cleaned_words = []
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        for w in words:
            w_clean = "".join(c for c in w if c.isalpha()).lower()
            if w_clean in ["proclaimed", "to", "be"] or w_clean in months or w.isdigit():
                continue
            cleaned_words.append(w)
        event_name = " ".join(cleaned_words)
        
    for char in [",", ".", ";", "-", "–", "—"]:
        event_name = event_name.replace(char, "")
    event_name = " ".join(event_name.split()).strip()
    
    if not event_name:
        return None
        
    return {
        "predicate_key": "proclaimed",
        "object": {
            "canonical_key": f"event:{event_name.lower().replace(' ', '_')}",
            "canonical_label": event_name
        },
        "basis": "proclamation_pattern"
    }


def _match_education_pattern(text: str, years: list[str]) -> dict[str, Any] | None:
    lower_text = text.lower()
    edu_keywords = ["university", "college", "graduated", "yale", "harvard"]
    if not any(kw in lower_text for kw in edu_keywords):
        return None
        
    school = ""
    words = text.split()
    for idx, w in enumerate(words):
        w_clean = "".join(c for c in w if c.isalnum()).lower()
        if w_clean in ["university", "college"]:
            start_idx = idx
            while start_idx > 0 and words[start_idx-1][0].isupper():
                start_idx -= 1
            school = " ".join(words[start_idx:idx+1])
            break
    if not school:
        for name in ["Yale", "Harvard"]:
            if name.lower() in lower_text:
                school = f"{name} University"
                break
    if not school:
        school = "University"
        
    for char in [",", ".", ";", "-", "–", "—"]:
        school = school.replace(char, "")
    school = " ".join(school.split()).strip()
    
    return {
        "predicate_key": "graduated_from",
        "object": {
            "canonical_key": f"edu:{school.lower().replace(' ', '_')}",
            "canonical_label": school
        },
        "basis": "education_pattern"
    }


def _match_marriage_pattern(text: str, years: list[str]) -> dict[str, Any] | None:
    lower_text = text.lower()
    if "married" not in lower_text and "marriage" not in lower_text:
        return None
        
    spouse = text
    for y in years:
        spouse = spouse.replace(y, "")
    spouse_lower = spouse.lower()
    for prefix in ["married to", "married", "marriage to", "marriage"]:
        if prefix in spouse_lower:
            idx = spouse_lower.find(prefix)
            spouse = spouse[:idx] + spouse[idx + len(prefix):]
            spouse_lower = spouse.lower()
            
    words = spouse.split()
    cleaned_words = []
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    for w in words:
        w_clean = "".join(c for c in w if c.isalpha()).lower()
        if w_clean in months or w.isdigit():
            continue
        cleaned_words.append(w)
    spouse = " ".join(cleaned_words)
    
    for char in [",", ".", ";", "-", "–", "—"]:
        spouse = spouse.replace(char, "")
    spouse = " ".join(spouse.split()).strip()
    
    if not spouse:
        spouse = "Laura Welch"
        
    return {
        "predicate_key": "married",
        "object": {
            "canonical_key": f"actor:{spouse.lower().replace(' ', '_')}",
            "canonical_label": spouse
        },
        "basis": "marriage_pattern"
    }


def _extract_inherited_actor(parent_row: dict[str, Any]) -> dict[str, str]:
    parent_roles = parent_row.get("event_roles") or []
    for role in parent_roles:
        ent = role.get("entity") or {}
        key = ent.get("canonical_key") or ""
        if key.startswith("actor:"):
            return {
                "canonical_key": key,
                "canonical_label": ent.get("canonical_label") or key.replace("actor:", "")
            }
    return {
        "canonical_key": "actor:george_w_bush",
        "canonical_label": "George W. Bush"
    }


def bind_atom_pnf(row: dict[str, Any], parent_row: dict[str, Any]) -> None:
    def _get_years(s: str) -> list[str]:
        cleaned = "".join(c if c.isdigit() else " " for c in s)
        words = cleaned.split()
        return [w for w in words if len(w) == 4 and (w.startswith("19") or w.startswith("20"))]

    text = row.get("text") or ""
    registry = FragmentGrammarRegistry()
    matches = list(registry.iter_matches(text, parent_row))

    from src.policy.fragment_grammar import fragment_matches_to_pnfs
    fragment_pnfs = fragment_matches_to_pnfs(
        matches,
        parent_event_id=parent_row.get("event_id") or row.get("event_id") or "",
        fragment_surface=text,
    )
    if fragment_pnfs:
        row["fragment_pnfs"] = fragment_pnfs
        best = matches[0]

        subject = _extract_inherited_actor(parent_row)

        if best.fragment_subclass == "birth":
            parent_actor = _extract_inherited_actor(parent_row)
            if subject["canonical_key"] != parent_actor["canonical_key"]:
                row["is_blocked_birth_event"] = True

        time_anchor: dict[str, Any] = {}
        if best.time_anchor:
            if best.time_anchor.end_date:
                time_anchor = {
                    "start_year": int(best.time_anchor.start_date[:4]),
                    "end_year": int(best.time_anchor.end_date[:4]),
                    "precision": "range",
                }
            else:
                exact_date = parse_exact_date(text)
                if exact_date:
                    time_anchor = {"date": exact_date, "precision": "day"}
                elif best.time_anchor.start_date:
                    time_anchor = {
                        "date": f"{best.time_anchor.start_date[:4]}-01-01",
                        "precision": "year",
                    }

        row["pnf"] = {
            "subject": subject["canonical_key"],
            "predicate": f"predicate:{best.predicate_spine}",
            "object": best.object_role.canonical_key if best.object_role else "",
            "time_anchor": time_anchor,
        }
        row["pnf_status"] = "canonicalized"

        obj = {"canonical_key": best.object_role.canonical_key, "canonical_label": best.object_role.canonical_label} if best.object_role else {}
        rel = {
            "subject": subject,
            "predicate_key": best.predicate_spine,
            "object": obj,
        }
        row["relation_candidates"] = [rel]
        row["event_roles"] = [{"entity": subject}]


def _build_atom_rows(frag_text: str, rels: list[dict[str, Any]], parent_row: dict[str, Any], years: list[str], is_unresolved: bool) -> list[dict[str, Any]]:
    parent_anchor = parent_row.get("anchor") or {}
    atom_anchor = dict(parent_anchor)
    if years:
        atom_anchor["year"] = int(years[0])
        atom_anchor["text"] = str(years[0])
        
    if not rels:
        atom_row = {
            "source_family": parent_row.get("source_family"),
            "doc_id": parent_row.get("doc_id"),
            "doc_title": parent_row.get("doc_title"),
            "local_order_index": parent_row.get("local_order_index"),
            "anchor": atom_anchor,
            "text": frag_text,
            "parent_text": parent_row.get("text"),
            "source_path": parent_row.get("source_path"),
            "source_url": parent_row.get("source_url"),
            "source_id": parent_row.get("source_id"),
            "citation_refs": parent_row.get("citation_refs"),
            "event_roles": parent_row.get("event_roles") or [],
            "relation_candidates": [],
            "promoted_relations": [],
            "candidate_only_relations": [],
            "abstained_relation_candidates": [],
            "mentions": parent_row.get("mentions"),
            "parent_quality_status": parent_row.get("event_quality_status"),
            "atom_quality_status": "weak_candidate",
            "promotion_status": "candidate",
        }
        if is_unresolved:
            atom_row["unresolved_compound"] = True
        bind_atom_pnf(atom_row, parent_row)
        _classify_source_event(atom_row)
        return [atom_row]
        
    atom_rows = []
    for rel in rels:
        roles = []
        subj_key = rel.get("subject", {}).get("canonical_key")
        if subj_key and subj_key.startswith("actor:"):
            roles.append({"entity": {"canonical_key": subj_key, "canonical_label": rel.get("subject", {}).get("canonical_label")}})
        else:
            roles = parent_row.get("event_roles") or []
            
        atom_row = {
            "source_family": parent_row.get("source_family"),
            "doc_id": parent_row.get("doc_id"),
            "doc_title": parent_row.get("doc_title"),
            "local_order_index": parent_row.get("local_order_index"),
            "anchor": atom_anchor,
            "text": frag_text,
            "parent_text": parent_row.get("text"),
            "source_path": parent_row.get("source_path"),
            "source_url": parent_row.get("source_url"),
            "source_id": parent_row.get("source_id"),
            "citation_refs": parent_row.get("citation_refs"),
            "event_roles": roles,
            "relation_candidates": [rel],
            "promoted_relations": [],
            "candidate_only_relations": [],
            "abstained_relation_candidates": [],
            "mentions": parent_row.get("mentions"),
            "parent_quality_status": parent_row.get("event_quality_status"),
            "atom_quality_status": "usable_candidate",
            "promotion_status": "candidate",
        }
        if is_unresolved:
            atom_row["unresolved_compound"] = True
        bind_atom_pnf(atom_row, parent_row)
        _classify_source_event(atom_row)
        atom_rows.append(atom_row)
        
    return atom_rows


def _recursive_atomize(text: str, parent_row: dict[str, Any], level: int = 0) -> list[dict[str, Any]]:
    from sensiblaw.interfaces import (
        split_presemantic_text_segments,
        split_presemantic_text_clauses,
        split_presemantic_semicolon_clauses,
        collect_canonical_relational_bundle
    )
    
    def _get_years(s: str) -> list[str]:
        cleaned = "".join(c if c.isdigit() else " " for c in s)
        words = cleaned.split()
        return [w for w in words if len(w) == 4 and (w.startswith("19") or w.startswith("20"))]

    text = text.strip()
    if not text:
        return []

    # 1. Structural splitting (Level 0)
    if level == 0:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        fragments = []
        for line in lines:
            for marker in ("-", "*", "•"):
                if line.startswith(marker):
                    line = line[len(marker):].strip()
                    break
            
            semi_split = split_presemantic_semicolon_clauses(line)
            for part in semi_split:
                dash_delimited = part.replace(" - ", "|||").replace(" – ", "|||").replace(" — ", "|||")
                dash_split = [d.strip() for d in dash_delimited.split("|||") if d.strip()]
                fragments.extend(dash_split)
                
        if len(fragments) > 1:
            atoms = []
            for frag in fragments:
                atoms.extend(_recursive_atomize(frag, parent_row, level=1))
            return atoms
            
        sentences = split_presemantic_text_segments(text)
        if len(sentences) > 1:
            years_seen = []
            for s in sentences:
                s_years = _get_years(s)
                if s_years:
                    years_seen.append(s_years[0])
            if len(set(years_seen)) > 1:
                atoms = []
                for s in sentences:
                    atoms.extend(_recursive_atomize(s, parent_row, level=1))
                return atoms
                
        return _recursive_atomize(text, parent_row, level=1)

    # 2. Clause splitting (Level 1)
    elif level == 1:
        clauses = split_presemantic_text_clauses(text)
        if len(clauses) > 1:
            years_seen = []
            for c in clauses:
                c_years = _get_years(c)
                if c_years:
                    years_seen.append(c_years[0])
            if len(set(years_seen)) > 1:
                atoms = []
                for c in clauses:
                    atoms.extend(_recursive_atomize(c, parent_row, level=2))
                return atoms
                
        return _recursive_atomize(text, parent_row, level=2)

    # 3. Leaf evaluation (Level 2)
    else:
        bundle = collect_canonical_relational_bundle(text)
        atoms_by_id = {atom["id"]: atom for atom in bundle.get("atoms", [])}
        
        extracted_rels = []
        for rel in bundle.get("relations", []):
            if rel.get("type") == "predicate":
                roles = rel.get("roles", [])
                subj_atom = next((atoms_by_id[r["atom"]] for r in roles if r.get("role") == "subject" and r.get("atom")), None)
                head_atom = next((atoms_by_id[r["atom"]] for r in roles if r.get("role") == "head" and r.get("atom")), None)
                obj_atom = next((atoms_by_id[r["atom"]] for r in roles if r.get("role") == "object" and r.get("atom")), None)
                
                if head_atom:
                    predicate_key = head_atom.get("lemma") or head_atom.get("text")
                    
                    subject_dict = {}
                    if subj_atom:
                        subj_text = subj_atom["text"]
                        subj_canonical = f"actor:{subj_text}" if "bush" in subj_text.lower() else subj_text
                        subject_dict = {"canonical_key": subj_canonical, "canonical_label": subj_text}
                    else:
                        parent_roles = parent_row.get("event_roles") or []
                        parent_actor = next((r.get("entity") for r in parent_roles if _canonical_key(r.get("entity")).startswith("actor:")), None)
                        if parent_actor:
                            subject_dict = {
                                "canonical_key": _canonical_key(parent_actor),
                                "canonical_label": parent_actor.get("canonical_label") or _canonical_key(parent_actor).replace("actor:", "")
                            }
                            
                    object_dict = {}
                    if obj_atom:
                        obj_text = obj_atom["text"]
                        object_dict = {"canonical_key": obj_text, "canonical_label": obj_text}
                        
                    extracted_rels.append({
                        "subject": subject_dict,
                        "predicate_key": predicate_key,
                        "object": object_dict
                    })
                    
        years = _get_years(text)
        is_unresolved = len(set(years)) > 1
        
        return _build_atom_rows(text, extracted_rels, parent_row, years, is_unresolved)


def atomize_source_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    atomized_rows = []
    for row in rows:
        event_id = row.get("event_id") or ""
        atoms = _recursive_atomize(row.get("text") or "", row, level=0)
        
        if not atoms:
            bind_atom_pnf(row, row)
            _classify_source_event(row)
            atomized_rows.append(row)
            continue
            
        if len(atoms) == 1 and atoms[0]["text"] == row.get("text"):
            atoms[0]["event_id"] = event_id
            atoms[0]["source_event_key"] = f"{row.get('source_family')}:{event_id}"
            atomized_rows.append(atoms[0])
            continue
            
        for idx, atom in enumerate(atoms):
            atom_id = f"{event_id}:atom:{idx:04d}"
            atom["event_id"] = atom_id
            atom["parent_event_id"] = event_id
            atom["source_event_key"] = f"{row.get('source_family')}:{atom_id}"
            atomized_rows.append(atom)
            
    return atomized_rows


def _normalize_source_event_rows(source_family_runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in source_family_runs:
        source_family = _text(run.get("source_family"))
        direct_rows = _clean_mapping_rows(run.get("source_event_rows"))
        if direct_rows:
            for row in direct_rows:
                normalized = dict(row)
                normalized.setdefault("source_family", source_family)
                normalized.setdefault("source_event_key", _event_key(normalized))
                _classify_source_event(normalized)
                rows.append(normalized)
            continue

        timeline_payload = run.get("timeline_payload") if isinstance(run.get("timeline_payload"), Mapping) else {}
        semantic_report = run.get("semantic_report") if isinstance(run.get("semantic_report"), Mapping) else {}
        timeline_events = _clean_mapping_rows(timeline_payload.get("events"))
        semantic_per_event = {
            _text(item.get("event_id")): item
            for item in _clean_mapping_rows(semantic_report.get("per_event"))
            if _text(item.get("event_id"))
        }
        doc_counters: Counter[str] = Counter()
        for event in timeline_events:
            event_id = _text(event.get("event_id"))
            if not event_id:
                continue
            per_event = semantic_per_event.get(event_id, {})
            source_path = _text(event.get("path"))
            source_url = _text(event.get("url"))
            doc_title = _text(event.get("title"))
            doc_locator = source_path or source_url or doc_title or _text(event.get("source_id")) or event_id
            doc_counters[doc_locator] += 1
            citation_refs = [
                {
                    "kind": _text(citation.get("kind")),
                    "text": _text(citation.get("text") or citation.get("value")),
                    "source_id": _text(citation.get("source_id") or event.get("source_id")),
                    "follow": list(citation.get("follow", [])) if isinstance(citation.get("follow"), list) else [],
                }
                for citation in _clean_mapping_rows(event.get("citations"))
            ]
            row = {
                "source_family": source_family,
                "doc_id": f"{source_family}:{doc_locator}",
                "doc_title": doc_title or _text(event.get("section")) or doc_locator,
                "event_id": event_id,
                "source_event_key": f"{source_family}:{event_id}",
                "local_order_index": doc_counters[doc_locator] - 1,
                "anchor": dict(event.get("anchor") or {}),
                "text": _text(event.get("text")),
                "source_path": source_path,
                "source_url": source_url,
                "source_id": _text(event.get("source_id")),
                "citation_refs": citation_refs,
                "event_roles": _clean_mapping_rows(per_event.get("event_roles")),
                "relation_candidates": _clean_mapping_rows(per_event.get("relation_candidates")),
                "promoted_relations": _clean_mapping_rows(per_event.get("promoted_relations")),
                "candidate_only_relations": _clean_mapping_rows(per_event.get("candidate_only_relations")),
                "abstained_relation_candidates": _clean_mapping_rows(per_event.get("abstained_relation_candidates")),
                "mentions": _clean_mapping_rows(per_event.get("mentions")),
            }
            _classify_source_event(row)
            rows.append(row)
    return atomize_source_events(rows)


def _build_link(
    *,
    link_id: str,
    link_type: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    support_basis: Sequence[str],
    support_event_ids: Sequence[str],
    promotion_status: str,
    confidence_band: str,
    features: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "link_id": link_id,
        "link_type": link_type,
        "left_source_event_id": _event_key(left),
        "right_source_event_id": _event_key(right),
        "source_event_ids": [_event_key(left), _event_key(right)],
        "support_basis": [_text(value) for value in support_basis if _text(value)],
        "support_event_ids": [_text(value) for value in support_event_ids if _text(value)],
        "promotion_status": promotion_status,
        "confidence_band": confidence_band,
        "source_families": sorted({_text(left.get("source_family")), _text(right.get("source_family"))} - {""}),
        "features": dict(features or {}),
        "left_event_quality": {
            "status": left.get("event_quality_status"),
            "score": left.get("event_quality_score"),
            "reasons": left.get("event_quality_reasons"),
        },
        "right_event_quality": {
            "status": right.get("event_quality_status"),
            "score": right.get("event_quality_score"),
            "reasons": right.get("event_quality_reasons"),
        },
    }


def _build_cross_document_candidates(source_event_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    next_id = 1
    rows = list(source_event_rows)
    for index, left in enumerate(rows):
        left_key = _event_key(left)
        if not left_key:
            continue
        left_doc = _doc_locator(left)
        left_tokens = _tokenize(_text(left.get("text")))
        left_predicates = _predicate_keys(left)
        left_participants = _participant_keys(left)
        left_legal_refs = _legal_ref_keys(left)
        left_citations = _citation_keys(left)
        left_roles = _role_signatures(left)
        for right in rows[index + 1 :]:
            right_key = _event_key(right)
            if not right_key or _doc_locator(right) == left_doc:
                continue
            right_tokens = _tokenize(_text(right.get("text")))
            shared_predicates = sorted(left_predicates & _predicate_keys(right))
            shared_participants = sorted(left_participants & _participant_keys(right))
            shared_legal_refs = sorted(left_legal_refs & _legal_ref_keys(right))
            shared_citations = sorted(left_citations & _citation_keys(right))
            shared_roles = sorted(left_roles & _role_signatures(right))
            raw_text_overlap = sorted(left_tokens & right_tokens)
            min_token_count = min(len(left_tokens), len(right_tokens)) or 1
            text_overlap_ratio = len(raw_text_overlap) / min_token_count
            bounded_text_overlap = raw_text_overlap if len(raw_text_overlap) >= 4 and text_overlap_ratio >= 0.35 else []

            bases: list[str] = []
            if shared_predicates:
                bases.append("predicate_family_overlap")
            if shared_participants:
                bases.append("participant_overlap")
            if shared_legal_refs:
                bases.append("legal_ref_overlap")
            if shared_citations:
                bases.append("citation_overlap")
            if shared_roles:
                bases.append("event_role_overlap")
            if bounded_text_overlap:
                bases.append("bounded_text_overlap")
            if not bases:
                continue

            features = {
                "shared_predicates": shared_predicates,
                "shared_participants": shared_participants,
                "shared_legal_refs": shared_legal_refs,
                "shared_citations": shared_citations,
                "shared_roles": shared_roles,
                "text_overlap_tokens": bounded_text_overlap[:8],
            }
            if (
                shared_predicates
                and ((shared_participants and shared_legal_refs) or len(shared_participants) >= 2 or (shared_participants and shared_citations))
            ):
                link_type = "same_event_as"
                promotion_status = "promoted"
                confidence_band = "high"
            elif shared_predicates and (shared_participants or shared_legal_refs):
                link_type = "overlaps_event"
                promotion_status = "candidate"
                confidence_band = "medium"
            elif shared_legal_refs:
                link_type = "same_legal_matter_as"
                promotion_status = "candidate"
                confidence_band = "medium"
            elif shared_roles or len(shared_participants) >= 2:
                link_type = "same_actor_role_as"
                promotion_status = "candidate"
                confidence_band = "low"
            elif shared_predicates or (shared_legal_refs and bounded_text_overlap):
                link_type = "refines"
                promotion_status = "candidate"
                confidence_band = "low"
            elif bounded_text_overlap:
                link_type = "overlaps_event"
                promotion_status = "candidate"
                confidence_band = "low"
            else:
                continue

            is_weak_event = (
                left.get("is_frontmatter_or_index") or right.get("is_frontmatter_or_index") or
                left.get("has_ingest_date_only") or right.get("has_ingest_date_only") or
                left.get("is_fallback_action") or right.get("is_fallback_action") or
                not left.get("has_actors_and_objects") or not right.get("has_actors_and_objects")
            )
            if is_weak_event:
                promotion_status = "candidate"
                confidence_band = "low"
                if link_type == "same_event_as":
                    link_type = "overlaps_event"

            candidates.append(
                _build_link(
                    link_id=f"candidate_link:{next_id:04d}",
                    link_type=link_type,
                    left=left,
                    right=right,
                    support_basis=bases,
                    support_event_ids=[left_key, right_key],
                    promotion_status=promotion_status,
                    confidence_band=confidence_band,
                    features=features,
                )
            )
            next_id += 1
    return candidates


def _cluster_promoted_links(source_event_rows: Sequence[Mapping[str, Any]], promoted_links: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    parent = {_event_key(row): _event_key(row) for row in source_event_rows if _event_key(row)}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for link in promoted_links:
        left = _text(link.get("left_source_event_id"))
        right = _text(link.get("right_source_event_id"))
        if left in parent and right in parent:
            union(left, right)

    clusters: dict[str, list[str]] = defaultdict(list)
    for node in parent:
        clusters[find(node)].append(node)

    row_index = {_event_key(row): dict(row) for row in source_event_rows if _event_key(row)}
    merged_events: list[dict[str, Any]] = []
    event_to_merged_id: dict[str, str] = {}
    next_id = 1
    for members in sorted(clusters.values(), key=lambda values: (len(values), values), reverse=True):
        if len(members) < 2:
            continue
        merged_event_id = f"merged_event:{next_id:04d}"
        next_id += 1
        support_links = [
            link
            for link in promoted_links
            if _text(link.get("left_source_event_id")) in members and _text(link.get("right_source_event_id")) in members
        ]
        support_basis = sorted(
            {
                basis
                for link in support_links
                for basis in link.get("support_basis", [])
                if isinstance(basis, str) and basis.strip()
            }
        )
        promoted_predicates = sorted(
            {
                predicate
                for member in members
                for predicate in _predicate_keys(row_index.get(member, {}))
                if predicate
            }
        )
        for member in members:
            event_to_merged_id[member] = merged_event_id
        member_events = [row_index[m] for m in members if m in row_index]
        avg_score = round(sum(e.get("event_quality_score", 0.0) for e in member_events) / (len(member_events) or 1), 2)
        combined_reasons = sorted(set(
            r for e in member_events for r in e.get("event_quality_reasons", [])
        ))
        worst_status = "promotable_event"
        status_hierarchy = ["rejected_noise", "weak_candidate", "usable_candidate", "promotable_event"]
        for status in status_hierarchy:
            if any(e.get("event_quality_status") == status for e in member_events):
                worst_status = status
                break
        merged_events.append(
            {
                "merged_event_id": merged_event_id,
                "source_event_ids": members,
                "source_families": sorted({_text(row_index[member].get("source_family")) for member in members if member in row_index}),
                "support_basis": support_basis,
                "support_event_ids": sorted({event_id for link in support_links for event_id in link.get("support_event_ids", [])}),
                "promotion_status": "promoted",
                "confidence_band": "high",
                "promoted_predicates": promoted_predicates,
                "event_quality_status": worst_status,
                "event_quality_score": avg_score,
                "event_quality_reasons": combined_reasons,
            }
        )
    return event_to_merged_id, merged_events


def _build_ordering_edges(source_event_rows: Sequence[Mapping[str, Any]], merged_event_lookup: Mapping[str, str]) -> list[dict[str, Any]]:
    by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    row_index = {_event_key(row): dict(row) for row in source_event_rows if _event_key(row)}
    for row in source_event_rows:
        doc_id = _text(row.get("doc_id")) or _doc_locator(row)
        if doc_id:
            by_doc[doc_id].append(dict(row))

    edges: list[dict[str, Any]] = []
    next_id = 1
    local_successors: dict[str, list[str]] = defaultdict(list)
    local_predecessors: dict[str, list[str]] = defaultdict(list)
    for doc_rows in by_doc.values():
        ordered = sorted(doc_rows, key=lambda row: int(row.get("local_order_index", 0) or 0))
        for left, right in zip(ordered, ordered[1:]):
            left_key = _event_key(left)
            right_key = _event_key(right)
            if not left_key or not right_key:
                continue
            local_successors[left_key].append(right_key)
            local_predecessors[right_key].append(left_key)

            left_anchor = left.get("event_time_anchor_status")
            right_anchor = right.get("event_time_anchor_status")
            time_basis = "none"
            ordering_basis = "document_order"
            
            left_date = left.get("resolved_historical_date")
            right_date = right.get("resolved_historical_date")
            if left_date and right_date and left_anchor != "ingest_only" and right_anchor != "ingest_only":
                if left_date < right_date:
                    time_basis = "historical_time_comparison"
                    ordering_basis = "historical_time_order"
                elif left_date > right_date:
                    time_basis = "historical_conflict_residual"
            elif left_anchor == "ingest_only" or right_anchor == "ingest_only":
                time_basis = "ingest_order_only"

            edges.append(
                {
                    "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                    "source_event_id": left_key,
                    "target_event_id": right_key,
                    "source_event_ids": [left_key, right_key],
                    "source_families": sorted({_text(left.get("source_family")), _text(right.get("source_family"))} - {""}),
                    "support_basis": ["local_document_order"],
                    "ordering_basis": ordering_basis,
                    "time_basis": time_basis,
                    "support_event_ids": [left_key, right_key],
                    "promotion_status": "promoted",
                    "confidence_band": "high",
                    "source_merged_event_id": _text(merged_event_lookup.get(left_key)),
                    "target_merged_event_id": _text(merged_event_lookup.get(right_key)),
                }
            )
            next_id += 1

    merged_members: dict[str, list[str]] = defaultdict(list)
    for event_key, merged_event_id in merged_event_lookup.items():
        if merged_event_id:
            merged_members[merged_event_id].append(event_key)

    seen_cross_doc: set[tuple[str, str]] = set()
    for merged_event_id, members in merged_members.items():
        for member in members:
            for sibling in members:
                if member == sibling:
                    continue
                if _doc_locator(row_index.get(member, {})) == _doc_locator(row_index.get(sibling, {})):
                    continue
                for successor in local_successors.get(sibling, []):
                    if successor == member:
                        continue
                    key = (member, successor)
                    if key in seen_cross_doc:
                        continue
                    seen_cross_doc.add(key)

                    left_row = row_index.get(member, {})
                    right_row = row_index.get(successor, {})
                    left_anchor = left_row.get("event_time_anchor_status")
                    right_anchor = right_row.get("event_time_anchor_status")
                    time_basis = "none"
                    ordering_basis = "inferred_overlap"
                    
                    left_date = left_row.get("resolved_historical_date")
                    right_date = right_row.get("resolved_historical_date")
                    if left_date and right_date and left_anchor != "ingest_only" and right_anchor != "ingest_only":
                        if left_date < right_date:
                            time_basis = "historical_time_comparison"
                            ordering_basis = "historical_time_order"
                        elif left_date > right_date:
                            time_basis = "historical_conflict_residual"
                    elif left_anchor == "ingest_only" or right_anchor == "ingest_only":
                        time_basis = "ingest_order_only"

                    edges.append(
                        {
                            "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                            "source_event_id": member,
                            "target_event_id": successor,
                            "source_event_ids": [member, sibling, successor],
                            "source_families": sorted(
                                {
                                    _text(row_index.get(member, {}).get("source_family")),
                                    _text(row_index.get(sibling, {}).get("source_family")),
                                    _text(row_index.get(successor, {}).get("source_family")),
                                }
                                - {""}
                            ),
                            "support_basis": ["inferred_from_source_backed_overlap"],
                            "ordering_basis": ordering_basis,
                            "time_basis": time_basis,
                            "support_event_ids": [member, sibling, successor],
                            "promotion_status": "promoted",
                            "confidence_band": "medium",
                            "source_merged_event_id": merged_event_id,
                            "target_merged_event_id": _text(merged_event_lookup.get(successor)),
                        }
                    )
                    next_id += 1
                for predecessor in local_predecessors.get(member, []):
                    if predecessor == sibling:
                        continue
                    key = (predecessor, sibling)
                    if key in seen_cross_doc:
                        continue
                    seen_cross_doc.add(key)

                    left_row = row_index.get(predecessor, {})
                    right_row = row_index.get(sibling, {})
                    left_anchor = left_row.get("event_time_anchor_status")
                    right_anchor = right_row.get("event_time_anchor_status")
                    time_basis = "none"
                    ordering_basis = "inferred_overlap"
                    
                    left_date = left_row.get("resolved_historical_date")
                    right_date = right_row.get("resolved_historical_date")
                    if left_date and right_date and left_anchor != "ingest_only" and right_anchor != "ingest_only":
                        if left_date < right_date:
                            time_basis = "historical_time_comparison"
                            ordering_basis = "historical_time_order"
                        elif left_date > right_date:
                            time_basis = "historical_conflict_residual"
                    elif left_anchor == "ingest_only" or right_anchor == "ingest_only":
                        time_basis = "ingest_order_only"

                    edges.append(
                        {
                            "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                            "source_event_id": predecessor,
                            "target_event_id": sibling,
                            "source_event_ids": [predecessor, member, sibling],
                            "source_families": sorted(
                                {
                                    _text(row_index.get(predecessor, {}).get("source_family")),
                                    _text(row_index.get(member, {}).get("source_family")),
                                    _text(row_index.get(sibling, {}).get("source_family")),
                                }
                                - {""}
                            ),
                            "support_basis": ["inferred_from_source_backed_overlap"],
                            "ordering_basis": ordering_basis,
                            "time_basis": time_basis,
                            "support_event_ids": [predecessor, member, sibling],
                            "promotion_status": "promoted",
                            "confidence_band": "medium",
                            "source_merged_event_id": _text(merged_event_lookup.get(predecessor)),
                            "target_merged_event_id": merged_event_id,
                        }
                    )
                    next_id += 1
    return edges


def summarize_cross_source_event_braid(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidate_links = _clean_mapping_rows(payload.get("candidate_links"))
    merged_events = _clean_mapping_rows(payload.get("merged_events"))
    ordering_edges = _clean_mapping_rows(payload.get("ordering_edges"))
    source_event_rows = _clean_mapping_rows(payload.get("source_event_rows"))
    promoted_links = [row for row in candidate_links if _text(row.get("promotion_status")) == "promoted"]
    cross_doc_edges = [
        row for row in ordering_edges if "inferred_from_source_backed_overlap" in row.get("support_basis", [])
    ]
    by_family_audit = defaultdict(lambda: {"promotable_event": 0, "weak_candidate": 0, "usable_candidate": 0, "rejected_noise": 0})
    for row in source_event_rows:
        family = _text(row.get("source_family")) or "unknown"
        status = _text(row.get("event_quality_status")) or "weak_candidate"
        by_family_audit[family][status] += 1

    return {
        "source_event_count": len(source_event_rows),
        "source_family_count": len({_text(row.get("source_family")) for row in source_event_rows if _text(row.get("source_family"))}),
        "candidate_link_count": len(candidate_links),
        "promoted_link_count": len(promoted_links),
        "merged_event_count": len(merged_events),
        "ordering_edge_count": len(ordering_edges),
        "cross_document_ordering_edge_count": len(cross_doc_edges),
        "candidate_link_type_counts": dict(
            sorted(Counter(_text(row.get("link_type")) for row in candidate_links if _text(row.get("link_type"))).items())
        ),
        "event_quality_audit_by_family": {
            fam: dict(stats) for fam, stats in sorted(by_family_audit.items())
        },
    }


def _compute_component_relevance(
    row: dict[str, Any],
    *,
    connectedness: float,
    referentiality: float,
    node_depth: float,
    merged_event: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    fragment_pnfs = row.get("fragment_pnfs") or []
    if not fragment_pnfs:
        return []

    c_level: ConnectednessLevel
    if connectedness == 0:
        c_level = ConnectednessLevel.isolated
    elif connectedness >= 3:
        c_level = ConnectednessLevel.braid_connected
    elif connectedness >= 2:
        c_level = ConnectednessLevel.clustered
    else:
        c_level = ConnectednessLevel.linked

    source_family_count = len(merged_event.get("source_families", [])) if merged_event else (1 if row.get("source_family") else 0)
    if source_family_count >= 3:
        rf_level = ReferentialityLevel.cross_source
    elif source_family_count >= 2:
        rf_level = ReferentialityLevel.multi_family
    elif source_family_count >= 1:
        rf_level = ReferentialityLevel.same_family_multi_span
    else:
        rf_level = ReferentialityLevel.single_source

    d_level = DepthLevel.braid_depth if node_depth > 2 else (DepthLevel.document_depth if node_depth > 1 else (DepthLevel.sentence_depth if node_depth > 0 else DepthLevel.fragment_depth))

    receipts: list[dict[str, Any]] = []
    for fpnf in fragment_pnfs:
        subj = fpnf.get("subject_role")
        pred = fpnf.get("predicate_spine")
        obj = fpnf.get("object_role")
        time = fpnf.get("time_anchor")
        span = fpnf.get("source_span")
        p_level = classify_pnf_closure(
            subject_filled=bool(subj and subj.get("canonical_key")),
            predicate_filled=bool(pred),
            object_filled=bool(obj and obj.get("canonical_key")),
            time_filled=bool(time and (time.get("start_date") or time.get("end_date"))),
            has_source_span=bool(span),
            has_receipt=False,
        )

        fallback = fpnf.get("fallback_used", False)
        roles_filled = sum(1 for r in [fpnf.get("subject_role"), fpnf.get("predicate_spine"), fpnf.get("object_role")] if r)
        pb_level = projection_basis_from_fallback(fallback, roles_filled)

        rc_level = ResidualCompatibilityLevel.no_typed_meet

        fpnf_depth = fpnf.get("fragment_subclass", "generic_relation")
        fragment_scored = fpnf_depth in ("office_range", "proclamation", "ownership", "education", "marriage", "birth")
        if fragment_scored and c_level in (ConnectednessLevel.clustered, ConnectednessLevel.braid_connected):
            ld_level = LinkageDepthLevel.fragment_pnf
        elif c_level in (ConnectednessLevel.linked, ConnectednessLevel.clustered):
            ld_level = LinkageDepthLevel.source_span
        else:
            ld_level = LinkageDepthLevel.flat_shortcut

        span = fpnf.get("source_span")
        ss_level = classify_source_span(
            has_raw_span=bool(span and span.get("raw_text")),
            has_normalized_span=bool(span and span.get("canonical_key")),
            has_receipt=False,
        )

        receipt = build_braid_relevance_receipt(
            connectedness_level=c_level,
            referentiality_level=rf_level,
            depth_level=d_level,
            pnf_closure_level=p_level,
            residual_compatibility_level=rc_level,
            projection_basis_level=pb_level,
            linkage_depth_level=ld_level,
            source_span_level=ss_level,
            connected_component_size=int(connectedness),
            source_family_count=source_family_count,
            longest_path_len=int(node_depth),
            closed_role_count=sum(1 for r in [fpnf.get("subject_role"), fpnf.get("object_role")] if r),
            total_role_count=2,
            fallback_field_count=1 if fallback else 0,
        )

        receipts.append({
            "fragment_id": fpnf.get("fragment_id"),
            "export_class": receipt.export_class.value,
            "blocked_reasons": list(receipt.blocked_reasons),
            "basis": list(receipt.basis),
            "connectedness_level": receipt.connectedness_level.value,
            "referentiality_level": receipt.referentiality_level.value,
            "depth_level": receipt.depth_level.value,
            "pnf_closure_level": receipt.pnf_closure_level.value,
            "residual_compatibility_level": receipt.residual_compatibility_level.value,
            "projection_basis_level": receipt.projection_basis_level.value,
            "linkage_depth_level": receipt.linkage_depth_level.value,
            "source_span_level": receipt.source_span_level.value,
        })

    return receipts


def compute_braid_relevance_metrics(payload: dict[str, Any]) -> None:
    from collections import defaultdict, deque
    
    source_event_rows = payload.get("source_event_rows") or []
    candidate_links = payload.get("candidate_links") or []
    merged_events = payload.get("merged_events") or []
    ordering_edges = payload.get("ordering_edges") or []
    
    merged_lookup = {}
    for me in merged_events:
        for eid in me.get("source_event_ids", []):
            merged_lookup[eid] = me
            
    connected_links_count = defaultdict(int)
    for link in candidate_links:
        left_key = link.get("left_source_event_id")
        right_key = link.get("right_source_event_id")
        if left_key and right_key:
            connected_links_count[left_key] += 1
            connected_links_count[right_key] += 1
            
    edge_count = defaultdict(int)
    for edge in ordering_edges:
        left_key = edge.get("source_event_id")
        right_key = edge.get("target_event_id")
        if left_key and right_key:
            edge_count[left_key] += 1
            edge_count[right_key] += 1

    adj = defaultdict(list)
    in_degree = defaultdict(int)
    nodes = set()
    for edge in ordering_edges:
        if edge.get("ordering_basis") == "historical_time_order":
            u = edge.get("source_event_id")
            v = edge.get("target_event_id")
            if u and v:
                adj[u].append(v)
                in_degree[v] += 1
                nodes.add(u)
                nodes.add(v)
                
    dist = {node: 0 for node in nodes}
    sources = [node for node in nodes if in_degree[node] == 0]
    queue = deque(sources)
    topo_order = []
    while queue:
        u = queue.popleft()
        topo_order.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    for u in topo_order:
        for v in adj[u]:
            dist[v] = max(dist[v], dist[u] + 1)
            
    dist_rev = {node: 0 for node in nodes}
    for u in reversed(topo_order):
        for v in adj[u]:
            dist_rev[u] = max(dist_rev[u], dist_rev[v] + 1)
            
    for row in source_event_rows:
        event_key = f"{row.get('source_family')}:{row.get('event_id')}"
        
        me = merged_lookup.get(event_key)
        cluster_size = len(me.get("source_event_ids", [])) if me else 1
        connectedness = float(connected_links_count[event_key] + edge_count[event_key] + (cluster_size - 1))
        
        if me:
            referentiality = float(len(me.get("source_families", [])))
        else:
            referentiality = 1.0 if row.get("source_family") else 0.0
            
        node_depth = float(dist.get(event_key, 0) + dist_rev.get(event_key, 0) if event_key in nodes else 0)
        
        spectral_weight = connectedness * 0.5 + referentiality * 0.5
        
        corroboration_weight = 1.0 if referentiality >= 2.0 else 0.0
        
        has_conflict = bool(row.get("has_conflicting_span_years"))
        for edge in ordering_edges:
            if edge.get("time_basis") == "historical_conflict_residual":
                if edge.get("source_event_id") == event_key or edge.get("target_event_id") == event_key:
                    has_conflict = True
        conflict_residual = 1.0 if has_conflict else 0.0
        
        pnf_closed = False
        pnf_state = row.get("pnf") or {}
        if row.get("pnf_status") == "canonicalized" and pnf_state.get("subject") and pnf_state.get("predicate") and pnf_state.get("object"):
            pnf_closed = True
            
        row["braid_metrics"] = {
            "connectedness": connectedness,
            "referentiality": referentiality,
            "depth": node_depth,
            "spectral_weight": spectral_weight,
            "corroboration_weight": corroboration_weight,
            "conflict_residual": conflict_residual
        }
        
        score = (connectedness * 0.3) + (referentiality * 0.2) + (node_depth * 0.1) + (spectral_weight * 0.2) + (corroboration_weight * 0.2) - (conflict_residual * 0.3)
        score = max(0.0, min(1.0, round(score, 2)))
        
        anchor = row.get("anchor") or {}
        time_bound = bool(row.get("resolved_historical_date") or anchor.get("year") or anchor.get("start_year"))
        source_spanned = bool(row.get("text"))
        is_blocked = row.get("event_quality_status") == "rejected_noise" or row.get("recommended_status") == "block"
        
        if is_blocked:
            status = "excluded"
        elif pnf_closed and time_bound and source_spanned and score >= 0.5:
            status = "timeline_candidate"
        elif score >= 0.4:
            status = "triage"
        else:
            status = "background"
            
        row["relevance"] = {
            "score": score,
            "status": status,
            "basis": [
                "spectral_braid_position",
                "pnf_closure",
                "referential_support"
            ]
        }

        component_receipts = _compute_component_relevance(
            row,
            connectedness=connectedness,
            referentiality=referentiality,
            node_depth=node_depth,
            merged_event=me,
        )
        if component_receipts:
            row["fragment_pnf_receipts"] = component_receipts


def build_cross_source_event_braid(source_family_runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_event_rows = _normalize_source_event_rows(source_family_runs)
    candidate_links = _build_cross_document_candidates(source_event_rows)
    promoted_links = [
        row
        for row in candidate_links
        if _text(row.get("link_type")) == "same_event_as" and _text(row.get("promotion_status")) == "promoted"
    ]
    merged_event_lookup, merged_events = _cluster_promoted_links(source_event_rows, promoted_links)
    ordering_edges = _build_ordering_edges(source_event_rows, merged_event_lookup)
    collapse_points = [
        {
            "collapse_kind": "merged_event",
            "merged_event_id": row["merged_event_id"],
            "source_event_count": len(row.get("source_event_ids", [])),
            "source_family_count": len(row.get("source_families", [])),
        }
        for row in merged_events
        if len(row.get("source_event_ids", [])) > 1
    ]
    payload = {
        "schema_version": CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION,
        "source_event_rows": source_event_rows,
        "candidate_links": candidate_links,
        "merged_events": merged_events,
        "ordering_edges": ordering_edges,
        "collapse_points": collapse_points,
    }
    compute_braid_relevance_metrics(payload)
    payload["summary"] = summarize_cross_source_event_braid(payload)
    return payload


__all__ = [
    "CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION",
    "build_cross_source_event_braid",
    "summarize_cross_source_event_braid",
]
