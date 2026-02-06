from src.glossary.service import GlossEntry
from src.pdf_ingest import _rules_to_atoms
from src.rules import Rule, UNKNOWN_PARTY


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

    rule_atoms = _rules_to_atoms([rule])

    assert rule_atoms, "expected structured rule atoms"
    structured = rule_atoms[0]
    assert structured.party == "court"
    assert structured.who == "court"
    assert structured.who_text == "the court"
    assert structured.conditions == "if requested"
    assert structured.subject_gloss == "the court"
    assert structured.subject is not None
    assert structured.subject.glossary is structured.subject_link
    assert structured.text == "The court must consider the evidence if requested"

    assert structured.elements, "expected rule elements"
    element = structured.elements[0]
    assert element.role == "circumstance"
    assert element.text == "if requested"
    assert element.conditions == "if requested"
    assert element.gloss == "Request condition"
    assert element.gloss_metadata == metadata
    assert element.gloss_metadata is not metadata
    assert element.glossary_id is not None

    flattened = structured.to_atoms()
    legacy_rule = flattened[0]
    assert legacy_rule.type == "rule"
    assert legacy_rule.party == "court"
    assert legacy_rule.text == structured.text
    legacy_element = next(atom for atom in flattened if atom.type == "element")
    assert legacy_element.role == "circumstance"
    assert legacy_element.text == "if requested"
    assert legacy_element.gloss == "Request condition"
    assert legacy_element.glossary_id == element.glossary_id


def test_rules_to_atoms_attaches_text_span_with_revision_id(monkeypatch):
    monkeypatch.setattr("src.pdf_ingest.lookup_gloss", lambda term: None)

    rule = Rule(
        actor="A person",
        modality="must",
        action="pay damages",
        party="person",
        who_text="A person",
        elements={"object": ["damages"]},
    )
    body = "A person must pay damages."

    rule_atoms = _rules_to_atoms(
        [rule],
        document_body=body,
        span_source="doc-1",
    )

    structured = rule_atoms[0]
    assert structured.text_span is not None
    assert structured.text_span.revision_id == "doc-1"
    assert (
        body[structured.text_span.start_char : structured.text_span.end_char]
        == structured.text
    )

    element = structured.elements[0]
    assert element.text_span is not None
    assert (
        body[element.text_span.start_char : element.text_span.end_char]
        == element.text
    )


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

    rule_atoms = _rules_to_atoms([rule])

    structured = rule_atoms[0]
    assert structured.elements, "expected rule elements"
    element = structured.elements[0]
    assert element.gloss == "the court"
    assert element.gloss_metadata is None
    assert element.glossary_id is None
    assert structured.subject_link is element.glossary

    legacy_element = structured.to_atoms()[1]
    assert legacy_element.gloss == "the court"
    assert legacy_element.glossary_id is None


def test_unknown_party_lint_atom_inherits_party_metadata(monkeypatch):
    monkeypatch.setattr("src.pdf_ingest.lookup_gloss", lambda term: None)

    rule = Rule(
        actor="The spaceship",
        modality="must",
        action="register with the ministry",
        party=UNKNOWN_PARTY,
        who_text="The spaceship",
    )

    rule_atoms = _rules_to_atoms([rule])

    structured = rule_atoms[0]
    assert structured.lints, "expected lint records for unknown party"
    lint = structured.lints[0]
    assert lint.code == "unknown_party"

    flattened = structured.to_atoms()
    lint_atom = next(atom for atom in flattened if atom.type == "lint")
    assert lint_atom.party == UNKNOWN_PARTY
    assert lint_atom.who == UNKNOWN_PARTY
    assert lint_atom.who_text == "The spaceship"
    assert lint_atom.gloss == "The spaceship"
