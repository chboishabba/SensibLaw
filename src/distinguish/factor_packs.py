from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

# Hard-coded factor packs for demonstration purposes. In a real system these
# would be derived from a case database. Only the data required for tests is
# included here.
_GLJ_PACKS: Dict[str, List[int]] = {
    "delay": [1],
    "lost evidence": [2],
}


def factor_pack_for_case(case_id: str) -> Dict[str, List[int]]:
    """Return factor cue to paragraph mapping for *case_id*.

    Currently only ``"[2002] HCA 14"`` is supported which corresponds to the
    fictionalised GLJ decision used in tests.  Unknown case identifiers raise a
    :class:`ValueError` to surface mistakes early.
    """

    if case_id == "[2002] HCA 14":
        return _GLJ_PACKS
    raise ValueError(f"Unknown case: {case_id}")


def distinguish_story(case_id: str, story_path: Path) -> Dict[str, List[Dict[str, object]]]:
    """Compare a story's facts against the factor packs for *case_id*.

    The story file is expected to contain a JSON object with a ``facts`` mapping
    of cue identifiers (using underscores) to booleans.  The returned dictionary
    contains ``overlap`` and ``diffs`` lists detailing which cues match and the
    associated paragraph numbers from the base case.
    """

    facts_data = json.loads(story_path.read_text())
    story_facts: Dict[str, bool] = facts_data.get("facts", {})
    packs = factor_pack_for_case(case_id)

    overlap: List[Dict[str, object]] = []
    diffs: List[Dict[str, object]] = []

    # Determine overlaps and diffs based on the story facts
    for cue, paras in packs.items():
        key = cue.replace(" ", "_")
        if story_facts.get(key):
            overlap.append({"cue": cue, "paragraphs": paras})
        else:
            diffs.append({"cue": cue, "paragraphs": paras})

    # Any additional true facts in the story not present in the base packs are
    # treated as differences without paragraph references.
    for key, present in story_facts.items():
        cue = key.replace("_", " ")
        if cue not in packs and present:
            diffs.append({"cue": cue, "paragraphs": []})

    return {"overlap": overlap, "diffs": diffs}
