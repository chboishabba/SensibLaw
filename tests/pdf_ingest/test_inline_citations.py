from src.pdf_ingest import _rules_to_atoms
from src.rules.extractor import extract_rules


def test_rules_to_atoms_extracts_inline_citations():
    text = "The judge must refer to some of the facts (R. v. Sidlow (1))."
    rules = extract_rules(text)
    assert len(rules) == 1

    rule_atoms = _rules_to_atoms(rules)
    assert len(rule_atoms) == 1

    rule_atom = rule_atoms[0]
    assert rule_atom.text == "The judge must refer to some of the facts"
    assert rule_atom.references
    assert rule_atom.references[0].citation_text == "R. v. Sidlow (1)"

    subject_atom = rule_atom.get_subject_atom()
    assert subject_atom.text == "The judge must refer to some of the facts"
    assert subject_atom.refs == ["R. v. Sidlow (1)"]
