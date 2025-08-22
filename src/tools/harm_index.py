"""Compute harm index scores from stakeholder metrics.

This tool aggregates metric files under ``data/harm_inputs`` and
computes a simple harm index score for each stakeholder. Scores are
calculated using a configurable weighting for each metric. Results are
written to JSON and a bar chart visualisation is produced.

Usage
-----
::

    python -m tools.harm_index --data-dir data/harm_inputs \
        --weights weights.json --json-out harm.json --chart-out harm.png

The ``weights`` file is optional. If omitted, each metric receives a
weight of ``1``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping, Any


Metrics = Dict[str, Dict[str, float]]
Scores = Dict[str, float]


def load_metrics(directory: Path) -> Metrics:
    """Load stakeholder metrics from ``directory``.

    Each ``*.json`` file is expected to contain a structure similar to::

        {
            "stakeholder": "group",  # optional, defaults to file stem
            "metrics": {"metric": value, ...}
        }

    Parameters
    ----------
    directory:
        Path to the folder containing metric files.
    """
    metrics: Metrics = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data: Dict[str, Any] = json.loads(path.read_text())
        except json.JSONDecodeError as exc:  # pragma: no cover - file errors
            raise ValueError(f"Invalid JSON in {path}") from exc

        name = data.get("stakeholder") or path.stem
        metrics[name] = {
            k: float(v) for k, v in data.get("metrics", {}).items()
        }
    return metrics


def compute_scores(metrics: Metrics, weights: Mapping[str, float] | None = None) -> Scores:
    """Compute weighted scores for each stakeholder."""
    weights = weights or {}
    scores: Scores = {}
    for name, values in metrics.items():
        score = 0.0
        for metric, value in values.items():
            score += value * float(weights.get(metric, 1.0))
        scores[name] = score
    return scores


def save_chart(scores: Scores, output: Path) -> None:
    """Render a bar chart of scores to ``output``."""
    if not scores:
        return
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("matplotlib is required for charting") from exc

    names = list(scores.keys())
    values = list(scores.values())
    plt.figure(figsize=(8, 4))
    plt.bar(names, values)
    plt.ylabel("Harm index")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def compute_harm_index(
    data_dir: Path | str = Path("data/harm_inputs"),
    weights: Mapping[str, float] | None = None,
    json_out: Path | None = None,
    chart_out: Path | None = None,
) -> Scores:
    """High level convenience wrapper.

    Parameters
    ----------
    data_dir:
        Directory containing stakeholder metric files.
    weights:
        Optional mapping of metric name to weight.
    json_out:
        Optional path to write JSON results.
    chart_out:
        Optional path to save a bar chart visualisation.
    """
    data_dir = Path(data_dir)
    metrics = load_metrics(data_dir)
    scores = compute_scores(metrics, weights)

    if json_out:
        Path(json_out).write_text(json.dumps(scores, indent=2))
    if chart_out:
        save_chart(scores, Path(chart_out))
    return scores


def main() -> None:  # pragma: no cover - CLI wrapper
    import argparse

    parser = argparse.ArgumentParser(description="Compute harm index scores")
    parser.add_argument(
        "--data-dir", default="data/harm_inputs", help="Metrics directory"
    )
    parser.add_argument(
        "--weights", help="Path to JSON file containing metric weightings"
    )
    parser.add_argument(
        "--json-out", default="harm_index.json", help="Output JSON file"
    )
    parser.add_argument(
        "--chart-out", default="harm_index.png", help="Output chart image"
    )
    args = parser.parse_args()

    weights = (
        json.loads(Path(args.weights).read_text()) if args.weights else None
    )
    compute_harm_index(
        data_dir=args.data_dir,
        weights=weights,
        json_out=args.json_out,
        chart_out=args.chart_out,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
