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
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

REQUEST_RE = re.compile(r"\bat\s+(?:President\s+)?([A-Z][a-z]+)(?:'s)?\s+request\b", re.IGNORECASE)
REPORTED_SUBJECT_RE = re.compile(r"\b(?:the\s+)?([A-Z][A-Za-z]+)\s+reported\b")


ACTION_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("initiated", re.compile(r"\binitiat(?:e|ed|es|ing)\b", re.IGNORECASE)),
    ("discharged", re.compile(r"\bdischarg(?:e|ed|es|ing)\b", re.IGNORECASE)),
    ("suspended", re.compile(r"\bsuspend(?:ed|s|ing)\b", re.IGNORECASE)),
    ("told", re.compile(r"\btold\b|\btell(?:s|ing)?\b", re.IGNORECASE)),
    ("voted", re.compile(r"\bvote(?:d|s|ing)?\b", re.IGNORECASE)),
    ("reported", re.compile(r"\breported\b|\breport(?:s|ed|ing)?\b", re.IGNORECASE)),
    ("cautioned", re.compile(r"\bcautioned\b|\bcaution(?:s|ed|ing)?\b", re.IGNORECASE)),
    ("gave_birth", re.compile(r"\bgave\s+birth\b", re.IGNORECASE)),
    ("defeated", re.compile(r"\bdefeat(?:ed|ing|s)?\b", re.IGNORECASE)),
    ("continued", re.compile(r"\bcontinue(?:d|s|ing)?\b", re.IGNORECASE)),
    ("weakened", re.compile(r"\bweaken(?:ed|ing|s)?\b", re.IGNORECASE)),
    ("intensified", re.compile(r"\bintensified\b", re.IGNORECASE)),
    ("began", re.compile(r"\bbegan\b|\bbeginning\b", re.IGNORECASE)),
    ("nominated", re.compile(r"\bnominated\b|\bnominate\b", re.IGNORECASE)),
    ("urged", re.compile(r"\burged\b|\burge\b", re.IGNORECASE)),
    ("commissioned_into", re.compile(r"\bcommissioned\b.*\binto\b", re.IGNORECASE)),
    ("commissioned", re.compile(r"\bcommissioned\b", re.IGNORECASE)),
    ("threw", re.compile(r"\bthrew\b|\bthrow\b", re.IGNORECASE)),
    ("entered", re.compile(r"\bentered\b|\benter\b", re.IGNORECASE)),
    ("gave_speech", re.compile(r"\b(?:was\s+)?giving\s+a\s+speech\b|\bgave\s+a\s+speech\b", re.IGNORECASE)),
    ("led", re.compile(r"\bled\b|\blead\b", re.IGNORECASE)),
    ("advised", re.compile(r"\badvised\b|\badvise\b", re.IGNORECASE)),
    ("departed", re.compile(r"\bdepart(?:ed)?\b", re.IGNORECASE)),
    ("requested", re.compile(r"\brequested\b|\brequest(?:s|ed)?\b", re.IGNORECASE)),
    ("completed", re.compile(r"\bcomplete(?:d)?\b", re.IGNORECASE)),
    ("withdrew", re.compile(r"\bwithdrew\b|\bwithdrawn\b|\bwithdraw\b", re.IGNORECASE)),
    ("retired", re.compile(r"\bretired\b|\bretirement\b", re.IGNORECASE)),
    ("died", re.compile(r"\bdied\b|\bdeath\b", re.IGNORECASE)),
    ("killed", re.compile(r"\bkilled\b|\bkill\b", re.IGNORECASE)),
    ("approved", re.compile(r"\bapproved\b|\bapprove\b", re.IGNORECASE)),
    ("bailout", re.compile(r"\bbailout\b|\bbail(?:ed)?\s+out\b", re.IGNORECASE)),
    ("takeover", re.compile(r"\btakeover\b|\btook\s+over\b|\btaken\s+over\b", re.IGNORECASE)),
    ("established", re.compile(r"\bestablished\b", re.IGNORECASE)),
    ("called", re.compile(r"\bcalled\b", re.IGNORECASE)),
    ("joined", re.compile(r"\bjoined\b", re.IGNORECASE)),
    ("selected", re.compile(r"\bselected\b", re.IGNORECASE)),
    ("signed", re.compile(r"\bsigned\b", re.IGNORECASE)),
    ("launched", re.compile(r"\blaunched\b", re.IGNORECASE)),
    ("arranged", re.compile(r"\barranged\b", re.IGNORECASE)),
    ("merged", re.compile(r"\bmerged\b", re.IGNORECASE)),
    ("ran", re.compile(r"\bran for\b|\bran\b", re.IGNORECASE)),
    ("won", re.compile(r"\bwon\b", re.IGNORECASE)),
    ("re_elected", re.compile(r"\bre-?elected\b", re.IGNORECASE)),
    ("said", re.compile(r"\bsaid\b", re.IGNORECASE)),
    ("released", re.compile(r"\breleased\b", re.IGNORECASE)),
]

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


