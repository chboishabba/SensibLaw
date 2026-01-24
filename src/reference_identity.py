from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from src.models.document import Document
from src.models.provision import (
    RuleReference,
    RuleAtom,
    RuleElement,
    Provision,
    _build_family_key,
    _extract_jurisdiction_hint,
)


@dataclass(frozen=True)
class ReferenceIdentity:
    """Stable, deterministic identity for a statute reference.

    This is additive-only: it does not alter extraction or dedup behaviour.
    """

    family_key: Optional[str]
    year: Optional[int]
    jurisdiction_hint: Optional[str]
    identity_hash: str


def normalize_for_identity(ref: RuleReference) -> ReferenceIdentity:
    """Derive a ReferenceIdentity from an existing RuleReference.

    The computation is intentionally side-effect free and based solely on
    already-extracted fields.
    """

    canonical_work = _normalise_work(ref.work)
    family_key = _build_family_key(canonical_work)
    year = _extract_year(canonical_work)
    jurisdiction_hint = _extract_jurisdiction_hint(canonical_work)

    payload = {
        "work": canonical_work or None,
        "section": (ref.section or "").strip().lower() or None,
        "pinpoint": (ref.pinpoint or "").strip().lower() or None,
        "family_key": family_key,
        "year": year,
        "jurisdiction_hint": jurisdiction_hint,
    }
    identity_hash = _hash_payload(payload)

    return ReferenceIdentity(
        family_key=family_key,
        year=year,
        jurisdiction_hint=jurisdiction_hint,
        identity_hash=identity_hash,
    )


def iter_references_from_document(doc: Document):
    """Yield all RuleReference instances contained in a Document."""

    for provision in doc.provisions:
        yield from _iter_provision_refs(provision)


def _iter_provision_refs(provision: Provision):
    for atom in provision.rule_atoms:
        yield from atom.references
        for element in atom.elements:
            yield from element.references
    for child in provision.children:
        yield from _iter_provision_refs(child)


def _hash_payload(payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload_json.encode("utf-8")).hexdigest()


def _extract_year(canonical_work: str) -> Optional[int]:
    import re

    match = re.search(r"\b(\d{4})\b", canonical_work)
    return int(match.group(1)) if match else None


def _normalise_work(work: Optional[str]) -> str:
    import re

    if not work:
        return ""
    cleaned = work.strip().lower()
    cleaned = re.sub(r"[\(\)\[\]{}]", " ", cleaned)
    cleaned = re.sub(r"[^\w&-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^(?:[ivxlcdm]+|[a-z])\b\s*", "", cleaned)
    return cleaned


__all__ = ["ReferenceIdentity", "normalize_for_identity", "iter_references_from_document"]
