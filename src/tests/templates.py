"""Declarative factor checklists for legal concept tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Factor:
    """A single factor considered in a legal test."""

    id: str
    description: str
    link: Optional[str] = None


@dataclass(frozen=True)
class TestTemplate:
    """Template describing the factors for evaluating a concept."""

    concept_id: str
    name: str
    threshold: int
    factors: List[Factor]


def _load_template(path: Path) -> TestTemplate:
    """Load a :class:`TestTemplate` from a JSON file."""

    data = json.loads(path.read_text())
    return TestTemplate(
        concept_id=data["concept_id"],
        name=data["name"],
        threshold=data["threshold"],
        factors=[Factor(**f) for f in data.get("factors", [])],
    )


# Directory containing template JSON files
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "tests" / "templates"

# Load template definitions from JSON files
GLJ_PERMANENT_STAY_TEST = _load_template(TEMPLATES_DIR / "glj_permanent_stay.json")
S4AA_TEMPLATE = _load_template(TEMPLATES_DIR / "au_cth_family_s4AA.json")
S90SB_TEMPLATE = _load_template(TEMPLATES_DIR / "au_cth_family_s90SB.json")
S90SM_TEMPLATE = _load_template(TEMPLATES_DIR / "au_cth_family_s90SM.json")

# Backwards compatibility alias
PERMANENT_STAY_TEST = GLJ_PERMANENT_STAY_TEST


# Registry mapping concept IDs to templates for lookup during evaluation
TEMPLATE_REGISTRY: Dict[str, TestTemplate] = {
    PERMANENT_STAY_TEST.concept_id: PERMANENT_STAY_TEST,
    S4AA_TEMPLATE.concept_id: S4AA_TEMPLATE,
    S90SB_TEMPLATE.concept_id: S90SB_TEMPLATE,
    S90SM_TEMPLATE.concept_id: S90SM_TEMPLATE,
}


__all__ = [
    "Factor",
    "TestTemplate",
    "TEMPLATE_REGISTRY",
    "PERMANENT_STAY_TEST",
    "GLJ_PERMANENT_STAY_TEST",
    "S4AA_TEMPLATE",
    "S90SB_TEMPLATE",
    "S90SM_TEMPLATE",
]

