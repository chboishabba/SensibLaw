"""Declarative factor checklists for legal concept tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from pathlib import Path
from typing import Dict, List
import json


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

PERMANENT_STAY_TEST = TestTemplate(
    concept_id="permanent_stay",
    name="Permanent Stay Test",
    factors=[
        Factor("delay", "Extent and impact of any prosecutorial delay"),
        Factor(
            "abuse_of_process",
            "Whether continuation would be an abuse of process",
        ),
        Factor(
            "fair_trial_possible",
            "Possibility of a fair trial despite the delay",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Family Law Act templates
# ---------------------------------------------------------------------------

DE_FACTO_RELATIONSHIP_TEST = TestTemplate(
    concept_id="au:cth:family:s4AA",
    name="De Facto Relationship Factors",
    factors=[
        Factor(
            "duration",
            "Duration of the relationship",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(a)",
        ),
        Factor(
            "common_residence",
            "Nature and extent of common residence",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(b)",
        ),
        Factor(
            "sexual_relationship",
            "Whether a sexual relationship exists",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(c)",
        ),
        Factor(
            "financial_dependence",
            "Degree of financial dependence or interdependence",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(d)",
        ),
        Factor(
            "property_arrangements",
            "Ownership, use and acquisition of property",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(e)",
        ),
        Factor(
            "mutual_commitment",
            "Degree of mutual commitment to a shared life",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(f)",
        ),
        Factor(
            "registration",
            "Whether the relationship is registered under law",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(g)",
        ),
        Factor(
            "children",
            "Care and support of children",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(h)",
        ),
        Factor(
            "reputation",
            "Reputation and public aspects of the relationship",
            "https://www.legislation.gov.au/Series/C2004A01565#s4AA(2)(i)",
        ),
    ],
)

DE_FACTO_PROPERTY_ORDER_ELIGIBILITY_TEST = TestTemplate(
    concept_id="au:cth:family:s90SB",
    name="De Facto Property Order Eligibility",
    factors=[
        Factor(
            "duration_two_years",
            "Relationship lasted at least two years",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SB(a)",
        ),
        Factor(
            "child",
            "There is a child of the relationship",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SB(b)",
        ),
        Factor(
            "substantial_contributions",
            "Applicant made substantial contributions and serious injustice without order",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SB(c)",
        ),
        Factor(
            "registered",
            "Relationship registered under prescribed law",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SB(d)",
        ),
    ],
)

DE_FACTO_PROPERTY_DIVISION_TEST = TestTemplate(
    concept_id="au:cth:family:s90SM",
    name="De Facto Property Division Factors",
    factors=[
        Factor(
            "financial_contributions",
            "Financial contributions to property or resources",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SM(4)(a)",
        ),
        Factor(
            "non_financial_contributions",
            "Non-financial contributions to property or resources",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SM(4)(b)",
        ),
        Factor(
            "welfare_contributions",
            "Contributions to welfare of family as homemaker or parent",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SM(4)(c)",
        ),
        Factor(
            "future_needs",
            "Effect of proposed order on earning capacity and future needs",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SM(4)(d)",
        ),
        Factor(
            "justice_equity",
            "Whether the proposed order is just and equitable",
            "https://www.legislation.gov.au/Series/C2004A01565#s90SM(3)",
        ),
    ],
)

# Registry mapping concept IDs to templates for lookup during evaluation
TEMPLATE_REGISTRY: Dict[str, TestTemplate] = {
    PERMANENT_STAY_TEST.concept_id: PERMANENT_STAY_TEST,
    DE_FACTO_RELATIONSHIP_TEST.concept_id: DE_FACTO_RELATIONSHIP_TEST,
    DE_FACTO_PROPERTY_ORDER_ELIGIBILITY_TEST.concept_id:
    DE_FACTO_PROPERTY_ORDER_ELIGIBILITY_TEST,
    DE_FACTO_PROPERTY_DIVISION_TEST.concept_id: DE_FACTO_PROPERTY_DIVISION_TEST,

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

    GLJ_PERMANENT_STAY_TEST.concept_id: GLJ_PERMANENT_STAY_TEST,
    S4AA_TEMPLATE.concept_id: S4AA_TEMPLATE,
    S90SB_TEMPLATE.concept_id: S90SB_TEMPLATE,
    S90SM_TEMPLATE.concept_id: S90SM_TEMPLATE,
}