def _extract_action(text: str) -> Tuple[Optional[str], List[str]]:
    warnings: List[str] = []
    # Choose the earliest matching action in the sentence, not the first pattern in the list.
    best: Optional[Tuple[int, int, str]] = None  # (start, -match_len, label)
    for label, pat in ACTION_PATTERNS:
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
    # Prefer simple past tense / participle forms that often carry event actions.
    t = re.sub(r"[\u2013\u2014-]", " ", text)
    # Exclude bracketed/citation noise and keep it simple.
    for m in re.finditer(r"\b([A-Za-z]{4,})(?:ed|ing)\b", t):
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
            if not purpose:
                continue
            if len(purpose) > 220:
                purpose = purpose[:220].rstrip() + "..."
            return purpose
    except Exception:
        return None
    return None


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
    "gave_speech": ("give",),
    "requested": ("request",),
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
}


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
            if len(txt) > 120:
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
        toks = [tok] + list(getattr(tok, "conjuncts", []))
        idxs = []
        for t in toks:
            idxs.extend([x.i for x in t.subtree])
        if not idxs:
            return str(getattr(tok, "text", "") or "").strip()
        span = doc[min(idxs) : max(idxs) + 1]
        out = re.sub(r"\s+", " ", str(getattr(span, "text", "") or "")).strip()
        # Appositive/participial tails often appear after commas; keep the head NP.
        if "," in out:
            out = out.split(",", 1)[0].strip()
        return out
    except Exception:
        return str(getattr(tok, "text", "") or "").strip()


def _resolve_subject_surface(surface: str, actors: List[dict], root_actor: str, root_surname: str) -> str:
    s = re.sub(r"\s+", " ", str(surface or "").strip())
    if not s:
        return s
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
    return s


def _subjects_for_action(doc, action: str, actors: List[dict], root_actor: str, root_surname: str) -> List[str]:
    if doc is None:
        return []
    act = str(action or "").strip().lower()
    if not act:
        return []
    lemmas = ACTION_LEMMAS.get(act, (act,))
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
    for v in verbs[:2]:
        subj_tokens = []
        for c in v.children:
            if str(getattr(c, "dep_", "")) in {"nsubj", "nsubjpass", "csubj"}:
                subj_tokens.append(c)
                subj_tokens.extend(list(getattr(c, "conjuncts", [])))
        for st in subj_tokens:
            surf = _subject_surface_for_token(doc, st)
            resolved = _resolve_subject_surface(surf, actors, root_actor, root_surname)
            key = resolved.lower()
            if resolved and key not in seen:
                seen.add(key)
                out.append(resolved)
    return out


