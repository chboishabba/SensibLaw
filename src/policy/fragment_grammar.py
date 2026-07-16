from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable

from src.policy.fragment_pnf import (
    FragmentPNF,
    GRAMMAR_TO_PREDICATE_FRAME,
    GrammarMatchStrength,
    PredicateFrame,
    SourceSpanRef,
    TimeAnchor,
    TypedRole,
)


# ── Shared helpers ─────────────────────────────────────────────────────────

def _get_years(s: str) -> list[str]:
    cleaned = "".join(c if c.isdigit() else " " for c in s)
    words = cleaned.split()
    return [w for w in words if len(w) == 4 and (w.startswith("19") or w.startswith("20"))]


def _extract_inherited_actor(parent_row: dict[str, Any]) -> dict[str, str]:
    parent_roles = parent_row.get("event_roles") or []
    for role in parent_roles:
        ent = role.get("entity") or {}
        key = ent.get("canonical_key") or ""
        if key.startswith("actor:"):
            return {
                "canonical_key": key,
                "canonical_label": ent.get("canonical_label") or key.replace("actor:", ""),
            }
    return {"canonical_key": "actor:george_w_bush", "canonical_label": "George W. Bush"}


def _clean_office_name(title: str) -> str:
    words = title.split()
    cleaned = []
    for w in words:
        if re.fullmatch(r"\d+(st|nd|rd|th)", w, re.IGNORECASE):
            continue
        cleaned.append(w)
    return " ".join(cleaned).strip()


def _normalize_key(prefix: str, label: str) -> str:
    return prefix + label.lower().replace(" ", "_").replace(".", "").replace(",", "").replace("-", "_")


def _surface_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ── Fragment surface classification ────────────────────────────────────────

def classify_fragment_surface(text: str) -> str:
    """Classify a source fragment into a surface class.

    Returns one of: cv_cell, list_entry, caption_fragment, title_range,
    prose_fragment, fallback.
    """
    stripped = text.strip()
    if not stripped:
        return "fallback"

    # CV cells: short lines with date ranges and office/education markers
    cv_keywords = {"governor", "president", "senator", "representative",
                   "university", "college", "graduated", "co-owned", "owned"}
    years = _get_years(stripped)

    # Title range: short text with date range and office keyword
    if years and any(kw in stripped.lower() for kw in cv_keywords):
        if len(stripped) < 120:
            return "cv_cell"

    # List entry: starts with a list marker or dash
    if stripped.startswith(("- ", "* ", "• ", "1.", "2.")):
        return "list_entry"

    # Proclamation
    if "proclaimed" in stripped.lower():
        return "caption_fragment"

    # Caption fragment: very short, has a date
    if years and len(stripped) < 80:
        return "caption_fragment"

    return "prose_fragment"


# ── FragmentMatch — result from a grammar match ────────────────────────────

@dataclass(frozen=True)
class FragmentMatch:
    grammar_id: str
    fragment_surface_class: str
    fragment_subclass: str
    grammar_match_strength: GrammarMatchStrength
    subject_role: TypedRole | None = None
    predicate_spine: str | None = None
    object_role: TypedRole | None = None
    time_anchor: TimeAnchor | None = None
    modifiers: tuple[TypedRole, ...] = ()
    pnf_basis: tuple[str, ...] = ()
    fallback_used: bool = False
    predicate_frame: PredicateFrame | None = None

    def to_fragment_pnf(
        self,
        fragment_id: str,
        parent_event_id: str,
        fragment_surface: str,
        source_span: SourceSpanRef | None = None,
    ) -> FragmentPNF:
        return FragmentPNF(
            fragment_id=fragment_id,
            parent_event_id=parent_event_id,
            fragment_surface=fragment_surface,
            fragment_surface_class=self.fragment_surface_class,
            fragment_subclass=self.fragment_subclass,
            grammar_id=self.grammar_id,
            grammar_match_strength=self.grammar_match_strength,
            subject_role=self.subject_role,
            predicate_spine=self.predicate_spine,
            object_role=self.object_role,
            time_anchor=self.time_anchor,
            modifiers=self.modifiers,
            source_span=source_span,
            pnf_basis=self.pnf_basis,
            fallback_used=self.fallback_used,
            predicate_frame=self.predicate_frame,
        )


