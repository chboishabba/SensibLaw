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
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from babel.numbers import parse_decimal as _babel_parse_decimal
except Exception:  # pragma: no cover - optional dependency
    _babel_parse_decimal = None


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
    return re.sub(r"\s+", " ", s).strip(" ,;:.()[]{}\"'")


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
    ("died", r"\bdied\b|\bdeath\b"),
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


def _extract_action(text: str, action_patterns: List[Tuple[str, re.Pattern[str]]]) -> Tuple[Optional[str], List[str]]:
    warnings: List[str] = []
    # Choose the earliest matching action in the sentence, not the first pattern in the list.
    best: Optional[Tuple[int, int, str]] = None  # (start, -match_len, label)
    for label, pat in action_patterns:
        m = pat.search(text)
        if not m:
            continue
        start = int(m.start())
        mlen = int(m.end() - m.start())
        cand = (start, -mlen, label)
        if best is None or cand < best:
            best = cand
    if best is not None:
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


def _canonical_action_from_doc(doc, action: str) -> Tuple[str, Optional[dict]]:
    base = _base_action_label(action)
    if not base:
        return "", None
    lemmas = {str(x or "").strip().lower() for x in _action_lemmas(base) if str(x or "").strip()}
    if not doc:
        return (next(iter(lemmas)) if lemmas else base), {
            "surface": str(action or ""),
            "tense": None,
            "aspect": None,
            "verb_form": None,
            "voice": None,
            "source": "fallback:action_lemmas",
        }

    candidates = []
    for t in doc:
        pos = str(getattr(t, "pos_", "") or "")
        if pos not in {"VERB", "AUX"}:
            continue
        lemma = str(getattr(t, "lemma_", "") or "").strip().lower()
        if lemma in lemmas:
            candidates.append(t)
    if not candidates:
        return (next(iter(lemmas)) if lemmas else base), {
            "surface": str(action or ""),
            "tense": None,
            "aspect": None,
            "verb_form": None,
            "voice": None,
            "source": "fallback:action_lemmas",
        }

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
    morph = getattr(tok, "morph", None)

    def _morph_value(name: str) -> Optional[str]:
        if morph is None:
            return None
        try:
            vals = morph.get(name)
            if vals:
                return str(vals[0])
        except Exception:
            return None
        return None

    voice = "Passive" if any(str(getattr(c, "dep_", "") or "") == "auxpass" for c in tok.children) else "Active"
    meta = {
        "surface": str(getattr(tok, "text", "") or action or ""),
        "tense": _morph_value("Tense"),
        "aspect": _morph_value("Aspect"),
        "verb_form": _morph_value("VerbForm"),
        "voice": voice,
        "source": "dep_lemma",
    }
    return lemma, meta


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


_LEADING_DETERMINER_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
_NON_VERB_HEAD_WORDS = {"for", "with", "into", "of", "in", "on", "at", "by", "from", "about"}
_NUMERIC_VALUE_RE = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?$")
_NUMERIC_MENTION_RE = re.compile(
    r"\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:%|percent|per\s+cent|million|billion|trillion|thousand|hundred|years?|months?|days?|lines?|points?|dollars?|usd|aud|eur|gbp)?\b",
    re.IGNORECASE,
)
_NUMERIC_COMPACT_SUFFIX_RE = re.compile(
    r"(?i)^([+-]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?))\s*(%|percent|million|billion|trillion|thousand|hundred|years?|months?|days?|lines?|points?|dollars?|usd|aud|eur|gbp)$"
)
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


def _normalize_numeric_mention(raw: str) -> str:
    t = _clean_entity_surface(raw)
    if not t:
        return ""
    t = re.sub(r"(?i)\bper\s+cent\b", "percent", t)
    compact = t.replace(" ", "")
    m = _NUMERIC_COMPACT_SUFFIX_RE.match(compact)
    if m:
        t = f"{m.group(1)} {m.group(2)}"
    return re.sub(r"\s+", " ", t).strip()


