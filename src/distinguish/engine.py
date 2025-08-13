from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, List


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


def extract_case_silhouette(paragraphs: Sequence[str]) -> CaseSilhouette:
    """Extract a minimal silhouette from judgment paragraphs.

    The first three paragraphs are treated as fact tags. Any paragraph starting
    with "Held" (case-insensitive) is treated as a holding hint.
    """

    facts: Dict[str, int] = {}
    holdings: Dict[str, int] = {}
    for idx, para in enumerate(paragraphs):
        text = para.strip()
        if not text:
            continue
        if idx < 3:
            facts[text] = idx
        if text.lower().startswith("held"):
            holdings[text] = idx
    return CaseSilhouette(facts, holdings, list(paragraphs))


def compare_cases(base: CaseSilhouette, candidate: CaseSilhouette) -> Dict[str, List[dict]]:
    """Compare two case silhouettes.

    Returns a dictionary with overlaps and missing conditions. Overlaps include
    supporting citations to paragraph indices and texts from both cases.
    """

    overlaps: List[dict] = []
    missing: List[dict] = []

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
                    },
                    "candidate": {
                        "index": cand_idx,
                        "paragraph": candidate.paragraphs[cand_idx],
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
                    },
                    "candidate": {
                        "index": cand_idx,
                        "paragraph": candidate.paragraphs[cand_idx],
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
                    },
                }
            )

    return {"overlaps": overlaps, "missing": missing}
