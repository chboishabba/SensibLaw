from src.models.provision import Atom, Provision


def test_provision_atom_round_trip_preserves_party_and_who_text():
    atom = Atom(
        type="rule",
        role="obligation",
        party="respondent",
        who="defence",
        who_text="The respondent",
        conditions="if ordered",
        text="must pay damages",
        refs=["s 10"],
        gloss="Obligation to compensate",
    )
    provision = Provision(text="Damages provision", atoms=[atom])

    data = provision.to_dict()
    assert data["atoms"][0]["party"] == "respondent"
    assert data["atoms"][0]["who"] == "defence"
    assert data["atoms"][0]["who_text"] == "The respondent"
    assert data["atoms"][0]["conditions"] == "if ordered"
    assert data["rule_atoms"], "structured rule atoms should be serialised"

    round_tripped = Provision.from_dict(data)
    assert round_tripped.atoms == [atom]
    assert round_tripped.atoms[0].refs == ["s 10"]
    assert round_tripped.rule_atoms, "structured rule atoms should be reconstructed"
