"""Reading fatigue reduction utilities for long-form bundles.

The helpers in this module provide three capabilities designed to keep
reviewers focussed on the portions of a bundle that actually advance a
matter:

* ``build_pin_cite_navigator`` groups paragraphs by the issues or factors
  they reference and emits keyboard-friendly shortcuts so the UI can offer a
  jump list without any pointer interaction.
* ``DuplicateDetector`` fingerprints paragraphs across multiple drafts and
  groups near-identical passages so redundant reading can be avoided.
* ``focus_lane`` filters a bundle to only the paragraphs linked to live
  issues or deadlines, enabling a "focus mode" experience.

None of the helpers touch IO – they operate on simple dataclasses so they can
be wired into whichever UI layer is consuming the structured bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

from .similarity import simhash


@dataclass(frozen=True)
class Paragraph:
    """Representation of a paragraph within a bundle.

    Attributes
    ----------
    pid:
        Stable identifier for the paragraph. This is typically a UUID or a
        composite key of page/paragraph numbers.
    text:
        Raw text of the paragraph.
    issues:
        Issue identifiers referenced in the paragraph.
    factors:
        Factor identifiers referenced in the paragraph.
    deadlines:
        Identifiers for deadlines or milestone anchors.
    """

    pid: str
    text: str
    issues: Tuple[str, ...] = ()
    factors: Tuple[str, ...] = ()
    deadlines: Tuple[str, ...] = ()


@dataclass(frozen=True)
class NavigatorEntry:
    """A single jump target for the pin-cite navigator."""

    label: str
    paragraph_ids: Tuple[str, ...]
    shortcut: str


def build_pin_cite_navigator(paragraphs: Iterable[Paragraph]) -> List[NavigatorEntry]:
    """Return keyboard-first navigation entries grouped by issue/factor.

    Each distinct issue or factor encountered becomes a navigator entry. The
    entry stores the ordered paragraph identifiers and a keyboard shortcut in
    the form ``"alt+<n>"``. Issues take precedence in ordering followed by
    factors, ensuring that a user working through live issues can jump through
    them sequentially without a mouse.
    """

    issue_to_paragraphs: Dict[str, List[str]] = {}
    factor_to_paragraphs: Dict[str, List[str]] = {}
    for para in paragraphs:
        if para.issues:
            for issue in para.issues:
                issue_to_paragraphs.setdefault(issue, []).append(para.pid)
        if para.factors:
            for factor in para.factors:
                factor_to_paragraphs.setdefault(factor, []).append(para.pid)

    entries: List[NavigatorEntry] = []
    shortcut_index = 1

    def _emit(label: str, para_ids: Sequence[str]) -> None:
        nonlocal shortcut_index
        if not para_ids:
            return
        shortcut = f"alt+{shortcut_index}"
        entries.append(
            NavigatorEntry(label=label, paragraph_ids=tuple(para_ids), shortcut=shortcut)
        )
        shortcut_index += 1

    for issue in sorted(issue_to_paragraphs):
        _emit(f"Issue: {issue}", issue_to_paragraphs[issue])
    for factor in sorted(factor_to_paragraphs):
        _emit(f"Factor: {factor}", factor_to_paragraphs[factor])

    return entries


def _hamming_distance(a: str, b: str) -> int:
    """Return the Hamming distance between two hex-encoded fingerprints."""

    return bin(int(a, 16) ^ int(b, 16)).count("1")


@dataclass(frozen=True)
class DuplicateHit:
    """Record of a duplicate paragraph discovered across drafts."""

    draft_index: int
    paragraph: Paragraph


@dataclass(frozen=True)
class DuplicateGroup:
    """Group of paragraphs that are near-identical across drafts."""

    fingerprint: str
    hits: Tuple[DuplicateHit, ...]


class DuplicateDetector:
    """Detect repeated paragraphs or exhibits across drafts.

    The detector fingerprints each paragraph using SimHash and groups entries
    whose fingerprints fall within a configurable Hamming distance threshold.
    """

    def __init__(self, *, threshold: int = 3) -> None:
        self.threshold = threshold

    def find_duplicates(
        self, drafts: Sequence[Sequence[Paragraph]]
    ) -> List[DuplicateGroup]:
        """Return grouped duplicates across ``drafts``.

        The returned groups always contain at least two hits from distinct
        drafts, ensuring they highlight redundant reading between versions.
        """

        fingerprints: List[Tuple[str, int, Paragraph]] = []
        for draft_index, draft in enumerate(drafts):
            for para in draft:
                fingerprint = simhash(para.text)
                fingerprints.append((fingerprint, draft_index, para))

        groups: List[DuplicateGroup] = []
        consumed: set[int] = set()
        for idx, (fp, draft_index, paragraph) in enumerate(fingerprints):
            if idx in consumed:
                continue
            hits = [DuplicateHit(draft_index=draft_index, paragraph=paragraph)]
            for other_idx in range(idx + 1, len(fingerprints)):
                if other_idx in consumed:
                    continue
                other_fp, other_draft, other_para = fingerprints[other_idx]
                if other_draft == draft_index:
                    continue
                if _hamming_distance(fp, other_fp) <= self.threshold:
                    hits.append(DuplicateHit(draft_index=other_draft, paragraph=other_para))
                    consumed.add(other_idx)
            if len(hits) > 1:
                consumed.add(idx)
                groups.append(DuplicateGroup(fingerprint=fp, hits=tuple(hits)))
        return groups


def focus_lane(
    paragraphs: Iterable[Paragraph],
    *,
    focus_issues: Iterable[str] | None = None,
    focus_deadlines: Iterable[str] | None = None,
) -> List[Paragraph]:
    """Filter ``paragraphs`` down to those tied to live issues/deadlines."""

    focus_issue_set = set(focus_issues or [])
    focus_deadline_set = set(focus_deadlines or [])

    def is_relevant(para: Paragraph) -> bool:
        if focus_issue_set and focus_issue_set.intersection(para.issues):
            return True
        if focus_deadline_set and focus_deadline_set.intersection(para.deadlines):
            return True
        # When no explicit focus is provided fall back to paragraphs with any metadata
        if not focus_issue_set and not focus_deadline_set:
            return bool(para.issues or para.factors or para.deadlines)
        return False

    return [para for para in paragraphs if is_relevant(para)]


__all__ = [
    "Paragraph",
    "NavigatorEntry",
    "DuplicateDetector",
    "DuplicateGroup",
    "DuplicateHit",
    "build_pin_cite_navigator",
    "focus_lane",
]

