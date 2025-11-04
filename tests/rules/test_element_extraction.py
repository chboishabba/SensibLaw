from pathlib import Path

import pytest

from src.pdf_ingest import build_document
from src.rules.extractor import extract_rules


@pytest.fixture
def murder_clause() -> str:
    return (
        "A person commits murder if the person intentionally causes serious injury to "
        "another resulting in the death of that person with intent to kill."
    )


@pytest.fixture
def graffiti_clause() -> str:
    return (
        "A person commits the offence of graffiti if the person intentionally marks "
        "property without the consent of the owner unless the marking is authorised."
    )


def test_murder_elements_are_classified(murder_clause: str) -> None:
    rules = extract_rules(murder_clause)
    assert len(rules) == 1

    elements = rules[0].elements
    assert "conduct" in elements
    assert any(
        frag.startswith("the person causes serious injury") for frag in elements["conduct"]
    )
    assert "fault" in elements
    assert any(frag.lower() == "intentionally" for frag in elements["fault"])
    assert any("intent to kill" in frag.lower() for frag in elements["fault"])
    assert "result" in elements
    assert any("resulting in the death" in frag.lower() for frag in elements["result"])
    assert any("if the person" in frag.lower() for frag in elements.get("circumstance", []))


def test_graffiti_elements_are_classified(graffiti_clause: str) -> None:
    rules = extract_rules(graffiti_clause)
    assert len(rules) == 1

    elements = rules[0].elements
    assert any(frag.startswith("the person marks property") for frag in elements["conduct"])
    assert any(frag.lower() == "intentionally" for frag in elements["fault"])
    assert any(
        "without the consent of the owner" in frag.lower()
        for frag in elements.get("circumstance", [])
    )
    assert any(
        "unless the marking is authorised" in frag.lower()
        for frag in elements.get("exception", [])
    )


def test_leading_condition_extracted_and_classified() -> None:
    text = (
        "If the court is satisfied that the applicant meets the criteria, "
        "it may grant the application."
    )

    rules = extract_rules(text)
    assert len(rules) == 1

    rule = rules[0]
    assert rule.conditions == "If the court is satisfied that the applicant meets the criteria"
    assert not rule.actor.lower().startswith("if")
    assert any(
        "if the court is satisfied that the applicant meets the criteria" in frag.lower()
        for frag in rule.elements.get("circumstance", [])
    )


def test_leading_condition_keeps_first_clause_actor() -> None:
    text = (
        "If the court is satisfied, the applicant must apply and the registrar must notify the parties."
    )

    rules = extract_rules(text)
    assert rules, "expected rules from conditional sentence"

    rule = rules[0]
    assert rule.actor.lower().startswith("the applicant")
    assert rule.conditions == "If the court is satisfied"


def test_document_atoms_include_element_roles(
    murder_clause: str, graffiti_clause: str
) -> None:
    pages = [
        {
            "page": 1,
            "heading": "Sample Offences",
            "text": f"{murder_clause} {graffiti_clause}",
        }
    ]

    document = build_document(pages, Path("dummy.pdf"))
    assert document.provisions
    provision = document.provisions[0]

    element_atoms = [atom for atom in provision.atoms if atom.type == "element"]
    assert element_atoms, "expected element atoms from rule extraction"

    def _atoms_for(role: str) -> list[str]:
        return [atom.text for atom in element_atoms if atom.role == role]

    assert any("serious injury" in (text or "").lower() for text in _atoms_for("conduct"))
    assert any("intentionally" == (text or "").lower() for text in _atoms_for("fault"))
    assert any("resulting in the death" in (text or "").lower() for text in _atoms_for("result"))
    assert any("without the consent" in (text or "").lower() for text in _atoms_for("circumstance"))
    assert any("unless the marking" in (text or "").lower() for text in _atoms_for("exception"))
