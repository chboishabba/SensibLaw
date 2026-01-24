from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Set

from src.models.provision import RuleReference
from src.reference_identity import normalize_for_identity


@dataclass(frozen=True)
class ReferenceDiff:
    added: Set[str]
    removed: Set[str]
    unchanged: Set[str]


def diff_references(lhs: Iterable[RuleReference], rhs: Iterable[RuleReference]) -> ReferenceDiff:
    """Compute a diff of references based on identity hashes."""

    left_hashes = {normalize_for_identity(ref).identity_hash for ref in lhs}
    right_hashes = {normalize_for_identity(ref).identity_hash for ref in rhs}

    added = right_hashes - left_hashes
    removed = left_hashes - right_hashes
    unchanged = left_hashes & right_hashes

    return ReferenceDiff(added=added, removed=removed, unchanged=unchanged)


__all__ = ["ReferenceDiff", "diff_references"]
