from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.text.residual_lattice import ResidualLevel, coerce_predicate_atom, meet_atom


FACT_EXTRACTION_PROBE_SCHEMA_VERSION = "sl.fact_extraction_probe.v0_1"

_REQUIRED_RECEIPTS = ("source", "excerpt", "statement", "observation")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _residual_name(level: ResidualLevel | str) -> str:
    if isinstance(level, ResidualLevel):
        return level.name.lower()
    return _text(level)


def _residual_rank(level: str) -> int:
    return {
        "exact": 0,
        "partial": 1,
        "no_typed_meet": 2,
        "contradiction": 3,
    }.get(level, 2)


def _missing_receipts(receipts: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in _REQUIRED_RECEIPTS:
        if not receipts.get(f"{key}_receipt_id") and not receipts.get(key):
            missing.append(key)
    return missing


def _compare_evidence(query_atom: Mapping[str, Any], evidence_atoms: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for index, raw_atom in enumerate(evidence_atoms, start=1):
        atom = _dict(raw_atom)
        residual = meet_atom(query_atom, atom)
        comparisons.append(
            {
                "evidence_ref": _text(atom.get("atom_id") or atom.get("id") or f"evidence:{index}"),
                "residual": residual.to_dict(),
                "residual_level": _residual_name(residual.level),
                "structural_signature": _text(atom.get("structural_signature")),
                "provenance": _list(atom.get("provenance")),
            }
        )
    return comparisons


def _aggregate_residual(comparisons: list[Mapping[str, Any]]) -> str:
    if not comparisons:
        return "no_typed_meet"
    levels = [_text(row.get("residual_level")) for row in comparisons]
    if "contradiction" in levels:
        return "contradiction"
    if "exact" in levels:
        return "exact"
    if "partial" in levels:
        return "partial"
    return "no_typed_meet"


def _status_for_case(
    *,
    aggregate_residual: str,
    missing_receipts: list[str],
    gate: Mapping[str, Any],
    explicit_status: str,
) -> str:
    if explicit_status:
        return explicit_status
    if missing_receipts:
        return "blocked_missing_receipt"
    if aggregate_residual == "contradiction":
        return "contested"
    if aggregate_residual == "no_typed_meet":
        return "abstained"
    if aggregate_residual == "partial":
        return "candidate"
    if bool(gate.get("promote")):
        return "promoted"
    return "supported"


def build_fact_extraction_probe(*, fact_cases: Iterable[Mapping[str, Any]], source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a deterministic fact-extraction proof over supplied receipts.

    This is a probe/read-model surface. It does not parse raw text, call an LLM,
    query Wikidata, or promote facts by itself. Callers must supply typed
    PredicatePNF atoms and source/excerpt/statement/observation receipts.
    """

    cases: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    residual_counts: dict[str, int] = {}
    for index, raw_case in enumerate(fact_cases, start=1):
        case = dict(raw_case)
        candidate = _dict(case.get("fact_candidate"))
        query_atom = _dict(candidate.get("predicate_atom"))
        normalized_query = coerce_predicate_atom(query_atom)
        evidence_atoms = [_dict(atom) for atom in _list(case.get("evidence_atoms")) if isinstance(atom, Mapping)]
        comparisons = _compare_evidence(query_atom, evidence_atoms) if normalized_query is not None else []
        aggregate_residual = _aggregate_residual(comparisons)
        receipts = _dict(case.get("receipts"))
        missing = _missing_receipts(receipts)
        gate = _dict(case.get("promotion_gate"))
        status = _status_for_case(
            aggregate_residual=aggregate_residual,
            missing_receipts=missing,
            gate=gate,
            explicit_status=_text(candidate.get("candidate_status")),
        )
        status_counts[status] = status_counts.get(status, 0) + 1
        residual_counts[aggregate_residual] = residual_counts.get(aggregate_residual, 0) + 1
        cases.append(
            {
                "case_id": _text(case.get("case_id")) or f"fact_case:{index}",
                "lane": _text(case.get("lane")),
                "source_span": _text(case.get("source_span")),
                "fact_candidate": {
                    "fact_id": _text(candidate.get("fact_id")) or f"fact_candidate:{index}",
                    "label": _text(candidate.get("label")),
                    "predicate_atom": normalized_query.to_dict() if normalized_query is not None else query_atom,
                    "status": status,
                },
                "receipts": receipts,
                "missing_receipts": missing,
                "evidence_comparisons": comparisons,
                "aggregate_residual": aggregate_residual,
                "support_count": sum(
                    1
                    for row in comparisons
                    if _residual_rank(_text(row.get("residual_level"))) <= _residual_rank("partial")
                ),
                "contradiction_count": sum(1 for row in comparisons if row.get("residual_level") == "contradiction"),
                "promotion_gate": {
                    "promote_requested": bool(gate.get("promote")),
                    "gate_status": "passed" if status == "promoted" else "not_promoted",
                    "blockers": sorted(
                        set(_list(gate.get("blockers")) + [f"missing_{receipt}_receipt" for receipt in missing])
                    ),
                },
                "authority_policy": "review_only",
            }
        )
    return {
        "schema_version": FACT_EXTRACTION_PROBE_SCHEMA_VERSION,
        "source": dict(source or {}),
        "case_count": len(cases),
        "cases": cases,
        "summary": {
            "status_counts": dict(sorted(status_counts.items())),
            "residual_counts": dict(sorted(residual_counts.items())),
            "missing_receipt_cases": sum(1 for row in cases if row["missing_receipts"]),
            "contested_cases": sum(1 for row in cases if row["fact_candidate"]["status"] == "contested"),
            "abstained_cases": sum(1 for row in cases if row["fact_candidate"]["status"] == "abstained"),
        },
        "authority_boundary": {
            "receipt_backed_observation_classes_only": True,
            "raw_sentence_as_fact": False,
            "llm_summary_as_fact": False,
            "keyword_facting": False,
            "facts_require_source_excerpt_statement_observation_receipts": True,
            "predicate_pnf_fibres_gate_comparison": True,
            "promotion_requires_gate": True,
            "review_only": True,
        },
    }


__all__ = ["FACT_EXTRACTION_PROBE_SCHEMA_VERSION", "build_fact_extraction_probe"]
