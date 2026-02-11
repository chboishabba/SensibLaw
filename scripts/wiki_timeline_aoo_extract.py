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


ACTION_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("gave_birth", re.compile(r"\bgave\s+birth\b", re.IGNORECASE)),
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

# Treat only a small verb-like allowlist as "purpose" to avoid misfires like
# "gave birth to fraternal twin daughters" (where "to" introduces the object).
PURPOSE_VERB_ALLOWLIST = {
    "be",
    "become",
    "raise",
    "create",
    "establish",
    "form",
    "support",
    "help",
    "mark",
    "inform",
    "allow",
    "prevent",
    "stop",
    "start",
    "serve",
    "win",
    "run",
    "campaign",
    "work",
    "make",
    "take",
    "join",
    "lead",
    "send",
    "call",
}


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
    # We do not use allowlists for legitimacy, only for a minimal type hint.
    lemma = (head_lemma or "").lower()
    if has_acronym or has_propn:
        if lemma in {"inspector", "inspectors", "official", "officials", "troop", "troops", "guard", "guards"}:
            return "COLLECTIVE_ROLE"
    if lemma in {"inspectors", "inspector"}:
        return "COLLECTIVE_ROLE"
    return "ABSTRACT"


def _extract_purpose(text: str) -> Optional[str]:
    # Keep simple but guarded: "to <verb> ..." only.
    # This prevents false "purpose" for objects introduced by "to" (e.g. "gave birth to ...").
    m = re.search(r"\bto\b\s+([A-Za-z]+)\b\s+(.+)$", text, flags=re.IGNORECASE)
    if not m:
        return None
    verb = m.group(1).strip().lower()
    if verb not in PURPOSE_VERB_ALLOWLIST:
        return None
    purpose = (verb + " " + m.group(2).strip()).strip()
    # Avoid huge payloads.
    if len(purpose) > 220:
        purpose = purpose[:220].rstrip() + "..."
    return purpose or None


def _extract_actor_tokens(text: str) -> List[str]:
    # Look for capitalized tokens; include possessive ('s) stripping.
    toks = []
    for m in re.finditer(r"\b([A-Z][a-z]+)(?:'s)?\b", text):
        t = m.group(1).strip()
        if t and t not in toks:
            toks.append(t)
    return toks


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
    args = ap.parse_args(argv)

    tl = _load_json(args.timeline)
    events = tl.get("events") or []
    if not isinstance(events, list):
        raise SystemExit("invalid timeline: events[] missing")

    alias_map: Dict[str, str] = {}
    if args.candidates.exists():
        alias_map = _guess_person_titles(_load_json(args.candidates))
    alias_keys = {k.lower() for k in alias_map.keys()}

    root_actor = str(args.root_actor).strip()
    root_surname = str(args.root_surname).strip()

    out_events: List[dict] = []
    for ev in events[: int(args.max_events)]:
        if not isinstance(ev, dict):
            continue
        text = str(ev.get("text") or "").strip()
        if not text:
            continue

        warnings: List[str] = []
        action, w_action = _extract_action(text)
        warnings.extend(w_action)
        purpose = _extract_purpose(text)

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

        # Objects: prefer sentence-local wikilinks from the timeline artifact.
        objects: List[dict] = []
        if isinstance(links, list):
            for t in links:
                if not isinstance(t, str):
                    continue
                title = t.strip()
                if not title:
                    continue
                objects.append({"title": title, "source": "wikilink"})

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

        # General multi-verb step extraction (bounded): if we didn't already split, emit up to 3 steps
        # by scanning for the earliest occurrences of known actions.
        if not steps:
            hits: List[Tuple[int, str]] = []
            for label, pat in ACTION_PATTERNS:
                m = pat.search(text)
                if not m:
                    continue
                hits.append((int(m.start()), label))
            hits = sorted(set(hits), key=lambda x: x[0])[:3]
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
                "warnings": warnings,
            }
        )

    out = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "source_timeline": {
            "path": str(args.timeline),
            "snapshot": tl.get("snapshot"),
        },
        "root_actor": {"label": root_actor, "surname": root_surname},
        "events": out_events,
        "notes": [
            "Sentence-local AAO extraction. Non-causal. Non-authoritative.",
            "Actors are heuristic: requester/subject roles are extracted by simple patterns and alias maps.",
            "Objects are primarily wikilinks from the timeline event; absence does not imply non-existence.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "events": len(out_events)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
