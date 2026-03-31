#!/usr/bin/env python3
"""Extract actor/action/object (AAO) mini-graphs from wiki timeline candidates.

This is sentence-local and non-causal:
- no inference beyond basic pattern extraction
- actors are resolved via (a) root actor surname, (b) alias map from candidates, (c) raw mention
- objects are primarily wikilinks present in the timeline event

Inputs (gitignored):
- `SensibLaw/.cache_local/wiki_timeline_gwb.json`
- optionally `SensibLaw/.cache_local/wiki_candidates_gwb.json` for alias resolution

Output (gitignored):
- `SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json`
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

try:
    from babel.numbers import parse_decimal as _babel_parse_decimal
except Exception:  # pragma: no cover - optional dependency
    _babel_parse_decimal = None

try:
    from src.models.attribution_claims import (
        AttributionType as _AttributionType,
        SourceEntityType as _SourceEntityType,
        attribution_id as _attribution_id,
        extraction_record_id as _extraction_record_id,
        source_entity_id as _source_entity_id,
    )
except Exception:  # pragma: no cover - optional dependency
    _AttributionType = None
    _SourceEntityType = None
    _attribution_id = None
    _extraction_record_id = None
    _source_entity_id = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.models.attribution_claims import (
            AttributionType as _AttributionType,
            SourceEntityType as _SourceEntityType,
            attribution_id as _attribution_id,
            extraction_record_id as _extraction_record_id,
            source_entity_id as _source_entity_id,
        )
    except Exception:
        pass

try:
    from src.models.numeric_claims import magnitude_id as _magnitude_id
except Exception:  # pragma: no cover - optional dependency
    _magnitude_id = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.models.numeric_claims import magnitude_id as _magnitude_id
    except Exception:
        pass

try:
    from src.nlp.epistemic_classifier import EpistemicClassifier as _EpistemicClassifier
except Exception:  # pragma: no cover - optional dependency
    _EpistemicClassifier = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.nlp.epistemic_classifier import EpistemicClassifier as _EpistemicClassifier
    except Exception:
        pass

try:
    from src.nlp.event_classifier import EventClassifier as _EventClassifier
except Exception:  # pragma: no cover - optional dependency
    _EventClassifier = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.nlp.event_classifier import EventClassifier as _EventClassifier
    except Exception:
        pass

try:
    from src.nlp.synset_mapper import DeterministicSynsetActionMapper as _SynsetActionMapper
except Exception:  # pragma: no cover - optional dependency
    _SynsetActionMapper = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.nlp.synset_mapper import DeterministicSynsetActionMapper as _SynsetActionMapper
    except Exception:
        pass

try:
    from src.nlp.ontology_mapping import (
        canonical_action_morphology as _canonical_action_morphology,
        unknown_action_morphology as _unknown_action_morphology,
    )
except Exception:  # pragma: no cover - optional dependency
    _canonical_action_morphology = None
    _unknown_action_morphology = None
    try:  # pragma: no cover - repo-root script execution fallback
        from SensibLaw.src.nlp.ontology_mapping import (
            canonical_action_morphology as _canonical_action_morphology,
            unknown_action_morphology as _unknown_action_morphology,
        )
    except Exception:
        pass


PERSON_NAME_RE = re.compile(r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4}$")

# Guardrail: Wikipedia titles that look like names but aren't people (wars, acts, offices, etc.)
NON_PERSON_TOKENS = {
    "war",
    "act",
    "crisis",
    "convention",
    "election",
    "fund",
    "court",
    "house",
    "senate",
    "committee",
    "administration",
    "university",
    "college",
    "hospital",
    "states",
    "state",
    "republican",
    "democratic",
    "recession",
    "attack",
    "bombing",
    "grenade",
    "terrorist",
    "terrorism",
    "force",
    "guard",
    "air",
    "army",
    "navy",
    "alliance",
    "forces",
    "troops",
    "operation",
    "memorial",
    "magazine",
    "election",
    "attacks",
}

ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
PARTY_ROLE_LABELS = {
    "appellant",
    "respondent",
    "the appellant",
    "the respondent",
    "the diocese",
    "diocese",
}
HONORIFIC_RE = re.compile(r"^(?:Mr|Mrs|Ms|Dr|Fr|Father|Justice|Judge)\.?\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)?$")
REQUESTER_TITLE_PREFIX_RE = re.compile(
    r"^(?:President|Prime Minister|PM|Senator|Governor|Justice|Judge|Mr|Mrs|Ms|Dr)\.?\s+",
    re.IGNORECASE,
)
CITATION_TOKEN_RE = re.compile(r"\b(?:CAB|SC|AS|RS|ABFM)\b", re.IGNORECASE)
CITATION_PAREN_RE = re.compile(r"\(([^)]{1,180})\)")
CITATION_TRAIL_RE = re.compile(r"(?:\s*[\[(](?:CAB|SC|AS|RS|ABFM)[^\])]{0,60}[\])])+\s*$", re.IGNORECASE)
POSSESSIVE_EVIDENCE_RE = re.compile(
    r"\b((?:Mr|Mrs|Ms|Dr|Fr|Father|Justice|Judge)\.?\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)?)\s*(?:’|')s\b",
    re.IGNORECASE,
)
FOOTNOTE_TAIL_RE = re.compile(r"(?:[.:;]\d+|\s+\d+)$")


def _looks_like_person_title(title: str) -> bool:
    t = str(title or "").strip()
    if not t:
        return False
    if not PERSON_NAME_RE.fullmatch(t):
        return False
    # Filter out common non-person constructs.
    parts = t.split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    if "of" in (p.lower() for p in parts):
        return False
    if any(p in ROMAN_NUMERALS for p in parts):
        return False
    if any(p.lower() in NON_PERSON_TOKENS for p in parts):
        return False
    return True


def _strip_parenthetical_citation_noise(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return s

    def repl(match: re.Match[str]) -> str:
        inner = str(match.group(1) or "").strip()
        if not inner:
            return match.group(0)
        if CITATION_TOKEN_RE.search(inner):
            return " "
        if re.search(r"\bT\d+(?:\.\d+)?\b", inner):
            return " "
        return match.group(0)

    s = CITATION_PAREN_RE.sub(repl, s)
    return re.sub(r"\s+", " ", s).strip()


def _clean_entity_surface(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return s
    s = FOOTNOTE_TAIL_RE.sub("", s).strip()
    s = CITATION_TRAIL_RE.sub("", s).strip()
    s = re.sub(r"\s+", " ", s).strip(" ,;:.()[]{}\"'")
    # Coalescing hygiene: drop a leading definite article ("the United States" -> "United States").
    # This is intentionally narrow (single leading token) and deterministic.
    parts = s.split()
    if len(parts) > 1 and str(parts[0]).lower() == "the":
        s = " ".join(parts[1:]).strip()
    return s


def _looks_like_person_mention(text: str) -> bool:
    s = _clean_entity_surface(text)
    if not s:
        return False
    if HONORIFIC_RE.fullmatch(s):
        return True
    return _looks_like_person_title(s)


def _looks_like_party_role(text: str) -> bool:
    s = _clean_entity_surface(text).lower()
    return s in PARTY_ROLE_LABELS


def _extract_possessive_person(surface: str) -> Optional[str]:
    s = re.sub(r"\s+", " ", str(surface or "").strip())
    if not s:
        return None
    m = POSSESSIVE_EVIDENCE_RE.search(s)
    if not m:
        return None
    out = _clean_entity_surface(str(m.group(1) or ""))
    return out or None


def _normalize_requester_surface(surface: str) -> str:
    s = _clean_entity_surface(surface)
    if not s:
        return ""
    # Handle both attached and token-split possessives: "Obama's" / "Obama 's".
    s = re.sub(r"\s+(?:'s|’s)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:'s|’s)\b", "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _resolve_requester_label(candidate: str, alias_map: Dict[str, str]) -> str:
    c = _normalize_requester_surface(candidate)
    if not c:
        return ""
    alias_lower = {str(k).strip().lower(): str(v) for k, v in (alias_map or {}).items() if str(k).strip() and str(v).strip()}
    probes = [c]
    core = REQUESTER_TITLE_PREFIX_RE.sub("", c).strip()
    if core:
        probes.append(core)
    for base in [core, c]:
        if base:
            parts = base.split()
            if parts:
                probes.append(parts[-1])
    for p in probes:
        if p in alias_map:
            return str(alias_map[p])
        pl = p.lower()
        if pl in alias_lower:
            return alias_lower[pl]
    return core or c


def _extract_requester_from_doc(doc, alias_map: Dict[str, str]) -> Tuple[Optional[str], Optional[str], bool]:
    if doc is None:
        return None, None, False
    for tok in doc:
        lemma = str(getattr(tok, "lemma_", "") or "").lower()
        pos = str(getattr(tok, "pos_", "") or "")
        if lemma != "request" or pos not in {"NOUN", "PROPN"}:
            continue

        poss_tokens = [c for c in tok.children if str(getattr(c, "dep_", "") or "") in {"poss", "nmod:poss"}]
        expanded = []
        for p in poss_tokens:
            expanded.append(p)
            expanded.extend(list(getattr(p, "conjuncts", [])))

        candidate = None
        for p in expanded:
            surf = _normalize_requester_surface(_subject_surface_for_token(doc, p))
            if not surf:
                continue
            low = surf.lower()
            if low in {"his", "her", "their", "its", "my", "our", "your", "whose"}:
                continue
            candidate = surf
            break

        if not candidate:
            continue

        candidate = _normalize_requester_surface(candidate)
        resolved = _resolve_requester_label(candidate, alias_map)
        subtree_tokens = [str(getattr(x, "text", "") or "").lower() for x in getattr(tok, "subtree", [])]
        has_title = "president" in subtree_tokens or str(candidate).lower().startswith("president ")
        return candidate, resolved, has_title

    return None, None, False


def _extract_requester_from_request_verbs(doc, alias_map: Dict[str, str]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extract the *target* of a request-like action (e.g. "urged Congress to ...").
    Returns (surface, resolved, source) or (None, None, "").
    """
    if doc is None:
        return None, None, ""

    alias_lower = {str(k).strip().lower(): str(v) for k, v in (alias_map or {}).items() if str(k).strip() and str(v).strip()}

    def resolve(surface: str) -> str:
        s = _normalize_requester_surface(surface)
        if not s:
            return ""
        if s in alias_map:
            return str(alias_map[s])
        sl = s.lower()
        if sl in alias_lower:
            return str(alias_lower[sl])
        return s

    # Deterministic v1 list; can be replaced by synset mapping behind the
    # semantic-backbone profile guard.
    request_signal_lemmas = {
        "ask",
        "request",
        "urge",
        "call",
        "encourage",
        "press",
        "demand",
        "require",
        "order",
        "instruct",
        "direct",
        "tell",
        "invite",
        "appeal",
    }

    candidates: List[Tuple[int, str, str, str]] = []
    for tok in doc:
        try:
            if str(getattr(tok, "pos_", "") or "") not in {"VERB", "AUX"}:
                continue
            lemma = str(getattr(tok, "lemma_", "") or "").strip().lower()
            if lemma not in request_signal_lemmas:
                continue

            # Prefer request-like verbs that govern an infinitival complement (to + VERB).
            has_inf = False
            for ch in getattr(tok, "children", []):
                if str(getattr(ch, "dep_", "") or "") != "xcomp":
                    continue
                for gc in getattr(ch, "children", []):
                    dep = str(getattr(gc, "dep_", "") or "")
                    if dep in {"mark", "aux"} and str(getattr(gc, "lemma_", "") or "").lower() == "to":
                        has_inf = True
                        break
                if has_inf:
                    break
            if not has_inf:
                continue

            targets = []
            for ch in getattr(tok, "children", []):
                dep = str(getattr(ch, "dep_", "") or "")
                if dep in {"dobj", "obj", "iobj", "dative"}:
                    targets.append(ch)
            for ch in getattr(tok, "children", []):
                if str(getattr(ch, "dep_", "") or "") != "prep":
                    continue
                if str(getattr(ch, "lemma_", "") or "").lower() != "to":
                    continue
                for gc in getattr(ch, "children", []):
                    if str(getattr(gc, "dep_", "") or "") in {"pobj", "obj"}:
                        targets.append(gc)

            for t in targets:
                surf = _normalize_requester_surface(_subject_surface_for_token(doc, t))
                if not surf:
                    continue
                low = surf.lower()
                # Avoid pronouns/weak placeholders.
                if low in {"him", "her", "them", "it", "us", "me", "you", "officials"}:
                    continue
                res = resolve(surf)
                if not res:
                    continue
                candidates.append((int(getattr(tok, "i", 10**9) or 10**9), surf, res, f"dep:req_verb:{lemma}"))
        except Exception:
            continue

    if not candidates:
        return None, None, ""
    candidates.sort(key=lambda t: (int(t[0]), str(t[2]).lower(), str(t[1]).lower()))
    _, surf, res, src = candidates[0]
    return surf, res, src


def _extract_passive_agents_from_doc(doc) -> List[str]:
    if doc is None:
        return []
    out: List[str] = []
    seen = set()

    def add(v: str) -> None:
        raw = _clean_entity_surface(v)
        if not raw:
            return
        norm = _normalize_agent_label(raw)
        key = norm.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(norm)

    for tok in doc:
        dep = str(getattr(tok, "dep_", "") or "")
        lemma = str(getattr(tok, "lemma_", "") or "").lower()
        if dep != "agent" and not (dep == "prep" and lemma == "by"):
            continue
        for c in tok.children:
            cdep = str(getattr(c, "dep_", "") or "")
            if cdep not in {"pobj", "obj"}:
                continue
            add(_subject_surface_for_token(doc, c))
            for cj in getattr(c, "conjuncts", []):
                add(_subject_surface_for_token(doc, cj))

    return out


REQUEST_RE = re.compile(r"\bat\s+(?:President\s+)?([A-Z][a-z]+)(?:'s)?\s+request\b", re.IGNORECASE)


DEFAULT_REQUESTER_TITLE_LABELS: Dict[str, str] = {
    "president": "U.S. President",
}
DEFAULT_COMMUNICATION_CHAIN_CONFIG: Dict[str, object] = {
    "communication_verbs": [
        "report",
        "say",
        "state",
        "warn",
        "caution",
        "announce",
        "hold",
        "find",
        "conclude",
        "contend",
        "argue",
        "note",
        "tell",
    ],
    "emit_attribution_step": True,
    "emit_embedded_steps": True,
    "embedded_step_limit": 2,
    "embedded_step_heads": ["ROOT", "conj"],
    "embedded_subject_policy": "prefer_local_subject",
    "attribution_modifier_key": "according_to",
}

DEFAULT_MODAL_CONTAINER_GRAMMAR: Dict[str, Dict[str, object]] = {
    "have": {
        "container_deps": ["dobj", "obj", "attr"],
        "container_nouns": ["tendency", "opportunity", "ability", "capacity", "failure", "requirement"],
        "require_to": True,
        "promote": "xcomp",
    },
    "be": {
        "container_deps": ["attr", "acomp", "oprd"],
        "container_nouns": ["able", "likely", "required"],
        "require_to": True,
        "promote": "xcomp",
    },
}

DEFAULT_ACTION_PATTERN_SPECS: List[Tuple[str, str]] = [
    ("initiated", r"\binitiat(?:e|ed|es|ing)\b"),
    ("discharged", r"\bdischarg(?:e|ed|es|ing)\b"),
    ("suspended", r"\bsuspend(?:ed|s|ing)\b"),
    ("told", r"\btold\b|\btell(?:s|ing)?\b"),
    ("voted", r"\bvote(?:d|s|ing)?\b"),
    ("reported", r"\breported\b|\breport(?:s|ed|ing)?\b"),
    ("cautioned", r"\bcautioned\b|\bcaution(?:s|ed|ing)?\b"),
    ("gave_birth", r"\bgave\s+birth\b"),
    ("defeated", r"\bdefeat(?:ed|ing|s)?\b"),
    ("continued", r"\bcontinue(?:d|s|ing)?\b"),
    ("weakened", r"\bweaken(?:ed|ing|s)?\b"),
    ("intensified", r"\bintensified\b"),
    ("began", r"\bbegan\b|\bbeginning\b"),
    ("nominated", r"\bnominated\b|\bnominate\b"),
    ("urged", r"\burged\b|\burge\b"),
    ("commissioned_into", r"\bcommissioned\b.*\binto\b"),
    ("commissioned", r"\bcommissioned\b"),
    ("threw", r"\bthrew\b|\bthrow\b"),
    ("entered", r"\bentered\b|\benter\b"),
    ("gave_speech", r"\b(?:was\s+)?giving\s+a\s+speech\b|\bgave\s+a\s+speech\b"),
    ("led", r"\bled\b|\blead\b"),
    ("advised", r"\badvised\b|\badvise\b"),
    ("departed", r"\bdepart(?:ed)?\b"),
    ("requested", r"\brequested\b|\brequest(?:s|ed)?\b"),
    ("completed", r"\bcomplete(?:d)?\b"),
    ("withdrew", r"\bwithdrew\b|\bwithdrawn\b|\bwithdraw\b"),
    ("retired", r"\bretired\b|\bretirement\b"),
    ("died", r"\bdie(?:d|s|ing)?\b"),
    ("drew", r"\bdrew\b|\bdraw(?:s|ing)?\b"),
    ("killed", r"\bkilled\b|\bkill\b"),
    ("approved", r"\bapproved\b|\bapprove\b"),
    ("bailout", r"\bbailout\b|\bbail(?:ed)?\s+out\b"),
    ("takeover", r"\btakeover\b|\btook\s+over\b|\btaken\s+over\b"),
    ("established", r"\bestablished\b"),
    ("called", r"\bcalled\b"),
    ("joined", r"\bjoined\b"),
    ("selected", r"\bselected\b"),
    ("signed", r"\bsigned\b"),
    ("launched", r"\blaunched\b"),
    ("arranged", r"\barranged\b"),
    ("merged", r"\bmerged\b"),
    ("ran", r"\bran for\b|\bran\b"),
    ("won", r"\bwon\b"),
    ("re_elected", r"\bre-?elected\b"),
    ("said", r"\bsaid\b"),
    ("released", r"\breleased\b"),
]


def _compile_action_patterns(pattern_specs: List[Tuple[str, str]]) -> List[Tuple[str, re.Pattern[str]]]:
    compiled: List[Tuple[str, re.Pattern[str]]] = []
    for label, pattern in pattern_specs:
        lab = str(label or "").strip()
        pat = str(pattern or "").strip()
        if not lab or not pat:
            continue
        try:
            compiled.append((lab, re.compile(pat, re.IGNORECASE)))
        except re.error:
            continue
    return compiled


ACTION_PATTERNS: List[Tuple[str, re.Pattern[str]]] = _compile_action_patterns(DEFAULT_ACTION_PATTERN_SPECS)

# Passive agent extraction for "were advised by the X ...", stopping before "to" (or punctuation).
# Keep this narrow and conservative; it's identity glue, not a full parser.
BY_AGENT_RE = re.compile(
    r"\b(?:was|were)\s+advised\s+by\s+(?:the\s+)?(.+?)(?:\s+to\b|,|;)",
    re.IGNORECASE,
)
US_ALIASES = {
    "u.s.": "United States",
    "us": "United States",
    "u.s": "United States",
    "united states": "United States",
}

def _is_year_token(tok: str) -> bool:
    s = (tok or "").strip()
    return bool(re.fullmatch(r"(?:19|20)\d{2}", s))


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _guess_person_titles(candidates_payload: dict) -> Dict[str, str]:
    """Build a last-name -> canonical title map from wiki candidates (heuristic)."""
    rows = candidates_payload.get("rows") or []
    out: Dict[str, str] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        if not _looks_like_person_title(title):
            continue
        last = title.split()[-1].strip()
        if not last:
            continue
        # Prefer higher score titles; input is typically already sorted by score desc.
        if last not in out:
            out[last] = title
    return out


def _candidate_titles(candidates_payload: dict) -> List[str]:
    rows = candidates_payload.get("rows") or []
    out: List[str] = []
    if not isinstance(rows, list):
        return out
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        t = str(row.get("title") or "").strip()
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _match_span_overlaps_verb(doc, start: int, end: int) -> bool:
    if doc is None:
        return True
    try:
        for tok in doc:
            pos = str(getattr(tok, "pos_", "") or "")
            if pos not in {"VERB", "AUX"}:
                continue
            st = int(getattr(tok, "idx", -1))
            if st < 0:
                continue
            en = st + len(str(getattr(tok, "text", "") or ""))
            if st < end and start < en:
                return True
    except Exception:
        return True
    return False


def _extract_action(
    text: str,
    action_patterns: List[Tuple[str, re.Pattern[str]]],
    doc=None,
    event_classifier: Optional[object] = None,
) -> Tuple[Optional[str], List[str]]:
    warnings: List[str] = []
    if doc is not None and event_classifier is not None:
        try:
            match = event_classifier.classify_from_doc(doc)
            if match is not None:
                label = str(getattr(match, "action_label", "") or "").strip()
                if label:
                    return label, warnings
        except Exception:
            pass
    # Choose the earliest matching action in the sentence, not the first pattern in the list.
    best: Optional[Tuple[int, int, str]] = None  # (start, -match_len, label)
    for label, pat in action_patterns:
        for m in pat.finditer(text):
            start = int(m.start())
            end = int(m.end())
            if not _match_span_overlaps_verb(doc, start, end):
                continue
            mlen = int(end - start)
            cand = (start, -mlen, label)
            if best is None or cand < best:
                best = cand
    if best is not None:
        warnings.append("fallback_action_regex")
        return best[2], warnings
    fb = _fallback_action(text)
    if fb:
        warnings.append("fallback_action")
        return fb, warnings
    warnings.append("no_action_match")
    return None, warnings


_FALLBACK_BAD_TOKENS = {
    "following",
    "still",
    "pending",
    "including",
    "beginning",
    "united",
}


def _fallback_action(text: str) -> Optional[str]:
    """Pick a deterministic verb-like token when no pattern matches.

    This is intentionally shallow: we prefer explicit patterns, but want fewer
    empty action slots in the AAO substrate.
    """
    # Prefer simple past-tense lexical forms first.
    # We intentionally avoid generic "-ing" matches here because they often
    # surface nominal/adjectival phrases (e.g., "turning point"), and spaCy
    # fallback below is better placed to decide clause-head verbs.
    t = re.sub(r"[\u2013\u2014-]", " ", text)
    # Exclude bracketed/citation noise and keep it simple.
    for m in re.finditer(r"\b([A-Za-z]{4,})ed\b", t):
        stem = m.group(1).lower()
        if stem in _FALLBACK_BAD_TOKENS:
            continue
        raw = m.group(0)
        # Avoid promoting ProperNoun-looking tokens into actions.
        if raw and raw[0].isupper():
            continue
        tok = raw.lower()
        # Avoid things that look like adjectives or section labels.
        if tok in {"pending", "still"}:
            continue
        return tok
    return None


