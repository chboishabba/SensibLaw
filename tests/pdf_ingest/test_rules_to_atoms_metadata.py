from src.pdf_ingest import _rules_to_atoms
from src.rules import Rule


def test_rules_to_atoms_includes_who_and_conditions_metadata():
    rule = Rule(
        actor="The court",
        modality="must",
        action="consider the evidence",
        conditions="if requested",
        elements={"circumstance": ["if requested"]},
        party="court",
        role="decision_maker",
        who_text="the court",
    )

    atoms = _rules_to_atoms([rule])

    rule_atom = next(atom for atom in atoms if atom.type == "rule")
    assert rule_atom.who == "court"
    assert rule_atom.party == "The court"
    assert rule_atom.conditions == "if requested"
    assert rule_atom.gloss == "the court"
    assert rule_atom.text == "The court must consider the evidence if requested"

    element_atom = next(atom for atom in atoms if atom.type == "element")
    assert element_atom.role == "circumstance"
    assert element_atom.text == "if requested"
    assert element_atom.who == "court"
    assert element_atom.conditions == "if requested"
    assert element_atom.gloss is None
    assert element_atom.gloss_metadata is None
