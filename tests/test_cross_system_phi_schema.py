import json
from pathlib import Path

import jsonschema
import pytest
import yaml


def _load_schema():
    return yaml.safe_load(Path("schemas/sl.cross_system_phi.contract.v1.schema.yaml").read_text())


def _load_payload():
    return json.loads(Path("examples/cross_system_phi_minimal.json").read_text())


def test_cross_system_phi_example_validates():
    jsonschema.validate(_load_payload(), _load_schema())


@pytest.mark.parametrize("bad_status", ["equivalent", "maybe", ""])
def test_cross_system_phi_rejects_unknown_status_values(bad_status: str):
    payload = _load_payload()
    payload["mappings"][0]["status"] = bad_status
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, _load_schema())


def test_cross_system_phi_requires_null_target_for_undefined_status():
    payload = _load_payload()
    payload["mappings"][1]["target_ref"] = "motif://civil_law_fr/not_checked"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, _load_schema())
