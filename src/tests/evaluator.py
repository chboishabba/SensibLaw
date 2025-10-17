"""Utilities for evaluating declarative legal tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence
import json


@dataclass
class ResultRow:
    """Single factor evaluation row."""

    factor: str
    status: bool
    evidence: List[str]


@dataclass
class ResultTable:
    """Collection of :class:`ResultRow` items."""

    rows: List[ResultRow]

    def to_json(self) -> List[Dict[str, object]]:
        return [asdict(row) for row in self.rows]


def evaluate(
    template: Mapping[str, Sequence[Mapping[str, object]]],
    facts: Mapping[str, Iterable[str]],
) -> ResultTable:
    """Evaluate ``facts`` against a declarative ``template``.

    Each factor definition in ``template['factors']`` is matched against the
    provided ``facts`` mapping.  If evidence is present for a factor the
    resulting row is marked ``status=True``.
    """

    rows: List[ResultRow] = []
    for factor in template.get("factors", []):
        identifier = str(factor.get("id") or factor.get("name"))
        evidence = list(facts.get(identifier, []))
        rows.append(ResultRow(factor=identifier, status=bool(evidence), evidence=evidence))
    return ResultTable(rows)


# ---------------------------------------------------------------------------
# Template loading helpers used by the CLI
# ---------------------------------------------------------------------------

@dataclass
class Factor:
    id: str
    description: str | None = None


@dataclass
class TestTemplate:
    concept_id: str
    name: str
    factors: List[Factor]


@dataclass
class FactorResult:
    id: str
    description: str
    status: str
    evidence: List[str]


@dataclass
class ConceptEvaluation:
    concept_id: str
    name: str
    results: List[FactorResult]

    def to_dict(self) -> Dict[str, object]:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "results": [asdict(row) for row in self.results],
        }


def load_templates(path: Path | str) -> Dict[str, TestTemplate]:
    """Load concept test templates from ``path``."""

    data = json.loads(Path(path).read_text())
    templates: Dict[str, TestTemplate] = {}
    for item in data:
        factors = [Factor(id=str(f.get("id")), description=f.get("description")) for f in item.get("factors", [])]
        templates[item["concept_id"]] = TestTemplate(
            concept_id=item["concept_id"],
            name=item.get("name", item["concept_id"]),
            factors=factors,
        )
    return templates


def evaluate_story(
    *, concept_id: str, story_path: Path | str, templates_path: Path | str
) -> ConceptEvaluation:
    """Evaluate a story against a stored concept template."""

    templates = load_templates(templates_path)
    if concept_id not in templates:
        raise KeyError(f"Unknown concept_id: {concept_id}")

    template = templates[concept_id]
    story = json.loads(Path(story_path).read_text())
    fact_records = story.get("facts", [])

    results: List[FactorResult] = []
    for factor in template.factors:
        relevant = [rec for rec in fact_records if rec.get("factor") == factor.id]
        if any(rec.get("met") for rec in relevant):
            status = "met"
        elif any(rec.get("met") is False for rec in relevant):
            status = "not_met"
        else:
            status = "unknown"
        evidence = [rec.get("evidence", "") for rec in relevant if rec.get("evidence")]
        results.append(
            FactorResult(
                id=factor.id,
                description=factor.description or factor.id,
                status=status,
                evidence=evidence,
            )
        )

    return ConceptEvaluation(concept_id=template.concept_id, name=template.name, results=results)


class FactorStatus(str, Enum):
    """Enumeration of possible factor states used by legacy callers."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNKNOWN = "unknown"


__all__ = [
    "ResultRow",
    "ResultTable",
    "evaluate",
    "load_templates",
    "evaluate_story",
    "TestTemplate",
    "Factor",
    "ConceptEvaluation",
    "FactorStatus",
]
