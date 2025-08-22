"""Compare a short story against the GLJ case silhouette."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence, Tuple, Dict, Any

# Ensure the src directory is importable when running from repository root
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distinguish.engine import CaseSilhouette, extract_case_silhouette, compare_cases


def load_silhouette(path: Path) -> CaseSilhouette:
    data = json.loads(path.read_text())
    return CaseSilhouette(
        fact_tags=data["fact_tags"],
        holding_hints=data["holding_hints"],
        paragraphs=data["paragraphs"],
    )


def compare_story_to_case(base: CaseSilhouette, story: Sequence[str]) -> Tuple[Dict[str, Any], CaseSilhouette]:
    candidate = extract_case_silhouette(story)
    comparison = compare_cases(base, candidate)
    return comparison, candidate


def main() -> None:
    here = Path(__file__).resolve().parent
    base = load_silhouette(here / "glj_silhouette.json")
    story = json.loads((here / "story.json").read_text())

    comparison, candidate = compare_story_to_case(base, story)

    for item in comparison["overlaps"]:
        print(f"OVERLAP ({item['type']}): {item['text']}")
        print(f"  GLJ \u00b6{item['base']['index'] + 1}: {item['base']['paragraph']}")
        print(f"  Story \u00b6{item['candidate']['index'] + 1}: {item['candidate']['paragraph']}")

    for item in comparison["missing"]:
        print(f"MISSING ({item['type']}): {item['text']}")
        print(f"  GLJ \u00b6{item['base']['index'] + 1}: {item['base']['paragraph']}")

    for token in comparison["b_only_tokens"]:
        idx = candidate.fact_tags[token]
        para = candidate.paragraphs[idx]
        print(f"EXTRA FACT: {token}")
        print(f"  Story \u00b6{idx + 1}: {para}")


if __name__ == "__main__":
    main()
