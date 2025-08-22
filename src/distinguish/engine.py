from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, List, Tuple, Set, TypedDict, Any

from dataclasses import dataclass, field
import re
from typing import Dict, Sequence, List, Tuple, Set

from .factors import GLJ_PERMANENT_STAY_CUES


@dataclass
class CaseSilhouette:
    """Concise representation of a case for comparison.

    Attributes:
        fact_tags: Mapping of fact descriptors to paragraph index.
        holding_hints: Mapping of holding descriptors to paragraph index.
        paragraphs: Original paragraph texts.
    """

    fact_tags: Dict[str, int]
    holding_hints: Dict[str, int]
    paragraphs: Sequence[str]
    anchors: Dict[int, str] = field(default_factory=dict)


def extract_case_silhouette(paragraphs: Sequence[str]) -> CaseSilhouette:
    """Extract a minimal silhouette from judgment paragraphs.

    The first three paragraphs are treated as fact tags. Any paragraph starting
    with "Held" (case-insensitive) is treated as a holding hint.
    """

    facts: Dict[str, int] = {}
    holdings: Dict[str, int] = {}
    anchors: Dict[int, str] = {}

    bracket_re = re.compile(r"\[(\d+)\]")
    pilcrow_re = re.compile(r"¶(\d+)")
    heading_re = re.compile(r"^\s*(\d+)[\.\)]?\s+")

    for idx, para in enumerate(paragraphs):
        text = para.strip()
        if not text:
            continue
        # anchor detection
        anchor_match = bracket_re.search(text)
        if anchor_match:
            anchors[idx] = anchor_match.group(0)
        else:
            anchor_match = pilcrow_re.search(text)
            if anchor_match:
                anchors[idx] = anchor_match.group(0)
            else:
                heading_match = heading_re.match(text)
                if heading_match:
                    anchors[idx] = heading_match.group(1)
        if idx < 3:
            facts[text] = idx
        if text.lower().startswith("held"):
            holdings[text] = idx
    return CaseSilhouette(facts, holdings, list(paragraphs), anchors)


def extract_holding_and_facts(paragraphs: Sequence[str]) -> Tuple[Set[str], Set[str]]:
    """Return sets of holding hints and fact tags from *paragraphs*.

    This is a lightweight helper primarily intended for tests and simple
    experiments.  It mirrors :func:`extract_case_silhouette` but returns two
    sets rather than a dataclass so that callers can easily reason about the
    extracted strings.
    """

    silhouette = extract_case_silhouette(paragraphs)
    holdings = set(silhouette.holding_hints.keys())
    facts = set(silhouette.fact_tags.keys())
    return holdings, facts


class ComparisonResult(TypedDict):
    """Mapping describing similarities and differences between cases."""

    overlaps: List[Dict[str, Any]]
    missing: List[Dict[str, Any]]
    overlap_tokens: List[str]
    a_only_tokens: List[str]
    b_only_tokens: List[str]


def compare_cases(base: CaseSilhouette, candidate: CaseSilhouette) -> ComparisonResult:
    """Compare two case silhouettes.

    Returns a dictionary with overlaps and missing conditions. Overlaps include
    supporting citations to paragraph indices and texts from both cases.
    """

    overlaps: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for fact, base_idx in base.fact_tags.items():
        if fact in candidate.fact_tags:
            cand_idx = candidate.fact_tags[fact]
            overlaps.append(
                {
                    "type": "fact",
                    "text": fact,
                    "base": {
                        "index": base_idx,
                        "paragraph": base.paragraphs[base_idx],
                        "anchor": base.anchors.get(base_idx),
                    },
                    "candidate": {
                        "index": cand_idx,
                        "paragraph": candidate.paragraphs[cand_idx],
                        "anchor": candidate.anchors.get(cand_idx),
                    },
                }
            )
        else:
            missing.append(
                {
                    "type": "fact",
                    "text": fact,
                    "base": {
                        "index": base_idx,
                        "paragraph": base.paragraphs[base_idx],
                        "anchor": base.anchors.get(base_idx),
                    },
                }
            )

    for holding, base_idx in base.holding_hints.items():
        if holding in candidate.holding_hints:
            cand_idx = candidate.holding_hints[holding]
            overlaps.append(
                {
                    "type": "holding",
                    "text": holding,
                    "base": {
                        "index": base_idx,
                        "paragraph": base.paragraphs[base_idx],
                        "anchor": base.anchors.get(base_idx),
                    },
                    "candidate": {
                        "index": cand_idx,
                        "paragraph": candidate.paragraphs[cand_idx],
                        "anchor": candidate.anchors.get(cand_idx),
                    },
                }
            )
        else:
            missing.append(
                {
                    "type": "holding",
                    "text": holding,
                    "base": {
                        "index": base_idx,
                        "paragraph": base.paragraphs[base_idx],
                        "anchor": base.anchors.get(base_idx),
                    },
                }
            )

    base_facts = set(base.fact_tags.keys())
    cand_facts = set(candidate.fact_tags.keys())
    return {
        "overlaps": overlaps,
        "missing": missing,
        "overlap_tokens": sorted(base_facts & cand_facts),
        "a_only_tokens": sorted(base_facts - cand_facts),
        "b_only_tokens": sorted(cand_facts - base_facts),
    }


def compare_story_to_case(
    story_tags: Dict[str, bool], case: CaseSilhouette
) -> Dict[str, List[dict]]:
    """Compare fact tags from a story to a case silhouette.

    ``story_tags`` is a mapping of factor identifiers to booleans indicating
    whether the fact is present in the story.  ``case`` provides the paragraphs
    from the base case which are scanned for cues defined in
    :mod:`src.distinguish.factors`.

    The result mirrors :func:`compare_cases` but only includes overlaps and
    missing factors referencing case paragraph indices.
    """

    overlaps: List[dict] = []
    missing: List[dict] = []

    for tag, present in story_tags.items():
        if not present:
            continue

        pattern = GLJ_PERMANENT_STAY_CUES.get(tag)
        match_idx = None
        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            for idx, para in enumerate(case.paragraphs):
                if regex.search(para):
                    match_idx = idx
                    break

        if match_idx is not None:
            overlaps.append(
                {
                    "id": tag,
                    "base": {"anchor": None},
                    "candidate": {
                        "index": match_idx,
                        "paragraph": case.paragraphs[match_idx],
                        "anchor": case.anchors.get(match_idx),
                    },
                }
            )
        else:
            missing.append(
                {
                    "id": tag,
                    "base": {"anchor": None},
                    "candidate": {"anchor": None},
                }
            )

    return {"overlaps": overlaps, "missing": missing}
