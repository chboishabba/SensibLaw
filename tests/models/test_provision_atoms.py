from src.models.provision import Atom, Provision


def test_provision_atom_round_trip_preserves_party_and_who_text():
    atom = Atom(
        type="rule",
        role="obligation",
        party="respondent",
        who_text="The respondent",
        text="must pay damages",
        refs=["s 10"],
        gloss="Obligation to compensate",
    )
    provision = Provision(text="Damages provision", atoms=[atom])

    data = provision.to_dict()
    assert data["atoms"][0]["party"] == "respondent"
    assert data["atoms"][0]["who_text"] == "The respondent"

    round_tripped = Provision.from_dict(data)
    assert round_tripped.atoms == [atom]
    assert round_tripped.atoms[0].refs == ["s 10"]
