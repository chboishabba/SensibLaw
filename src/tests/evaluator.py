"""Evaluation of legal test factors against provided facts."""

from __future__ import annotations

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

