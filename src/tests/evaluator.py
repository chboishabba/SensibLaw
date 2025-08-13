from __future__ import annotations

"""Evaluation utilities for declarative concept tests."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

from .templates import Factor, TestTemplate


@dataclass
class FactorResult:
    """Result for a single factor in a test."""

    factor: Factor
    status: str
    evidence: List[str]


@dataclass
class Evaluation:
    """Full evaluation output for a concept."""

    template: TestTemplate
    results: List[FactorResult]


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

def load_templates(path: Path | str) -> Dict[str, TestTemplate]:
    """Load test templates from a JSON file.

    The JSON structure is expected to be a list of templates, where each template
    has ``concept_id``, ``name`` and ``factors`` (list of ``{"id", "description"}``).
    """

    data = json.loads(Path(path).read_text())
    templates: Dict[str, TestTemplate] = {}
    for tmpl in data:
        factors = [Factor(**f) for f in tmpl.get("factors", [])]
        templates[tmpl["concept_id"]] = TestTemplate(
            concept_id=tmpl["concept_id"],
            name=tmpl.get("name", tmpl["concept_id"]),
            factors=factors,
        )
    return templates


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _determine_status(records: Iterable[Mapping[str, object]]) -> str:
    statuses = [rec.get("met") for rec in records if "met" in rec]
    if True in statuses:
        return "met"
    if False in statuses:
        return "not_met"
    return "unknown"


def evaluate(*, concept_id: str, story_path: Path | str, templates_path: Path | str) -> Evaluation:
    """Evaluate a story against the specified concept template."""

    templates = load_templates(templates_path)
    if concept_id not in templates:
        raise KeyError(f"Unknown concept_id: {concept_id}")
    template = templates[concept_id]

    story = json.loads(Path(story_path).read_text())
    facts = story.get("facts", [])

    results: List[FactorResult] = []
    for factor in template.factors:
        relevant = [f for f in facts if f.get("factor") == factor.id]
        status = _determine_status(relevant)
        evidence = [f.get("evidence", "") for f in relevant if f.get("evidence")]
        results.append(FactorResult(factor=factor, status=status, evidence=evidence))

    return Evaluation(template=template, results=results)


__all__ = ["FactorResult", "Evaluation", "load_templates", "evaluate"]

