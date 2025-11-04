from src.pdf_ingest import _rules_to_atoms, _strip_inline_citations
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
    assert rule_atom.references[0].work == "R. v. Sidlow (1)"

    subject_atom = rule_atom.get_subject_atom()
    assert subject_atom.text == "The judge must refer to some of the facts"
    assert subject_atom.refs == ["R. v. Sidlow (1)"]


def test_strip_inline_citations_extracts_metadata():
    text, references = _strip_inline_citations(
        "The duty applies (Mabo v Queensland (No 2) (1992) 175 CLR 1 at 15)."
    )

    assert text == "The duty applies"
    assert len(references) == 1
    reference = references[0]
    assert reference.work == "Mabo v Queensland (No 2)"
    assert reference.section == "(1992) 175 CLR 1"
    assert reference.pinpoint == "15"
    assert reference.citation_text == "Mabo v Queensland (No 2) (1992) 175 CLR 1 at 15"
