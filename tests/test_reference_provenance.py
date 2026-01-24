from src.models.provision import RuleReference


def test_provenance_present():
    ref = RuleReference(work="Crimes Act 1914", section="s 5B", provenance={"clause_id": "1"})
    assert ref.provenance is not None


def test_provenance_droppable():
    ref = RuleReference(work="Crimes Act 1914", section="s 5B", provenance={"page_numbers": {1}})
    stripped = ref.to_dict()
    stripped["provenance"] = None
    assert stripped["provenance"] is None
