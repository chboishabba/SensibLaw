"""Generate structured counter briefs using a trivial adversarial approach.

This module provides a helper to consume a textual brief and emit a JSON
structure containing adversarial rebuttals.  The implementation here does not
rely on any external model; instead it produces simple counter statements for
teaching and testing purposes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def _adversarial_response(claim: str) -> str:
    """Return a simple counter argument for ``claim``.

    The function intentionally provides a deterministic placeholder response so
    tests can make assertions about the output structure without depending on
    external language models.
    """

    return f"Counter: the assertion '{claim}' lacks sufficient support."


def generate_counter_brief(input_file: Path, output_dir: Path | None = None) -> Dict[str, List[Dict[str, str]]]:
    """Create a counter brief from ``input_file`` and persist the result.

    Parameters
    ----------
    input_file:
        Path to the text file containing the original brief.  Each non-empty
        line is treated as a separate claim.
    output_dir:
        Directory where the JSON rebuttal should be written.  If omitted, the
        default ``output/counter_briefs`` relative to the current working
        directory is used.

    Returns
    -------
    dict
        A dictionary with a single key ``"rebuttals"`` containing the list of
        claim/rebuttal pairs.
    """

    if output_dir is None:
        output_dir = Path("output/counter_briefs")

    text = input_file.read_text(encoding="utf-8")
    claims = [line.strip() for line in text.splitlines() if line.strip()]

    rebuttals: List[Dict[str, str]] = []
    for claim in claims:
        rebuttals.append({"claim": claim, "rebuttal": _adversarial_response(claim)})

    result: Dict[str, List[Dict[str, str]]] = {"rebuttals": rebuttals}

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{input_file.stem}.json"
    out_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return result


def main() -> None:  # pragma: no cover - convenience wrapper
    parser = argparse.ArgumentParser(
        description="Generate a counter brief using a trivial adversarial bundle",
    )
    parser.add_argument("--file", type=Path, required=True, help="Input brief file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/counter_briefs"),
        help="Directory for generated counter briefs",
    )
    args = parser.parse_args()
    result = generate_counter_brief(args.file, args.output_dir)
    print(json.dumps(result))


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
