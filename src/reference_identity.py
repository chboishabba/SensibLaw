from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Set, Tuple

from src.models.provision import RuleReference, _build_family_key, _extract_jurisdiction_hint


@dataclass(frozen=True)
class ReferenceIdentity:
    """Derived identity for a statute reference (metadata-only)."""

    work: Optional[str]
    section: Optional[str]
    pinpoint: Optional[str]
    family_key: Optional[str]
    year: Optional[int]
    jurisdiction_hint: Optional[str]
    identity_hash: str

    @classmethod
    def compute(cls, ref: RuleReference) -> "ReferenceIdentity":
        """Compute a deterministic identity from an existing RuleReference."""

        work = (ref.work or "").strip().lower() or None
        section = (ref.section or "").strip().lower() or None
        pinpoint = (ref.pinpoint or "").strip().lower() or None
        family_key = ref.family_key or _build_family_key(work)
        year = ref.year
        if year is None:
            match = re.search(r"\b(\d{4})\b", work or "")
            year = int(match.group(1)) if match else None
        jurisdiction_hint = ref.jurisdiction_hint or _extract_jurisdiction_hint(work)

        payload = {
            "work": work,
            "section": section,
            "pinpoint": pinpoint,
            "family_key": family_key,
            "year": year,
            "jurisdiction_hint": jurisdiction_hint,
        }
        identity_hash = hashlib.sha1(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return cls(
            work=work,
            section=section,
            pinpoint=pinpoint,
            family_key=family_key,
            year=year,
            jurisdiction_hint=jurisdiction_hint,
            identity_hash=identity_hash,
        )


@dataclass(frozen=True)
class ReferenceDiff:
    added: Set[str]
    removed: Set[str]
    unchanged: Set[str]


def diff_references(old: Iterable[RuleReference], new: Iterable[RuleReference]) -> ReferenceDiff:
    """Compute a proof-safe diff using identity hashes only."""

    old_ids = {_identity_hash(ref) for ref in old}
    new_ids = {_identity_hash(ref) for ref in new}

    unchanged = old_ids & new_ids
    added = new_ids - unchanged
    removed = old_ids - unchanged

    return ReferenceDiff(added=added, removed=removed, unchanged=unchanged)


def _identity_hash(ref: RuleReference) -> str:
    if not ref.identity_hash:
        # Populate on the fly without mutating caller
        return ReferenceIdentity.compute(ref).identity_hash
    return ref.identity_hash
