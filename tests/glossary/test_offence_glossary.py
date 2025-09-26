from __future__ import annotations

from src.pdf_ingest import _rules_to_atoms
from src.rules.extractor import extract_rules


def _build_rule_atoms(text: str):
    rules = extract_rules(text)
    assert rules, "expected at least one rule from sample text"
    return _rules_to_atoms(rules)


def test_offence_elements_receive_curated_gloss():
    text = (
        "A person commits the offence of aggravated assault if the person, with intent "
        "to cause death, causes an injury resulting in grievous bodily harm."
    )
    rule_atoms = _build_rule_atoms(text)
    elements = {
        element.text: element for rule in rule_atoms for element in rule.elements
    }

    fault_element = elements["with intent to cause death"]
    assert (
        fault_element.gloss
        == "R v Smith [2001] HCA 12 confirmed that murder requires an intention to kill."
    )
    assert fault_element.gloss_metadata == {
        "case": "R v Smith",
        "citation": "[2001] HCA 12",
    }
    assert fault_element.glossary_id is not None

    result_element = elements["resulting in grievous bodily harm"]
    assert (
        result_element.gloss
        == "Brown v R [1995] HCA 34 treated grievous bodily harm as a qualifying result for serious offences."
    )
    assert result_element.gloss_metadata == {
        "case": "Brown v R",
        "citation": "[1995] HCA 34",
    }
    assert result_element.glossary_id is not None
    assert result_element.glossary_id != fault_element.glossary_id


def test_offence_element_without_gloss_remains_unannotated():
    text = (
        "A person commits the offence of aggravated assault if the person causes an injury "
        "without lawful excuse."
    )
    rule_atoms = _build_rule_atoms(text)
    for rule_atom in rule_atoms:
        for element in rule_atom.elements:
            assert element.text != "with intent to cause death"
            assert element.gloss_metadata is None
            assert element.glossary_id is None
            if element.gloss is not None:
                assert element.gloss == rule_atom.subject_gloss