def _normalize_agent_label(raw: str) -> str:
    t = re.sub(r"\s+", " ", str(raw or "").strip())
    tl = t.lower().strip(". ")
    return US_ALIASES.get(tl) or t


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(obj: object) -> str:
    # Deterministic JSON hash for version-pin checks (stable keys + separators).
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha256_text(blob)


def _profile_action_pattern_specs(profile_payload: dict) -> List[Tuple[str, str]]:
    rows = profile_payload.get("action_patterns")
    if not isinstance(rows, list) or not rows:
        return list(DEFAULT_ACTION_PATTERN_SPECS)
    out: List[Tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        pattern = str(row.get("pattern") or "").strip()
        if label and pattern:
            out.append((label, pattern))
    return out or list(DEFAULT_ACTION_PATTERN_SPECS)


def _profile_requester_title_labels(profile_payload: dict) -> Dict[str, str]:
    out = dict(DEFAULT_REQUESTER_TITLE_LABELS)
    labels = profile_payload.get("requester_title_labels")
    if not isinstance(labels, dict):
        return out
    for k, v in labels.items():
        key = str(k or "").strip().lower()
        val = str(v or "").strip()
        if key and val:
            out[key] = val
    return out


def _profile_modal_container_grammar(profile_payload: dict) -> Dict[str, Dict[str, object]]:
    rows = profile_payload.get("modal_container_grammar")
    if not isinstance(rows, dict):
        return dict(DEFAULT_MODAL_CONTAINER_GRAMMAR)
    out: Dict[str, Dict[str, object]] = {}
    for head, rule in rows.items():
        hk = str(head or "").strip().lower()
        if not hk or not isinstance(rule, dict):
            continue
        deps = [str(x).strip() for x in (rule.get("container_deps") or []) if str(x).strip()]
        nouns = [str(x).strip().lower() for x in (rule.get("container_nouns") or []) if str(x).strip()]
        out[hk] = {
            "container_deps": deps or list(DEFAULT_MODAL_CONTAINER_GRAMMAR.get(hk, {}).get("container_deps") or []),
            "container_nouns": nouns or list(DEFAULT_MODAL_CONTAINER_GRAMMAR.get(hk, {}).get("container_nouns") or []),
            "require_to": bool(rule.get("require_to", True)),
            "promote": str(rule.get("promote") or "xcomp"),
        }
    return out or dict(DEFAULT_MODAL_CONTAINER_GRAMMAR)


def _profile_communication_chain_config(profile_payload: dict) -> Dict[str, object]:
    cfg = dict(DEFAULT_COMMUNICATION_CHAIN_CONFIG)
    rows = profile_payload.get("communication_chain")
    if not isinstance(rows, dict):
        return cfg
    verbs = rows.get("communication_verbs")
    if isinstance(verbs, list):
        vv = [str(x or "").strip().lower() for x in verbs if str(x or "").strip()]
        if vv:
            cfg["communication_verbs"] = vv
    for key in ("emit_attribution_step", "emit_embedded_steps"):
        if key in rows:
            cfg[key] = bool(rows.get(key))
    if "embedded_step_limit" in rows:
        try:
            cfg["embedded_step_limit"] = max(1, int(rows.get("embedded_step_limit") or 1))
        except Exception:
            pass
    heads = rows.get("embedded_step_heads")
    if isinstance(heads, list):
        hh = [str(x or "").strip() for x in heads if str(x or "").strip()]
        if hh:
            cfg["embedded_step_heads"] = hh
    policy = str(rows.get("embedded_subject_policy") or "").strip()
    if policy:
        cfg["embedded_subject_policy"] = policy
    attr_key = str(rows.get("attribution_modifier_key") or "").strip()
    if attr_key:
        cfg["attribution_modifier_key"] = attr_key
    return cfg


def _profile_epistemic_verbs(profile_payload: dict, comm_cfg: Dict[str, object]) -> List[str]:
    explicit = profile_payload.get("epistemic_verbs")
    if isinstance(explicit, list):
        out = [str(x or "").strip().lower() for x in explicit if str(x or "").strip()]
        if out:
            return list(dict.fromkeys(out))
    comm = [str(x or "").strip().lower() for x in (comm_cfg.get("communication_verbs") or []) if str(x or "").strip()]
    return list(dict.fromkeys(comm))


_ALLOWED_SEMANTIC_RESOURCES = {"none", "wordnet", "babelnet", "wordnet+babelnet"}
_ALLOWED_WSD_POLICIES = {"none", "rule_deterministic", "model_version_pinned"}


def _profile_semantic_backbone_config(profile_payload: dict) -> Tuple[Dict[str, object], List[str], Optional[str]]:
    cfg_raw = profile_payload.get("semantic_backbone")
    cfg = cfg_raw if isinstance(cfg_raw, dict) else {}
    warnings: List[str] = []

    resource = str(cfg.get("resource") or "none").strip().lower()
    if resource not in _ALLOWED_SEMANTIC_RESOURCES:
        warnings.append("semantic_backbone_resource_invalid_fallback_none")
        resource = "none"

    wsd_policy = str(cfg.get("wsd_policy") or "none").strip().lower()
    if wsd_policy not in _ALLOWED_WSD_POLICIES:
        return (
            {
                "resource": resource,
                "wsd_policy": "none",
                "llm_enabled": False,
                "deterministic": True,
            },
            warnings,
            "semantic_backbone_wsd_policy_not_deterministic",
        )

    llm_enabled = bool(cfg.get("llm_enabled", False))
    if llm_enabled:
        return (
            {
                "resource": resource,
                "wsd_policy": wsd_policy,
                "llm_enabled": False,
                "deterministic": False,
            },
            warnings,
            "semantic_backbone_llm_not_allowed",
        )

    deterministic = wsd_policy in {"none", "rule_deterministic", "model_version_pinned"}
    return (
        {
            "resource": resource,
            "wsd_policy": wsd_policy,
            "llm_enabled": False,
            "deterministic": bool(deterministic),
        },
        warnings,
        None,
    )


def _profile_synset_action_map(profile_payload: dict) -> Dict[str, str]:
    rows = profile_payload.get("synset_action_map")
    if not isinstance(rows, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in rows.items():
        sid = str(k or "").strip().lower()
        lab = str(v or "").strip()
        if sid and lab:
            out[sid] = lab
    return out


def _profile_babelnet_lemma_synsets(profile_payload: dict) -> Dict[str, List[str]]:
    rows = profile_payload.get("babelnet_lemma_synsets")
    if not isinstance(rows, dict):
        return {}
    out: Dict[str, List[str]] = {}
    for k, v in rows.items():
        lemma = str(k or "").strip().lower()
        if not lemma:
            continue
        if not isinstance(v, list):
            continue
        syns = sorted({str(x or "").strip().lower() for x in v if str(x or "").strip()})
        if syns:
            out[lemma] = syns
    return out


def _profile_semantic_version_pins(profile_payload: dict) -> Dict[str, str]:
    pins = profile_payload.get("semantic_version_pins")
    if not isinstance(pins, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in pins.items():
        kk = str(k or "").strip().lower()
        vv = str(v or "").strip()
        if kk and vv:
            out[kk] = vv
    return out


def _try_load_spacy(model: str) -> Tuple[Optional[object], Optional[dict], Optional[str]]:
    try:
        import spacy  # type: ignore

        nlp = spacy.load(model)
        meta = getattr(nlp, "meta", {}) or {}
        name = str(meta.get("name") or model)
        ver = str(meta.get("version") or "")

        # Hash a small stable footprint if possible.
        p = getattr(nlp, "path", None)
        h = None
        if p:
            try:
                meta_path = Path(p) / "meta.json"
                cfg_path = Path(p) / "config.cfg"
                blob = ""
                if meta_path.exists():
                    blob += meta_path.read_text(encoding="utf-8")
                if cfg_path.exists():
                    blob += "\n---\n" + cfg_path.read_text(encoding="utf-8")
                if blob.strip():
                    h = _sha256_text(blob)
            except Exception:
                h = None

        info = {
            "name": "spacy",
            "model": model,
            "model_name": name,
            "model_version": ver,
            "spacy_version": getattr(spacy, "__version__", ""),
            "model_sha256": h,
        }
        return nlp, info, None
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def _span_type_for_np(chunk_text: str, head_lemma: str, has_acronym: bool, has_propn: bool) -> str:
    # Span candidates are explicitly not entities; this is a shallow hint for surfacing.
    # This must not be used as a truth admissibility gate.
    lemma = (head_lemma or "").lower()
    if has_acronym or has_propn:
        if lemma in {"inspector", "inspectors", "official", "officials", "troop", "troops", "guard", "guards"}:
            return "COLLECTIVE_ROLE"
    if lemma in {"inspectors", "inspector"}:
        return "COLLECTIVE_ROLE"
    return "ABSTRACT"


MONTH_WORDS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


def _extract_purpose(text: str) -> Optional[str]:
    # Deprecated: purpose extraction is now dependency-gated when spaCy is available.
    # This function remains as a compatibility fallback and intentionally returns None.
    _ = text
    return None


def _extract_purpose_from_doc(doc) -> Optional[str]:
    """
    Purpose is a subordinate infinitival verb clause ("to" as PART attached to a VERB),
    not a prepositional attachment ("gave birth to ...").

    Deterministic: uses only POS/dep labels and token spans (no NER/meaning).
    """
    if doc is None:
        return None
    try:
        for t in doc:
            if (t.text or "").lower() != "to":
                continue
            # Infinitival marker "to" (PART) attaches to a verb head (aux/mark are both seen).
            if getattr(t, "pos_", "") != "PART":
                continue
            if getattr(t, "dep_", "") not in {"aux", "mark"}:
                continue
            head = getattr(t, "head", None)
            if head is None or getattr(head, "pos_", "") != "VERB":
                continue

            idxs = [x.i for x in head.subtree] or [head.i]
            start_i = min(min(idxs), t.i)
            end_i = max(idxs) + 1
            span = doc[start_i:end_i]
            purpose = str(getattr(span, "text", "") or "").strip()
            if purpose.lower().startswith("to "):
                purpose = purpose[3:].strip()
            purpose = _clean_entity_surface(_strip_parenthetical_citation_noise(purpose))
            if not purpose:
                continue
            if len(purpose) > 220:
                purpose = purpose[:220].rstrip() + "..."
            return purpose
    except Exception:
        return None
    return None


def _promote_modal_container_action(
    doc,
    action: Optional[str],
    modal_grammar: Dict[str, Dict[str, object]],
) -> Tuple[Optional[str], Optional[dict]]:
    if doc is None:
        return action, None
    try:
        root = None
        for t in doc:
            dep = str(getattr(t, "dep_", "") or "")
            pos = str(getattr(t, "pos_", "") or "")
            if dep == "ROOT" and pos in {"VERB", "AUX"}:
                root = t
                break
        if root is None:
            return action, None
        root_lemma = str(getattr(root, "lemma_", "") or "").strip().lower()
        if not root_lemma:
            return action, None
        rule = modal_grammar.get(root_lemma)
        if not isinstance(rule, dict):
            return action, None
        if str(rule.get("promote") or "").strip().lower() != "xcomp":
            return action, None

        dep_allow = {str(x).strip() for x in (rule.get("container_deps") or []) if str(x).strip()}
        noun_allow = {str(x).strip().lower() for x in (rule.get("container_nouns") or []) if str(x).strip()}

        container = None
        for c in root.children:
            dep = str(getattr(c, "dep_", "") or "")
            if dep_allow and dep not in dep_allow:
                continue
            lem = str(getattr(c, "lemma_", "") or getattr(c, "text", "") or "").strip().lower()
            if noun_allow and lem not in noun_allow:
                continue
            container = c
            break
        if container is None:
            return action, None

        promoted_verb = None
        # Common legal-prose pattern: "had a tendency/opportunity to VERB"
        # where VERB is attached as acl under the container noun.
        for c in container.children:
            dep = str(getattr(c, "dep_", "") or "")
            if dep not in {"acl", "xcomp", "ccomp"}:
                continue
            if str(getattr(c, "pos_", "") or "") != "VERB":
                continue
            promoted_verb = c
            break

        xcomp = None
        for c in root.children:
            if str(getattr(c, "dep_", "") or "") != "xcomp":
                continue
            if str(getattr(c, "pos_", "") or "") != "VERB":
                continue
            xcomp = c
            break
        if promoted_verb is None:
            promoted_verb = xcomp
        if promoted_verb is None:
            return action, None

        if bool(rule.get("require_to", True)):
            has_to = False
            for m in promoted_verb.children:
                txt = str(getattr(m, "text", "") or "").strip().lower()
                dep = str(getattr(m, "dep_", "") or "")
                if txt == "to" and dep in {"aux", "mark"}:
                    has_to = True
                    break
            if not has_to:
                return action, None

        promoted = str(getattr(promoted_verb, "lemma_", "") or getattr(promoted_verb, "text", "") or "").strip().lower()
        if not promoted:
            return action, None
        mod = {
            "kind": "modal_container",
            "container": str(getattr(container, "lemma_", "") or getattr(container, "text", "") or "").strip().lower(),
            "governing_action": root_lemma,
            "source": "dep_modal_container",
        }
        return promoted, mod
    except Exception:
        return action, None


def _extract_actor_tokens(text: str) -> List[str]:
    # Look for capitalized tokens; include possessive ('s) stripping.
    toks = []
    for m in re.finditer(r"\b([A-Z][a-z]+)(?:'s)?\b", text):
        t = m.group(1).strip()
        if t and t not in toks:
            toks.append(t)
    return toks


ACTION_LEMMAS: Dict[str, Tuple[str, ...]] = {
    "gave_birth": ("give",),
    "commissioned_into": ("commission",),
    "commissioned": ("commission",),
    "gave_speech": ("give",),
    "requested": ("request",),
    "established": ("establish",),
    "joined": ("join",),
    "selected": ("select",),
    "launched": ("launch",),
    "called": ("call",),
    "arranged": ("arrange",),
    "merged": ("merge",),
    "ran": ("run",),
    "won": ("win",),
    "re_elected": ("elect",),
    "said": ("say",),
    "released": ("release",),
    "approved": ("approve",),
    "killed": ("kill",),
    "nominated": ("nominate",),
    "urged": ("urge",),
    "entered": ("enter",),
    "departed": ("depart",),
    "advised": ("advise",),
    "retired": ("retire",),
    "withdrew": ("withdraw",),
    "died": ("die",),
    "drew": ("draw",),
    "completed": ("complete",),
    "reported": ("report",),
    "cautioned": ("caution",),
    "weakening": ("weaken", "continue"),
    "told": ("tell",),
    "voted": ("vote",),
    "initiated": ("initiate",),
    "discharged": ("discharge",),
    "suspended": ("suspend",),
    "signed": ("sign",),
    "led": ("lead",),
    "request": ("request",),
}


def _base_action_label(action: str) -> str:
    a = str(action or "").strip().lower()
    # Backward-compat: older artifacts encoded negation in action labels.
    # New artifacts keep action canonical and store negation as metadata.
    if a.startswith("not_"):
        return a[4:]
    return a


def _action_lemmas(action: str) -> Tuple[str, ...]:
    base = _base_action_label(action)
    return ACTION_LEMMAS.get(base, (base,))


def _is_claim_bearing_action(action: str, epistemic_verbs: List[str]) -> bool:
    verbs = {str(x or "").strip().lower() for x in (epistemic_verbs or []) if str(x or "").strip()}
    if not verbs:
        return False
    for lemma in _action_lemmas(action):
        if str(lemma or "").strip().lower() in verbs:
            return True
    return False


def _step_has_claim_modifier(step: dict) -> bool:
    mods = step.get("modifiers") if isinstance(step, dict) else None
    if not isinstance(mods, list):
        return False
    for m in mods:
        if not isinstance(m, dict):
            continue
        kind = str(m.get("kind") or "").strip().lower()
        if kind in {"attribution", "communication_attribution"}:
            return True
    return False


def _token_has_epistemic_dependency_signal(tok) -> bool:
    for ch in getattr(tok, "children", []):
        dep = str(getattr(ch, "dep_", "") or "")
        if dep in {"ccomp", "xcomp"}:
            return True
    return False


def _step_token_map_for_actions(doc, steps: List[dict]) -> Dict[int, object]:
    if doc is None or not steps:
        return {}
    out: Dict[int, object] = {}
    used = set()
    for idx, step in enumerate(steps):
        lemmas = {str(x or "").strip().lower() for x in _action_lemmas(str(step.get("action") or "")) if str(x or "").strip()}
        if not lemmas:
            continue
        cands = []
        for tok in doc:
            if str(getattr(tok, "pos_", "") or "") not in {"VERB", "AUX"}:
                continue
            lemma = str(getattr(tok, "lemma_", "") or "").strip().lower()
            if lemma not in lemmas:
                continue
            cands.append(tok)
        if not cands:
            continue
        pick = next((t for t in cands if int(getattr(t, "i", -1)) not in used), None)
        if pick is None:
            pick = cands[0]
        ti = int(getattr(pick, "i", -1))
        if ti >= 0:
            used.add(ti)
        out[idx] = pick
    return out


def _claim_modality_for_action(action: str) -> str:
    lemmas = {str(x or "").strip().lower() for x in _action_lemmas(action)}
    if lemmas & {"estimate", "forecast", "project", "predict"}:
        return "projection"
    if lemmas & {"report", "find", "conclude", "hold", "note"}:
        return "reported"
    return "stated"


def _annotate_claim_bearing_steps(
    doc,
    steps: List[dict],
    event_id: str,
    epistemic_verbs: List[str],
    classifier: Optional[object] = None,
) -> List[int]:
    claim_indices: List[int] = []
    step_tok = _step_token_map_for_actions(doc, steps)
    for idx, step in enumerate(steps):
        action = str(step.get("action") or "")
        dep_signal = False
        tok = step_tok.get(idx)
        classifier_epistemic = False
        if tok is not None:
            dep_signal = _token_has_epistemic_dependency_signal(tok)
            if classifier is not None:
                try:
                    ci = classifier.classify_from_doc(doc, int(getattr(tok, "i", -1)))
                    ptype = str(getattr(getattr(ci, "predicate_type", None), "value", "") or "")
                    if ptype:
                        step["predicate_type"] = ptype
                    step["predicate_confidence"] = float(getattr(ci, "confidence", 0.0) or 0.0)
                    feats = getattr(ci, "features", None)
                    if isinstance(feats, dict):
                        step["classification_features"] = feats
                    classifier_epistemic = ptype == "epistemic"
                except Exception:
                    pass
        mod_signal = _step_has_claim_modifier(step)
        lex_signal = _is_claim_bearing_action(action, epistemic_verbs)
        # Dependency/modifier/classifier signals are primary; lexical is fallback for sparse parses.
        structural_signal = bool(classifier_epistemic or dep_signal or mod_signal)
        is_claim = bool(structural_signal or (not structural_signal and lex_signal))
        step["claim_bearing"] = bool(is_claim)
        if not is_claim:
            continue
        claim_indices.append(idx)
        step["claim_modality"] = _claim_modality_for_action(action)
        step["claim_id"] = f"{event_id}:step:{idx}"
    return claim_indices


def _canonical_action_from_doc(doc, action: str) -> Tuple[str, Optional[dict]]:
    base = _base_action_label(action)
    if not base:
        return "", None
    lemmas = {str(x or "").strip().lower() for x in _action_lemmas(base) if str(x or "").strip()}
    if not doc:
        fallback_lemma = next(iter(lemmas)) if lemmas else base
        if _unknown_action_morphology is not None:
            meta = _unknown_action_morphology(surface=str(action or ""), source="fallback:action_lemmas")
        else:
            meta = {
                "surface": str(action or ""),
                "tense": "unknown",
                "aspect": "unknown",
                "verb_form": "unknown",
                "voice": "unknown",
                "mood": "unknown",
                "modality": "asserted",
                "source": "fallback:action_lemmas",
            }
        return fallback_lemma, meta

    candidates = []
    for t in doc:
        pos = str(getattr(t, "pos_", "") or "")
        if pos not in {"VERB", "AUX"}:
            continue
        lemma = str(getattr(t, "lemma_", "") or "").strip().lower()
        if lemma in lemmas:
            candidates.append(t)
    if not candidates:
        fallback_lemma = next(iter(lemmas)) if lemmas else base
        if _unknown_action_morphology is not None:
            meta = _unknown_action_morphology(surface=str(action or ""), source="fallback:action_lemmas")
        else:
            meta = {
                "surface": str(action or ""),
                "tense": "unknown",
                "aspect": "unknown",
                "verb_form": "unknown",
                "voice": "unknown",
                "mood": "unknown",
                "modality": "asserted",
                "source": "fallback:action_lemmas",
            }
        return fallback_lemma, meta

    def _rank(tok) -> Tuple[int, int, int]:
        dep = str(getattr(tok, "dep_", "") or "")
        morph = getattr(tok, "morph", None)
        verb_form = ""
        if morph is not None:
            try:
                vals = morph.get("VerbForm")
                verb_form = vals[0] if vals else ""
            except Exception:
                verb_form = ""
        root_rank = 0 if dep == "ROOT" else 1
        finite_rank = 0 if str(verb_form).lower() == "fin" else 1
        idx_rank = int(getattr(tok, "i", 10_000))
        return (root_rank, finite_rank, idx_rank)

    tok = sorted(candidates, key=_rank)[0]
    lemma = str(getattr(tok, "lemma_", "") or base).strip().lower() or base
    if _canonical_action_morphology is not None:
        meta = _canonical_action_morphology(
            tok,
            surface=str(getattr(tok, "text", "") or action or ""),
            source="dep_lemma",
            modality_hint="asserted",
        )
    else:
        meta = {
            "surface": str(getattr(tok, "text", "") or action or ""),
            "tense": "unknown",
            "aspect": "unknown",
            "verb_form": "unknown",
            "voice": "unknown",
            "mood": "unknown",
            "modality": "asserted",
            "source": "dep_lemma",
        }
    return lemma, meta


def _should_demote_non_eventive_action(doc, action: str) -> bool:
    if not doc or not action:
        return False
    action_norm = str(action or "").strip().lower()
    if not action_norm:
        return False
    root = None
    for tok in doc:
        if str(getattr(tok, "dep_", "") or "") == "ROOT":
            root = tok
            break
    if root is None:
        return False
    root_lemma = str(getattr(root, "lemma_", "") or "").strip().lower()
    if root_lemma not in {"be", "have"}:
        return False
    saw_eventive_match = False
    saw_nominal_match = False
    for tok in doc:
        text_norm = str(getattr(tok, "text", "") or "").strip().lower()
        lemma_norm = str(getattr(tok, "lemma_", "") or "").strip().lower()
        if action_norm not in {text_norm, lemma_norm}:
            continue
        pos = str(getattr(tok, "pos_", "") or "")
        if pos in {"VERB", "AUX"}:
            saw_eventive_match = True
        elif pos in {"NOUN", "ADJ", "PROPN"}:
            saw_nominal_match = True
    return saw_nominal_match and not saw_eventive_match


def _norm_phrase(s: str) -> str:
    t = re.sub(r"[^A-Za-z0-9 ]+", " ", str(s or ""))
    return re.sub(r"\s+", " ", t).strip().lower()


def _token_set(s: str) -> set:
    out = set()
    for w in re.split(r"\s+", _norm_phrase(s)):
        if not w:
            continue
        if len(w) <= 1:
            continue
        out.add(w)
    return out


_NON_VERB_HEAD_WORDS = {"for", "with", "into", "of", "in", "on", "at", "by", "from", "about"}
_NUMERIC_VALUE_RE = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?$")
_NUMERIC_MENTION_RE = re.compile(
    r"(?:(?:us\$|a\$|[$€£])\s*|(?:usd|aud|eur|gbp)\s+)?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:%|percent|per\s+cent|million|billion|trillion|thousand|hundred|years?|months?|days?|lines?|points?|dollars?|usd|aud|eur|gbp)?",
    re.IGNORECASE,
)
_NUMERIC_COMPACT_SUFFIX_RE = re.compile(
    r"(?i)^([+-]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?))\s*(%|percent|million|billion|trillion|thousand|hundred|years?|months?|days?|lines?|points?|dollars?|usd|aud|eur|gbp)$"
)
_NUMERIC_SCALE_TOKENS = {"hundred", "thousand", "million", "billion", "trillion"}
_NUMERIC_SCALE_MULTIPLIERS = {
    "hundred": Decimal("1e2"),
    "thousand": Decimal("1e3"),
    "million": Decimal("1e6"),
    "billion": Decimal("1e9"),
    "trillion": Decimal("1e12"),
}
_NUMERIC_CURRENCY_WORD_TOKENS = {"usd", "aud", "eur", "gbp"}
_NUMERIC_CURRENCY_PREFIX_TOKENS = {
    "$": "usd",
    "us$": "usd",
    "a$": "aud",
    "€": "eur",
    "£": "gbp",
    "usd": "usd",
    "aud": "aud",
    "eur": "eur",
    "gbp": "gbp",
}
_NUMERIC_WORD_TOKENS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
    "thousand",
    "million",
    "billion",
    "trillion",
}
_NUMERIC_UNIT_TOKENS = {
    "%",
    "percent",
    "percentage",
    "per",
    "cent",
    "point",
    "points",
    "year",
    "years",
    "month",
    "months",
    "day",
    "days",
    "line",
    "lines",
    "dollar",
    "dollars",
    "usd",
    "aud",
    "eur",
    "gbp",
}
_NUMERIC_FILLER_TOKENS = {
    "of",
    "the",
    "a",
    "an",
    "and",
    "to",
    "for",
    "in",
    "on",
    "at",
    "by",
    "from",
    "with",
    "or",
    "than",
    "more",
    "less",
    "about",
    "around",
    "over",
    "under",
}
_NUMERIC_ROLE_TRANSACTION_ACTIONS = {
    "buy",
    "purchase",
    "acquire",
    "sell",
    "arrange",
    "launch",
}
_NUMERIC_ROLE_INVEST_ACTIONS = {"invest", "fund"}
_NUMERIC_ROLE_REVENUE_ACTIONS = {"earn", "make", "generate", "collect", "receive"}
_NUMERIC_ROLE_COST_ACTIONS = {"cost", "spend", "pay", "allocate"}
_NUMERIC_DEP_UNIT_HEADS = {
    "percent",
    "percentage",
    "dollar",
    "dollars",
    "year",
    "years",
    "month",
    "months",
    "day",
    "days",
    "line",
    "lines",
    "point",
    "points",
}


def _normalize_numeric_mention(raw: str) -> str:
    t = _clean_entity_surface(raw)
    if not t:
        return ""
    t = re.sub(r"(?i)\bper\s+cent\b", "percent", t)
    toks = [x for x in t.split() if x]
    if toks:
        m0 = _NUMERIC_COMPACT_SUFFIX_RE.match(str(toks[0]))
        if m0:
            toks = [str(m0.group(1)), str(m0.group(2))] + toks[1:]
            t = " ".join(toks)
    currency_code = ""
    m_cur = re.match(r"(?i)^(us\$|a\$|\$|€|£|usd|aud|eur|gbp)\s*(.+)$", t)
    if m_cur:
        cur = str(m_cur.group(1) or "").strip().lower()
        t = str(m_cur.group(2) or "").strip()
        currency_code = _NUMERIC_CURRENCY_PREFIX_TOKENS.get(cur, "")
    compact = t.replace(" ", "")
    m = _NUMERIC_COMPACT_SUFFIX_RE.match(compact)
    if m:
        t = f"{m.group(1)} {m.group(2)}"
    if currency_code and not re.search(r"(?i)\b(?:usd|aud|eur|gbp|dollars?)\b", t):
        t = f"{t} {currency_code}"
    return re.sub(r"\s+", " ", t).strip()


def _numeric_key(raw: str) -> str:
    t = _normalize_numeric_mention(raw)
    if not t:
        return ""
    parts = [p for p in str(t).strip().split() if p]
    if not parts:
        return ""
    num_raw = str(parts[0] or "").strip()
    if not num_raw:
        return ""
    unit_parts = [str(x).strip().lower() for x in parts[1:] if str(x).strip()]
    canonical_units: List[str] = []
    for u in unit_parts:
        if u in {"%", "percentage", "percent"}:
            canonical_units.append("percent")
            continue
        if u in {"dollar", "dollars", "usd"}:
            canonical_units.append("usd")
            continue
        if u in {"aud", "eur", "gbp"}:
            canonical_units.append(u)
            continue
        if u in {"years", "year"}:
            canonical_units.append("year")
            continue
        if u in {"months", "month"}:
            canonical_units.append("month")
            continue
        if u in {"days", "day"}:
            canonical_units.append("day")
            continue
        if u in {"lines", "line"}:
            canonical_units.append("line")
            continue
        if u in {"points", "point"}:
            canonical_units.append("point")
            continue
        if u in _NUMERIC_SCALE_TOKENS:
            canonical_units.append(u)
            continue
        return ""

    dec: Optional[Decimal] = None
    if _babel_parse_decimal is not None:
        try:
            parsed = _babel_parse_decimal(num_raw, locale="en_US")
            dec = Decimal(str(parsed))
        except Exception:
            dec = None
    if dec is None:
        try:
            dec = Decimal(num_raw.replace(",", ""))
        except InvalidOperation:
            return ""

    def _value_text(d: Decimal, scientific: bool = False) -> str:
        if scientific:
            sci = format(d.normalize(), "E")
            mantissa, exponent = sci.split("E", 1)
            mantissa = mantissa.rstrip("0").rstrip(".")
            if not mantissa:
                mantissa = "0"
            return f"{mantissa}e{int(exponent)}"
        out = format(d.normalize(), "f")
        if "." in out:
            out = out.rstrip("0").rstrip(".")
        if out == "-0":
            out = "0"
        return out

    unit = ""
    scale = ""
    currency = ""
    use_scientific = False
    if canonical_units:
        uniq_units = list(dict.fromkeys(canonical_units))
        if len(uniq_units) == 1:
            unit = uniq_units[0]
        elif len(uniq_units) == 2:
            scale = next((u for u in uniq_units if u in _NUMERIC_SCALE_TOKENS), "")
            currency = next((u for u in uniq_units if u in _NUMERIC_CURRENCY_WORD_TOKENS), "")
            if not (scale and currency):
                return ""
            multiplier = _NUMERIC_SCALE_MULTIPLIERS.get(scale)
            if multiplier is None:
                return ""
            dec = dec * multiplier
            unit = currency
            use_scientific = True
        else:
            return ""
    value = _value_text(dec, scientific=use_scientific)
    return f"{value}|{unit}"


def _numeric_unit_from_key(nk: str) -> str:
    k = str(nk or "").strip()
    if "|" not in k:
        return ""
    return k.split("|", 1)[1].strip().lower()


def _numeric_value_from_key(nk: str) -> str:
    k = str(nk or "").strip()
    if "|" not in k:
        return ""
    return k.split("|", 1)[0].strip()


def _significant_figures_from_text(num_text: str) -> Optional[int]:
    s = str(num_text or "").strip().lower().replace(",", "")
    if not s:
        return None
    if s[0] in {"+", "-"}:
        s = s[1:]
    if not s:
        return None
    if "." in s:
        if s.startswith("0."):
            frac = s.split(".", 1)[1]
            frac = frac.lstrip("0")
            return len(frac) if frac else 1
        digits = s.replace(".", "")
        digits = digits.lstrip("0")
        return len(digits) if digits else 1
    digits = s.lstrip("0")
    return len(digits) if digits else 1


def _numeric_expression_metadata(raw: str, nk: str) -> dict:
    src = _normalize_numeric_mention(raw)
    if not src:
        return {
            "mantissa_text": None,
            "scale_word": None,
            "exponent_from_scale": None,
            "significant_figures": None,
            "coercion_applied": False,
        }
    toks = [t for t in src.split() if t]
    mantissa_text = ""
    scale_word = None
    exponent = None
    if toks:
        first = str(toks[0] or "")
        m_comp = _NUMERIC_COMPACT_SUFFIX_RE.match(first)
        if m_comp:
            mantissa_text = str(m_comp.group(1) or "").replace(",", "")
            cand_scale = str(m_comp.group(2) or "").strip().lower()
            if cand_scale in _NUMERIC_SCALE_TOKENS:
                scale_word = cand_scale
        else:
            mantissa_text = first.replace(",", "")
            if len(toks) > 1:
                cand_scale = str(toks[1] or "").strip().lower()
                if cand_scale in _NUMERIC_SCALE_TOKENS:
                    scale_word = cand_scale
    if scale_word in _NUMERIC_SCALE_MULTIPLIERS:
        try:
            exp_str = format(_NUMERIC_SCALE_MULTIPLIERS[scale_word], "E").split("E", 1)[1]
            exponent = int(exp_str)
        except Exception:
            exponent = None
    sig_figs = _significant_figures_from_text(mantissa_text)
    canonical_value = _numeric_value_from_key(nk)
    coercion_applied = False
    if mantissa_text and canonical_value:
        try:
            coercion_applied = format(Decimal(mantissa_text).normalize(), "f").rstrip("0").rstrip(".") != canonical_value
        except Exception:
            coercion_applied = bool(scale_word)
    elif scale_word:
        coercion_applied = True
    return {
        "mantissa_text": mantissa_text or None,
        "scale_word": scale_word,
        "exponent_from_scale": exponent,
        "significant_figures": sig_figs,
        "coercion_applied": bool(coercion_applied),
    }


def _numeric_surface_metadata(raw: str) -> dict:
    text = re.sub(r"\s+", " ", str(raw or "").strip())
    if not text:
        return {
            "currency_symbol_position": "none",
            "compact_suffix_used": False,
            "scale_word_used": False,
            "thousands_separator_used": False,
            "spacing_pattern": "unknown",
            "raw_surface_hash": None,
        }
    low = text.lower()
    currency_symbol_position = "none"
    if re.match(r"^\s*(?:us\$|a\$|\$|€|£)", text, flags=re.IGNORECASE):
        currency_symbol_position = "prefix"
    elif re.search(r"(?:us\$|a\$|\$|€|£)\s*$", text, flags=re.IGNORECASE):
        currency_symbol_position = "suffix"
    compact_suffix_used = bool(re.search(r"\d(?:k|m|bn|b|t)\b", low))
    scale_word_used = bool(re.search(r"\b(?:hundred|thousand|million|billion|trillion)\b", low)) or bool(
        re.search(r"\d(?:hundred|thousand|million|billion|trillion)\b", low)
    )
    thousands_separator_used = bool(re.search(r"\d,\d", text))
    if re.search(r"\d(?:hundred|thousand|million|billion|trillion)\b", low) or re.search(
        r"(?:us\$|a\$|\$|€|£)\d", text, flags=re.IGNORECASE
    ):
        spacing_pattern = "no_space"
    elif re.search(r"\d\s+(?:hundred|thousand|million|billion|trillion)\b", low):
        spacing_pattern = "space"
    else:
        spacing_pattern = "unknown"
    return {
        "currency_symbol_position": currency_symbol_position,
        "compact_suffix_used": compact_suffix_used,
        "scale_word_used": scale_word_used,
        "thousands_separator_used": thousands_separator_used,
        "spacing_pattern": spacing_pattern,
        "raw_surface_hash": hashlib.sha1(low.encode("utf-8")).hexdigest()[:16] if low else None,
    }


def _numeric_normalized_payload(nk: str, raw: str = "") -> dict:
    value = _numeric_value_from_key(nk)
    unit = _numeric_unit_from_key(nk)
    scale = ""
    currency = ""
    if "_" in unit:
        left, right = unit.split("_", 1)
        if left in _NUMERIC_SCALE_TOKENS and right in _NUMERIC_CURRENCY_WORD_TOKENS:
            scale = left
            currency = right
    elif unit in _NUMERIC_CURRENCY_WORD_TOKENS:
        currency = unit
    elif unit in _NUMERIC_SCALE_TOKENS:
        scale = unit

    out = {
        "value": value,
        "unit": unit,
        "scale": scale or None,
        "currency": currency or None,
        "expression": _numeric_expression_metadata(raw, nk),
        "surface": _numeric_surface_metadata(raw),
    }
    if _magnitude_id is not None and value:
        try:
            out["magnitude_id"] = _magnitude_id(Decimal(value), unit)
        except Exception:
            out["magnitude_id"] = f"mag:{value}|{unit}"
    elif value:
        out["magnitude_id"] = f"mag:{value}|{unit}"
    return out


def _years_in_text(text: str) -> List[int]:
    out = set()
    for y in re.findall(r"\b(?:19|20)\d{2}\b", str(text or "")):
        try:
            out.add(int(y))
        except Exception:
            continue
    return sorted(out)


def _contains_month_word(text: str) -> bool:
    toks = _norm_phrase(str(text or "")).split()
    return any(tok in MONTH_WORDS for tok in toks)


def _collect_date_like_char_ranges(doc) -> List[Tuple[int, int]]:
    if doc is None:
        return []
    out: List[Tuple[int, int]] = []
    seen = set()
    try:
        for ent in getattr(doc, "ents", []):
            st = int(getattr(ent, "start_char", -1))
            en = int(getattr(ent, "end_char", -1))
            if st < 0 or en <= st:
                continue
            label = str(getattr(ent, "label_", "") or "")
            txt = str(getattr(ent, "text", "") or "")
            has_digit = any(ch.isdigit() for ch in txt)
            if label in {"DATE", "TIME"} or (has_digit and _contains_month_word(txt)):
                key = (st, en)
                if key in seen:
                    continue
                seen.add(key)
                out.append(key)
    except Exception:
        return []

    # Token-pattern fallback: month-word + day (+ optional year). This catches
    # "September 11 attacks" even when NER doesn't emit a DATE entity.
    try:
        toks = list(doc)
        i = 0
        while i < len(toks):
            t0 = toks[i]
            w0 = str(getattr(t0, "text", "") or "").strip()
            if not w0:
                i += 1
                continue
            if _norm_phrase(w0).lower() not in MONTH_WORDS:
                i += 1
                continue

            j = i + 1
            # Skip punctuation like commas between month and day.
            while j < len(toks) and str(getattr(toks[j], "text", "") or "").strip() in {",", ".", "–", "-", "—"}:
                j += 1
            if j >= len(toks):
                i += 1
                continue
            t1 = toks[j]
            w1 = str(getattr(t1, "text", "") or "").strip()
            if not w1 or not any(ch.isdigit() for ch in w1):
                i += 1
                continue

            k = j + 1
            while k < len(toks) and str(getattr(toks[k], "text", "") or "").strip() in {",", ".", "–", "-", "—"}:
                k += 1
            if k < len(toks):
                w2 = str(getattr(toks[k], "text", "") or "").strip()
                if len(w2) == 4 and w2.isdigit():
                    end_tok = toks[k]
                else:
                    end_tok = toks[j]
            else:
                end_tok = toks[j]

            st = int(getattr(t0, "idx", -1) or -1)
            en = int(getattr(end_tok, "idx", -1) or -1)
            if st >= 0 and en >= st:
                en = en + len(str(getattr(end_tok, "text", "") or ""))
                key = (st, en)
                if key not in seen:
                    seen.add(key)
                    out.append(key)
            i = j
    except Exception:
        pass
    return out


def _is_date_like_numeric_key(nk: str) -> bool:
    unit = _numeric_unit_from_key(nk)
    if unit not in {"", "year", "month", "day"}:
        return False
    value = _numeric_value_from_key(nk).lstrip("+-")
    if not value.isdigit():
        return False
    return len(value) <= 2 or len(value) == 4


def _scan_left_digits(text: str, idx_exclusive: int) -> str:
    j = int(idx_exclusive) - 1
    out = []
    while j >= 0:
        ch = text[j]
        if not ch.isdigit():
            break
        out.append(ch)
        j -= 1
    if not out:
        return ""
    out.reverse()
    return "".join(out)


def _scan_right_digits(text: str, idx_inclusive: int) -> str:
    j = int(idx_inclusive)
    out = []
    n = len(text)
    while j < n:
        ch = text[j]
        if not ch.isdigit():
            break
        out.append(ch)
        j += 1
    return "".join(out)


def _is_slash_date_fragment(text: str, start_char: int, end_char: int, nk: str) -> bool:
    if not _is_date_like_numeric_key(nk):
        return False
    s = str(text or "")
    if start_char < 0 or end_char <= start_char or end_char > len(s):
        return False
    left = ""
    right = ""
    if start_char > 0 and s[start_char - 1] == "/":
        left = _scan_left_digits(s, start_char - 1)
    if end_char < len(s) and s[end_char] == "/":
        right = _scan_right_digits(s, end_char + 1)
    other = left or right
    if not other:
        return False
    value = _numeric_value_from_key(nk).lstrip("+-")
    if not value.isdigit() or not other.isdigit():
        return False
    a = int(value)
    b = int(other)
    if a < 1 or b < 1 or a > 31 or b > 31:
        return False
    return a <= 12 or b <= 12


def _nearest_years_from_doc(doc, token_i: int, limit: int = 2) -> List[int]:
    if doc is None:
        return []
    pairs: List[Tuple[int, int]] = []
    try:
        for ent in getattr(doc, "ents", []):
            if str(getattr(ent, "label_", "") or "") != "DATE":
                continue
            ys = _years_in_text(str(getattr(ent, "text", "") or ""))
            if not ys:
                continue
            st = int(getattr(ent, "start", token_i))
            en = int(getattr(ent, "end", token_i + 1)) - 1
            dist = min(abs(int(token_i) - st), abs(int(token_i) - en))
            for y in ys:
                pairs.append((dist, int(y)))
    except Exception:
        return []
    if not pairs:
        return []
    out: List[int] = []
    seen = set()
    for _, y in sorted(pairs, key=lambda t: (int(t[0]), int(t[1]))):
        if y in seen:
            continue
        seen.add(y)
        out.append(y)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _nearest_date_text_from_doc(doc, token_i: int) -> Optional[str]:
    if doc is None:
        return None
    pairs: List[Tuple[int, str]] = []
    try:
        for ent in getattr(doc, "ents", []):
            if str(getattr(ent, "label_", "") or "") != "DATE":
                continue
            txt = _clean_entity_surface(str(getattr(ent, "text", "") or ""))
            if not txt:
                continue
            st = int(getattr(ent, "start", token_i))
            en = int(getattr(ent, "end", token_i + 1)) - 1
            dist = min(abs(int(token_i) - st), abs(int(token_i) - en))
            pairs.append((dist, txt))
    except Exception:
        return None
    if not pairs:
        return None
    return sorted(pairs, key=lambda t: (int(t[0]), str(t[1])))[0][1]


def _compact_time_anchor(anchor: Optional[dict]) -> Optional[dict]:
    if not isinstance(anchor, dict):
        return None
    out = {}
    for k in ("year", "month", "day", "precision", "kind", "text"):
        if k in anchor and anchor.get(k) not in (None, ""):
            out[k] = anchor.get(k)
    return out or None


def _infer_numeric_role(action: str, nk: str, context: str) -> str:
    act = _base_action_label(action)
    unit = _numeric_unit_from_key(nk)
    ctx = f" {_norm_phrase(context)} "

    if unit == "percent":
        return "percentage_of" if " of " in ctx else "rate"

    is_currency = bool(unit in {"usd", "aud", "eur", "gbp"} or unit.endswith("_usd") or unit.endswith("_aud") or unit.endswith("_eur") or unit.endswith("_gbp"))
    if is_currency:
        if act in _NUMERIC_ROLE_INVEST_ACTIONS:
            return "personal_investment"
        if act in _NUMERIC_ROLE_REVENUE_ACTIONS:
            return "revenue"
        if act in _NUMERIC_ROLE_COST_ACTIONS:
            return "cost"
        if act in _NUMERIC_ROLE_TRANSACTION_ACTIONS:
            if " purchase " in ctx or " acquire " in ctx or " sale " in ctx or " sell " in ctx or " stake " in ctx:
                return "transaction_price"
            if " for " in ctx:
                return "transaction_price"
        return "cost"

    return "count"


def _extract_numeric_span_candidates(doc) -> List[dict]:
    if doc is None:
        return []
    out: List[dict] = []
    seen = set()
    date_ranges = _collect_date_like_char_ranges(doc)

    def _quantity_of_from_head(head_tok) -> Optional[str]:
        try:
            for child in head_tok.children:
                dep = str(getattr(child, "dep_", "") or "")
                lem = str(getattr(child, "lemma_", "") or getattr(child, "text", "") or "").strip().lower()
                if dep not in {"prep", "nmod"} or lem != "of":
                    continue
                for pobj in child.children:
                    pdep = str(getattr(pobj, "dep_", "") or "")
                    if pdep not in {"pobj", "obj"}:
                        continue
                    surfaced = _clean_entity_surface(_subject_surface_for_token(doc, pobj))
                    if surfaced:
                        return surfaced
        except Exception:
            return None
        return None

    def _enrich_from_dep(cand: dict) -> dict:
        root_i = int(cand.get("root_i", -1))
        if root_i < 0 or root_i >= len(doc):
            return cand
        try:
            tok = doc[root_i]
            dep = str(getattr(tok, "dep_", "") or "")
            if dep not in {"nummod", "npadvmod"}:
                return cand
            head = getattr(tok, "head", None)
            if head is None:
                return cand
            head_lemma = str(getattr(head, "lemma_", "") or getattr(head, "text", "") or "").strip().lower()
            head_text = _clean_entity_surface(str(getattr(head, "text", "") or ""))
            # Recover omitted count units from dependency heads (e.g., "71 ... lines").
            if not _numeric_unit_from_key(str(cand.get("key") or "")) and head_lemma in _NUMERIC_DEP_UNIT_HEADS and head_text:
                composed = _normalize_numeric_mention(f"{str(cand.get('value') or '')} {head_text}")
                nk2 = _numeric_key(composed)
                if nk2:
                    cand["value"] = composed
                    cand["key"] = nk2
                    cand["source"] = f"{str(cand.get('source') or '')}+dep_unit"
            quantity_of = _quantity_of_from_head(head)
            if quantity_of:
                cand["quantity_of"] = quantity_of
        except Exception:
            return cand
        return cand

    def emit(span, source: str) -> None:
        raw = str(getattr(span, "text", "") or "").strip()
        if not raw:
            return
        val = _normalize_numeric_mention(raw)
        start_tok_i = int(getattr(span, "start", -1))
        currency_code = ""
        if start_tok_i >= 0:
            try:
                first_tok = str(getattr(doc[start_tok_i], "text", "") or "").strip().lower()
                if first_tok in _NUMERIC_CURRENCY_PREFIX_TOKENS:
                    currency_code = _NUMERIC_CURRENCY_PREFIX_TOKENS.get(first_tok, "")
                elif start_tok_i > 0:
                    prev_tok = str(getattr(doc[start_tok_i - 1], "text", "") or "").strip().lower()
                    if prev_tok in _NUMERIC_CURRENCY_PREFIX_TOKENS:
                        currency_code = _NUMERIC_CURRENCY_PREFIX_TOKENS.get(prev_tok, "")
            except Exception:
                currency_code = ""
        if currency_code and not re.search(r"(?i)\b(?:usd|aud|eur|gbp|dollars?)\b", val):
            val = _normalize_numeric_mention(f"{val} {currency_code}")
        nk = _numeric_key(val)
        if not nk:
            return
        if re.fullmatch(r"(?:19|20)\d{2}\|", nk):
            # Time anchors are handled in temporal lanes, not numeric claims.
            return
        start = int(getattr(span, "start_char", -1))
        end = int(getattr(span, "end_char", -1))
        if _is_slash_date_fragment(str(getattr(doc, "text", "") or ""), start, end, nk):
            return
        overlaps_date = any(ds < end and start < de for ds, de in date_ranges if ds >= 0 and de > ds)
        if overlaps_date and _is_date_like_numeric_key(nk):
            return
        # Prefer a numeric modifier token (`nummod`) within the span as the
        # dependency anchor. spaCy NER spans (e.g., PERCENT) often pick the unit
        # head ("percent") as `.root`, but enrichment (unit/quantity-of) is
        # driven by the numeric token.
        root = getattr(span, "root", None)
        root_tok = root
        try:
            best_i = None
            for t in span:
                dep = str(getattr(t, "dep_", "") or "")
                if dep not in {"nummod", "npadvmod"}:
                    continue
                if not bool(getattr(t, "like_num", False)):
                    continue
                ti = int(getattr(t, "i", -1))
                if ti < 0:
                    continue
                if best_i is None or ti < best_i:
                    best_i = ti
                    root_tok = t
        except Exception:
            root_tok = root
        root_i = int(getattr(root_tok, "i", -1)) if root_tok is not None else -1
        cand = {
            "start": start,
            "end": end,
            "root_i": root_i,
            "raw": raw,
            "value": val,
            "key": nk,
            "source": source,
        }
        cand = _enrich_from_dep(cand)
        nk = str(cand.get("key") or "")
        key = (start, end, nk)
        if key in seen:
            return
        seen.add(key)
        out.append(cand)

    try:
        for ent in getattr(doc, "ents", []):
            label = str(getattr(ent, "label_", "") or "")
            if label in {"CARDINAL", "QUANTITY", "PERCENT", "MONEY"}:
                emit(ent, "doc_ent")
    except Exception:
        pass

    try:
        toks = list(doc)
        i = 0
        while i < len(toks):
            tok = toks[i]
            ttxt = str(getattr(tok, "text", "") or "").strip()
            lower = ttxt.lower()
            looks_numeric = (
                bool(getattr(tok, "like_num", False))
                or bool(_NUMERIC_VALUE_RE.fullmatch(lower))
                or bool(_NUMERIC_COMPACT_SUFFIX_RE.match(ttxt.replace(" ", "")))
                or any(ch.isdigit() for ch in ttxt)
            )
            if not looks_numeric:
                i += 1
                continue
            start_i = i
            if i > 0:
                prev = str(getattr(toks[i - 1], "text", "") or "").strip().lower()
                if prev in _NUMERIC_CURRENCY_PREFIX_TOKENS:
                    start_i = i - 1

            j = i + 1
            while j < len(toks):
                nxt = str(getattr(toks[j], "text", "") or "").strip().lower()
                if nxt in _NUMERIC_UNIT_TOKENS or nxt in _NUMERIC_SCALE_TOKENS or nxt in _NUMERIC_CURRENCY_WORD_TOKENS or nxt == "%":
                    j += 1
                    continue
                break
            span = doc[start_i:j]
            emit(span, "token_scan")
            i = j
    except Exception:
        pass

    out.sort(key=lambda x: (int(x.get("start", -1)), int(x.get("end", -1)), str(x.get("key") or "")))
    return out


def _governing_verb_token(doc, token_i: int):
    if doc is None:
        return None
    if token_i < 0 or token_i >= len(doc):
        return None
    cur = doc[token_i]
    for _ in range(16):
        pos = str(getattr(cur, "pos_", "") or "")
        dep = str(getattr(cur, "dep_", "") or "")
        if pos in {"VERB", "AUX"} and dep != "aux":
            return cur
        nxt = getattr(cur, "head", None)
        if nxt is None or nxt is cur:
            break
        cur = nxt
    return None


def _nearest_token_distance(indices: List[int], target: int) -> int:
    if not indices:
        return 10**9
    return min(abs(int(x) - int(target)) for x in indices)


def _extract_step_numeric_claims(
    doc,
    text: str,
    steps: List[dict],
    event_anchor: Optional[dict] = None,
) -> Dict[int, List[dict]]:
    if doc is None or not steps:
        return {}

    step_lemmas: List[set] = []
    step_verb_indices: List[List[int]] = []
    for s in steps:
        action = str(s.get("action") or "")
        lemmas = {str(x).lower() for x in _action_lemmas(action) if str(x).strip()}
        step_lemmas.append(lemmas)
        idxs: List[int] = []
        for tok in doc:
            pos = str(getattr(tok, "pos_", "") or "")
            if pos not in {"VERB", "AUX"}:
                continue
            lemma = str(getattr(tok, "lemma_", "") or "").lower()
            if lemma in lemmas:
                idxs.append(int(getattr(tok, "i", -1)))
        step_verb_indices.append(sorted([x for x in idxs if x >= 0]))

    claims_by_step: Dict[int, List[dict]] = {i: [] for i in range(len(steps))}
    seen_step_claim = set()
    compact_anchor = _compact_time_anchor(event_anchor)
    cands = _extract_numeric_span_candidates(doc)
    for cand in cands:
        root_i = int(cand.get("root_i", -1))
        gov = _governing_verb_token(doc, root_i)
        target_idx: Optional[int] = None
        alignment = "nearest_step"
        if gov is not None:
            gov_lemma = str(getattr(gov, "lemma_", "") or "").lower()
            gov_i = int(getattr(gov, "i", -1))
            matched = [i for i, lems in enumerate(step_lemmas) if gov_lemma in lems]
            if matched:
                target_idx = min(
                    matched,
                    key=lambda i: _nearest_token_distance(step_verb_indices[i], gov_i),
                )
                alignment = "dep_governor"
            else:
                anc = getattr(gov, "head", None)
                hops = 0
                while anc is not None and anc is not getattr(anc, "head", None) and hops < 12:
                    apos = str(getattr(anc, "pos_", "") or "")
                    if apos in {"VERB", "AUX"}:
                        anc_lemma = str(getattr(anc, "lemma_", "") or "").lower()
                        anc_i = int(getattr(anc, "i", -1))
                        anc_match = [i for i, lems in enumerate(step_lemmas) if anc_lemma in lems]
                        if anc_match:
                            target_idx = min(
                                anc_match,
                                key=lambda i: _nearest_token_distance(step_verb_indices[i], anc_i),
                            )
                            alignment = "dep_verb_chain"
                            break
                    anc = getattr(anc, "head", None)
                    hops += 1

        if target_idx is None:
            scored = [
                (i, _nearest_token_distance(step_verb_indices[i], root_i))
                for i in range(len(steps))
                if step_verb_indices[i]
            ]
            if scored:
                target_idx = sorted(scored, key=lambda t: (t[1], t[0]))[0][0]
            elif len(steps) == 1:
                target_idx = 0

        if target_idx is None:
            continue

        step = steps[target_idx]
        action = str(step.get("action") or "")
        context_text = str(cand.get("raw") or "")
        if gov is not None:
            try:
                subtree_tokens = list(getattr(gov, "subtree", []))
                if subtree_tokens:
                    st = min(int(getattr(t, "i", 0)) for t in subtree_tokens)
                    en = max(int(getattr(t, "i", 0)) for t in subtree_tokens) + 1
                    context_text = str(doc[st:en].text or context_text)
            except Exception:
                pass

        nk = str(cand.get("key") or "")
        role = _infer_numeric_role(action, nk, context_text)
        applies_to: Optional[str] = None
        if role == "personal_investment":
            subs = [str(x) for x in (step.get("subjects") or []) if str(x).strip()]
            applies_to = subs[0] if subs else None
        elif role == "transaction_price":
            ents = [str(x) for x in (step.get("entity_objects") or step.get("objects") or []) if str(x).strip()]
            applies_to = ents[0] if ents else None
        elif role in {"count", "percentage_of"}:
            qo = _clean_entity_surface(str(cand.get("quantity_of") or ""))
            if qo:
                applies_to = qo

        claim_key = (target_idx, nk, role)
        if claim_key in seen_step_claim:
            continue
        seen_step_claim.add(claim_key)
        claim = {
            "key": nk,
            "value": str(cand.get("value") or ""),
            "role": role,
            "alignment": alignment,
            "governing_action": _base_action_label(action),
            "normalized": _numeric_normalized_payload(nk, raw=str(cand.get("raw") or "")),
        }
        years = _nearest_years_from_doc(doc, root_i, limit=2)
        nearest_date_text = _nearest_date_text_from_doc(doc, root_i)
        if not years:
            years = _years_in_text(context_text)
        if not years:
            years = _years_in_text(text)
        if years:
            claim["time_years"] = years
        if nearest_date_text:
            # spaCy DATE entities sometimes drop the year ("May" instead of
            # "May 2004"). If we have an event anchor year and the DATE mention
            # is month-qualified, prefer anchoring to the event-year to avoid
            # losing attribution precision.
            if compact_anchor and _contains_month_word(nearest_date_text) and not _years_in_text(nearest_date_text):
                ay = compact_anchor.get("year")
                atxt = str(compact_anchor.get("text") or "").strip()
                if isinstance(ay, int) and ay > 0:
                    if atxt and str(ay) in atxt and _contains_month_word(atxt):
                        nearest_date_text = atxt
                    else:
                        nearest_date_text = f"{nearest_date_text} {ay}".strip()
            claim["time_text"] = nearest_date_text
        if compact_anchor:
            claim["time_anchor"] = dict(compact_anchor)
        if applies_to:
            claim["applies_to"] = applies_to
        claims_by_step[target_idx].append(claim)

    for idx in list(claims_by_step.keys()):
        claims_by_step[idx].sort(key=lambda x: (str(x.get("key") or ""), str(x.get("role") or "")))
    return claims_by_step


def _dedupe_numeric_objects_prefer_currency(values: List[str]) -> List[str]:
    chosen: Dict[str, Tuple[int, bool, str]] = {}
    for idx, raw in enumerate(values or []):
        val = _normalize_numeric_mention(str(raw or ""))
        if not val:
            continue
        parts = [p for p in val.split() if p]
        has_currency = any(p.lower() in _NUMERIC_CURRENCY_WORD_TOKENS for p in parts)
        base = " ".join([p for p in parts if p.lower() not in _NUMERIC_CURRENCY_WORD_TOKENS]).strip().lower()
        key = base or val.lower()
        prev = chosen.get(key)
        if prev is None:
            chosen[key] = (idx, has_currency, val)
            continue
        prev_idx, prev_has_currency, prev_val = prev
        if has_currency and not prev_has_currency:
            chosen[key] = (idx, has_currency, val)
        elif has_currency == prev_has_currency and idx < prev_idx:
            chosen[key] = (idx, has_currency, val)
        else:
            chosen[key] = (prev_idx, prev_has_currency, prev_val)
    return [x[2] for x in sorted(chosen.values(), key=lambda t: t[0])]


def _fallback_source_entity_id(entity_type: str, title: str, url: str, version_hash: str) -> str:
    payload = f"{entity_type}|{title}|{url}|{version_hash}".strip().lower()
    return f"source:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _build_source_entity(snapshot: dict) -> dict:
    snap = snapshot if isinstance(snapshot, dict) else {}
    title = str(snap.get("title") or "Wikipedia timeline source").strip() or "Wikipedia timeline source"
    url = str(snap.get("source_url") or "").strip()
    version_hash = str(snap.get("revid") or "").strip()
    publication_date = str(snap.get("rev_timestamp") or "").strip() or None
    if _source_entity_id is not None and _SourceEntityType is not None:
        sid = _source_entity_id(
            _SourceEntityType.WIKIPEDIA_ARTICLE,
            title,
            url=url,
            version_hash=version_hash,
        )
        stype = _SourceEntityType.WIKIPEDIA_ARTICLE.value
    else:
        sid = _fallback_source_entity_id("wikipedia_article", title, url, version_hash)
        stype = "wikipedia_article"
    return {
        "id": sid,
        "type": stype,
        "title": title,
        "publication_date": publication_date,
        "url": url or None,
        "version_hash": version_hash or None,
    }


def _attribution_id_for_claim(
    claim_id: str,
    attributed_actor_id: str,
    attribution_type: str,
    source_entity_id: str,
    reporting_actor_id: str = "",
) -> str:
    if _attribution_id is not None and _AttributionType is not None:
        enum_type = _AttributionType.REPORTED_STATEMENT if attribution_type == "reported_statement" else _AttributionType.DIRECT_STATEMENT
        return _attribution_id(
            claim_id=claim_id,
            attributed_actor_id=attributed_actor_id,
            attribution_type=enum_type,
            source_entity_id_value=source_entity_id,
            reporting_actor_id=reporting_actor_id,
        )
    payload = f"{claim_id}|{attributed_actor_id}|{attribution_type}|{source_entity_id}|{reporting_actor_id}".lower()
    return f"attr:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _build_event_attributions(
    event_id: str,
    steps: List[dict],
    source_entity_id: str,
    communication_verbs: List[str],
) -> List[dict]:
    comm = {str(x or "").strip().lower() for x in (communication_verbs or []) if str(x or "").strip()}
    out: List[dict] = []
    seen = set()
    for idx, step in enumerate(steps):
        if not bool(step.get("claim_bearing")):
            continue
        subs = [str(x).strip() for x in (step.get("subjects") or []) if str(x).strip()]
        if not subs:
            continue
        action = str(step.get("action") or "")
        lemmas = {str(x or "").strip().lower() for x in _action_lemmas(action)}
        attr_type = "reported_statement" if (lemmas & comm) else "direct_statement"
        claim_id = str(step.get("claim_id") or f"{event_id}:step:{idx}")
        attributed_actor = subs[0]
        aid = _attribution_id_for_claim(claim_id, attributed_actor, attr_type, source_entity_id)
        key = (claim_id, attributed_actor.lower(), attr_type)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": aid,
                "claim_id": claim_id,
                "step_index": int(idx),
                "attributed_actor_id": attributed_actor,
                "attribution_type": attr_type,
                "source_entity_id": source_entity_id,
                "certainty_level": "explicit",
                "extraction_method": "summary",
            }
        )
    out.sort(key=lambda x: (int(x.get("step_index", 0)), str(x.get("attributed_actor_id") or "")))
    return out