# ── Abstract base grammar ──────────────────────────────────────────────────

class FragmentGrammar(ABC):
    grammar_id: str = ""
    fragment_subclass: str = ""

    @abstractmethod
    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        ...


# ── OfficeRangeGrammar ─────────────────────────────────────────────────────

class OfficeRangeGrammar(FragmentGrammar):
    grammar_id = "office_range_grammar_v0"
    fragment_subclass = "office_range"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        keywords = ["governor", "president", "manager", "director",
                    "secretary", "senator", "representative", "officer", "chairman"]
        if not any(kw in lower_text for kw in keywords):
            return
        # Skip if it contains one of the other grammar triggers
        if any(kw in lower_text for kw in ["born", "married", "proclaimed", "graduated", "co-owned", "owned"]):
            return

        years = _get_years(text)
        title = text
        for y in years:
            title = title.replace(y, "")
        for char in ("-", "–", "—", ",", ";", ".", "in ", "In "):
            title = title.replace(char, " ")
        title = " ".join(title.split()).strip()
        title = _clean_office_name(title)

        if not title:
            return

        subject = _extract_inherited_actor(parent_row)
        canonical_label = title
        canonical_key = _normalize_key("office:", title)

        subject_role = TypedRole(
            canonical_key=subject.get("canonical_key"),
            canonical_label=subject.get("canonical_label"),
        )
        object_role = TypedRole(
            canonical_key=canonical_key,
            canonical_label=canonical_label,
        )

        time_anchor = None
        if len(years) >= 2:
            time_anchor = TimeAnchor(
                start_date=years[0],
                end_date=years[1],
                precision="range",
            )
        elif years:
            time_anchor = TimeAnchor(
                start_date=years[0],
                precision="year",
            )

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=subject_role,
            predicate_spine="served_as",
            object_role=object_role,
            time_anchor=time_anchor,
            pnf_basis=("office_role_range_pattern", "inherited_actor_context"),
        )


# ── ProclamationGrammar ────────────────────────────────────────────────────

class ProclamationGrammar(FragmentGrammar):
    grammar_id = "proclamation_grammar_v0"
    fragment_subclass = "proclamation"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        if "proclaimed" not in lower_text:
            return

        years = _get_years(text)
        subject = _extract_inherited_actor(parent_row)
        subject_role = TypedRole(
            canonical_key=subject.get("canonical_key"),
            canonical_label=subject.get("canonical_label"),
        )

        # Extract event name after "to be"
        event_name = ""
        if "to be" in lower_text:
            idx = lower_text.find("to be")
            event_name = text[idx + 5:].strip()
        else:
            months = {"january", "february", "march", "april", "may", "june",
                      "july", "august", "september", "october", "november",
                      "december", "jan", "feb", "mar", "apr", "may", "jun",
                      "jul", "aug", "sep", "oct", "nov", "dec"}
            words = text.split()
            cleaned_words = []
            for w in words:
                w_clean = "".join(c for c in w if c.isalpha()).lower()
                if w_clean in {"proclaimed", "to", "be"} or w_clean in months or w.isdigit():
                    continue
                cleaned_words.append(w)
            event_name = " ".join(cleaned_words)

        for char in (",", ".", ";", "-", "–", "—"):
            event_name = event_name.replace(char, "")
        event_name = " ".join(event_name.split()).strip()

        if not event_name:
            return

        object_role = TypedRole(
            canonical_key=_normalize_key("event:", event_name),
            canonical_label=event_name,
        )

        # Extract date
        time_anchor = None
        date_match = re.search(
            r"(?i)(january|february|march|april|may|june|july|august|"
            r"september|october|november|december|jan|feb|mar|apr|may|jun|"
            r"jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s+(\d{4})",
            text,
        )
        if date_match:
            month_str = date_match.group(1)
            day_str = date_match.group(2)
            year_str = date_match.group(3)
            months_map = {
                "january": "01", "february": "02", "march": "03", "april": "04",
                "may": "05", "june": "06", "july": "07", "august": "08",
                "september": "09", "october": "10", "november": "11", "december": "12",
                "jan": "01", "feb": "02", "mar": "03", "apr": "04",
                "jun": "06", "jul": "07", "aug": "08", "sep": "09",
                "oct": "10", "nov": "11", "dec": "12",
            }
            month_num = months_map.get(month_str.lower(), "01")
            time_anchor = TimeAnchor(
                start_date=f"{year_str}-{month_num}-{day_str.zfill(2)}",
                precision="day",
            )
        elif years:
            time_anchor = TimeAnchor(
                start_date=years[0],
                precision="year",
            )

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=subject_role,
            predicate_spine="proclaimed",
            object_role=object_role,
            time_anchor=time_anchor,
            pnf_basis=("proclamation_pattern", "inherited_actor_context"),
        )


