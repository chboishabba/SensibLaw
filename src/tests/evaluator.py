from __future__ import annotations

"""Evaluation engine for legal test templates."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from .templates import Factor, TestTemplate


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
