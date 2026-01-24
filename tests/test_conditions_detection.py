import pytest

from datetime import date
from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference
from src.obligations import extract_obligations_from_document

def _doc(body: str, refs: list[RuleReference], source_id: str = "doc") -> Document:
    metadata = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2023, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=metadata, body=body, provisions=[prov])


def test_if_condition_attached():
    body = "A person must report if an incident occurs."
    ref = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    doc = _doc(body, [ref])
    obligations = extract_obligations_from_document(doc)
    assert obligations
    conds = obligations[0].conditions
    assert conds
    assert any(c.type == "if" for c in conds)


def test_unless_condition_attached():
    body = "An officer must secure the site unless it is unsafe to do so."
    ref = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    doc = _doc(body, [ref])
    obligations = extract_obligations_from_document(doc)
    cond_types = {c.type for c in obligations[0].conditions}
    assert "unless" in cond_types


def test_except_does_not_create_new_obligation():
    body = "This Part does not apply except for emergencies."
    ref = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    doc = _doc(body, [ref])
    obligations = extract_obligations_from_document(doc)
    assert len(obligations) == 1
    cond_types = {c.type for c in obligations[0].conditions}
    assert "except" in cond_types


def test_clause_boundary_isolation_for_conditions():
    body = "A driver must stop if signalled. The passenger may leave."
    ref1 = RuleReference(work="Road Act 2010", provenance={"clause_id": "doc-clause-0"})
    ref2 = RuleReference(work="Road Act 2010", provenance={"clause_id": "doc-clause-1"})
    doc = _doc(body, [ref1, ref2])
    obligations = extract_obligations_from_document(doc)
    assert len(obligations) == 2
    first_conditions = {c.type for c in obligations[0].conditions}
    second_conditions = {c.type for c in obligations[1].conditions}
    assert "if" in first_conditions
    assert "if" not in second_conditions


def test_condition_attachment_ocr_stable():
    base = "A person must report if injured."
    noisy = "A person must report  if  injured."
    ref = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    doc_base = _doc(base, [ref], source_id="doc")
    doc_noisy = _doc(noisy, [ref], source_id="doc")
    conds_base = extract_obligations_from_document(doc_base)[0].conditions
    conds_noisy = extract_obligations_from_document(doc_noisy)[0].conditions
    assert {(c.type) for c in conds_base} == {(c.type) for c in conds_noisy}