def _requester_coverage_summary(events: List[dict]) -> dict:
    total = 0
    request_signal_events = 0
    requester_events = 0
    missing_requester_event_ids: List[str] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        total += 1
        actors = ev.get("actors") or []
        has_requester = any(
            str(a.get("role") or "").strip().lower() in {"requester", "requester_meta"}
            for a in actors
            if isinstance(a, dict)
        )
        text = str(ev.get("text") or "")
        has_request_clause = bool(re.search(r"\bat\s+[^.]{1,120}?\brequest\b", text, flags=re.IGNORECASE))
        if not (has_request_clause or has_requester):
            continue
        request_signal_events += 1
        if has_requester:
            requester_events += 1
        else:
            missing_requester_event_ids.append(str(ev.get("event_id") or ""))
    return {
        "total_events": int(total),
        "request_signal_events": int(request_signal_events),
        "requester_events": int(requester_events),
        "missing_requester_event_ids": [x for x in missing_requester_event_ids if x],
    }


def _normalize_actor_rows(actors: List[dict]) -> List[dict]:
    out: List[dict] = []
    for a in actors or []:
        if not isinstance(a, dict):
            continue
        row = dict(a)
        role = str(row.get("role") or "").strip().lower()
        label = str(row.get("label") or "").strip()
        resolved = str(row.get("resolved") or "").strip()
        if role in {"subject", "requester"}:
            n_label = _normalize_subject_label(label)
            n_resolved = _normalize_subject_label(resolved or label)
            if n_label:
                row["label"] = n_label
            if n_resolved:
                row["resolved"] = n_resolved
        else:
            # Keep non-subject lanes cleaned but do not force determiner stripping.
            c_label = _clean_entity_surface(label)
            c_resolved = _clean_entity_surface(resolved)
            if c_label:
                row["label"] = c_label
            if c_resolved:
                row["resolved"] = c_resolved
        out.append(row)
    return out


