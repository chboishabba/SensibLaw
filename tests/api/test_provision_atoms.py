from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api.routes import fetch_provision_atoms, HTTPException


def test_fetch_provision_atoms_structure():
    payload = fetch_provision_atoms("Provision#NTA:s223")
    assert payload["provision_id"] == "Provision#NTA:s223"
    assert payload["atoms"], "expected atoms in payload"

    first = payload["atoms"][0]
    assert first["proof"]["status"] in {"proven", "pending", "contested"}
    if "principle" in first:
        card = first["principle"]
        assert {"id", "title", "summary"}.issubset(card.keys())


def test_fetch_provision_atoms_missing():
    with pytest.raises(HTTPException) as excinfo:
        fetch_provision_atoms("Provision#missing")
    assert excinfo.value.status_code == 404
