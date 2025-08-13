"""Run concept matching, checklist evaluation and proof-tree generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

# Ensure the src directory is importable when running from repository root
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distinguish.engine import (
    CaseSilhouette,
    compare_cases,
    extract_case_silhouette,
)
from pipeline import normalise, match_concepts, build_cloud
from tests.templates import TEMPLATE_REGISTRY


def load_base_silhouette(path: Path) -> CaseSilhouette:
    data = json.loads(path.read_text())
    return CaseSilhouette(
        fact_tags=data["fact_tags"],
        holding_hints=data["holding_hints"],
        paragraphs=data["paragraphs"],
    )


def evaluate_checklist(tokens: list[str]) -> Dict[str, bool]:
    template = TEMPLATE_REGISTRY["permanent_stay"]
    token_set = set(tokens)
    results: Dict[str, bool] = {}
    for factor in template.factors:
        # Very naive matching: factor id split into tokens
        keywords = factor.id.split("_")
        results[factor.id] = any(k in token_set for k in keywords)
    return results


def build_proof_tree(evaluation: Dict[str, bool]) -> str:
    lines = ["digraph ProofTree {", '  concept [label="Permanent Stay"]']
    template = TEMPLATE_REGISTRY["permanent_stay"]
    for factor in template.factors:
        present = evaluation.get(factor.id, False)
        node_label = f"{factor.description}\\n{'YES' if present else 'NO'}"
        lines.append(f'  {factor.id} [label="{node_label}"]')
        lines.append(f'  concept -> {factor.id}')
    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    here = Path(__file__).resolve().parent
    base = load_base_silhouette(here / "glj_silhouette.json")

    story_text = (here / "story.txt").read_text()
    story_paragraphs = [p.strip() for p in story_text.split(".") if p.strip()]
    candidate = extract_case_silhouette(story_paragraphs)

    comparison = compare_cases(base, candidate)

    normalised = normalise(story_text)
    tokens = match_concepts(normalised)
    cloud = build_cloud(tokens)
    evaluation = evaluate_checklist(tokens)
    proof_tree_dot = build_proof_tree(evaluation)

    result = {
        "concept_cloud": cloud,
        "comparison": comparison,
        "evaluation": evaluation,
    }

    (here / "results.json").write_text(json.dumps(result, indent=2))
    (here / "proof_tree.dot").write_text(proof_tree_dot)
    print("Wrote results.json and proof_tree.dot to", here)


if __name__ == "__main__":
    main()