def _fallback_actor_from_doc(doc) -> Tuple[Optional[str], Optional[str]]:
    """Return a conservative actor fallback from a spaCy doc."""
    try:
        for tok in doc:
            dep = str(getattr(tok, "dep_", "") or "").lower()
            if dep in {"nsubj", "nsubjpass"} and str(getattr(tok, "text", "")).strip():
                return str(tok.text).strip(), "doc_subject"
    except Exception:
        pass
    try:
        for chunk in getattr(doc, "noun_chunks", []):
            txt = _clean_entity_surface(str(getattr(chunk, "text", "") or ""))
            if txt:
                return txt, "lead_np"
    except Exception:
        pass
    return None, None


def _fallback_actor_from_text(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z][A-Za-z.'-]+)\b", str(text or ""))
    if not m:
        return None
    return _clean_entity_surface(m.group(1))


def _build_extraction_record(source_entity_id: str, parser_info: Optional[dict], generated_at: str) -> dict:
    parser_version = "wiki_timeline_aoo_extract@unknown"
    if isinstance(parser_info, dict):
        model = str(parser_info.get("model") or parser_info.get("model_name") or "unknown").strip()
        version = str(parser_info.get("model_version") or "").strip()
        parser_version = f"wiki_timeline_aoo_extract@{model}{('-' + version) if version else ''}"
    if _extraction_record_id is not None:
        rid = _extraction_record_id(
            source_entity_id_value=source_entity_id,
            parser_version=parser_version,
            extraction_timestamp=generated_at,
        )
    else:
        payload = f"{source_entity_id}|{parser_version}|{generated_at}".lower()
        rid = f"xrec:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"
    return {
        "id": rid,
        "source_entity_id": source_entity_id,
        "parser_version": parser_version,
        "extraction_timestamp": generated_at,
        "confidence_score": None,
    }


def _strip_leading_determiner(text: str) -> str:
    t = " ".join(str(text or "").strip().split())
    if not t:
        return ""
    parts = t.split(" ")
    if not parts:
        return ""
    first = parts[0].strip().lower()
    if first in {"the", "a", "an"} and len(parts) > 1:
        return " ".join(parts[1:]).strip()
    return t


def _normalize_subject_label(text: str) -> str:
    s = _clean_entity_surface(text)
    if not s:
        return ""
    return _clean_entity_surface(_strip_leading_determiner(s))


def _object_keys(title: str) -> List[str]:
    base = _norm_phrase(title)
    if not base:
        return []
    keys = [base]
    det = _norm_phrase(_strip_leading_determiner(title))
    if det and det != base:
        keys.append(det)
    return keys


def _object_row_score(row: dict) -> float:
    src = str(row.get("source") or "")
    score = 0.0
    if src == "wikilink":
        score += 100.0
    elif src == "dep_object":
        score += 20.0
    hints = row.get("resolver_hints") or []
    if isinstance(hints, list):
        for h in hints:
            if not isinstance(h, dict):
                continue
            kind = str(h.get("kind") or "")
            lane = str(h.get("lane") or "")
            hs = float(h.get("score") or 0.0)
            if kind == "exact":
                score += 20.0 + hs
                if lane == "sentence_link":
                    score += 2.0
            elif kind == "near":
                score += 5.0 + hs
    if _strip_leading_determiner(str(row.get("title") or "")) == str(row.get("title") or ""):
        score += 1.0
    return score


def _exact_resolver_hint_titles(row: Optional[dict]) -> List[str]:
    if not isinstance(row, dict):
        return []
    hints = row.get("resolver_hints") or []
    if not isinstance(hints, list):
        return []
    ranked: List[Tuple[float, str, str]] = []
    for h in hints:
        if not isinstance(h, dict):
            continue
        if str(h.get("kind") or "") != "exact":
            continue
        title = _clean_entity_surface(str(h.get("title") or ""))
        if not title:
            continue
        ranked.append((float(h.get("score") or 0.0), str(h.get("lane") or ""), title))
    ranked.sort(key=lambda t: (-t[0], t[1], t[2].lower()))
    out: List[str] = []
    seen = set()
    for _, _, title in ranked:
        lk = title.lower()
        if lk in seen:
            continue
        seen.add(lk)
        out.append(title)
    return out


def _row_identity_keys(row: Optional[dict]) -> List[str]:
    if not isinstance(row, dict):
        return []
    keys: List[str] = []
    title = _clean_entity_surface(str(row.get("title") or ""))
    if title:
        keys.extend(_object_keys(title))
    for hinted in _exact_resolver_hint_titles(row):
        keys.extend(_object_keys(hinted))
    out: List[str] = []
    seen = set()
    for k in keys:
        kk = _norm_phrase(k)
        if not kk or kk in seen:
            continue
        seen.add(kk)
        out.append(kk)
    return out


def _preferred_entity_label(title: str, row: Optional[dict]) -> str:
    hints = _exact_resolver_hint_titles(row)
    if hints:
        return hints[0]
    return _clean_entity_surface(title)


def _step_subject_key(subjects: List[str]) -> Tuple[str, ...]:
    vals = set()
    for s in subjects or []:
        cleaned = _normalize_subject_label(str(s or ""))
        if not cleaned:
            continue
        vals.add(cleaned.lower())
    return tuple(sorted(vals))


def _step_object_key(objects: List[str], object_row_by_key: Dict[str, dict]) -> Tuple[str, ...]:
    vals = set()
    for obj in objects or []:
        cleaned = _clean_entity_surface(str(obj or ""))
        if not cleaned:
            continue
        row = None
        for key in _object_keys(cleaned):
            row = object_row_by_key.get(_norm_phrase(key))
            if row is not None:
                break
        if row is not None:
            ids = _row_identity_keys(row)
            if ids:
                vals.add(ids[0])
                continue
        det = _strip_leading_determiner(cleaned)
        vals.add(_norm_phrase(det or cleaned))
    return tuple(sorted(v for v in vals if v))


def _is_entity_like_object(title: str, row: Optional[dict]) -> bool:
    cleaned_title = _clean_entity_surface(title)
    if not cleaned_title:
        return False
    if _looks_like_person_mention(cleaned_title) or _looks_like_party_role(cleaned_title):
        return True
    if not isinstance(row, dict):
        return False
    src = str(row.get("source") or "")
    if src == "wikilink":
        return True
    hints = row.get("resolver_hints") or []
    if isinstance(hints, list):
        for h in hints:
            if not isinstance(h, dict):
                continue
            kind = str(h.get("kind") or "")
            lane = str(h.get("lane") or "")
            hs = float(h.get("score") or 0.0)
            if kind == "exact" and hs >= 0.95:
                return True
            if kind == "near" and lane == "sentence_link" and hs >= 0.93:
                return True
    return False


def _is_numeric_token(tok: str) -> bool:
    t = str(tok or "").strip().lower().strip(".,;:()[]{}\"'")
    if not t:
        return False
    if _NUMERIC_VALUE_RE.fullmatch(t):
        return True
    if t in _NUMERIC_WORD_TOKENS:
        return True
    return False


def _is_numeric_object(title: str, row: Optional[dict]) -> bool:
    cleaned_title = _clean_entity_surface(title)
    if not cleaned_title:
        return False
    if _looks_like_person_mention(cleaned_title) or _looks_like_party_role(cleaned_title):
        return False
    # Keep temporal anchors in the time lane, not numeric objects.
    if re.fullmatch(r"(?:19|20)\d{2}", cleaned_title):
        return False
    low = cleaned_title.lower()
    if any(m in low for m in MONTH_WORDS) and re.search(r"\b(?:19|20)\d{2}\b", low):
        return False
    toks = [re.sub(r"^[^A-Za-z0-9%+-]+|[^A-Za-z0-9%+-]+$", "", t) for t in cleaned_title.split()]
    toks = [t for t in toks if t]
    if not toks:
        return False
    has_numeric = False
    has_value_token = False
    numeric_word_count = 0
    for tok in toks:
        tl = tok.lower()
        if _is_numeric_token(tl):
            has_numeric = True
            if _NUMERIC_VALUE_RE.fullmatch(tl) or any(ch.isdigit() for ch in tl):
                has_value_token = True
            elif tl in _NUMERIC_WORD_TOKENS:
                numeric_word_count += 1
            continue
        if tl in _NUMERIC_UNIT_TOKENS or tl in _NUMERIC_FILLER_TOKENS:
            continue
        return False
    if has_numeric and (has_value_token or numeric_word_count >= 2):
        return True
    hints = row.get("resolver_hints") if isinstance(row, dict) else None
    if isinstance(hints, list):
        for h in hints:
            if not isinstance(h, dict):
                continue
            t = _clean_entity_surface(str(h.get("title") or ""))
            if not t:
                continue
            if _NUMERIC_VALUE_RE.fullmatch(t.lower()):
                return True
    return False


def _extract_numeric_mentions(text: str, doc=None) -> List[str]:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return []

    out: List[str] = []
    seen = set()
    date_ranges = _collect_date_like_char_ranges(doc)

    def _emit(cand: str, start_char: int = -1, end_char: int = -1, window_text: str = "") -> None:
        c = _normalize_numeric_mention(cand)
        if not c:
            return
        # Ignore likely date fragments; timeline anchors handle dates separately.
        if re.fullmatch(r"(?:19|20)\d{2}", c):
            return
        if CITATION_TOKEN_RE.search(c):
            return
        k = _numeric_key(c)
        if not k or k in seen:
            return
        unit = _numeric_unit_from_key(k)
        value = _numeric_value_from_key(k)
        if _is_slash_date_fragment(s, start_char, end_char, k):
            return
        if start_char >= 0 and end_char > start_char:
            overlaps_date = any(ds < end_char and start_char < de for ds, de in date_ranges)
            if overlaps_date and unit in {"", "year", "month", "day"}:
                return
        if unit in {"", "year", "month", "day"}:
            ctx = str(window_text or "").lower()
            if ctx and any(month in ctx for month in MONTH_WORDS):
                if value.isdigit() and (len(value) <= 2 or len(value) == 4):
                    return
        seen.add(k)
        out.append(c)

    # Preferred path: parser spans first, then token-local extraction.
    if doc is not None:
        # Span-candidates path: preserves dependency-derived units (e.g., "71 lines")
        # and avoids date fragments via overlap checks.
        covered: List[Tuple[int, int]] = []

        def _covered_overlap(st: int, en: int) -> bool:
            if st < 0 or en <= st:
                return False
            return any(cs < en and st < ce for cs, ce in covered if cs >= 0 and ce > cs)

        try:
            for cand in _extract_numeric_span_candidates(doc):
                st = int(cand.get("start", -1) or -1)
                en = int(cand.get("end", -1) or -1)
                if st >= 0 and en > st:
                    covered.append((st, en))
                _emit(
                    str(cand.get("value") or cand.get("raw") or ""),
                    start_char=st,
                    end_char=en,
                )
        except Exception:
            pass

        try:
            for ent in getattr(doc, "ents", []):
                label = str(getattr(ent, "label_", "") or "")
                if label in {"CARDINAL", "QUANTITY", "PERCENT", "MONEY"}:
                    est = int(getattr(ent, "start_char", -1))
                    een = int(getattr(ent, "end_char", -1))
                    if _covered_overlap(est, een):
                        continue
                    _emit(str(getattr(ent, "text", "") or ""), start_char=est, end_char=een)
        except Exception:
            pass

        try:
            toks = list(doc)
            i = 0
            while i < len(toks):
                tok = toks[i]
                ttxt = str(getattr(tok, "text", "") or "").strip()
                if not ttxt:
                    i += 1
                    continue
                lower = ttxt.lower()
                compact = ttxt.replace(" ", "")
                token_currency_code = ""
                compact_num = compact
                for pfx in ("us$", "a$", "$", "€", "£"):
                    if compact_num.lower().startswith(pfx):
                        token_currency_code = _NUMERIC_CURRENCY_PREFIX_TOKENS.get(pfx, "")
                        compact_num = compact_num[len(pfx) :]
                        break
                is_num = (
                    bool(getattr(tok, "like_num", False))
                    or bool(_NUMERIC_VALUE_RE.fullmatch(lower))
                    or bool(_NUMERIC_COMPACT_SUFFIX_RE.match(compact))
                    or bool(_NUMERIC_VALUE_RE.fullmatch(compact_num.lower()))
                    or bool(_NUMERIC_COMPACT_SUFFIX_RE.match(compact_num))
                )
                if not is_num:
                    i += 1
                    continue

                start_i = i
                currency_code = token_currency_code
                if i > 0:
                    prev_tok = str(getattr(toks[i - 1], "text", "") or "").strip().lower()
                    if prev_tok in _NUMERIC_CURRENCY_PREFIX_TOKENS:
                        start_i = i - 1
                    if not currency_code:
                        currency_code = _NUMERIC_CURRENCY_PREFIX_TOKENS.get(prev_tok, "")

                parts = [ttxt]
                j = i + 1

                # Stitch grouped thousand separators when tokenizer splits "21,500".
                if re.fullmatch(r"\d{1,3}", ttxt):
                    try:
                        start_idx = int(getattr(tok, "idx", 0) or 0)
                    except Exception:
                        start_idx = 0
                    m_group = re.match(r"\d{1,3}(?:,\d{3})+", s[start_idx:])
                    if m_group:
                        grouped = str(m_group.group(0) or "")
                        if grouped and len(grouped) > len(ttxt):
                            parts = [grouped]
                            span_end = start_idx + len(grouped)
                            while j < len(toks):
                                try:
                                    t_idx = int(getattr(toks[j], "idx", 0) or 0)
                                except Exception:
                                    t_idx = span_end
                                if t_idx < span_end:
                                    j += 1
                                    continue
                                break

                while j < len(toks):
                    nt = str(getattr(toks[j], "text", "") or "").strip()
                    if not nt:
                        j += 1
                        continue
                    nl = nt.lower()
                    if nl == "per" and (j + 1) < len(toks):
                        nxt = str(getattr(toks[j + 1], "text", "") or "").strip().lower()
                        if nxt == "cent":
                            parts.extend([nt, str(getattr(toks[j + 1], "text", "") or "").strip()])
                            j += 2
                            continue
                    if nl in _NUMERIC_UNIT_TOKENS or nl == "%":
                        parts.append(nt)
                        j += 1
                        continue
                    break

                if currency_code:
                    low_parts = {str(x).strip().lower() for x in parts if str(x).strip()}
                    if not any(x in {"usd", "aud", "eur", "gbp", "dollar", "dollars"} for x in low_parts):
                        parts.append(currency_code)

                # Skip obvious month/day/year contexts.
                win_start = max(0, int(getattr(tok, "idx", 0) or 0) - 16)
                end_tok = toks[j - 1] if j > i else tok
                win_end = min(
                    len(s),
                    int((getattr(end_tok, "idx", 0) or 0) + len(str(getattr(end_tok, "text", "") or ""))) + 16,
                )
                window = s[win_start:win_end].lower()
                candidate = " ".join([x for x in parts if x])
                if any(month in window for month in MONTH_WORDS):
                    if re.fullmatch(r"\d{1,2}|\d{4}", _normalize_numeric_mention(candidate)):
                        i = j
                        continue

                span_start_char = int(getattr(toks[start_i], "idx", -1) or -1)
                if j > start_i:
                    end_tok = toks[j - 1]
                else:
                    end_tok = tok
                span_end_char = int(getattr(end_tok, "idx", -1) or -1)
                if span_end_char >= 0:
                    span_end_char += len(str(getattr(end_tok, "text", "") or ""))
                if _covered_overlap(span_start_char, span_end_char):
                    i = j
                    continue
                _emit(candidate, start_char=span_start_char, end_char=span_end_char, window_text=window)
                i = j
                continue
        except Exception:
            pass

    # Fallback: regex mention scan (worst-case safety rail only when parser
    # extraction is unavailable or yielded no candidates).
    if doc is None or not out:
        for m in _NUMERIC_MENTION_RE.finditer(s):
            # Guard against fragment captures from grouped values (e.g., 21 / 500 from 21,500).
            if m.end() < len(s) and s[m.end()] == ",":
                continue
            if m.start() > 0 and s[m.start() - 1] == ",":
                continue
            start = max(0, m.start() - 14)
            end = min(len(s), m.end() + 14)
            window = s[start:end].lower()
            cand = str(m.group(0) or "")
            if any(month in window for month in MONTH_WORDS):
                if re.fullmatch(r"\d{1,2}|\d{4}", _normalize_numeric_mention(cand)):
                    continue
            _emit(cand, start_char=int(m.start()), end_char=int(m.end()), window_text=window)

    return out


def _collect_dep_objects(doc) -> List[str]:
    """Collect sentence-local object-like noun phrases from dependency structure."""
    if doc is None:
        return []
    obj_deps = {"dobj", "obj", "pobj", "attr", "oprd", "dative"}
    out: List[str] = []
    seen = set()
    try:
        for chunk in getattr(doc, "noun_chunks", []):
            root = getattr(chunk, "root", None)
            if root is None:
                continue
            dep = str(getattr(root, "dep_", "") or "")
            if dep not in obj_deps:
                # Handle conjunct objects.
                if dep == "conj" and str(getattr(getattr(root, "head", None), "dep_", "") or "") in obj_deps:
                    pass
                else:
                    continue
            if str(getattr(root, "pos_", "") or "") == "PRON":
                continue
            txt = re.sub(r"\s+", " ", str(getattr(chunk, "text", "") or "")).strip()
            if not txt:
                continue
            txt = _clean_entity_surface(txt)
            if not txt:
                continue
            if len(txt) > 120:
                continue
            if CITATION_TOKEN_RE.search(txt):
                continue
            # Skip obvious time phrases; time is handled by anchors.
            low = txt.lower()
            if any(m in low for m in MONTH_WORDS):
                continue
            if re.search(r"\b(?:19|20)\d{2}\b", txt):
                continue
            k = _norm_phrase(txt)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(txt)
    except Exception:
        return out
    return out


def _expand_person_mentions(text: str, alias_map: Dict[str, str]) -> List[str]:
    out: List[str] = []
    seen = set()
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return out
    low = s.lower()
    if not any(x in low for x in (" or ", " and ", "either ", "neither ")):
        return out

    def add(name: str) -> None:
        n = re.sub(r"\s+", " ", str(name or "").strip())
        if not n:
            return
        k = n.lower()
        if k in seen:
            return
        seen.add(k)
        out.append(n)

    for m in re.finditer(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3})\b", s):
        cand = m.group(1).strip()
        if _looks_like_person_title(cand):
            add(cand)

    for m in re.finditer(r"\b([A-Z][a-z]+)\b", s):
        tok = m.group(1).strip()
        if tok.lower() in MONTH_WORDS:
            continue
        resolved = alias_map.get(tok) or ""
        if resolved:
            add(resolved)
    return out