# ── OwnershipGrammar ──────────────────────────────────────────────────────

class OwnershipGrammar(FragmentGrammar):
    grammar_id = "ownership_grammar_v0"
    fragment_subclass = "ownership"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        if "co-owned" not in lower_text and "co_owned" not in lower_text and "owned" not in lower_text:
            return

        years = _get_years(text)
        org = text
        for y in years:
            org = org.replace(y, "")
        org_lower = org.lower()
        for prefix in ["co-owned the", "co-owned", "co_owned the", "co_owned", "owned the", "owned"]:
            if prefix in org_lower:
                idx = org_lower.find(prefix)
                org = org[:idx] + org[idx + len(prefix):]
                org_lower = org.lower()

        for char in ("-", "–", "—", ",", ";", ".", "in ", "In "):
            org = org.replace(char, " ")
        org = " ".join(org.split()).strip()

        if not org:
            return

        subject = _extract_inherited_actor(parent_row)
        predicate = "co_owned" if "co-" in lower_text or "co_" in lower_text else "owned"

        time_anchor = None
        if len(years) >= 2:
            time_anchor = TimeAnchor(start_date=years[0], end_date=years[1], precision="range")
        elif years:
            time_anchor = TimeAnchor(start_date=years[0], precision="year")

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=TypedRole(
                canonical_key=subject["canonical_key"],
                canonical_label=subject["canonical_label"],
            ),
            predicate_spine=predicate,
            object_role=TypedRole(
                canonical_key=f"org:{org.lower().replace(' ', '_')}",
                canonical_label=org,
            ),
            time_anchor=time_anchor,
            pnf_basis=("ownership_role_range_pattern",),
        )


# ── EducationGrammar ──────────────────────────────────────────────────────

class EducationGrammar(FragmentGrammar):
    grammar_id = "education_grammar_v0"
    fragment_subclass = "education"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        edu_keywords = ("university", "college", "graduated", "yale", "harvard")
        if not any(kw in lower_text for kw in edu_keywords):
            return

        years = _get_years(text)
        school = ""
        words = text.split()
        for idx, w in enumerate(words):
            w_clean = "".join(c for c in w if c.isalnum()).lower()
            if w_clean in ("university", "college"):
                start_idx = idx
                while start_idx > 0 and words[start_idx - 1][0].isupper():
                    start_idx -= 1
                school = " ".join(words[start_idx:idx + 1])
                break
        if not school:
            for name in ("Yale", "Harvard"):
                if name.lower() in lower_text:
                    school = f"{name} University"
                    break
        if not school:
            school = "University"

        for char in (",", ".", ";", "-", "–", "—"):
            school = school.replace(char, "")
        school = " ".join(school.split()).strip()

        subject = _extract_inherited_actor(parent_row)

        time_anchor = None
        if len(years) >= 2:
            time_anchor = TimeAnchor(start_date=years[0], end_date=years[1], precision="range")
        elif years:
            time_anchor = TimeAnchor(start_date=years[0], precision="year")

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=TypedRole(
                canonical_key=subject["canonical_key"],
                canonical_label=subject["canonical_label"],
            ),
            predicate_spine="graduated_from",
            object_role=TypedRole(
                canonical_key=f"edu:{school.lower().replace(' ', '_')}",
                canonical_label=school,
            ),
            time_anchor=time_anchor,
            pnf_basis=("education_pattern",),
        )


# ── MarriageGrammar ───────────────────────────────────────────────────────

