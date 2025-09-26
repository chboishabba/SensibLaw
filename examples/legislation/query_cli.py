"""Utilities for querying cleaned legislation excerpts in ``examples/legislation``.

The CLI is lightweight so it can run in demo environments without external
vector databases.  It performs rule-based routing of a query to precomputed
summaries that highlight the most practitioner-relevant nuggets.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List

DATA_DIR = Path(__file__).resolve().parent

DATASETS: Dict[str, Dict[str, str]] = {
    "penalties_and_sentences_part_2": {
        "path": "penalties_and_sentences_part_2.json",
        "description": "Queensland sentencing principles distilled from Part 2 of the Penalties and Sentences Act 1992.",
    },
    "criminal_code_qld_s302": {
        "path": "criminal_code_qld_s302.json",
        "description": "Checklist and defences for murder under s 302 of the Queensland Criminal Code.",
    },
}


def load_dataset(name: str) -> Dict:
    """Return the dataset payload merged with its metadata."""

    if name not in DATASETS:
        raise KeyError(f"Unknown dataset '{name}'.")

    payload_path = DATA_DIR / DATASETS[name]["path"]
    metadata_path = payload_path.with_suffix(".metadata.json")

    with payload_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        payload["metadata"] = metadata
    else:
        payload["metadata"] = {
            "dataset": name,
            "warning": "metadata file missing",
        }

    return payload


def _format_list(items: Iterable[str], bullet: str = "- ") -> str:
    return "\n".join(f"{bullet}{item}" for item in items)


def answer_query(dataset: Dict, query: str) -> str:
    """Generate a textual answer for the supported showcase queries."""

    q = query.lower()
    paragraphs: List[str] = []

    if "governing principles" in q and dataset.get("provisions"):
        paragraphs.append(
            "Governing principles drawn from Part 2 of the Penalties and Sentences Act:"
        )
        for provision in dataset["provisions"]:
            principles = provision.get("principles") or []
            if not principles:
                continue
            heading = f"s {provision['section']} {provision['heading']}"
            paragraphs.append(heading)
            paragraphs.append(_format_list(principles, bullet="  • "))
        paragraphs.append(
            "Refer to the metadata for source and cleaning notes: "
            + dataset.get("metadata", {}).get("source_url", "n/a")
        )
        return "\n".join(paragraphs)

    if "checklist" in q and "murder" in q and dataset.get("elements"):
        paragraphs.append("Checklist for establishing murder under the Queensland Criminal Code:")
        for element in dataset["elements"]:
            paragraphs.append(f"Element: {element['element']}")
            paragraphs.append(textwrap.fill(element["description"], width=88))
            paragraphs.append("Steps:")
            paragraphs.append(_format_list(element.get("checklist", []), bullet="  □ "))
        defences = dataset.get("defences", [])
        if defences:
            paragraphs.append("Relevant statutory defences to consider:")
            for defence in defences:
                paragraphs.append(
                    f"  → {defence['name']} ({defence['statutory_reference']}): {defence['summary']}"
                )
        paragraphs.append(
            "For authorities illustrating the elements see: "
            + "; ".join(case["name"] for case in dataset.get("related_cases", []))
        )
        return "\n".join(paragraphs)

    # Fallback summary for exploratory usage.
    metadata = dataset.get("metadata", {})
    summary_lines = [
        f"Dataset: {metadata.get('dataset', 'unknown')}",
        f"Act: {dataset.get('act', 'unknown')}",
        metadata.get("usage", "Usage guidance not available."),
        "Try queries such as 'List governing principles' or 'Checklist for murder'.",
    ]
    return "\n".join(summary_lines)


def run_demo() -> str:
    """Return a formatted demonstration covering the flagship queries."""

    demo_outputs: List[str] = []

    penalties = load_dataset("penalties_and_sentences_part_2")
    demo_outputs.append(
        answer_query(penalties, "List governing principles for sentencing under Part 2.")
    )

    murder = load_dataset("criminal_code_qld_s302")
    demo_outputs.append(answer_query(murder, "Checklist for murder"))

    return "\n\n".join(demo_outputs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query cleaned legislation snippets bundled with SensibLaw demos."
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASETS.keys()),
        help="Dataset identifier to consult when answering the query.",
    )
    parser.add_argument("--query", help="Natural language query to run against the dataset.")
    parser.add_argument(
        "--list", action="store_true", help="List available datasets and exit."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the pre-defined demonstration queries for stakeholder showcases.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list:
        print("Available datasets:")
        for name in sorted(DATASETS.keys()):
            print(f"- {name}: {DATASETS[name]['description']}")
        return

    if args.demo:
        print(run_demo())
        return

    if not args.dataset or not args.query:
        raise SystemExit("Both --dataset and --query are required unless --list or --demo is used.")

    dataset = load_dataset(args.dataset)
    print(answer_query(dataset, args.query))


if __name__ == "__main__":
    main()