def _objects_for_action(
    doc,
    action: str,
    fallback: List[str],
    text: str,
    alias_map: Dict[str, str],
    anchor_year: Optional[int],
) -> List[str]:
    def filtered_fallback() -> List[str]:
        out_fb: List[str] = []
        seen_fb = set()
        for f in list(fallback):
            k = _clean_entity_surface(str(f or ""))
            if not k:
                continue
            if CITATION_TOKEN_RE.search(k):
                continue
            if _base_action_label(action) != "request" and re.search(r"\brequest\b", k, flags=re.IGNORECASE):
                continue
            lk = k.lower()
            if lk in seen_fb:
                continue
            seen_fb.add(lk)
            out_fb.append(k)
        return out_fb

    if doc is None:
        return filtered_fallback()
    base_action = _base_action_label(action)
    lemmas = set(_action_lemmas(base_action))
    if not lemmas:
        return filtered_fallback()

    out: List[str] = []
    seen = set()

    def add(v: str) -> None:
        k = _clean_entity_surface(str(v or ""))
        if not k:
            return
        if CITATION_TOKEN_RE.search(k):
            return
        if base_action != "request" and re.search(r"\brequest\b", k, flags=re.IGNORECASE):
            return
        lk = k.lower()
        if lk in seen:
            return
        seen.add(lk)
        out.append(k)

    def add_from_chunk(tok) -> None:
        txt = ""
        try:
            for ch in getattr(doc, "noun_chunks", []):
                root = getattr(ch, "root", None)
                if root is not None and int(getattr(root, "i", -1)) == int(getattr(tok, "i", -2)):
                    txt = re.sub(r"\s+", " ", str(getattr(ch, "text", "") or "")).strip()
                    break
        except Exception:
            txt = ""
        if not txt:
            idxs = [x.i for x in getattr(tok, "subtree", [])] or [int(getattr(tok, "i", 0))]
            span = doc[min(idxs) : max(idxs) + 1]
            txt = _clean_entity_surface(str(getattr(span, "text", "") or ""))
        if txt:
            add(txt)

    try:
        allowed_preps = {"for", "to", "into", "with", "of"}
        for v in doc:
            if str(getattr(v, "pos_", "") or "") not in {"VERB", "AUX"}:
                continue
            if str(getattr(v, "lemma_", "") or "").lower() not in lemmas:
                continue
            for c in v.children:
                dep = str(getattr(c, "dep_", "") or "")
                if dep in {"dobj", "obj", "attr", "oprd", "dative"}:
                    add_from_chunk(c)
                if dep == "prep":
                    ptxt = str(getattr(c, "text", "") or "").strip().lower()
                    if ptxt not in allowed_preps:
                        continue
                    for g in c.children:
                        if str(getattr(g, "dep_", "") or "") == "pobj":
                            add_from_chunk(g)
                            for gg in g.children:
                                if str(getattr(gg, "dep_", "") or "") == "prep":
                                    for p2 in gg.children:
                                        if str(getattr(p2, "dep_", "") or "") == "pobj":
                                            add_from_chunk(p2)
    except Exception:
        return list(fallback)

    # Expand coordinated person phrases for vote/reporting clauses:
    # "either Trump or Joe Biden" -> ["Donald Trump", "Joe Biden"].
    expanded_people: List[str] = []
    for x in list(out):
        expanded_people.extend(_expand_person_mentions(x, alias_map))
    for p in expanded_people:
        add(p)

    # Contextual election object from explicit sentence wording (deterministic, no inference beyond text+anchor).
    low = str(text or "").lower()
    if base_action in {"voted", "vote"} and "general election" in low:
        add("general election")
        if "trump" in low:
            add(alias_map.get("Trump") or "Donald Trump")
        if anchor_year and "trump" in low and "biden" in low and anchor_year > 0:
            add(f"{int(anchor_year) - 1} United States presidential election")

    if out:
        for f in filtered_fallback():
            lf = str(f).lower()
            if base_action == "told":
                if "people (magazine)" in lf:
                    add(f)
                continue
            if base_action in {"voted", "vote"} and "people (magazine)" in lf:
                continue
            add(f)
        # De-noise known split tokens when a canonical wiki title is present.
        if "people (magazine)" in {x.lower() for x in out}:
            out = [x for x in out if x.lower() not in {"people", "magazine"}]
        return out
    return filtered_fallback()


def _action_negation(doc, action: str) -> Optional[dict]:
    if doc is None:
        return None
    lemmas = set(_action_lemmas(action))
    if not lemmas:
        return None
    try:
        for v in doc:
            if str(getattr(v, "lemma_", "") or "").lower() not in lemmas:
                continue
            if str(getattr(v, "pos_", "") or "") not in {"VERB", "AUX"}:
                continue
            for c in v.children:
                if str(getattr(c, "dep_", "") or "") == "neg":
                    return {"kind": "not", "scope": "action", "source": "dep:neg"}
    except Exception:
        return None
    return None


def _resolver_hints_for_object(obj_title: str, sent_links: List[str], para_links: List[str], candidate_titles: List[str]) -> List[dict]:
    """Return deterministic exact/near resolver hints for a non-wikilink object phrase."""
    obj = str(obj_title or "").strip()
    if not obj:
        return []
    obj_norm = _norm_phrase(obj)
    obj_toks = _token_set(obj)
    if not obj_norm:
        return []

    hints: List[dict] = []
    seen = set()

    def add_hint(title: str, lane: str, kind: str, score: float) -> None:
        t = str(title or "").strip()
        if not t:
            return
        key = (t.lower(), lane, kind)
        if key in seen:
            return
        seen.add(key)
        hints.append({"lane": lane, "kind": kind, "title": t, "score": round(float(score), 4)})

    def eval_lane(titles: List[str], lane: str) -> None:
        for t in titles:
            t_norm = _norm_phrase(t)
            if not t_norm:
                continue
            if t_norm == obj_norm:
                add_hint(t, lane, "exact", 1.0)
                continue
            if obj_norm in t_norm or t_norm in obj_norm:
                add_hint(t, lane, "near", 0.93)
                continue
            tt = _token_set(t)
            if not tt or not obj_toks:
                continue
            inter = len(obj_toks & tt)
            if inter == 0:
                continue
            j = inter / max(1, len(obj_toks | tt))
            if j >= 0.45:
                add_hint(t, lane, "near", 0.70 + (0.20 * min(1.0, j)))

    eval_lane(sent_links or [], "sentence_link")
    eval_lane(para_links or [], "paragraph_link")
    eval_lane(candidate_titles or [], "candidate_title")

    hints.sort(key=lambda h: (-float(h.get("score") or 0.0), str(h.get("lane") or ""), str(h.get("title") or "")))
    return hints[:8]


def _subject_surface_for_token(doc, tok) -> str:
    try:
        toks = list(getattr(tok, "subtree", []))
        if not toks:
            return str(getattr(tok, "text", "") or "").strip()
        # Remove conjunction sibling spans when caller already iterates conjuncts separately.
        # For conjunct tokens themselves, keep local subtree intact.
        conj_drop = set()
        if str(getattr(tok, "dep_", "") or "") != "conj":
            for cj in getattr(tok, "conjuncts", []):
                conj_drop.update(int(x.i) for x in getattr(cj, "subtree", []))
            for c in getattr(tok, "children", []):
                if str(getattr(c, "dep_", "") or "") == "cc":
                    conj_drop.add(int(getattr(c, "i", -1)))
            toks = [t for t in toks if int(getattr(t, "i", -1)) not in conj_drop]
        toks = sorted(toks, key=lambda x: int(getattr(x, "i", 0)))

        # Drop clausal modifier tails for NP surfaces (e.g., `the electorate approved ...`).
        # We want the head NP, not attached relative/acl clauses.
        try:
            cut = None
            head_i = int(getattr(tok, "i", -1))
            for idx, t in enumerate(toks):
                ti = int(getattr(t, "i", -1))
                if ti == head_i:
                    continue
                dep = str(getattr(t, "dep_", "") or "")
                pos = str(getattr(t, "pos_", "") or "")
                if dep in {"acl", "relcl", "advcl"} and pos in {"VERB", "AUX"}:
                    cut = idx
                    break
            if cut is not None and cut > 0:
                toks = toks[:cut]
        except Exception:
            pass

        out = re.sub(r"\s+", " ", " ".join(str(getattr(t, "text", "") or "") for t in toks)).strip()
        # Appositive/participial tails often appear after commas; keep the head NP.
        if "," in out:
            out = out.split(",", 1)[0].strip()
        return out
    except Exception:
        return str(getattr(tok, "text", "") or "").strip()


def _resolve_subject_surface(surface: str, actors: List[dict], root_actor: str, root_surname: str) -> str:
    s = _normalize_subject_label(surface)
    if not s:
        return s
    poss = _extract_possessive_person(s)
    if poss:
        return _normalize_subject_label(poss)
    low = s.lower()
    # For first-person corpus docs (memoirs, transcripts), allow a declared root actor to absorb "I/me/my".
    if low in {"i", "me", "my", "myself"} and root_actor:
        return _normalize_subject_label(root_actor)
    if low in {"he", "him", "his"} and root_actor:
        return _normalize_subject_label(root_actor)
    if low in {"that", "which", "who"}:
        return ""
    s = _canonicalize_root_actor_surface(s, root_actor, root_surname)

    s_norm = _norm_phrase(_strip_leading_determiner(s))
    best = None
    best_len = -1
    for a in actors:
        resolved = _normalize_subject_label(str(a.get("resolved") or ""))
        label = _normalize_subject_label(str(a.get("label") or ""))
        for cand in (resolved, label):
            if not cand:
                continue
            c_norm = _norm_phrase(_strip_leading_determiner(cand))
            if not c_norm:
                continue
            if s_norm == c_norm or s_norm in c_norm or c_norm in s_norm:
                if len(cand) > best_len:
                    best = _normalize_subject_label(resolved or cand)
                    best_len = len(cand)
    if best:
        return _canonicalize_root_actor_surface(best, root_actor, root_surname)

    # Surname fallback for standalone root-actor references.
    if root_surname and re.search(rf"\b{re.escape(root_surname)}\b", s, flags=re.IGNORECASE):
        return _normalize_subject_label(root_actor or s)
    return _normalize_subject_label(s)