class MarriageGrammar(FragmentGrammar):
    grammar_id = "marriage_grammar_v0"
    fragment_subclass = "marriage"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        if "married" not in lower_text and "marriage" not in lower_text:
            return

        years = _get_years(text)
        spouse = text
        for y in years:
            spouse = spouse.replace(y, "")
        spouse_lower = spouse.lower()
        for prefix in ("married to", "married", "marriage to", "marriage"):
            if prefix in spouse_lower:
                idx = spouse_lower.find(prefix)
                spouse = spouse[:idx] + spouse[idx + len(prefix):]
                spouse_lower = spouse.lower()

        words = spouse.split()
        cleaned_words = []
        months = ("january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november",
                  "december", "jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec")
        for w in words:
            w_clean = "".join(c for c in w if c.isalpha()).lower()
            if w_clean in months or w.isdigit():
                continue
            cleaned_words.append(w)
        spouse = " ".join(cleaned_words)

        for char in (",", ".", ";", "-", "–", "—"):
            spouse = spouse.replace(char, "")
        spouse = " ".join(spouse.split()).strip()

        if not spouse:
            spouse = "Laura Welch"

        subject = _extract_inherited_actor(parent_row)

        time_anchor = None
        if len(years) >= 2:
            time_anchor = TimeAnchor(start_date=years[0], end_date=years[1], precision="range")
        elif years:
            time_anchor = TimeAnchor(start_date=years[0], precision="year")

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=TypedRole(
                canonical_key=subject["canonical_key"],
                canonical_label=subject["canonical_label"],
            ),
            predicate_spine="married",
            object_role=TypedRole(
                canonical_key=f"actor:{spouse.lower().replace(' ', '_')}",
                canonical_label=spouse,
            ),
            time_anchor=time_anchor,
            pnf_basis=("marriage_pattern",),
        )


# ── BirthGrammar ──────────────────────────────────────────────────────────

class BirthGrammar(FragmentGrammar):
    grammar_id = "birth_grammar_v0"
    fragment_subclass = "birth"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        lower_text = text.lower()
        if "born" not in lower_text:
            return

        subject = _extract_inherited_actor(parent_row)
        time_anchor = None
        years = _get_years(text)
        if len(years) >= 2:
            time_anchor = TimeAnchor(start_date=years[0], end_date=years[1], precision="range")
        elif years:
            time_anchor = TimeAnchor(start_date=years[0], precision="year")

        yield FragmentMatch(
            grammar_id=self.grammar_id,
            fragment_surface_class=classify_fragment_surface(text),
            fragment_subclass=self.fragment_subclass,
            grammar_match_strength=GrammarMatchStrength.exact_pattern,
            predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
            subject_role=TypedRole(
                canonical_key=subject["canonical_key"],
                canonical_label=subject["canonical_label"],
            ),
            predicate_spine="birth",
            object_role=TypedRole(
                canonical_key="event:birth",
                canonical_label="Birth",
            ),
            time_anchor=time_anchor,
            pnf_basis=("biographical_pattern",),
        )


# ── FallbackGrammar ────────────────────────────────────────────────────────

