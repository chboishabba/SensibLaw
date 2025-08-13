"""Declarative factor checklists for legal concept tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Factor:
    """A single factor considered in a legal test."""

    id: str
    description: str


@dataclass(frozen=True)
class TestTemplate:
    """Template describing the factors for evaluating a concept."""

    concept_id: str
    name: str
    factors: List[Factor]


# ---------------------------------------------------------------------------
# Example templates
# ---------------------------------------------------------------------------

PERMANENT_STAY_TEST = TestTemplate(
    concept_id="permanent_stay",
    name="Permanent Stay Test",
    factors=[
        Factor("delay", "Extent and impact of any prosecutorial delay"),
        Factor("abuse_of_process", "Whether continuation would be an abuse of process"),
        Factor("fair_trial_possible", "Possibility of a fair trial despite the delay"),
    ],
)

S4AA_TEST = TestTemplate(
    concept_id="s4AA",
    name="Section 4AA Test",
    factors=[
        Factor("f1", "Example factor one"),
        Factor("f2", "Example factor two"),
    ],
)

# Registry mapping concept IDs to templates for lookup during evaluation
TEMPLATE_REGISTRY: Dict[str, TestTemplate] = {
    PERMANENT_STAY_TEST.concept_id: PERMANENT_STAY_TEST,
    S4AA_TEST.concept_id: S4AA_TEST,
}