def _canonicalize_root_actor_surface(surface: str, root_actor: str, root_surname: str) -> str:
    """Map partial root-actor name surfaces back to canonical root actor.

    Example: "Walker Bush" in lead passive clauses should resolve to root actor
    when token set is a subset of the configured root actor tokens.
    """
    s = _normalize_subject_label(surface)
    root = _normalize_subject_label(root_actor)
    if not s or not root:
        return s
    surname = re.sub(r"[^a-z]", "", str(root_surname or "").strip().lower())
    if not surname:
        return s
    s_parts = [p for p in s.split() if p]
    r_parts = [p for p in root.split() if p]
    if len(s_parts) < 2 or len(r_parts) < 2:
        return s
    def norm_tok(x: str) -> str:
        return re.sub(r"[^a-z]", "", str(x or "").lower())

    s_tokens = {norm_tok(p) for p in s_parts if norm_tok(p)}
    r_tokens = {norm_tok(p) for p in r_parts if norm_tok(p)}
    if surname not in s_tokens:
        return s
    root_initials = {t for t in r_tokens if len(t) == 1}
    unmatched = []
    for tok in s_tokens:
        if tok in r_tokens:
            continue
        if tok and tok[0] in root_initials:
            continue
        unmatched.append(tok)
    if not unmatched:
        return root
    return s


def _subjects_for_action(doc, action: str, actors: List[dict], root_actor: str, root_surname: str) -> List[str]:
    if doc is None:
        return []
    act = _base_action_label(action)
    if not act:
        return []

    # Deterministic fallback for first-person corpus rows when the underlying NLP
    # pipeline does not provide POS/DEP annotations (common in minimal installs).
    if root_actor:
        try:
            # Prefer tokenization if doc is a spaCy Doc; otherwise fall back to raw string.
            toks = []
            try:
                toks = [str(getattr(t, "text", "") or "") for t in doc]  # type: ignore[assignment]
            except Exception:
                toks = []
            text_low = " ".join(toks).lower() if toks else str(getattr(doc, "text", doc) or "").lower()
            # Only absorb nominative first-person pronouns as subjects.
            if any(p in text_low.split() for p in ("i", "we")):
                return [_normalize_subject_label(root_actor)]
        except Exception:
            pass

    lemmas = _action_lemmas(act)
    verbs = []
    for t in doc:
        lemma = str(getattr(t, "lemma_", "") or "").lower()
        pos = str(getattr(t, "pos_", "") or "")
        if pos not in {"VERB", "AUX"}:
            continue
        if lemma in lemmas:
            verbs.append(t)
    if not verbs:
        return []
    verbs = sorted(verbs, key=lambda x: (0 if str(getattr(x, "dep_", "")) == "ROOT" else 1, int(getattr(x, "i", 10_000))))

    out: List[str] = []
    seen = set()
    subj_deps = {"nsubj", "nsubjpass", "csubj"}
    for v in verbs[:2]:
        subj_tokens = []
        for c in v.children:
            if str(getattr(c, "dep_", "")) in subj_deps:
                subj_tokens.append(c)
                subj_tokens.extend(list(getattr(c, "conjuncts", [])))
        for st in subj_tokens:
            surf = _subject_surface_for_token(doc, st)
            resolved = _resolve_subject_surface(surf, actors, root_actor, root_surname)
            key = resolved.lower()
            if resolved and key not in seen:
                seen.add(key)
                out.append(resolved)
    if out:
        return out

    # Modal-container and complement verbs often inherit subject from governing verb:
    # "Fr Pickin had a tendency to abuse ..." -> subject belongs to "had", not "abuse".
    for v in verbs[:2]:
        cur = v
        for _ in range(2):
            h = getattr(cur, "head", None)
            if h is None or h == cur:
                break
            subj_tokens = []
            for c in h.children:
                if str(getattr(c, "dep_", "")) in subj_deps:
                    subj_tokens.append(c)
                    subj_tokens.extend(list(getattr(c, "conjuncts", [])))
            for st in subj_tokens:
                surf = _subject_surface_for_token(doc, st)
                resolved = _resolve_subject_surface(surf, actors, root_actor, root_surname)
                key = resolved.lower()
                if resolved and key not in seen:
                    seen.add(key)
                    out.append(resolved)
            if out:
                break
            cur = h
    return out


def _subjects_for_verb_token(
    doc,
    verb_token,
    actors: List[dict],
    root_actor: str,
    root_surname: str,
    allow_inherit: bool = True,
) -> List[str]:
    out: List[str] = []
    seen = set()
    subj_deps = {"nsubj", "nsubjpass", "csubj"}

    def collect_from_head(head_token) -> bool:
        subj_tokens = []
        for c in head_token.children:
            if str(getattr(c, "dep_", "") or "") in subj_deps:
                subj_tokens.append(c)
                subj_tokens.extend(list(getattr(c, "conjuncts", [])))
        for st in subj_tokens:
            surf = _subject_surface_for_token(doc, st)
            resolved = _resolve_subject_surface(surf, actors, root_actor, root_surname)
            key = str(resolved).lower()
            if resolved and key not in seen:
                seen.add(key)
                out.append(resolved)
        return bool(out)

    if collect_from_head(verb_token):
        return out
    if not allow_inherit:
        return out
    cur = verb_token
    for _ in range(2):
        h = getattr(cur, "head", None)
        if h is None or h == cur:
            break
        if collect_from_head(h):
            return out
        cur = h
    return out


def _objects_for_verb_token(doc, verb_token) -> List[str]:
    out: List[str] = []
    seen = set()
    allowed_preps = {"for", "to", "into", "with", "of"}

    def add(v: str) -> None:
        k = _clean_entity_surface(str(v or ""))
        if not k:
            return
        if CITATION_TOKEN_RE.search(k):
            return
        lk = k.lower()
        if lk in seen:
            return
        seen.add(lk)
        out.append(k)

    def add_from_chunk(tok) -> None:
        txt = ""
        try:
            for ch in getattr(doc, "noun_chunks", []):
                root = getattr(ch, "root", None)
                if root is not None and int(getattr(root, "i", -1)) == int(getattr(tok, "i", -2)):
                    txt = _clean_entity_surface(str(getattr(ch, "text", "") or ""))
                    break
        except Exception:
            txt = ""
        if not txt:
            idxs = [x.i for x in getattr(tok, "subtree", [])] or [int(getattr(tok, "i", 0))]
            span = doc[min(idxs) : max(idxs) + 1]
            txt = _clean_entity_surface(str(getattr(span, "text", "") or ""))
        if txt:
            add(txt)

    for c in verb_token.children:
        dep = str(getattr(c, "dep_", "") or "")
        if dep in {"dobj", "obj", "attr", "oprd", "dative"}:
            add_from_chunk(c)
        if dep == "prep":
            ptxt = str(getattr(c, "text", "") or "").strip().lower()
            if ptxt not in allowed_preps:
                continue
            for g in c.children:
                if str(getattr(g, "dep_", "") or "") == "pobj":
                    add_from_chunk(g)
                    for gg in g.children:
                        if str(getattr(gg, "dep_", "") or "") == "prep":
                            for p2 in gg.children:
                                if str(getattr(p2, "dep_", "") or "") == "pobj":
                                    add_from_chunk(p2)
    return out


def _extract_communication_chain_steps(
    doc,
    actors: List[dict],
    root_actor: str,
    root_surname: str,
    comm_cfg: Dict[str, object],
) -> List[dict]:
    if doc is None:
        return []
    verbs_allow = {str(x or "").strip().lower() for x in (comm_cfg.get("communication_verbs") or []) if str(x or "").strip()}
    if not verbs_allow:
        return []
    emit_attr = bool(comm_cfg.get("emit_attribution_step", True))
    emit_embedded = bool(comm_cfg.get("emit_embedded_steps", True))
    emb_limit = max(1, int(comm_cfg.get("embedded_step_limit") or 2))
    emb_heads = {str(x or "").strip() for x in (comm_cfg.get("embedded_step_heads") or []) if str(x or "").strip()}
    subj_policy = str(comm_cfg.get("embedded_subject_policy") or "prefer_local_subject").strip().lower()
    attr_key = str(comm_cfg.get("attribution_modifier_key") or "according_to").strip() or "according_to"

    comm_heads = []
    for t in doc:
        if str(getattr(t, "pos_", "") or "") not in {"VERB", "AUX"}:
            continue
        lem = str(getattr(t, "lemma_", "") or "").strip().lower()
        if lem in verbs_allow:
            comm_heads.append(t)
    if not comm_heads:
        return []

    steps: List[dict] = []
    for head in comm_heads[:3]:
        head_lemma = str(getattr(head, "lemma_", "") or getattr(head, "text", "") or "").strip().lower()
        if not head_lemma:
            continue
        attr_subjects = _subjects_for_verb_token(
            doc,
            head,
            actors,
            root_actor=root_actor,
            root_surname=root_surname,
            allow_inherit=True,
        )
        if emit_attr:
            attr_objs = _objects_for_verb_token(doc, head)
            steps.append(
                {
                    "action": head_lemma,
                    "subjects": list(attr_subjects),
                    "objects": attr_objs,
                    "purpose": None,
                    "modifiers": [{"kind": "communication_attribution", "source": "dep_communication"}],
                }
            )
        if not emit_embedded:
            continue

        embedded = []
        for c in head.children:
            dep = str(getattr(c, "dep_", "") or "")
            if dep not in {"ccomp", "xcomp"}:
                continue
            if str(getattr(c, "pos_", "") or "") != "VERB":
                continue
            embedded.append(c)
            if "conj" in emb_heads:
                embedded.extend(list(getattr(c, "conjuncts", [])))
        if not embedded:
            continue
        dedup_emb = []
        seen_i = set()
        for e in embedded:
            i = int(getattr(e, "i", -1))
            if i in seen_i:
                continue
            seen_i.add(i)
            dedup_emb.append(e)
        dedup_emb = sorted(dedup_emb, key=lambda t: int(getattr(t, "i", 0)))[:emb_limit]

        for e in dedup_emb:
            e_lemma = str(getattr(e, "lemma_", "") or getattr(e, "text", "") or "").strip().lower()
            if not e_lemma:
                continue
            subjects = _subjects_for_verb_token(
                doc,
                e,
                actors,
                root_actor=root_actor,
                root_surname=root_surname,
                allow_inherit=False,
            )
            if not subjects and subj_policy.endswith("else_inherit"):
                subjects = list(attr_subjects)
            e_objs = _objects_for_verb_token(doc, e)
            mods = []
            if attr_subjects:
                mods.append(
                    {
                        "kind": "attribution",
                        "source": "dep_ccomp",
                        "key": attr_key,
                        "value": list(attr_subjects),
                    }
                )
            steps.append(
                {
                    "action": e_lemma,
                    "subjects": subjects,
                    "objects": e_objs,
                    "purpose": None,
                    "modifiers": mods,
                }
            )
    return steps


def _purpose_to_step(purpose: Optional[str], fallback_subjects: List[str], nlp: Optional[object] = None) -> Optional[dict]:
    p = re.sub(r"\s+", " ", str(purpose or "").strip())
    if not p:
        return None
    if nlp is not None:
        try:
            doc = nlp(p)
            vt = None
            for t in doc:
                if str(getattr(t, "pos_", "") or "") == "VERB" and str(getattr(t, "dep_", "") or "") == "ROOT":
                    vt = t
                    break
            if vt is None:
                for t in doc:
                    if str(getattr(t, "pos_", "") or "") == "VERB":
                        vt = t
                        break
            if vt is None:
                return None
            verb = str(getattr(vt, "lemma_", "") or getattr(vt, "text", "") or "").strip().lower()
            if not verb or verb in _NON_VERB_HEAD_WORDS:
                return None
            obj = re.sub(r"\s+", " ", str(doc[int(getattr(vt, "i", 0)) + 1 :].text or "")).strip()
            if not obj:
                for c in vt.children:
                    if str(getattr(c, "dep_", "") or "") in {"dobj", "obj", "attr", "oprd", "dative", "pobj"}:
                        idxs = [x.i for x in getattr(c, "subtree", [])] or [int(getattr(c, "i", 0))]
                        obj = re.sub(r"\s+", " ", str(doc[min(idxs) : max(idxs) + 1].text or "")).strip()
                        if obj:
                            break
            if not obj:
                return None
            return {
                "action": verb,
                "subjects": list(fallback_subjects or []),
                "objects": [obj],
                "purpose": None,
            }
        except Exception:
            pass
    m = re.match(r"^([a-z]+)\s+(.+)$", p, flags=re.IGNORECASE)
    if not m:
        return None
    verb = m.group(1).strip().lower()
    obj = m.group(2).strip()
    if not verb or not obj or len(verb) < 2 or verb in _NON_VERB_HEAD_WORDS:
        return None
    return {
        "action": verb,
        "subjects": list(fallback_subjects or []),
        "objects": [obj],
        "purpose": None,
    }


def _infer_requester_from_steps(steps: List[dict], requester_title_label: str) -> Optional[str]:
    title_norm = str(requester_title_label or "").strip().lower()
    for s in steps or []:
        if _base_action_label(str(s.get("action") or "")) != "request":
            continue
        subs = [str(x).strip() for x in (s.get("subjects") or []) if str(x).strip()]
        for sub in subs:
            low = sub.lower()
            if low in {"president", "prime minister", "pm"}:
                continue
            if title_norm and low == title_norm:
                continue
            return sub
        if subs:
            return subs[0]
    return None


def _surname_is_part_of_name(text: str, surname: str, blocked_first_tokens: Optional[set] = None) -> bool:
    # Heuristic: if sentence contains "<Capitalized> <Surname>", treat surname as part of a name
    # and avoid mapping it to the root actor by default.
    if not surname:
        return False
    blocked = blocked_first_tokens or set()
    pat = re.compile(rf"\b([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?\s+{re.escape(surname)}\b")
    for m in pat.finditer(text):
        first = (m.group(1) or "").strip()
        if first.lower() in {"president", "governor", "senator", "rep", "representative", "mr", "mrs", "ms", "dr", "chief"}:
            continue
        if first.lower() in blocked:
            continue
        return True
    return False


def _extract_capitalized_surname_names(
    text: str,
    surname: str,
    blocked_first_tokens: Optional[set] = None,
    root_actor: str = "",
) -> List[str]:
    """Extract 2-token names like 'Laura Bush' when surname appears in-sentence.

    Wikipedia prose sometimes leaves spouse/child names unlinked; this keeps the AAO substrate
    reviewable without asserting identity beyond the surface form.
    """
    if not surname:
        return []
    out: List[str] = []
    blocked = blocked_first_tokens or set()
    title_like = {"president", "governor", "senator", "rep", "representative", "mr", "mrs", "ms", "dr", "chief"}
    for m in re.finditer(rf"\b((?:[A-Z][a-z]+\s+)?[A-Z][a-z]+)\s+{re.escape(surname)}\b", text):
        prefix = [p for p in str(m.group(1) or "").split() if p]
        if not prefix:
            continue
        while prefix and prefix[0].lower() in title_like:
            prefix = prefix[1:]
        if not prefix:
            continue
        if len(prefix) == 1 and prefix[0].lower() in blocked:
            continue
        if len(prefix) >= 2 and prefix[0].lower() in blocked:
            prefix = prefix[1:]
        if not prefix:
            continue
        full = " ".join([*prefix, surname])
        full = _canonicalize_root_actor_surface(full, root_actor, surname)
        if full not in out:
            out.append(full)
    return out


