from __future__ import annotations

"""Evaluation of legal test factors against provided facts."""

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Mapping, Sequence


@dataclass
class ResultRow:
    """A single row in the result table for one factor."""

    factor: str
    """Identifier for the factor being evaluated."""

    status: bool
    """Whether the factor is satisfied (``True``) or not (``False``)."""

    evidence: List[str]
    """References or citations supporting the factor's status."""


@dataclass
class ResultTable:
    """A collection of :class:`ResultRow` results.

    The table is designed to be JSON serialisable via ``to_json``.
    """

    rows: List[ResultRow]

    def to_json(self) -> List[Dict[str, object]]:
        """Return the table in a JSON serialisable form."""

        return [asdict(row) for row in self.rows]


def evaluate(template: Mapping[str, Sequence[Mapping[str, object]]], facts: Mapping[str, Iterable[str]]) -> ResultTable:
    """Evaluate ``facts`` against a factor ``template``.

    Parameters
    ----------
    template:
        Mapping containing at least a ``"factors"`` key whose value is a
        sequence of factor definitions. Each factor must define either an
        ``"id"`` or ``"name"`` field which will be used as the identifier
        in the resulting table.
    facts:
        Mapping of factor identifiers to an iterable of evidence references.

    Returns
    -------
    ResultTable
        Table listing each factor with a boolean ``status`` and a list of
        supporting ``evidence`` references. Factors present in the template but
        absent from ``facts`` are marked with ``status=False`` and an empty
        evidence list.
    """

    factor_defs = template.get("factors", [])
    rows: List[ResultRow] = []
    for f in factor_defs:
        identifier = str(f.get("id") or f.get("name"))
        # Gather supporting evidence references if provided
        evidence = list(facts.get(identifier, []))
        status = bool(evidence)
        rows.append(ResultRow(factor=identifier, status=status, evidence=evidence))
    return ResultTable(rows)


"""Evaluation utilities for declarative concept tests."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

"""Evaluation engine for legal test templates."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

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

class FactorStatus(str, Enum):
    """Possible evaluation states for a factor."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNKNOWN = "unknown"


@dataclass
class FactorResult:
    """Outcome for a single factor along with supporting evidence."""

    id: str
    description: str
    status: FactorStatus
    evidence: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "evidence": list(self.evidence),
        }


@dataclass
class ResultTable:
    """Collection of factor results for a test template."""

    concept_id: str
    name: str
    results: List[FactorResult]

    def to_dict(self) -> Dict[str, object]:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "results": [r.to_dict() for r in self.results],
        }


def evaluate(template: TestTemplate, story: Dict[str, object]) -> ResultTable:
    """Evaluate a story against a test template.

    The ``story`` is expected to contain a ``factors`` mapping where each key
    corresponds to a factor ID from the template. Each factor entry is a
    mapping with a ``status`` boolean and ``evidence`` list of IDs. Example::

        {
            "factors": {
                "f1": {"status": true, "evidence": ["e1"]},
                "f2": {"status": false, "evidence": ["e2"]},
            }
        }
    """

    factor_data: Dict[str, Dict[str, object]] = story.get("factors", {})  # type: ignore[assignment]
    results: List[FactorResult] = []
    for factor in template.factors:
        entry = factor_data.get(factor.id, {})
        status_val = entry.get("status")
        if status_val is True:
            status = FactorStatus.SATISFIED
        elif status_val is False:
            status = FactorStatus.UNSATISFIED
        else:
            status = FactorStatus.UNKNOWN
        evidence = entry.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        results.append(
            FactorResult(
                id=factor.id,
                description=factor.description,
                status=status,
                evidence=[str(e) for e in evidence],
            )
        )
    return ResultTable(template.concept_id, template.name, results)
