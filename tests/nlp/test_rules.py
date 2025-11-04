from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import pytest
import spacy

from src.nlp.rules import match_rules
from src.rules.extractor import extract_rules

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load_samples() -> Iterable[tuple[str, dict]]:
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        yield path.stem, json.loads(path.read_text())


SAMPLES = list(_load_samples())


def _normalise_rule(rule_dict: dict) -> dict:
    normalised = deepcopy(rule_dict)
    elements = normalised.get("elements", {})
    normalised["elements"] = {key: sorted(value) for key, value in sorted(elements.items())}
    return normalised


@pytest.mark.parametrize(("name", "data"), SAMPLES)
def test_rule_extraction_matches_golden(name: str, data: dict) -> None:
    expected_rules = [_normalise_rule(rule) for rule in data["rules"]]
    actual_rules = [_normalise_rule(asdict(rule)) for rule in extract_rules(data["text"])]

    assert actual_rules == expected_rules

    expected_modalities = {rule["modality"] for rule in expected_rules}
    actual_modalities = {rule["modality"] for rule in actual_rules}
    assert actual_modalities == expected_modalities


def test_match_rules_primary_modality_and_conditions() -> None:
    nlp = spacy.blank("en")
    doc = nlp("A person must not drive if intoxicated under s 5B.")
    summary = match_rules(doc)

    assert summary.primary_modality == "must not"
    assert summary.modalities == ["must not"]
    assert summary.conditions == ["if"]
    assert summary.references == ["s 5B"]


def test_match_rules_normalises_subject_to() -> None:
    nlp = spacy.blank("en")
    doc = nlp("The authority may issue permits subject to this Part.")
    summary = match_rules(doc)

    assert summary.primary_modality == "may"
    assert summary.conditions == ["subject to"]
    assert "this Part" in summary.references


def test_match_rules_keeps_first_modality() -> None:
    nlp = spacy.blank("en")
    doc = nlp("A person may act and must comply.")
    summary = match_rules(doc)

    assert summary.modalities == ["may", "must"]
    assert summary.primary_modality == "may"