def _build_aoo_payload_from_namespace(args: argparse.Namespace) -> dict:
    profile_payload: dict = {}
    profile_loaded = False
    profile_sha256: Optional[str] = None
    profile_error: Optional[str] = None
    if args.profile.exists():
        try:
            profile_raw = args.profile.read_text(encoding="utf-8")
            profile_sha256 = _sha256_text(profile_raw)
            parsed = json.loads(profile_raw)
            if isinstance(parsed, dict):
                profile_payload = parsed
                profile_loaded = True
            else:
                profile_error = "profile_json_not_object"
        except Exception as e:
            profile_error = f"{type(e).__name__}: {e}"

    requester_title_labels = _profile_requester_title_labels(profile_payload)
    modal_container_grammar = _profile_modal_container_grammar(profile_payload)
    communication_chain_config = _profile_communication_chain_config(profile_payload)
    epistemic_verbs = _profile_epistemic_verbs(profile_payload, communication_chain_config)
    semantic_backbone, semantic_warnings, semantic_error = _profile_semantic_backbone_config(profile_payload)
    if semantic_error:
        raise SystemExit(f"invalid extraction profile semantic_backbone: {semantic_error}")
    action_pattern_specs = _profile_action_pattern_specs(profile_payload)
    action_patterns = _compile_action_patterns(action_pattern_specs)
    if not action_patterns:
        action_patterns = list(ACTION_PATTERNS)

    profile_info = {
        "path": str(args.profile),
        "loaded_from_file": bool(profile_loaded),
        "profile_id": str(profile_payload.get("profile_id") or "builtin-default"),
        "profile_version": str(profile_payload.get("profile_version") or "1.0.0"),
        "sha256": profile_sha256,
        "action_pattern_count": int(len(action_patterns)),
        "requester_title_labels": requester_title_labels,
        "modal_container_grammar": modal_container_grammar,
        "communication_chain": communication_chain_config,
        "semantic_backbone": semantic_backbone,
        "semantic_version_pins": _profile_semantic_version_pins(profile_payload),
        "synset_action_map_count": int(len(_profile_synset_action_map(profile_payload))),
        "synset_action_map_sha256": _sha256_json(_profile_synset_action_map(profile_payload)),
        "babelnet_table_sha256": _sha256_json(_profile_babelnet_lemma_synsets(profile_payload)),
        "epistemic_verbs": epistemic_verbs,
        "predicate_classifier": "src.nlp.epistemic_classifier" if _EpistemicClassifier is not None else "builtin_step_signals",
        "action_classifier": "src.nlp.event_classifier" if _EventClassifier is not None else "regex_fallback",
        "warnings": semantic_warnings,
        "error": profile_error,
    }

    tl = getattr(args, "timeline_payload", None)
    if not isinstance(tl, dict):
        tl = _load_json(args.timeline)
    events = tl.get("events") or []
    if not isinstance(events, list):
        raise SystemExit("invalid timeline: events[] missing")
    source_entity = _build_source_entity(tl.get("snapshot") or {})

    alias_map: Dict[str, str] = {}
    candidate_titles: List[str] = []
    candidates_payload: dict = {}
    if args.candidates.exists():
        candidates_payload = _load_json(args.candidates)
        alias_map = _guess_person_titles(candidates_payload)
        candidate_titles = _candidate_titles(candidates_payload)
    root_actor = str(args.root_actor).strip()
    root_surname = str(args.root_surname).strip()
    if root_surname and root_actor:
        alias_map[root_surname] = root_actor
    alias_keys = {k.lower() for k in alias_map.keys()}

    nlp = None
    parser_info = None
    parser_error = None
    if not args.no_spacy:
        nlp, parser_info, parser_error = _try_load_spacy(str(args.spacy_model))
    classifier = _EpistemicClassifier(nlp) if (_EpistemicClassifier is not None and nlp is not None) else None

    synset_mapper = None
    if (
        nlp is not None
        and _SynsetActionMapper is not None
        and str((semantic_backbone or {}).get("resource") or "none").lower() != "none"
    ):
        pins = _profile_semantic_version_pins(profile_payload)
        synset_action_map = _profile_synset_action_map(profile_payload)
        babelnet_lemma_synsets = _profile_babelnet_lemma_synsets(profile_payload)

        # Enforce runtime version pins before enabling semantic mapping.
        req_wn = str(pins.get("wordnet") or "").strip()
        if "wordnet" in str((semantic_backbone or {}).get("resource") or "").lower() and not req_wn:
            raise SystemExit("invalid extraction profile: semantic_version_pins.wordnet required when wordnet enabled")

        req_syn_map = str(pins.get("synset_action_map_sha256") or "").strip()
        if not req_syn_map:
            raise SystemExit("invalid extraction profile: semantic_version_pins.synset_action_map_sha256 required when semantic mapping enabled")
        if _sha256_json(synset_action_map) != req_syn_map:
            raise SystemExit("synset_action_map sha256 pin mismatch")

        if "babelnet" in str((semantic_backbone or {}).get("resource") or "").lower():
            req_babel = str(pins.get("babelnet_table_sha256") or "").strip()
            if not req_babel:
                raise SystemExit("invalid extraction profile: semantic_version_pins.babelnet_table_sha256 required when babelnet enabled")
            if _sha256_json(babelnet_lemma_synsets) != req_babel:
                raise SystemExit("babelnet table sha256 pin mismatch")

        synset_mapper = _SynsetActionMapper(
            resource=str((semantic_backbone or {}).get("resource") or "none"),
            wsd_policy=str((semantic_backbone or {}).get("wsd_policy") or "none"),
            version_pins=pins,
            synset_action_map=synset_action_map,
            babelnet_lemma_synsets=babelnet_lemma_synsets,
        )

        wn_ver = str(getattr(synset_mapper, "metadata", lambda: {})().get("wordnet_version") or "").strip()
        if req_wn and wn_ver and wn_ver != req_wn:
            raise SystemExit(f"wordnet version pin mismatch: required={req_wn} actual={wn_ver}")

    event_classifier = (
        _EventClassifier(ACTION_LEMMAS, synset_mapper=synset_mapper)
        if (_EventClassifier is not None and nlp is not None)
        else None
    )

    out_events: List[dict] = []
    generated_at = _utc_now_iso()
    # Track recurrence of span candidates across events (truth capture; view promotion uses thresholds).
    span_seen: Dict[Tuple[str, str], set] = {}
    for ev in events[: int(args.max_events)]:
        if not isinstance(ev, dict):
            continue
        text = str(ev.get("text") or "").strip()
        if not text:
            continue
        root_actor_ev = str(ev.get("root_actor") or "").strip() or root_actor
        root_surname_ev = str(ev.get("root_surname") or "").strip() or root_surname
        parse_text = _strip_parenthetical_citation_noise(text)
        if not parse_text:
            parse_text = text

        warnings: List[str] = []
        doc = None
        if nlp is not None:
            try:
                doc = nlp(parse_text)
            except Exception:
                doc = None

        action, w_action = _extract_action(parse_text, action_patterns, doc=doc, event_classifier=event_classifier)
        warnings.extend(w_action)
        purpose = _extract_purpose_from_doc(doc) if doc is not None else None
        if not action and doc is not None:
            # Deterministic fallback: choose a verb root when pattern matching misses.
            try:
                cand = None
                for t in doc:
                    if getattr(t, "dep_", "") == "ROOT" and getattr(t, "pos_", "") in {"VERB", "AUX"}:
                        cand = t
                        break
                if cand is None:
                    for t in doc:
                        if getattr(t, "pos_", "") not in {"VERB", "AUX"}:
                            continue
                        morph = getattr(t, "morph", None)
                        verb_form = ""
                        if morph is not None:
                            try:
                                vals = morph.get("VerbForm")
                                verb_form = vals[0] if vals else ""
                            except Exception:
                                verb_form = ""
                        if str(verb_form).lower() == "fin":
                            cand = t
                            break
                if cand is None:
                    for t in doc:
                        if getattr(t, "pos_", "") != "VERB":
                            continue
                        if getattr(t, "dep_", "") in {"ccomp", "xcomp", "acl", "conj", "relcl"}:
                            cand = t
                            break
                if cand is None:
                    for t in doc:
                        if getattr(t, "pos_", "") in {"VERB", "AUX"}:
                            cand = t
                            break
                if cand is not None:
                    cand_lemma = (getattr(cand, "lemma_", "") or "").strip().lower()
                    if cand_lemma in {"be", "have"}:
                        preferred = None
                        for dep in ("xcomp", "ccomp", "acl", "conj", "relcl"):
                            for t in doc:
                                if getattr(t, "pos_", "") != "VERB":
                                    continue
                                if (getattr(t, "lemma_", "") or "").strip().lower() in {"be", "have"}:
                                    continue
                                if getattr(t, "dep_", "") == dep:
                                    preferred = t
                                    break
                            if preferred is not None:
                                break
                        if preferred is not None:
                            cand = preferred
                if cand is not None:
                    lab = (getattr(cand, "lemma_", "") or getattr(cand, "text", "") or "").strip().lower()
                    if lab:
                        action = lab
                        warnings.append("fallback_action_spacy")
            except Exception:
                pass

        modal_container_modifier = None
        modal_promoted_action = ""
        if doc is not None and action:
            promoted_action, modal_container_modifier = _promote_modal_container_action(doc, action, modal_container_grammar)
            if promoted_action and promoted_action != action:
                action = promoted_action
                warnings.append("modal_container_promoted")
            if modal_container_modifier:
                modal_promoted_action = str(action or "")

        event_action_surface = str(action or "")
        event_action_meta: Optional[dict] = None
        if action:
            if _should_demote_non_eventive_action(doc, action):
                warnings.append("demoted_non_eventive_action")
                action = None
                event_action_surface = ""
            if action:
                canon_action, action_meta = _canonical_action_from_doc(doc, action)
                if canon_action:
                    action = canon_action
                if action_meta:
                    event_action_meta = action_meta

        requester: Optional[str] = None
        requester_resolved: Optional[str] = None
        requester_has_title = False
        requester_title_label = requester_title_labels.get("president", DEFAULT_REQUESTER_TITLE_LABELS.get("president", "U.S. President"))

        # Dependency-first requester extraction; regex fallback remains safety rail.
        requester, requester_resolved, requester_has_title = _extract_requester_from_doc(doc, alias_map)
        requester_source = "dep:request"
        if not requester:
            req2, req2_res, req2_src = _extract_requester_from_request_verbs(doc, alias_map)
            if req2:
                requester = req2
                requester_resolved = req2_res
                requester_has_title = False
                requester_source = req2_src
        if not requester:
            allow_regex = os.getenv("ITIR_ALLOW_REQUEST_REGEX", "").lower() in {"1", "true", "yes", "on"}
            if allow_regex:
                rm = REQUEST_RE.search(parse_text)
                if rm:
                    requester = _normalize_requester_surface(rm.group(1))
                    requester_resolved = _resolve_requester_label(requester, alias_map)
                    requester_has_title = bool(re.search(r"\bPresident\b", str(rm.group(0) or ""), flags=re.IGNORECASE))
                    requester_source = "fallback_regex:request"
                    warnings.append("fallback_requester_regex_disabled_default")

        tokens = _extract_actor_tokens(parse_text)
        actors: List[dict] = []

        # Requester (alias-resolved if possible).
        if requester:
            resolved = _normalize_subject_label(requester_resolved or alias_map.get(requester) or requester)
            requester = _normalize_subject_label(requester)
            requester_resolved = resolved
            actors.append(
                {"label": requester, "resolved": resolved, "role": "requester", "source": requester_source}
            )
            if requester_has_title:
                actors.append(
                    {
                        "label": "President",
                        "resolved": requester_title_label,
                        "role": "requester_meta",
                        "source": f"{requester_source}:title",
                    }
                )

        # Root actor from standalone surname mention (avoid mapping "Laura Bush"/"Barbara Bush" etc).
        if (
            root_surname_ev
            and re.search(rf"\b{re.escape(root_surname_ev)}\b", parse_text)
            and not _surname_is_part_of_name(parse_text, root_surname_ev, blocked_first_tokens=alias_keys)
        ):
            actors.append(
                {"label": root_surname_ev, "resolved": root_actor_ev, "role": "subject", "source": "root_surname"}
            )

        # If surname appears as part of a name, include the surface full-name as an actor.
        if root_surname_ev and _surname_is_part_of_name(parse_text, root_surname_ev, blocked_first_tokens=alias_keys):
            for full in _extract_capitalized_surname_names(
                parse_text,
                root_surname_ev,
                blocked_first_tokens=alias_keys,
                root_actor=root_actor_ev,
            ):
                actors.append({"label": full, "resolved": full, "role": "subject", "source": "surface_name"})

        # Other alias-resolved person tokens in the sentence.
        for tok in tokens:
            if requester and tok.lower() == requester.lower():
                continue
            if root_surname_ev and tok.lower() == root_surname_ev.lower():
                continue
            if tok in alias_map:
                actors.append({"label": tok, "resolved": alias_map[tok], "role": "subject", "source": "alias_map"})

        # Promote person-looking wikilinks as actors too (sentence-local identity glue).
        links = ev.get("links") or []
        if isinstance(links, list):
            for t in links:
                if not isinstance(t, str):
                    continue
                title = t.strip()
                if not title:
                    continue
                if _looks_like_person_title(title):
                    actors.append({"label": title, "resolved": title, "role": "subject", "source": "wikilink_person"})

        # Passive agent extraction: dependency-first; regex fallback is safety rail.
        dep_agents = _extract_passive_agents_from_doc(doc)
        if dep_agents:
            for agent in dep_agents:
                n_agent = _normalize_subject_label(agent)
                actors.append({"label": n_agent, "resolved": n_agent, "role": "subject", "source": "dep:by_agent"})
        else:
            am = BY_AGENT_RE.search(parse_text)
            if am:
                agent_raw = (am.group(1) or "").strip()
                if agent_raw:
                    agent = _normalize_agent_label(agent_raw)
                    actors.append(
                        {
                            "label": _normalize_subject_label(agent_raw),
                            "resolved": _normalize_subject_label(agent),
                            "role": "subject",
                            "source": "fallback_regex:by_agent",
                        }
                    )
                    warnings.append("fallback_by_agent_regex")

        actors = _normalize_actor_rows(actors)

        # De-dupe by resolved label.
        seen = set()
        deduped: List[dict] = []
        for a in actors:
            key = _normalize_subject_label(str(a.get("resolved") or a.get("label") or ""))
            if not key or key in seen:
                continue
            seen.add(key)
            a["resolved"] = key
            a["label"] = _normalize_subject_label(str(a.get("label") or key))
            deduped.append(a)
        actors = deduped

        # Dependency subject pass for the primary action; fills obvious gaps like
        # "the Pentagon reported ..." or "U.S. and British forces initiated ...".
        dep_subjects = _subjects_for_action(doc, action or "", actors, root_actor_ev, root_surname_ev) if doc is not None else []
        if dep_subjects:
            existing = {str(a.get("resolved") or "").strip().lower() for a in actors}
            for ds in dep_subjects:
                ds_norm = _normalize_subject_label(ds)
                k = str(ds_norm or "").strip().lower()
                if not k or k in existing:
                    continue
                actors.append(
                    {
                        "label": ds_norm,
                        "resolved": ds_norm,
                        "role": "subject",
                        "source": "dep_subject",
                        "provenance": {"actor_fallback": "dep_subject"},
                    }
                )
                existing.add(k)
        elif root_actor_ev:
            # When spaCy isn't available (doc=None), we still want basic narrator linkage
            # for first-person corpus artifacts (memoirs/transcripts).
            low = str(parse_text or "").lower()
            toks = low.split()
            if "i" in toks or "we" in toks:
                existing = {str(a.get("resolved") or "").strip().lower() for a in actors}
                ra = _normalize_subject_label(root_actor_ev)
                if ra and ra.lower() not in existing:
                    actors.append({"label": ra, "resolved": ra, "role": "subject", "source": "surface_pronoun"})
                    warnings.append("fallback_subject_pronoun")
        if not actors and action:
            fallback_actor = None
            fallback_source = None
            if doc is not None:
                fallback_actor, fallback_source = _fallback_actor_from_doc(doc)
            if not fallback_actor:
                fallback_actor = _fallback_actor_from_text(parse_text)
                fallback_source = fallback_source or "surface_cap"
            if fallback_actor:
                fa_norm = _normalize_subject_label(fallback_actor)
                if fa_norm:
                    actors.append(
                        {
                            "label": fa_norm,
                            "resolved": fa_norm,
                            "role": "subject",
                            "source": "actor_fallback",
                            "provenance": {"actor_fallback": str(fallback_source or "fallback")},
                        }
                    )

        # Objects: prefer sentence-local wikilinks from the timeline artifact.
        objects: List[dict] = []
        para_links = ev.get("links_para") or []
        if isinstance(links, list):
            for t in links:
                if not isinstance(t, str):
                    continue
                title = t.strip()
                if not title:
                    continue
                objects.append({"title": title, "source": "wikilink"})

        # Dependency object fallback lane for unlinked noun-phrase objects.
        if doc is not None:
            for t in _collect_dep_objects(doc):
                objects.append({"title": t, "source": "dep_object"})

        # Add a few sentence-local surface objects when they are load-bearing but not linked.
        # This is still deterministic and sentence-local; no causal inference.
        if re.search(r"\bthe war\b", parse_text, flags=re.IGNORECASE):
            objects.append({"title": "the war", "source": "surface_phrase"})
        wm = re.search(r"\b(?:to\s+)?continue\s+weakening\s+(.+?)(?:[.;]|$)", parse_text, flags=re.IGNORECASE)
        if wm:
            tail = re.sub(r"\s+", " ", str(wm.group(1) or "")).strip()
            if tail:
                objects.append({"title": tail, "source": "surface_phrase"})

        # De-dupe object titles.
        wikilink_token_sets = []
        for o in objects:
            if str(o.get("source") or "") == "wikilink":
                wikilink_token_sets.append(_token_set(str(o.get("title") or "")))
        obj_pos_by_key: Dict[str, int] = {}
        obj_score_by_pos: Dict[int, float] = {}
        dedup_obj: List[dict] = []
        for o in objects:
            k = _clean_entity_surface(str(o.get("title") or ""))
            if not k:
                continue
            src = str(o.get("source") or "")
            if src == "dep_object":
                kn = _norm_phrase(k)
                if kn in {"a number", "number"}:
                    continue
                kt = _token_set(k)
                if kt and any(kt <= wts and len(kt) <= 2 for wts in wikilink_token_sets if wts):
                    continue
            row = {"title": k, "source": src}
            if src == "wikilink":
                row["resolver_hints"] = [{"lane": "sentence_link", "kind": "exact", "title": k, "score": 1.0}]
            else:
                hints = _resolver_hints_for_object(k, links if isinstance(links, list) else [], para_links if isinstance(para_links, list) else [], candidate_titles)
                if hints:
                    row["resolver_hints"] = hints
            keys = _row_identity_keys(row) or [_norm_phrase(x) for x in _object_keys(k) if _norm_phrase(x)]
            existing_pos = None
            for key in keys:
                if key in obj_pos_by_key:
                    existing_pos = obj_pos_by_key[key]
                    break
            if existing_pos is None:
                pos = len(dedup_obj)
                dedup_obj.append(row)
                score = _object_row_score(row)
                obj_score_by_pos[pos] = score
                for key in (_row_identity_keys(row) or keys):
                    obj_pos_by_key[key] = pos
                continue
            prev = dedup_obj[existing_pos]
            prev_hints = prev.get("resolver_hints") if isinstance(prev, dict) else None
            new_hints = row.get("resolver_hints")
            merged_hints: List[dict] = []
            seen_hint = set()
            for h in (prev_hints or []) + (new_hints or []):
                if not isinstance(h, dict):
                    continue
                hk = (str(h.get("lane") or ""), str(h.get("kind") or ""), str(h.get("title") or ""))
                if hk in seen_hint:
                    continue
                seen_hint.add(hk)
                merged_hints.append(h)
            if merged_hints:
                prev["resolver_hints"] = merged_hints
            prev_score = float(obj_score_by_pos.get(existing_pos, 0.0))
            new_score = _object_row_score(row)
            if new_score > prev_score:
                row["resolver_hints"] = merged_hints
                dedup_obj[existing_pos] = row
                obj_score_by_pos[existing_pos] = new_score
                for key in (_row_identity_keys(row) or keys):
                    obj_pos_by_key[key] = existing_pos
        objects = dedup_obj

        if not actors:
            warnings.append("no_actors_extracted")
        if not objects:
            warnings.append("no_objects_extracted")

        # Step structure: allow multiple actions per sentence (still sentence-local, non-causal).
        # This is a UI/curation aid so we can represent "joined ... and was commissioned ..." etc.
        # For step subjects, treat passive agents as step-local (avoid polluting all steps).
        subj_all = [
            a.get("resolved")
            for a in actors
            if a.get("role") not in {"requester", "requester_meta"}
            and a.get("resolved")
            and a.get("source") != "pattern:by_agent"
        ]
        steps: List[dict] = []
        anchor_year = int((ev.get("anchor") or {}).get("year") or 0) or None

        # Joined + commissioned split (override any single-action default).
        if re.search(r"\bjoined\b", parse_text, flags=re.IGNORECASE) and re.search(r"\bcommissioned\b.*\binto\b", parse_text, flags=re.IGNORECASE):
            joined_objs = [o.get("title") for o in objects if "Air Force" in str(o.get("title") or "")] or [o.get("title") for o in objects]
            guard_objs = [o.get("title") for o in objects if "Guard" in str(o.get("title") or "")] or [o.get("title") for o in objects]
            steps = [
                {"action": "joined", "subjects": subj_all, "objects": joined_objs, "purpose": None},
                {"action": "commissioned_into", "subjects": subj_all, "objects": guard_objs, "purpose": None},
            ]

        # Speech + threw split (very common structure).
        if re.search(r"\bthrew\b", parse_text, flags=re.IGNORECASE):
            steps = []
            thrower = None
            for a in actors:
                if a.get("role") == "requester":
                    continue
                r = str(a.get("resolved") or "")
                if r and r != root_actor_ev and _looks_like_person_title(r):
                    thrower = r
                    break

            if re.search(r"\b(?:was\s+)?giving\s+a\s+speech\b|\bgave\s+a\s+speech\b", parse_text, flags=re.IGNORECASE):
                loc_objs = [o.get("title") for o in objects if any(k in str(o.get("title") or "") for k in ("Square", "Tbilisi"))] or [o.get("title") for o in objects]
                steps.append(
                    {
                        "action": "gave_speech",
                        "subjects": [root_actor_ev] if root_actor_ev in subj_all else subj_all,
                        "objects": loc_objs,
                        "purpose": None,
                    }
                )

            grenade_obj = ["hand grenade"] if re.search(r"\bgrenade\b", parse_text, flags=re.IGNORECASE) else []
            steps.append(
                {
                    "action": "threw",
                    "subjects": [thrower] if thrower else subj_all,
                    "objects": grenade_obj or [o.get("title") for o in objects],
                    "purpose": None,
                }
            )

        # General multi-verb step extraction (bounded): if we didn't already split, emit up to 3 steps
        # by scanning for the earliest occurrences of known actions.
        if not steps:
            hits: List[Tuple[int, str]] = []
            if doc is not None and event_classifier is not None:
                try:
                    for m in event_classifier.collect_candidates(doc):
                        label = str(getattr(m, "action_label", "") or "").strip()
                        start_char = int(getattr(m, "start_char", -1))
                        if not label:
                            continue
                        if start_char < 0:
                            start_char = int(getattr(m, "token_index", 0))
                        hits.append((start_char, label))
                except Exception:
                    pass

            if not hits:
                for label, pat in action_patterns:
                    best_start: Optional[int] = None
                    for m in pat.finditer(parse_text):
                        st = int(m.start())
                        en = int(m.end())
                        if not _match_span_overlaps_verb(doc, st, en):
                            continue
                        if best_start is None or st < best_start:
                            best_start = st
                    if best_start is None:
                        continue
                    hits.append((best_start, label))
            hits = sorted(set(hits), key=lambda x: x[0])[:4]
            for _, lab in hits:
                if lab == "advised":
                    # Prefer the extracted passive agent as the doer if present.
                    agent = next((a.get("resolved") for a in actors if a.get("source") == "pattern:by_agent"), None)
                    subj = [agent] if agent else subj_all
                    step_objs = _objects_for_action(
                        doc,
                        "advised",
                        [o.get("title") for o in objects],
                        parse_text,
                        alias_map,
                        anchor_year,
                    )
                    steps.append({"action": "advised", "subjects": [x for x in subj if x], "objects": step_objs, "purpose": None})
                else:
                    step_objs = _objects_for_action(
                        doc,
                        lab,
                        [o.get("title") for o in objects],
                        parse_text,
                        alias_map,
                        anchor_year,
                    )
                    steps.append({"action": lab, "subjects": subj_all, "objects": step_objs, "purpose": None})

        # Dependency-based communication/complement chains (profile-driven) replace sentence-family hacks
        # like "reported ... cautioned ...". This captures attribution + embedded payload steps.
        if doc is not None:
            comm_steps = _extract_communication_chain_steps(
                doc,
                actors,
                root_actor=root_actor_ev,
                root_surname=root_surname_ev,
                comm_cfg=communication_chain_config,
            )
            if comm_steps:
                comm_verbs = {
                    str(x or "").strip().lower()
                    for x in (communication_chain_config.get("communication_verbs") or [])
                    if str(x or "").strip()
                }
                existing_lemmas = []
                for s in steps:
                    base = _base_action_label(str(s.get("action") or ""))
                    existing_lemmas.extend([str(l).lower() for l in _action_lemmas(base)])
                existing_has_comm = any(l in comm_verbs for l in existing_lemmas)
                if existing_has_comm or not steps:
                    steps = comm_steps
                else:
                    steps.extend(comm_steps)

        # Default single-step representation if no split was applied.
        if not steps and action:
            step_objs = _objects_for_action(
                doc,
                action,
                [o.get("title") for o in objects],
                parse_text,
                alias_map,
                anchor_year,
            )
            steps.append(
                {
                    "action": action,
                    "subjects": subj_all,
                    "objects": step_objs,
                    "modifiers": [modal_container_modifier] if isinstance(modal_container_modifier, dict) else [],
                    "purpose": purpose,
                }
            )
        elif steps and purpose:
            # If we extracted a purpose clause, attach it to the last step by default.
            # This preserves truth (purpose exists) while keeping the AAO rendering step-local.
            if all((s.get("purpose") is None) for s in steps if isinstance(s, dict)):
                try:
                    steps[-1]["purpose"] = purpose
                except Exception:
                    pass

        # Refine step subjects with dependency extraction to avoid false co-subjects
        # (e.g. "Joe Biden" in an object phrase, or child names in birth events).
        if doc is not None and steps:
            for st in steps:
                act = str(st.get("action") or "")
                if _base_action_label(act) == "request" and requester_resolved:
                    st["subjects"] = [requester_title_label, requester_resolved] if requester_has_title else [requester_resolved]
                    continue
                ss = _subjects_for_action(doc, act, actors, root_actor_ev, root_surname_ev)
                if ss:
                    st["subjects"] = ss
                step_objs = _objects_for_action(
                    doc,
                    act,
                    list(st.get("objects") or [o.get("title") for o in objects]),
                    parse_text,
                    alias_map,
                    anchor_year,
                )
                if step_objs:
                    st["objects"] = step_objs
                negation = _action_negation(doc, act)
                if negation:
                    st["negation"] = negation
                if (
                    isinstance(modal_container_modifier, dict)
                    and modal_promoted_action
                    and _base_action_label(act) == _base_action_label(modal_promoted_action)
                ):
                    mods = st.get("modifiers")
                    if not isinstance(mods, list):
                        mods = []
                        st["modifiers"] = mods
                    if modal_container_modifier not in mods:
                        mods.append(modal_container_modifier)

        # Normalize "at ... request" into a requester-led step and avoid actor leakage.
        if requester_resolved and steps:
            request_idxs = [i for i, s in enumerate(steps) if _base_action_label(str(s.get("action") or "")) in {"requested", "request"}]
            if request_idxs:
                non_request_subjects: List[str] = []
                for s in steps:
                    if _base_action_label(str(s.get("action") or "")) in {"requested", "request"}:
                        continue
                    for sub in (s.get("subjects") or []):
                        if sub and sub not in non_request_subjects:
                            non_request_subjects.append(sub)
                request_objects = non_request_subjects or [x for x in subj_all if x]
                request_subjects = [requester_resolved]
                if requester_has_title:
                    request_subjects = [requester_title_label, requester_resolved]
                request_step = {
                    "action": "request",
                    "subjects": request_subjects,
                    "objects": request_objects,
                    "purpose": None,
                }
                keep = [s for s in steps if _base_action_label(str(s.get("action") or "")) not in {"requested", "request"}]
                steps = [request_step] + keep

        # Fallback: if request action exists but requester role wasn't extracted
        # from dependency/regex, infer it deterministically from request-step subjects.
        if (not requester_resolved) and steps:
            inferred_req = _infer_requester_from_steps(steps, requester_title_label)
            if inferred_req:
                requester = _normalize_subject_label(inferred_req)
                requester_resolved = _normalize_subject_label(_resolve_requester_label(inferred_req, alias_map) or inferred_req)
                already = {
                    (str(a.get("resolved") or a.get("label") or "").strip().lower(), str(a.get("role") or "").strip().lower())
                    for a in actors
                    if isinstance(a, dict)
                }
                key = (requester_resolved.strip().lower(), "requester")
                if key not in already:
                    actors.append(
                        {
                            "label": requester,
                            "resolved": requester_resolved,
                            "role": "requester",
                            "source": "fallback_step:request",
                        }
                    )
                    warnings.append("fallback_requester_from_step")

        # Start a minimal nesting/chain lane: if a purpose clause is present, emit a derived
        # purpose-step (verb + object phrase) when it is not already represented.
        if steps and purpose:
            pstep = _purpose_to_step(purpose, list(steps[-1].get("subjects") or subj_all), nlp=nlp)
            if pstep:
                pverb = str(pstep.get("action") or "").lower()
                represented = {str(s.get("action") or "").lower() for s in steps}
                if pverb == "continue" and "weakening" in represented:
                    pstep = None
                if pstep and pverb not in represented:
                    steps.append(pstep)

        # Span candidates lane (unresolved mentions with provenance; not entities).
        span_candidates: List[dict] = []
        if doc is not None:
            try:
                # Avoid emitting spans that are already hard-resolved as entities in this sentence.
                resolved_texts = set()
                resolved_tokens = set()
                resolved_phrases: List[str] = []
                for a in actors:
                    lbl = str(a.get("label") or "").strip()
                    if lbl:
                        resolved_texts.add(lbl.lower())
                        resolved_phrases.append(lbl)
                    r = str(a.get("resolved") or "").strip()
                    if r:
                        resolved_texts.add(r.lower())
                        resolved_phrases.append(r)
                    for w in re.split(r"\\s+", (r or lbl).strip()):
                        w = w.strip(".,;:()[]{}\"'").lower()
                        if w and w.isalpha():
                            resolved_tokens.add(w)
                for o in objects:
                    t = str(o.get("title") or "").strip()
                    if t:
                        resolved_texts.add(t.lower())
                        resolved_phrases.append(t)
                    for w in re.split(r"\\s+", t.strip()):
                        w = w.strip(".,;:()[]{}\"'").lower()
                        if w and w.isalpha():
                            resolved_tokens.add(w)

                # Always treat the declared root actor/surname as resolved for span suppression.
                if root_actor_ev:
                    resolved_phrases.append(root_actor_ev)
                    for w in re.split(r"\\s+", root_actor_ev.strip()):
                        w = w.strip(".,;:()[]{}\"'").lower()
                        if w and w.isalpha():
                            resolved_tokens.add(w)
                if root_surname_ev:
                    resolved_tokens.add(root_surname_ev.strip().lower())

                # Collect approximate resolved text spans by substring search (deterministic, best-effort).
                resolved_spans: List[Tuple[int, int]] = []
                low_text = text.lower()
                for ph in resolved_phrases:
                    s = re.sub(r"\\s+", " ", str(ph or "").strip())
                    if len(s) < 3:
                        continue
                    sl = s.lower()
                    start0 = 0
                    while True:
                        i = low_text.find(sl, start0)
                        if i < 0:
                            break
                        resolved_spans.append((i, i + len(sl)))
                        start0 = i + len(sl)

                for chunk in getattr(doc, "noun_chunks", []):
                    s = str(chunk.text or "").strip()
                    if not s:
                        continue
                    if len(s) > 80:
                        continue
                    sn = re.sub(r"\s+", " ", s).strip()
                    if not any(ch.isalnum() for ch in sn):
                        continue
                    words = [w.strip(".,;:()[]{}\"'") for w in sn.split() if w.strip()]
                    if not words:
                        continue

                    head = getattr(chunk, "root", None)
                    # Suppress pure pronoun/determiner NPs (they're structural glue, not useful unresolved mentions).
                    head_pos = getattr(head, "pos_", "") if head is not None else ""
                    if head_pos in {"PRON", "DET"} and len(words) == 1:
                        continue
                    head_lemma = getattr(head, "lemma_", "") if head is not None else ""
                    has_acronym = any(getattr(t, "is_upper", False) and getattr(t, "is_alpha", False) and len(getattr(t, "text", "")) >= 2 for t in chunk)
                    has_propn = any(getattr(t, "pos_", "") == "PROPN" for t in chunk)
                    span_type = _span_type_for_np(sn, head_lemma, has_acronym=has_acronym, has_propn=has_propn)

                    start = int(getattr(chunk, "start_char", 0))
                    end = int(getattr(chunk, "end_char", start + len(sn)))
                    if start < 0 or end <= start or end > len(text) + 2:
                        continue

                    # Determine overlap with resolved entity text spans (definitional: span lane is unresolved mentions).
                    overlaps_resolved = False
                    for a0, b0 in resolved_spans:
                        if a0 < end and start < b0:
                            overlaps_resolved = True
                            break

                    # Deterministic time-expression suppression (time anchors are modeled separately).
                    low_words = [w.lower() for w in words if w]
                    is_time_expr = False
                    if any(w in MONTH_WORDS for w in low_words):
                        is_time_expr = True
                    if any(_is_year_token(w) for w in low_words):
                        is_time_expr = True

                    # Token overlap suppression: drop if the chunk is largely composed of resolved entity tokens.
                    non_stop = []
                    for t in chunk:
                        if getattr(t, "is_alpha", False) and not getattr(t, "is_stop", False):
                            non_stop.append(re.sub(r"[^a-z]+", "", str(getattr(t, "text", "")).lower()))
                    non_stop = [w for w in non_stop if w]
                    if non_stop and all(w in resolved_tokens for w in non_stop):
                        overlaps_resolved = True
                    chunk_alpha = [re.sub(r"[^a-z]+", "", w.lower()) for w in words]
                    chunk_alpha = [w for w in chunk_alpha if w]
                    if chunk_alpha and all(w in resolved_tokens for w in chunk_alpha):
                        overlaps_resolved = True

                    # Definitional filters for this lane:
                    # - exclude overlaps with resolved entities
                    # - exclude time-only mentions
                    if overlaps_resolved:
                        continue
                    if is_time_expr:
                        continue
                    if sn.lower() in resolved_texts:
                        continue
                    if len(words) == 1 and words[0].lower() in resolved_tokens:
                        continue

                    token_count = len(words)
                    view_score = 0.20
                    if token_count >= 2:
                        view_score += 0.35
                    if has_propn or has_acronym:
                        view_score += 0.20
                    if span_type == "COLLECTIVE_ROLE":
                        view_score += 0.25
                    view_score = max(0.0, min(1.0, view_score))

                    span_id = f"span:{str(ev.get('event_id'))}:{start}:{end}"
                    cand = {
                        "span_id": span_id,
                        "event_id": ev.get("event_id"),
                        "span": {"kind": "event_text", "start": start, "end": end},
                        "text": sn,
                        "span_type": span_type,
                        "sources": [{"source": "dep_parse", "note": "noun_chunk"}],
                        "hygiene": {
                            "token_count": int(token_count),
                            "is_time_expression": bool(is_time_expr),
                            "overlaps_resolved_entity": bool(overlaps_resolved),
                            "view_score": float(view_score),
                        },
                    }
                    span_candidates.append(cand)
                    span_seen.setdefault((sn.lower(), span_type), set()).add(str(ev.get("event_id")))
            except Exception:
                # If parsing fails, keep lane empty; provenance is still preserved in event.text.
                pass

        # De-dupe steps (action + subjects + objects).
        for s in steps:
            subj_vals: List[str] = []
            subj_seen = set()
            for sub in (s.get("subjects") or []):
                ns = _normalize_subject_label(sub)
                k = ns.lower()
                if not ns or k in subj_seen:
                    continue
                subj_seen.add(k)
                subj_vals.append(ns)
            s["subjects"] = subj_vals
            raw_action = str(s.get("action") or "").strip()
            if not raw_action:
                continue
            canon_action, action_meta = _canonical_action_from_doc(doc, raw_action)
            if canon_action:
                s["action"] = canon_action
            if action_meta:
                s["action_meta"] = action_meta
            if canon_action and raw_action != canon_action:
                s["action_surface"] = raw_action

        object_row_by_key: Dict[str, dict] = {}
        for o in objects:
            t = str(o.get("title") or "").strip()
            for key in _row_identity_keys(o):
                object_row_by_key.setdefault(key, o)
            if not _row_identity_keys(o):
                for key in _object_keys(t):
                    nk = _norm_phrase(key)
                    if nk:
                        object_row_by_key.setdefault(nk, o)

        seen_steps = set()
        dedup_steps: List[dict] = []
        for s in steps:
            key = (
                str(s.get("action") or ""),
                _step_subject_key([x for x in (s.get("subjects") or []) if x]),
                _step_object_key([x for x in (s.get("objects") or []) if x], object_row_by_key),
                str((s.get("negation") or {}).get("kind") or ""),
            )
            if key in seen_steps:
                continue
            seen_steps.add(key)
            dedup_steps.append(s)
        steps = dedup_steps

        event_id = str(ev.get("event_id") or "")
        claim_step_indices = _annotate_claim_bearing_steps(
            doc,
            steps,
            event_id,
            epistemic_verbs,
            classifier=classifier,
        )
        allowed_step_numeric_keys: Optional[set] = set()
        for n in _extract_numeric_mentions(text, doc=doc):
            nk = _numeric_key(str(n))
            if nk:
                allowed_step_numeric_keys.add(nk)

        for s in steps:
            st_objs = [x for x in (s.get("objects") or []) if x]
            entity_objects: List[str] = []
            numeric_objects: List[str] = []
            modifier_objects: List[str] = []
            seen_entity = set()
            seen_numeric = set()
            seen_modifier = set()
            for obj in st_objs:
                cleaned_obj = _clean_entity_surface(str(obj))
                if not cleaned_obj:
                    continue
                keys = _object_keys(cleaned_obj)
                row = None
                for key in keys:
                    row = object_row_by_key.get(_norm_phrase(key))
                    if row is not None:
                        break
                if _is_entity_like_object(cleaned_obj, row):
                    label = _preferred_entity_label(cleaned_obj, row)
                    lk = label.lower()
                    if lk not in seen_entity:
                        seen_entity.add(lk)
                        entity_objects.append(label)
                elif _is_numeric_object(cleaned_obj, row):
                    lk = _numeric_key(cleaned_obj)
                    if not lk:
                        continue
                    if allowed_step_numeric_keys is not None and lk not in allowed_step_numeric_keys:
                        continue
                    if lk not in seen_numeric:
                        seen_numeric.add(lk)
                        numeric_objects.append(_normalize_numeric_mention(cleaned_obj))
                else:
                    lk = cleaned_obj.lower()
                    if lk not in seen_modifier:
                        seen_modifier.add(lk)
                        modifier_objects.append(cleaned_obj)
            s["entity_objects"] = entity_objects
            s["numeric_objects"] = numeric_objects
            s["modifier_objects"] = modifier_objects

        # Step-scoped numeric role typing and multi-verb alignment.
        step_numeric_claims = _extract_step_numeric_claims(doc, text, steps, event_anchor=ev.get("anchor"))
        for i, s in enumerate(steps):
            claims = list(step_numeric_claims.get(i) or [])
            if claims and s.get("claim_id"):
                for c in claims:
                    if isinstance(c, dict):
                        c["claim_id"] = str(s.get("claim_id") or "")
            s["numeric_claims"] = claims
            if claims:
                seen_num = {_numeric_key(str(x)) for x in (s.get("numeric_objects") or []) if str(x).strip()}
                for c in claims:
                    nk = str(c.get("key") or "")
                    val = str(c.get("value") or "")
                    if not nk or not val:
                        continue
                    if allowed_step_numeric_keys is not None and nk not in allowed_step_numeric_keys:
                        continue
                    if nk in seen_num:
                        continue
                    seen_num.add(nk)
                    s.setdefault("numeric_objects", []).append(val)

        chains: List[dict] = []
        if len(steps) > 1:
            for i in range(len(steps) - 1):
                chains.append({"from_step": i, "to_step": i + 1, "kind": "sequence"})
        # Deterministic clause-level linkage: ccomp/xcomp maps to content/infinitive relation between steps.
        if doc is not None and len(steps) > 1:
            step_by_action: Dict[str, List[int]] = {}
            for i, s in enumerate(steps):
                base = _base_action_label(str(s.get("action") or ""))
                for lm in _action_lemmas(base):
                    step_by_action.setdefault(str(lm).lower(), []).append(i)
            seen_chain = {(c.get("from_step"), c.get("to_step"), c.get("kind")) for c in chains}
            for tok in doc:
                dep = str(getattr(tok, "dep_", "") or "")
                if dep not in {"ccomp", "xcomp"}:
                    continue
                head = getattr(tok, "head", None)
                if head is None:
                    continue
                child_lemma = str(getattr(tok, "lemma_", "") or "").lower()
                head_lemma = str(getattr(head, "lemma_", "") or "").lower()
                if not child_lemma or not head_lemma:
                    continue
                from_idxs = step_by_action.get(head_lemma, [])
                to_idxs = step_by_action.get(child_lemma, [])
                if not from_idxs or not to_idxs:
                    continue
                key = (from_idxs[0], to_idxs[0], "content_clause" if dep == "ccomp" else "infinitive_clause")
                if key in seen_chain:
                    continue
                chains.append({"from_step": from_idxs[0], "to_step": to_idxs[0], "kind": key[2]})
                seen_chain.add(key)
        for i, s in enumerate(steps):
            if s.get("purpose"):
                chains.append({"from_step": i, "to": "purpose", "kind": "purpose_clause"})

        event_entity_objects = [o.get("title") for o in objects if _is_entity_like_object(str(o.get("title") or ""), o)]
        event_numeric_objects = [o.get("title") for o in objects if _is_numeric_object(str(o.get("title") or ""), o)]
        event_modifier_objects = [
            o.get("title")
            for o in objects
            if (not _is_entity_like_object(str(o.get("title") or ""), o)) and (not _is_numeric_object(str(o.get("title") or ""), o))
        ]
        # Second pass: preserve raw numeric mentions from sentence text in a dedicated lane.
        seen_event_numeric = {_numeric_key(str(x)) for x in event_numeric_objects if str(x).strip()}
        for n in _extract_numeric_mentions(text, doc=doc):
            nk = _numeric_key(n)
            if not nk or nk in seen_event_numeric:
                continue
            seen_event_numeric.add(nk)
            event_numeric_objects.append(_normalize_numeric_mention(n))
        event_numeric_objects = _dedupe_numeric_objects_prefer_currency(event_numeric_objects)

        event_numeric_claims: List[dict] = []
        for idx, s in enumerate(steps):
            for c in (s.get("numeric_claims") or []):
                if not isinstance(c, dict):
                    continue
                cc = dict(c)
                cc["step_index"] = int(idx)
                event_numeric_claims.append(cc)

        event_attributions = _build_event_attributions(
            event_id=event_id,
            steps=steps,
            source_entity_id=str(source_entity.get("id") or ""),
            communication_verbs=[str(x or "") for x in (communication_chain_config.get("communication_verbs") or [])],
        )

        # Source-pack / per-row source hints: preserve URL/path metadata when present on the
        # timeline row (non-authoritative; used for follow-on inspection).
        citations: List[dict] = []
        row_url = str(ev.get("url") or "").strip()
        row_source_id = str(ev.get("source_id") or "").strip()
        row_title = str(ev.get("title") or "").strip() or str(ev.get("text") or "").strip()
        if row_url:
            provider = "source_document"
            mode = "url"
            follow = [{"provider": provider, "mode": mode, "url": row_url}]
            citations.append(
                {
                    "text": row_title or row_url,
                    "kind": "source_row",
                    "follower_order": ["source_document"],
                    "follow": follow,
                    "source_id": row_source_id or None,
                }
            )
        else:
            # Local pack seed paths use the url field to carry a filesystem path.
            row_path = str(ev.get("path") or "").strip()
            if row_path:
                follow = [{"provider": "source_document", "mode": "path", "path": row_path}]
                citations.append(
                    {
                        "text": row_title or row_path,
                        "kind": "source_row",
                        "follower_order": ["source_document"],
                        "follow": follow,
                        "source_id": row_source_id or None,
                    }
                )

        out_events.append(
            {
                "event_id": ev.get("event_id"),
                "anchor": ev.get("anchor"),
                "section": ev.get("section"),
                "text": text,
                "actors": actors,
                "action": action,
                "action_meta": event_action_meta,
                "action_surface": event_action_surface if action and event_action_surface and event_action_surface != action else None,
                "steps": steps,
                "objects": objects,
                "entity_objects": event_entity_objects,
                "numeric_objects": event_numeric_objects,
                "numeric_claims": event_numeric_claims,
                "modifier_objects": event_modifier_objects,
                "purpose": purpose,
                "chains": chains,
                "span_candidates": span_candidates,
                "claim_bearing": bool(claim_step_indices),
                "claim_step_indices": claim_step_indices,
                "attributions": event_attributions,
                "citations": citations,
                "warnings": warnings,
            }
        )

    # Populate recurrence counts for span candidates.
    recur = {(k[0], k[1]): len(v) for k, v in span_seen.items()}
    for ev in out_events:
        sc = ev.get("span_candidates") or []
        if not isinstance(sc, list):
            continue
        for c in sc:
            if not isinstance(c, dict):
                continue
            txt = str(c.get("text") or "").strip().lower()
            st = str(c.get("span_type") or "").strip()
            seen_events = recur.get((txt, st))
            if seen_events is not None:
                c["recurrence"] = {"seen_events": int(seen_events)}

    requester_coverage = _requester_coverage_summary(out_events)
    out = {
        "ok": True,
        "generated_at": generated_at,
        "parser": (
            parser_info
            if parser_info
            else ({"name": "spacy", "model": str(args.spacy_model), "error": parser_error} if parser_error else None)
        ),
        "extraction_profile": profile_info,
        "source_timeline": {
            "path": str(args.timeline),
            "snapshot": tl.get("snapshot"),
        },
        "source_entity": source_entity,
        "extraction_record": _build_extraction_record(str(source_entity.get("id") or ""), parser_info, generated_at),
        "requester_coverage": requester_coverage,
        "root_actor": {"label": root_actor, "surname": root_surname},
        "events": out_events,
        "notes": [
            "Sentence-local AAO extraction. Non-causal. Non-authoritative.",
            "Actors are heuristic: requester/subject roles are dependency-first with regex fallback safety rails and alias maps.",
            "Objects are primarily wikilinks from the timeline event with dependency/surface fallbacks; absence does not imply non-existence.",
            "Non-wikilink objects may include resolver_hints against sentence links, paragraph links, and candidate titles.",
            "Numeric mentions are emitted in dedicated numeric lanes (`numeric_objects` and step-scoped `numeric_claims` with role/alignment metadata).",
            "Claim-bearing steps are tagged via profile-driven epistemic verbs, with event-scoped attribution attachments.",
            "Actions are canonical verb labels; negation is stored separately under step.negation (no not_* action proliferation).",
            "Span candidates are unresolved mentions (TextSpan-like) for view-layer surfacing/promotion; they are not entities.",
        ],
    }

    # Canonical persistence: DB-first, idempotent per (run_id,event_id). JSON is an export artifact.
    if not args.no_db:
        persist_fn = None
        try:
            from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run as persist_fn
        except Exception:  # pragma: no cover - script execution outside package layout
            try:
                from SensibLaw.src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run as persist_fn
            except Exception:
                persist_fn = None

        if persist_fn is None:
            raise SystemExit("SQLite persistence requested but src.wiki_timeline.sqlite_store is unavailable")

        res = persist_fn(
            db_path=Path(args.db_path),
            out_payload=out,
            timeline_path=Path(args.timeline),
            candidates_path=Path(args.candidates) if args.candidates and Path(args.candidates).exists() else None,
            profile_path=Path(args.profile) if args.profile and Path(args.profile).exists() else None,
            extractor_path=Path(__file__),
        )
        out["run_id"] = res.run_id
        out["persistence_inputs"] = {
            "timeline_sha256": res.timeline_sha256,
            "profile_sha256": res.profile_sha256,
            "parser_signature_sha256": res.parser_signature_sha256,
            "extractor_sha256": res.extractor_sha256,
        }

    return out


