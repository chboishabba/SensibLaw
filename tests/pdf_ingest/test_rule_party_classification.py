import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdf_ingest import _rules_to_atoms
from src.rules import UNKNOWN_PARTY
from src.rules.extractor import extract_rules


def _rules_and_atoms(text: str):
    rules = extract_rules(text)
    rule_atoms = _rules_to_atoms(rules)
    legacy_atoms = [atom for rule in rule_atoms for atom in rule.to_atoms()]
    return rules, rule_atoms, legacy_atoms


def _first_atom_of_type(atoms, atom_type):
    return next(atom for atom in atoms if atom.type == atom_type)


def test_offence_clause_classified_as_defence():
    text = "A person is guilty of theft if they dishonestly appropriate property."
    rules, rule_atoms, atoms = _rules_and_atoms(text)

    assert rules
    rule = rules[0]
    assert rule.party == "defence"
    assert rule.role == "accused"
    assert rule.who_text == "the accused"

    assert rule_atoms[0].party == "defence"
    assert rule_atoms[0].subject_gloss == "the accused"

    principle = _first_atom_of_type(atoms, "rule")
    assert principle.who == "defence"
    assert principle.gloss == "the accused"


def test_sentencing_clause_classified_as_court():
    text = "The court must consider the victim impact statement before sentencing."
    rules, rule_atoms, atoms = _rules_and_atoms(text)

    assert rules
    rule = rules[0]
    assert rule.party == "court"
    assert rule.role == "decision_maker"
    assert rule.who_text == "the court"

    assert rule_atoms[0].party == "court"
    assert rule_atoms[0].subject_gloss == "the court"

    principle = _first_atom_of_type(atoms, "rule")
    assert principle.who == "court"
    assert principle.gloss == "the court"


def test_unknown_actor_triggers_lint_atom():
    text = "The spaceship must register with the ministry."
    rules, rule_atoms, atoms = _rules_and_atoms(text)

    assert rules
    rule = rules[0]
    assert rule.party == UNKNOWN_PARTY

    assert rule_atoms[0].party == UNKNOWN_PARTY

    principle = _first_atom_of_type(atoms, "rule")
    assert principle.who == UNKNOWN_PARTY
    assert principle.gloss == "The spaceship"

    lint_atoms = [atom for atom in atoms if atom.type == "lint"]
    assert lint_atoms, "lint atom should be emitted for unknown actors"
    assert any(atom.role == "unknown_party" for atom in lint_atoms)
    assert any("spaceship" in (atom.text or "").lower() for atom in lint_atoms)
    assert all(atom.who == UNKNOWN_PARTY for atom in lint_atoms)
