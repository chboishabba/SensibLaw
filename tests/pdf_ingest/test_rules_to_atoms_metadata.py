from src.glossary.service import GlossEntry
from src.pdf_ingest import _rules_to_atoms
from src.rules import Rule


def test_rules_to_atoms_includes_party_who_text_and_gloss(monkeypatch):
    metadata = {"source": "curated", "category": "example"}

    def fake_lookup(term: str):
        if term == "if requested":
            return GlossEntry(
                phrase=term,
                text="Request condition",
                metadata=metadata,
            )
        return None

    monkeypatch.setattr("src.pdf_ingest.lookup_gloss", fake_lookup)

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
    assert rule_atom.party == "court"
    assert rule_atom.who == "court"
    assert rule_atom.who_text == "the court"
    assert rule_atom.conditions == "if requested"
    assert rule_atom.gloss == "the court"
    assert rule_atom.text == "The court must consider the evidence if requested"

    element_atom = next(atom for atom in atoms if atom.type == "element")
    assert element_atom.role == "circumstance"
    assert element_atom.text == "if requested"
    assert element_atom.party == "court"
    assert element_atom.who == "court"
    assert element_atom.who_text == "the court"
    assert element_atom.conditions == "if requested"
    assert element_atom.gloss == "Request condition"
    assert element_atom.gloss_metadata == metadata
    assert element_atom.gloss_metadata is not metadata


def test_element_atoms_fall_back_to_who_text_when_no_gloss(monkeypatch):
    monkeypatch.setattr("src.pdf_ingest.lookup_gloss", lambda term: None)

    rule = Rule(
        actor="The court",
        modality="must",
        action="consider the evidence",
        elements={"circumstance": ["if requested"]},
        party="court",
        who_text="the court",
    )

    atoms = _rules_to_atoms([rule])

    element_atom = next(atom for atom in atoms if atom.type == "element")
    assert element_atom.gloss == "the court"
    assert element_atom.gloss_metadata is None
