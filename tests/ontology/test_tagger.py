from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


@dataclass
class Atom:
    type: str | None = None
    role: str | None = None
    text: str | None = None


@dataclass
class Provision:
    text: str
    principles: list[str] = field(default_factory=list)
    customs: list[str] = field(default_factory=list)
    atoms: list[Atom] = field(default_factory=list)


models_module = types.ModuleType("models")
provision_module = types.ModuleType("models.provision")
provision_module.Atom = Atom
provision_module.Provision = Provision
models_module.provision = provision_module
sys.modules.setdefault("models", models_module)
sys.modules.setdefault("models.provision", provision_module)

from src.ontology import tagger


def test_tag_text_creates_provision():
    prov = tagger.tag_text("Fair business practices support environmental protection.")
    assert "fairness" in prov.principles
    principle_atoms = [a for a in prov.atoms if a.role == "principle"]
    assert any(a.text == "fairness" for a in principle_atoms)
    assert "business_practice" in prov.customs


def test_tag_provision_updates_in_place():
    prov = Provision(text="Fair business practices support environmental protection.")
    tags = tagger.tag_provision(prov)
    assert "fairness" in prov.principles
    assert "business_practice" in prov.customs
    principle_atoms = [a for a in prov.atoms if a.role == "principle"]
    assert any(a.text == "fairness" for a in principle_atoms)
    assert "environment" in tags and "conservation" in tags["environment"]


def test_load_ontology_ignores_non_string_keyword_entries(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(
        json.dumps(
            {
                "broken": [{"label": "ignored"}],
                "working": ["fairness", "environment"],
            }
        )
    )

    loaded = tagger._load_ontology(path)

    assert loaded == {"working": ["fairness", "environment"]}


def test_tag_provision_skips_dict_keyword_payloads(monkeypatch):
    monkeypatch.setattr(
        tagger,
        "ONTOLOGIES",
        {
            "broken": {"items": [{"label": "ignored"}]},
            "lpo": {"fairness": ["fairness"]},
        },
    )

    prov = Provision(text="Fairness matters here.")

    tags = tagger.tag_provision(prov)

    assert tags == {"lpo": ["fairness"]}
    assert prov.principles == ["fairness"]


def test_tag_provision_ignores_non_string_text_payload(monkeypatch):
    monkeypatch.setattr(
        tagger,
        "ONTOLOGIES",
        {"lpo": {"fairness": ["fairness"]}},
    )

    prov = Provision(text={"raw": "fairness"})  # type: ignore[arg-type]

    tags = tagger.tag_provision(prov)

    assert tags == {}
    assert prov.principles == []
