from __future__ import annotations

from src.pdf_ingest import _rules_to_atoms
from src.rules.extractor import extract_rules


def _build_atoms(text: str):
    rules = extract_rules(text)
    assert rules, "expected at least one rule from sample text"
    return _rules_to_atoms(rules)


def test_offence_elements_receive_curated_gloss():
    text = (
        "A person commits the offence of aggravated assault if the person, with intent "
        "to cause death, causes an injury resulting in grievous bodily harm."
    )
    atoms = _build_atoms(text)
    by_text = {atom.text: atom for atom in atoms if atom.type == "element"}

    fault_atom = by_text["with intent to cause death"]
    assert (
        fault_atom.gloss
        == "R v Smith [2001] HCA 12 confirmed that murder requires an intention to kill."
    )
    assert fault_atom.gloss_metadata == {"case": "R v Smith", "citation": "[2001] HCA 12"}

    result_atom = by_text["resulting in grievous bodily harm"]
    assert (
        result_atom.gloss
        == "Brown v R [1995] HCA 34 treated grievous bodily harm as a qualifying result for serious offences."
    )
    assert result_atom.gloss_metadata == {"case": "Brown v R", "citation": "[1995] HCA 34"}


def test_offence_element_without_gloss_remains_unannotated():
    text = (
        "A person commits the offence of aggravated assault if the person causes an injury "
        "without lawful excuse."
    )
    atoms = _build_atoms(text)
    for atom in atoms:
        if atom.type == "element":
            assert atom.text != "with intent to cause death"
            assert atom.gloss is None
            assert atom.gloss_metadata is None