def _purpose_to_step(purpose: Optional[str], fallback_subjects: List[str]) -> Optional[dict]:
    p = re.sub(r"\s+", " ", str(purpose or "").strip())
    if not p:
        return None
    m = re.match(r"^([a-z]+)\s+(.+)$", p, flags=re.IGNORECASE)
    if not m:
        return None
    verb = m.group(1).strip().lower()
    obj = m.group(2).strip()
    if not verb or not obj:
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
    ap.add_argument("--spacy-model", default="en_core_web_sm", help="spaCy model for deterministic role/attachment parsing")
    ap.add_argument("--no-spacy", action="store_true", help="Disable spaCy parsing (span candidates lane will be empty)")
    args = ap.parse_args(argv)

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

        warnings: List[str] = []
        doc = None
        if nlp is not None:
            try:
                doc = nlp(text)
            except Exception:
                doc = None

        action, w_action = _extract_action(text)
        warnings.extend(w_action)
        purpose = _extract_purpose_from_doc(doc) if doc is not None else None
        if not action and doc is not None:
            # Deterministic fallback: choose a verb root when pattern matching misses.
            try:
                cand = None
                for t in doc:
                    if getattr(t, "pos_", "") == "VERB" and getattr(t, "dep_", "") == "ROOT":
                        cand = t
                        break
                if cand is None:
                    for t in doc:
                        if getattr(t, "pos_", "") == "VERB":
                            cand = t
                            break
                if cand is not None:
                    lab = (getattr(cand, "lemma_", "") or getattr(cand, "text", "") or "").strip().lower()
                    if lab:
                        action = lab
                        warnings.append("fallback_action_spacy")
            except Exception:
                pass

        requester: Optional[str] = None
        rm = REQUEST_RE.search(text)
        if rm:
            requester = rm.group(1)

        tokens = _extract_actor_tokens(text)
        actors: List[dict] = []

        # Requester (alias-resolved if possible).
        if requester:
            resolved = alias_map.get(requester) or requester
            actors.append(
                {"label": requester, "resolved": resolved, "role": "requester", "source": "pattern:request"}
            )

        # Organization-like subject for "X reported ..." constructions (e.g., "the Pentagon reported ...").
        rm_sub = REPORTED_SUBJECT_RE.search(text)
        if rm_sub:
            rep = str(rm_sub.group(1) or "").strip()
            if rep:
                actors.append({"label": rep, "resolved": rep, "role": "subject", "source": "pattern:reported_subject"})

        # Root actor from standalone surname mention (avoid mapping "Laura Bush"/"Barbara Bush" etc).
        if (
            root_surname
            and re.search(rf"\b{re.escape(root_surname)}\b", text)
            and not _surname_is_part_of_name(text, root_surname, blocked_first_tokens=alias_keys)
        ):
            actors.append(
                {"label": root_surname, "resolved": root_actor, "role": "subject", "source": "root_surname"}
            )

        # If surname appears as part of a name, include the surface full-name as an actor.
        if root_surname and _surname_is_part_of_name(text, root_surname, blocked_first_tokens=alias_keys):
            for full in _extract_capitalized_surname_names(text, root_surname, blocked_first_tokens=alias_keys):
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
        am = BY_AGENT_RE.search(text)
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
        if re.search(r"\bthe war\b", text, flags=re.IGNORECASE):
            objects.append({"title": "the war", "source": "surface_phrase"})
        wm = re.search(r"\b(?:to\s+)?continue\s+weakening\s+(.+?)(?:[.;]|$)", text, flags=re.IGNORECASE)
        if wm:
            tail = re.sub(r"\s+", " ", str(wm.group(1) or "")).strip()
            if tail:
                objects.append({"title": tail, "source": "surface_phrase"})

        # De-dupe object titles.
        wikilink_token_sets = []
        for o in objects:
            if str(o.get("source") or "") == "wikilink":
                wikilink_token_sets.append(_token_set(str(o.get("title") or "")))
        seen_obj = set()
        dedup_obj: List[dict] = []
        for o in objects:
            k = str(o.get("title") or "").strip()
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
            kl = k.lower()
            if kl in seen_obj:
                continue
            seen_obj.add(kl)
            row = {"title": k, "source": src}
            if src == "wikilink":
                row["resolver_hints"] = [{"lane": "sentence_link", "kind": "exact", "title": k, "score": 1.0}]
            else:
                hints = _resolver_hints_for_object(k, links if isinstance(links, list) else [], para_links if isinstance(para_links, list) else [], candidate_titles)
                if hints:
                    row["resolver_hints"] = hints
            dedup_obj.append(row)
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
            if a.get("role") != "requester" and a.get("resolved") and a.get("source") != "pattern:by_agent"
        ]
        steps: List[dict] = []

        # Joined + commissioned split (override any single-action default).
        if re.search(r"\bjoined\b", text, flags=re.IGNORECASE) and re.search(r"\bcommissioned\b.*\binto\b", text, flags=re.IGNORECASE):
            joined_objs = [o.get("title") for o in objects if "Air Force" in str(o.get("title") or "")] or [o.get("title") for o in objects]
            guard_objs = [o.get("title") for o in objects if "Guard" in str(o.get("title") or "")] or [o.get("title") for o in objects]
            steps = [
                {"action": "joined", "subjects": subj_all, "objects": joined_objs, "purpose": None},
                {"action": "commissioned_into", "subjects": subj_all, "objects": guard_objs, "purpose": None},
            ]

        # Speech + threw split (very common structure).
        if re.search(r"\bthrew\b", text, flags=re.IGNORECASE):
            steps = []
            thrower = None
            for a in actors:
                if a.get("role") == "requester":
                    continue
                r = str(a.get("resolved") or "")
                if r and r != root_actor and _looks_like_person_title(r):
                    thrower = r
                    break

            if re.search(r"\b(?:was\s+)?giving\s+a\s+speech\b|\bgave\s+a\s+speech\b", text, flags=re.IGNORECASE):
                loc_objs = [o.get("title") for o in objects if any(k in str(o.get("title") or "") for k in ("Square", "Tbilisi"))] or [o.get("title") for o in objects]
                steps.append(
                    {
                        "action": "gave_speech",
                        "subjects": [root_actor] if root_actor in subj_all else subj_all,
                        "objects": loc_objs,
                        "purpose": None,
                    }
                )

            grenade_obj = ["hand grenade"] if re.search(r"\bgrenade\b", text, flags=re.IGNORECASE) else []
            steps.append(
                {
                    "action": "threw",
                    "subjects": [thrower] if thrower else subj_all,
                    "objects": grenade_obj or [o.get("title") for o in objects],
                    "purpose": None,
                }
            )

        # Reported + cautioned split for Afghanistan/Iraq style prose.
        if (
            not steps
            and re.search(r"\breported\b", text, flags=re.IGNORECASE)
            and re.search(r"\bcautioned\b", text, flags=re.IGNORECASE)
        ):
            rep_subj = None
            rm_sub = REPORTED_SUBJECT_RE.search(text)
            if rm_sub:
                rep_subj = str(rm_sub.group(1) or "").strip() or None
            step_subj = [rep_subj] if rep_subj else subj_all
            all_objs = [o.get("title") for o in objects]
            caution_objs = list(all_objs)
            if re.search(r"\bthe war\b", text, flags=re.IGNORECASE) and "the war" not in caution_objs:
                caution_objs.insert(0, "the war")
            weaken_tail = None
            wm = re.search(r"\b(?:to\s+)?continue\s+weakening\s+(.+?)(?:[.;]|$)", text, flags=re.IGNORECASE)
            if wm:
                weaken_tail = re.sub(r"\s+", " ", str(wm.group(1) or "")).strip() or None
                if weaken_tail and weaken_tail not in caution_objs:
                    caution_objs.append(weaken_tail)
            steps = [
                {"action": "reported", "subjects": step_subj, "objects": all_objs, "purpose": None},
                {"action": "cautioned", "subjects": step_subj, "objects": caution_objs, "purpose": None},
            ]
            if weaken_tail:
                steps.append({"action": "weakening", "subjects": step_subj, "objects": [weaken_tail], "purpose": None})

        # General multi-verb step extraction (bounded): if we didn't already split, emit up to 3 steps
        # by scanning for the earliest occurrences of known actions.
        if not steps:
            hits: List[Tuple[int, str]] = []
            for label, pat in ACTION_PATTERNS:
                m = pat.search(text)
                if not m:
                    continue
                hits.append((int(m.start()), label))
            hits = sorted(set(hits), key=lambda x: x[0])[:4]
            for _, lab in hits:
                if lab == "advised":
                    # Prefer the extracted passive agent as the doer if present.
                    agent = next((a.get("resolved") for a in actors if a.get("source") == "pattern:by_agent"), None)
                    subj = [agent] if agent else subj_all
                    steps.append({"action": "advised", "subjects": [x for x in subj if x], "objects": [o.get("title") for o in objects], "purpose": None})
                else:
                    steps.append({"action": lab, "subjects": subj_all, "objects": [o.get("title") for o in objects], "purpose": None})

        # Default single-step representation if no split was applied.
        if not steps and action:
            steps.append(
                {
                    "action": action,
                    "subjects": subj_all,
                    "objects": [o.get("title") for o in objects],
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
                ss = _subjects_for_action(doc, act, actors, root_actor, root_surname)
                if ss:
                    st["subjects"] = ss

        # Start a minimal nesting/chain lane: if a purpose clause is present, emit a derived
        # purpose-step (verb + object phrase) when it is not already represented.
        if steps and purpose:
            pstep = _purpose_to_step(purpose, list(steps[-1].get("subjects") or subj_all))
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
        seen_steps = set()
        dedup_steps: List[dict] = []
        for s in steps:
            key = (
                str(s.get("action") or ""),
                tuple(x for x in (s.get("subjects") or []) if x),
                tuple(x for x in (s.get("objects") or []) if x),
            )
            if key in seen_steps:
                continue
            seen_steps.add(key)
            dedup_steps.append(s)
        steps = dedup_steps

        chains: List[dict] = []
        if len(steps) > 1:
            for i in range(len(steps) - 1):
                chains.append({"from_step": i, "to_step": i + 1, "kind": "sequence"})
        for i, s in enumerate(steps):
            if s.get("purpose"):
                chains.append({"from_step": i, "to": "purpose", "kind": "purpose_clause"})

        out_events.append(
            {
                "event_id": ev.get("event_id"),
                "anchor": ev.get("anchor"),
                "section": ev.get("section"),
                "text": text,
                "actors": actors,
                "action": action,
                "steps": steps,
                "objects": objects,
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
            "Span candidates are unresolved mentions (TextSpan-like) for view-layer surfacing/promotion; they are not entities.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "events": len(out_events)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
