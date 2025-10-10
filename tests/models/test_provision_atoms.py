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


def test_atom_from_dict_preserves_legacy_who_mapping():
    legacy_atom = {
        "type": "rule",
        "role": "obligation",
        "who": {"party": "applicant", "text": "The applicant"},
        "text": "must file documents",
        "refs": ["s 3"],
    }

    atom = Atom.from_dict(legacy_atom)

    assert atom.party == "applicant"
    assert atom.who_text == "The applicant"
    assert atom.text == "must file documents"
    assert atom.refs == ["s 3"]


def test_atom_from_dict_preserves_legacy_conditions_when_missing_who_text():
    legacy_atom = {
        "type": "rule",
        "role": "obligation",
        "conditions": ["during proceedings", "before hearing"],
        "text": "must notify the court",
    }

    atom = Atom.from_dict(legacy_atom)

    assert atom.party is None
    assert atom.who_text == "during proceedings before hearing"
    assert atom.text == "must notify the court"
