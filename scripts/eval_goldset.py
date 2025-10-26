"""Evaluate extractor performance against curated gold sets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Set, Tuple

from src.ingestion.section_parser import fetch_section
from src.ingestion.frl import fetch_acts
from src.tests.templates import TEMPLATE_REGISTRY


ROOT = Path(__file__).resolve().parents[1]
GOLDSETS = ROOT / "tests" / "goldsets"


def _normalise_reference(ref: object) -> str:
    """Render a reference-like structure as a comparable string."""

    if isinstance(ref, dict):
        for key in ("citation_text", "text", "label"):
            value = ref.get(key)
            if value:
                return str(value)
        parts = [ref.get("work"), ref.get("section"), ref.get("pinpoint")]
        joined = " ".join(str(part) for part in parts if part)
        if joined:
            return joined
        return json.dumps(ref, sort_keys=True)
    if isinstance(ref, (list, tuple)):
        return " ".join(str(part) for part in ref if part)
    if ref is None:
        return ""
    return str(ref)


def _pr(expected: Iterable[Set[str]], predicted: Iterable[Set[str]]) -> Tuple[float, float]:
    """Compute micro-averaged precision and recall for sets."""
    tp = fp = fn = 0
    for exp, pred in zip(expected, predicted):
        tp += len(exp & pred)
        fp += len(pred - exp)
        fn += len(exp - pred)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall


def evaluate(threshold: float = 0.9) -> bool:
    """Run gold set evaluation and return success flag."""
    # Cross references
    section_cases = json.loads((GOLDSETS / "sections.json").read_text())
    exp_refs = []
    pred_refs = []
    for case in section_cases:
        exp_refs.append(set(case.get("cross_refs", [])))
        data = fetch_section(case["html"])
        references = data.get("rules", {}).get("references", [])
        pred_refs.append(
            {
                normalised
                for normalised in (
                    _normalise_reference(ref)
                    for ref in references
                )
                if normalised
            }
        )
    refs_p, refs_r = _pr(exp_refs, pred_refs)

    # Citations
    citation_data = json.loads((GOLDSETS / "citations.json").read_text())
    nodes, edges = fetch_acts("http://example", data=citation_data["acts"])
    pred_cites = {
        (e["from"], e["to"], e.get("text", ""))
        for e in edges
        if e["type"] == "cites"
    }
    exp_cites = {
        (c["from"], c["to"], c.get("text", ""))
        for c in citation_data["citations"]
    }
    cites_p, cites_r = _pr([exp_cites], [pred_cites])

    # Checklists
    checklist_cases = json.loads((GOLDSETS / "checklists.json").read_text())
    exp_factors = []
    pred_factors = []
    for case in checklist_cases:
        story = json.loads((ROOT / case["story"]).read_text())
        template = TEMPLATE_REGISTRY[story["template_id"]]
        passed = {fid for fid, val in story["facts"].items() if val}
        valid_ids = {f.id for f in template.factors}
        pred_factors.append(passed & valid_ids)
        exp_factors.append(set(case.get("passed_factors", [])))
    chk_p, chk_r = _pr(exp_factors, pred_factors)

    print(f"Cross refs precision={refs_p:.2f} recall={refs_r:.2f}")
    print(f"Citations precision={cites_p:.2f} recall={cites_r:.2f}")
    print(f"Checklists precision={chk_p:.2f} recall={chk_r:.2f}")

    metrics = [refs_p, refs_r, cites_p, cites_r, chk_p, chk_r]
    return all(m >= threshold for m in metrics)


def main(threshold: float = 0.9) -> None:
    if not evaluate(threshold):
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate gold sets")
    parser.add_argument("--threshold", type=float, default=0.9)
    args = parser.parse_args()
    main(args.threshold)