def build_aoo_payload_from_timeline(
    *,
    timeline_payload: dict,
    timeline_path: Path | None = None,
    candidates_path: Path | None = None,
    root_actor: str = "George W. Bush",
    root_surname: str = "Bush",
    max_events: int = 260,
    profile_path: Path | None = None,
    db_path: Path | None = None,
    no_db: bool = True,
    spacy_model: str = "en_core_web_sm",
    no_spacy: bool = False,
) -> dict:
    if timeline_path is None:
        timeline_path = Path("SensibLaw/.cache_local/wiki_timeline_gwb.json")
    if candidates_path is None:
        candidates_path = Path("SensibLaw/.cache_local/wiki_candidates_gwb.json")
    if profile_path is None:
        profile_path = Path("SensibLaw/policies/wiki_timeline_aoo_profile_v1.json")
    if db_path is None:
        db_path = Path(".cache_local/itir.sqlite")
    return _build_aoo_payload_from_namespace(
        argparse.Namespace(
            timeline=timeline_path,
            candidates=candidates_path,
            out=Path("SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json"),
            root_actor=root_actor,
            root_surname=root_surname,
            max_events=max_events,
            profile=profile_path,
            db_path=db_path,
            no_db=no_db,
            spacy_model=spacy_model,
            no_spacy=no_spacy,
            timeline_payload=timeline_payload,
        )
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Extract AAO mini-graphs from wiki timeline candidates.")
    ap.add_argument(
        "--timeline",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_timeline_gwb.json"),
        help="Input timeline JSON (default: %(default)s)",
    )
    ap.add_argument(
        "--candidates",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.json"),
        help="Optional wiki candidates JSON for alias resolution (default: %(default)s)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json"),
        help="Output AAO JSON (default: %(default)s)",
    )
    ap.add_argument("--root-actor", default="George W. Bush", help="Root actor label for 'Bush' mentions")
    ap.add_argument("--root-surname", default="Bush", help="Surname token that resolves to root actor")
    ap.add_argument("--max-events", type=int, default=260, help="Max events to process (default: 260)")
    ap.add_argument(
        "--profile",
        type=Path,
        default=Path("SensibLaw/policies/wiki_timeline_aoo_profile_v1.json"),
        help="Extraction profile JSON (action patterns/title labels) (default: %(default)s)",
    )
    ap.add_argument(
        "--db-path",
        type=Path,
        default=Path(".cache_local/itir.sqlite"),
        help="SQLite persistence target for canonical storage (JSON remains an export) (default: %(default)s)",
    )
    ap.add_argument("--no-db", action="store_true", help="Disable SQLite persistence (export JSON only)")
    ap.add_argument("--spacy-model", default="en_core_web_sm", help="spaCy model for deterministic role/attachment parsing")
    ap.add_argument("--no-spacy", action="store_true", help="Disable spaCy parsing (span candidates lane will be empty)")
    args = ap.parse_args(argv)

    out = _build_aoo_payload_from_namespace(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "events": len(out.get("events") or [])}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
