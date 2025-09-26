import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.models.provision import Provision
from src.ontology.tagger import tag_text, tag_provision


def test_tag_text_creates_provision():
    prov = tag_text("Fair business practices support environmental protection.")
    assert "fairness" in prov.principles
    principle_atoms = [a for a in prov.atoms if a.role == "principle"]
    assert any(a.text == "fairness" for a in principle_atoms)
    assert "business_practice" in prov.customs


def test_tag_provision_updates_in_place():
    prov = Provision(text="Fair business practices support environmental protection.")
    tags = tag_provision(prov)
    assert "fairness" in prov.principles
    assert "business_practice" in prov.customs
    principle_atoms = [a for a in prov.atoms if a.role == "principle"]
    assert any(a.text == "fairness" for a in principle_atoms)
    assert "environment" in tags and "conservation" in tags["environment"]