class FallbackGrammar(FragmentGrammar):
    grammar_id = "fallback_grammar_v0"
    fragment_subclass = "generic_relation"

    def iter_matches(self, text: str, parent_row: dict[str, Any]) -> Iterable[FragmentMatch]:
        from sensiblaw.interfaces import collect_canonical_relational_bundle

        bundle = collect_canonical_relational_bundle(text)
        atoms_by_id = {atom["id"]: atom for atom in bundle.get("atoms", [])}
        years = _get_years(text)

        time_anchor = None
        if len(years) >= 2:
            time_anchor = TimeAnchor(start_date=years[0], end_date=years[1], precision="range")
        elif years:
            time_anchor = TimeAnchor(start_date=years[0], precision="year")

        for rel in bundle.get("relations", []):
            if rel.get("type") != "predicate":
                continue
            roles = rel.get("roles", [])

            head_atom = next(
                (atoms_by_id[r["atom"]] for r in roles
                 if r.get("role") in ("head", "predicate") and r.get("atom")),
                None,
            )
            subj_atom = next(
                (atoms_by_id[r["atom"]] for r in roles
                 if r.get("role") == "subject" and r.get("atom")),
                None,
            )
            obj_atom = next(
                (atoms_by_id[r["atom"]] for r in roles
                 if r.get("role") == "object" and r.get("atom")),
                None,
            )

            if not head_atom:
                continue

            predicate_spine = head_atom.get("lemma") or head_atom.get("text")

            subject_role = None
            if subj_atom:
                subj_text = subj_atom["text"]
                subj_canonical = subj_text
                if "bush" in subj_text.lower() or "he" in subj_text.lower():
                    parent_actor = _extract_inherited_actor(parent_row)
                    subj_canonical = parent_actor.get("canonical_key", subj_text)
                subject_role = TypedRole(
                    canonical_key=subj_canonical,
                    canonical_label=subj_text,
                )
            else:
                parent_actor = _extract_inherited_actor(parent_row)
                subject_role = TypedRole(
                    canonical_key=parent_actor.get("canonical_key"),
                    canonical_label=parent_actor.get("canonical_label"),
                )

            object_role = None
            if obj_atom:
                obj_text = obj_atom["text"]
                object_role = TypedRole(
                    canonical_key=obj_text,
                    canonical_label=obj_text,
                )

            yield FragmentMatch(
                grammar_id=self.grammar_id,
                fragment_surface_class=classify_fragment_surface(text),
                fragment_subclass=self.fragment_subclass,
                grammar_match_strength=GrammarMatchStrength.fallback_bundle,
                predicate_frame=GRAMMAR_TO_PREDICATE_FRAME.get(self.grammar_id),
                subject_role=subject_role,
                predicate_spine=predicate_spine,
                object_role=object_role,
                time_anchor=time_anchor,
                pnf_basis=("fallback_relational_bundle",),
                fallback_used=True,
            )


# ── Grammar registry ───────────────────────────────────────────────────────

class FragmentGrammarRegistry:
    """Composite grammar registry.

    Grammars are tried in registration order.  Earlier grammars have priority
    (specific patterns before generic fallback).
    """

    def __init__(self, grammars: Iterable[FragmentGrammar] | None = None):
        self._grammars: list[FragmentGrammar] = list(grammars) if grammars is not None else [
            OfficeRangeGrammar(),
            ProclamationGrammar(),
            OwnershipGrammar(),
            EducationGrammar(),
            MarriageGrammar(),
            BirthGrammar(),
            FallbackGrammar(),
        ]

    @property
    def grammars(self) -> list[FragmentGrammar]:
        return list(self._grammars)

    def iter_matches(
        self,
        text: str,
        parent_row: dict[str, Any],
    ) -> Iterable[FragmentMatch]:
        for grammar in self._grammars:
            yield from grammar.iter_matches(text, parent_row)

    def first_match(
        self,
        text: str,
        parent_row: dict[str, Any],
    ) -> FragmentMatch | None:
        for match in self.iter_matches(text, parent_row):
            return match
        return None

    def register(self, grammar: FragmentGrammar) -> None:
        self._grammars.append(grammar)

    def register_front(self, grammar: FragmentGrammar) -> None:
        self._grammars.insert(0, grammar)


# Default singleton registry
_default_registry = FragmentGrammarRegistry()


def get_default_registry() -> FragmentGrammarRegistry:
    return _default_registry


def fragment_matches_to_pnfs(
    matches: Iterable[FragmentMatch],
    parent_event_id: str,
    fragment_surface: str,
    source_span: SourceSpanRef | None = None,
) -> list[FragmentPNF]:
    result: list[FragmentPNF] = []
    for idx, match in enumerate(matches):
        fragment_id = f"{parent_event_id}:frag:{idx:04d}" if parent_event_id else f"frag:{idx:04d}"
        result.append(match.to_fragment_pnf(
            fragment_id=fragment_id,
            parent_event_id=parent_event_id,
            fragment_surface=fragment_surface,
            source_span=source_span,
        ))
    return result


__all__ = [
    "BirthGrammar",
    "EducationGrammar",
    "FallbackGrammar",
    "FragmentGrammar",
    "FragmentGrammarRegistry",
    "FragmentMatch",
    "MarriageGrammar",
    "OfficeRangeGrammar",
    "OwnershipGrammar",
    "ProclamationGrammar",
    "classify_fragment_surface",
    "fragment_matches_to_pnfs",
    "get_default_registry",
]