def _numeric_key(raw: str) -> str:
    t = _normalize_numeric_mention(raw)
    if not t:
        return ""

    m = re.match(
        r"(?i)^([+-]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?))(?:\s*(%|percent|million|billion|trillion|thousand|hundred|years?|months?|days?|lines?|points?|dollars?|usd|aud|eur|gbp))?$",
        t.strip(),
    )
    if not m:
        return ""

    num_raw = str(m.group(1) or "").strip()
    unit = str(m.group(2) or "").strip().lower()

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
            return re.sub(r"\s+", " ", t.lower()).strip()

    value = format(dec.normalize(), "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    if value == "-0":
        value = "0"
    return f"{value}|{unit}"


def _strip_leading_determiner(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    return _LEADING_DETERMINER_RE.sub("", t, count=1).strip()


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
        cleaned = _clean_entity_surface(str(s or ""))
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

    def _emit(cand: str) -> None:
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
        seen.add(k)
        out.append(c)

    # Preferred path: token-local extraction from parser output.
    if doc is not None:
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
                is_num = (
                    bool(getattr(tok, "like_num", False))
                    or bool(_NUMERIC_VALUE_RE.fullmatch(lower))
                    or bool(_NUMERIC_COMPACT_SUFFIX_RE.match(ttxt.replace(" ", "")))
                )
                if not is_num:
                    i += 1
                    continue

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

                _emit(candidate)
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
            _emit(cand)

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
        out = re.sub(r"\s+", " ", " ".join(str(getattr(t, "text", "") or "") for t in toks)).strip()
        # Appositive/participial tails often appear after commas; keep the head NP.
        if "," in out:
            out = out.split(",", 1)[0].strip()
        return out
    except Exception:
        return str(getattr(tok, "text", "") or "").strip()


def _resolve_subject_surface(surface: str, actors: List[dict], root_actor: str, root_surname: str) -> str:
    s = _clean_entity_surface(surface)
    if not s:
        return s
    poss = _extract_possessive_person(s)
    if poss:
        return poss
    low = s.lower()
    if low in {"he", "him", "his"} and root_actor:
        return root_actor
    if low in {"that", "which", "who"}:
        return ""

    s_norm = _norm_phrase(s)
    best = None
    best_len = -1
    for a in actors:
        resolved = str(a.get("resolved") or "").strip()
        label = str(a.get("label") or "").strip()
        for cand in (resolved, label):
            if not cand:
                continue
            c_norm = _norm_phrase(cand)
            if not c_norm:
                continue
            if s_norm == c_norm or s_norm in c_norm or c_norm in s_norm:
                if len(cand) > best_len:
                    best = resolved or cand
                    best_len = len(cand)
    if best:
        return best

    # Surname fallback for standalone root-actor references.
    if root_surname and re.search(rf"\b{re.escape(root_surname)}\b", s, flags=re.IGNORECASE):
        return root_actor or s
    return _clean_entity_surface(s)


def _subjects_for_action(doc, action: str, actors: List[dict], root_actor: str, root_surname: str) -> List[str]:
    if doc is None:
        return []
    act = _base_action_label(action)
    if not act:
        return []
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


def _extract_capitalized_surname_names(text: str, surname: str, blocked_first_tokens: Optional[set] = None) -> List[str]:
    """Extract 2-token names like 'Laura Bush' when surname appears in-sentence.

    Wikipedia prose sometimes leaves spouse/child names unlinked; this keeps the AAO substrate
    reviewable without asserting identity beyond the surface form.
    """
    if not surname:
        return []
    out: List[str] = []
    blocked = blocked_first_tokens or set()
    for m in re.finditer(rf"\b([A-Z][a-z]+)\s+{re.escape(surname)}\b", text):
        first = m.group(1).strip()
        if first.lower() in {"president", "governor", "senator", "rep", "representative", "mr", "mrs", "ms", "dr", "chief"}:
            continue
        if first.lower() in blocked:
            continue
        full = f"{first} {surname}"
        if full not in out:
            out.append(full)
    return out


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
    ap.add_argument("--spacy-model", default="en_core_web_sm", help="spaCy model for deterministic role/attachment parsing")
    ap.add_argument("--no-spacy", action="store_true", help="Disable spaCy parsing (span candidates lane will be empty)")
    args = ap.parse_args(argv)

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
        "error": profile_error,
    }

    tl = _load_json(args.timeline)
    events = tl.get("events") or []
    if not isinstance(events, list):
        raise SystemExit("invalid timeline: events[] missing")

    alias_map: Dict[str, str] = {}
    candidate_titles: List[str] = []
    candidates_payload: dict = {}
    if args.candidates.exists():
        candidates_payload = _load_json(args.candidates)
        alias_map = _guess_person_titles(candidates_payload)
        candidate_titles = _candidate_titles(candidates_payload)
    alias_keys = {k.lower() for k in alias_map.keys()}

    root_actor = str(args.root_actor).strip()
    root_surname = str(args.root_surname).strip()

    nlp = None
    parser_info = None
    parser_error = None
    if not args.no_spacy:
        nlp, parser_info, parser_error = _try_load_spacy(str(args.spacy_model))

    out_events: List[dict] = []
    # Track recurrence of span candidates across events (truth capture; view promotion uses thresholds).
    span_seen: Dict[Tuple[str, str], set] = {}
    for ev in events[: int(args.max_events)]:
        if not isinstance(ev, dict):
            continue
        text = str(ev.get("text") or "").strip()
        if not text:
            continue
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

        action, w_action = _extract_action(parse_text, action_patterns)
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
            canon_action, action_meta = _canonical_action_from_doc(doc, action)
            if canon_action:
                action = canon_action
            if action_meta:
                event_action_meta = action_meta

        requester: Optional[str] = None
        requester_resolved: Optional[str] = None
        requester_has_title = False
        requester_title_label = requester_title_labels.get("president", DEFAULT_REQUESTER_TITLE_LABELS.get("president", "U.S. President"))
        rm = REQUEST_RE.search(parse_text)
        if rm:
            requester = rm.group(1)
            requester_has_title = bool(re.search(r"\bPresident\b", str(rm.group(0) or ""), flags=re.IGNORECASE))

        tokens = _extract_actor_tokens(parse_text)
        actors: List[dict] = []

        # Requester (alias-resolved if possible).
        if requester:
            resolved = alias_map.get(requester) or requester
            requester_resolved = resolved
            actors.append(
                {"label": requester, "resolved": resolved, "role": "requester", "source": "pattern:request"}
            )
            if requester_has_title:
                actors.append(
                    {
                        "label": "President",
                        "resolved": requester_title_label,
                        "role": "requester_meta",
                        "source": "pattern:request_title",
                    }
                )

        # Root actor from standalone surname mention (avoid mapping "Laura Bush"/"Barbara Bush" etc).
        if (
            root_surname
            and re.search(rf"\b{re.escape(root_surname)}\b", parse_text)
            and not _surname_is_part_of_name(parse_text, root_surname, blocked_first_tokens=alias_keys)
        ):
            actors.append(
                {"label": root_surname, "resolved": root_actor, "role": "subject", "source": "root_surname"}
            )

        # If surname appears as part of a name, include the surface full-name as an actor.
        if root_surname and _surname_is_part_of_name(parse_text, root_surname, blocked_first_tokens=alias_keys):
            for full in _extract_capitalized_surname_names(parse_text, root_surname, blocked_first_tokens=alias_keys):
                actors.append({"label": full, "resolved": full, "role": "subject", "source": "surface_name"})

        # Other alias-resolved person tokens in the sentence.
        for tok in tokens:
            if requester and tok.lower() == requester.lower():
                continue
            if tok.lower() == root_surname.lower():
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

        # Passive agent: "were advised by the U.S." etc.
        am = BY_AGENT_RE.search(parse_text)
        if am:
            agent_raw = (am.group(1) or "").strip()
            if agent_raw:
                agent = _normalize_agent_label(agent_raw)
                actors.append({"label": agent_raw, "resolved": agent, "role": "subject", "source": "pattern:by_agent"})

        # De-dupe by resolved label.
        seen = set()
        deduped: List[dict] = []
        for a in actors:
            key = str(a.get("resolved") or a.get("label") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(a)
        actors = deduped

        # Dependency subject pass for the primary action; fills obvious gaps like
        # "the Pentagon reported ..." or "U.S. and British forces initiated ...".
        dep_subjects = _subjects_for_action(doc, action or "", actors, root_actor, root_surname) if doc is not None else []
        if dep_subjects:
            existing = {str(a.get("resolved") or "").strip().lower() for a in actors}
            for ds in dep_subjects:
                k = str(ds or "").strip().lower()
                if not k or k in existing:
                    continue
                actors.append({"label": ds, "resolved": ds, "role": "subject", "source": "dep_subject"})
                existing.add(k)

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
                if r and r != root_actor and _looks_like_person_title(r):
                    thrower = r
                    break

            if re.search(r"\b(?:was\s+)?giving\s+a\s+speech\b|\bgave\s+a\s+speech\b", parse_text, flags=re.IGNORECASE):
                loc_objs = [o.get("title") for o in objects if any(k in str(o.get("title") or "") for k in ("Square", "Tbilisi"))] or [o.get("title") for o in objects]
                steps.append(
                    {
                        "action": "gave_speech",
                        "subjects": [root_actor] if root_actor in subj_all else subj_all,
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
            for label, pat in action_patterns:
                m = pat.search(parse_text)
                if not m:
                    continue
                hits.append((int(m.start()), label))
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
                root_actor=root_actor,
                root_surname=root_surname,
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
                ss = _subjects_for_action(doc, act, actors, root_actor, root_surname)
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
                if root_actor:
                    resolved_phrases.append(root_actor)
                    for w in re.split(r"\\s+", root_actor.strip()):
                        w = w.strip(".,;:()[]{}\"'").lower()
                        if w and w.isalpha():
                            resolved_tokens.add(w)
                if root_surname:
                    resolved_tokens.add(root_surname.strip().lower())

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
                "modifier_objects": event_modifier_objects,
                "purpose": purpose,
                "chains": chains,
                "span_candidates": span_candidates,
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

    out = {
        "ok": True,
        "generated_at": _utc_now_iso(),
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
        "root_actor": {"label": root_actor, "surname": root_surname},
        "events": out_events,
        "notes": [
            "Sentence-local AAO extraction. Non-causal. Non-authoritative.",
            "Actors are heuristic: requester/subject roles are extracted by simple patterns and alias maps.",
            "Objects are primarily wikilinks from the timeline event with dependency/surface fallbacks; absence does not imply non-existence.",
            "Non-wikilink objects may include resolver_hints against sentence links, paragraph links, and candidate titles.",
            "Numeric mentions are emitted in a dedicated numeric_objects lane (including sentence second-pass captures).",
            "Actions are canonical verb labels; negation is stored separately under step.negation (no not_* action proliferation).",
            "Span candidates are unresolved mentions (TextSpan-like) for view-layer surfacing/promotion; they are not entities.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "events": len(out_events)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
