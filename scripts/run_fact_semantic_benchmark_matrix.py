#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts.benchmark_fact_semantics import main as benchmark_main

_DEFAULT_DRIFT_THRESHOLDS = {
    "assertion_count": 0.15,
    "policy_count": 0.15,
    "facts_serialized_count": 0.15,
    "relation_count": 0.25,
}


def _load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_report_identity(path: Path, payload: dict[str, object]) -> tuple[str | None, int | None]:
    corpus_id = str(payload.get("corpus_id") or "").strip() or None
    count_raw = payload.get("count")
    count = int(count_raw) if isinstance(count_raw, int) else None
    if corpus_id and count is not None:
        return corpus_id, count
    stem = path.stem
    stem = re.sub(r"^\d{8}T\d{6}_", "", stem)
    match = re.match(r"(?P<corpus_id>.+)_(?P<count>\d+)(?:_v\d+)?$", stem)
    if not match:
        return corpus_id, count
    return corpus_id or match.group("corpus_id"), count if count is not None else int(match.group("count"))


def _load_report_payload(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_baseline_report(baseline_dir: Path, *, corpus_id: str, count: int) -> tuple[Path | None, dict[str, object] | None]:
    candidates: list[tuple[float, Path, dict[str, object]]] = []
    for path in baseline_dir.rglob("*.json"):
        payload = _load_report_payload(path)
        if not isinstance(payload, dict):
            continue
        report_corpus_id, report_count = _infer_report_identity(path, payload)
        if report_corpus_id != corpus_id or report_count != count:
            continue
        candidates.append((path.stat().st_mtime, path, payload))
    if not candidates:
        return None, None
    _, path, payload = max(candidates, key=lambda item: item[0])
    return path, payload


def _relative_delta(current: int | float, baseline: int | float) -> float | None:
    if baseline == 0:
        return None
    return round((float(current) - float(baseline)) / float(baseline), 6)


def _build_drift_summary(
    payload: dict[str, object],
    baseline_payload: dict[str, object] | None,
) -> tuple[dict[str, object] | None, dict[str, dict[str, object]], list[str]]:
    refresh = payload.get("refresh") if isinstance(payload.get("refresh"), dict) else {}
    expectation = payload.get("expectation_summary") if isinstance(payload.get("expectation_summary"), dict) else {}
    guardrail_status: dict[str, dict[str, object]] = {}
    review_recommendations: list[str] = []
    if not isinstance(baseline_payload, dict):
        guardrail_status["baseline"] = {"status": "no_baseline"}
        class_recall = float(expectation.get("class_expectation_recall", 1.0))
        policy_recall = float(expectation.get("policy_expectation_recall", 1.0))
        guardrail_status["class_expectation_recall"] = {
            "status": "warn" if class_recall < 1.0 else "ok",
            "threshold": 1.0,
            "value": class_recall,
        }
        guardrail_status["policy_expectation_recall"] = {
            "status": "warn" if policy_recall < 1.0 else "ok",
            "threshold": 1.0,
            "value": policy_recall,
        }
        if class_recall < 1.0:
            review_recommendations.append("Class expectation recall below 1.0; inspect entries with missing expected classes.")
        if policy_recall < 1.0:
            review_recommendations.append("Policy expectation recall below 1.0; inspect entries with missing expected policies.")
        return None, guardrail_status, review_recommendations

    baseline_refresh = baseline_payload.get("refresh") if isinstance(baseline_payload.get("refresh"), dict) else {}
    drift: dict[str, object] = {}
    metric_labels = {
        "assertion_count": "assertions",
        "relation_count": "relations",
        "policy_count": "policies",
        "facts_serialized_count": "facts",
    }
    for metric_key, label in metric_labels.items():
        current_value = int(refresh.get(metric_key, 0))
        baseline_value = int(baseline_refresh.get(metric_key, 0))
        delta = _relative_delta(current_value, baseline_value)
        drift[label] = {
            "current": current_value,
            "baseline": baseline_value,
            "relative_delta": delta,
        }
        if delta is None:
            guardrail_status[metric_key] = {
                "status": "not_applicable",
                "threshold": _DEFAULT_DRIFT_THRESHOLDS[metric_key],
                "relative_delta": None,
            }
            continue
        status = "warn" if abs(delta) > _DEFAULT_DRIFT_THRESHOLDS[metric_key] else "ok"
        guardrail_status[metric_key] = {
            "status": status,
            "threshold": _DEFAULT_DRIFT_THRESHOLDS[metric_key],
            "relative_delta": delta,
        }
        if status == "warn":
            review_recommendations.append(
                f"{label} drift {delta:+.1%} exceeds {_DEFAULT_DRIFT_THRESHOLDS[metric_key]:.0%} threshold."
            )

    elapsed_ms = float(payload.get("elapsed_ms", 0.0))
    baseline_elapsed_ms = float(baseline_payload.get("elapsed_ms", 0.0))
    drift["elapsed_ms"] = {
        "current": elapsed_ms,
        "baseline": baseline_elapsed_ms,
        "relative_delta": _relative_delta(elapsed_ms, baseline_elapsed_ms) if baseline_elapsed_ms else None,
    }

    class_recall = float(expectation.get("class_expectation_recall", 1.0))
    policy_recall = float(expectation.get("policy_expectation_recall", 1.0))
    guardrail_status["class_expectation_recall"] = {
        "status": "warn" if class_recall < 1.0 else "ok",
        "threshold": 1.0,
        "value": class_recall,
    }
    guardrail_status["policy_expectation_recall"] = {
        "status": "warn" if policy_recall < 1.0 else "ok",
        "threshold": 1.0,
        "value": policy_recall,
    }
    if class_recall < 1.0:
        review_recommendations.append("Class expectation recall below 1.0; inspect entries with missing expected classes.")
    if policy_recall < 1.0:
        review_recommendations.append("Policy expectation recall below 1.0; inspect entries with missing expected policies.")

    return drift, guardrail_status, review_recommendations


def _review_targets(corpus_id: str, payload: dict[str, object], limit: int = 3) -> list[dict[str, object]]:
    rows = payload.get("entry_diagnostics")
    if not isinstance(rows, list):
        return []
    filtered = [row for row in rows if isinstance(row, dict)]
    if corpus_id == "wiki_revision":
        filtered.sort(
            key=lambda row: (
                0 if row.get("missing_expected_classes") or row.get("missing_expected_policies") else 1,
                -int(row.get("relation_count", 0)),
                -len(list(row.get("unexpected_signal_classes", []))),
                str(row.get("entry_id", "")),
            )
        )
    elif corpus_id == "au_legal":
        filtered.sort(
            key=lambda row: (
                -int(row.get("relation_count", 0)),
                -(len(list(row.get("unexpected_signal_classes", []))) + len(list(row.get("unexpected_policy_outcomes", [])))),
                0 if row.get("missing_expected_classes") or row.get("missing_expected_policies") else 1,
                str(row.get("entry_id", "")),
            )
        )
    else:
        filtered.sort(
            key=lambda row: (
                -(len(list(row.get("missing_expected_classes", []))) + len(list(row.get("missing_expected_policies", [])))),
                -int(row.get("policy_count", 0)),
                -int(row.get("assertion_count", 0)),
                str(row.get("entry_id", "")),
            )
        )
    targets: list[dict[str, object]] = []
    for row in filtered[:limit]:
        reasons: list[str] = []
        if row.get("missing_expected_classes"):
            reasons.append("missing_expected_classes")
        if row.get("missing_expected_policies"):
            reasons.append("missing_expected_policies")
        if int(row.get("relation_count", 0)) > 0:
            reasons.append("relation_volume")
        if row.get("unexpected_signal_classes") or row.get("unexpected_policy_outcomes"):
            reasons.append("unexpected_output")
        targets.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "relation_count": int(row.get("relation_count", 0)),
                "assertion_count": int(row.get("assertion_count", 0)),
                "policy_count": int(row.get("policy_count", 0)),
                "missing_expected_classes": list(row.get("missing_expected_classes", [])),
                "missing_expected_policies": list(row.get("missing_expected_policies", [])),
                "reasons": reasons,
            }
        )
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fact semantic benchmark matrix from a corpus manifest.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/fact_semantic_bench/corpus_manifest.json"),
        help="Path to the benchmark corpus manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".cache_local/fact_semantic_bench"),
        help="Directory where per-run JSON reports will be written.",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=None,
        help="Optional directory containing prior benchmark reports for drift comparison. Defaults to output-dir.",
    )
    parser.add_argument(
        "--max-tier",
        type=int,
        default=None,
        help="Optional maximum tier size to run.",
    )
    parser.add_argument(
        "--corpus-id",
        action="append",
        default=[],
        help="Optional corpus_id to run. Repeatable.",
    )
    args = parser.parse_args(argv)

    manifest = _load_manifest(args.manifest)
    corpus_rows = manifest.get("corpora")
    if not isinstance(corpus_rows, list) or not corpus_rows:
        raise SystemExit(f"Manifest has no corpora: {args.manifest}")

    selected = {str(value) for value in args.corpus_id if str(value).strip()}
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = args.baseline_dir or output_dir

    started = time.strftime("%Y%m%dT%H%M%S")
    results: list[dict[str, object]] = []
    for row in corpus_rows:
        if not isinstance(row, dict):
            continue
        corpus_id = str(row.get("corpus_id") or "").strip()
        if not corpus_id:
            continue
        if selected and corpus_id not in selected:
            continue
        corpus_path = Path(str(row.get("path") or ""))
        tiers = row.get("tiers")
        if not isinstance(tiers, list):
            continue
        for tier in tiers:
            count = int(tier)
            if args.max_tier is not None and count > args.max_tier:
                continue
            report_path = output_dir / f"{started}_{corpus_id}_{count}.json"
            baseline_report_path, baseline_payload = _find_baseline_report(baseline_dir, corpus_id=corpus_id, count=count)
            with tempfile.TemporaryDirectory(prefix=f"bench-{corpus_id}-{count}-") as tmpdir:
                db_path = Path(tmpdir) / "bench.sqlite"
                original_stdout = sys.stdout
                try:
                    from io import StringIO

                    capture = StringIO()
                    sys.stdout = capture
                    exit_code = benchmark_main(
                        [
                            "--corpus-file",
                            str(corpus_path),
                            "--count",
                            str(count),
                            "--db-path",
                            str(db_path),
                        ]
                    )
                finally:
                    sys.stdout = original_stdout
                output = capture.getvalue().strip()
                payload = json.loads(output) if output else {}
                payload["exit_code"] = exit_code
                payload["corpus_id"] = corpus_id
                payload["manifest_path"] = str(args.manifest)
                payload["baseline_report_path"] = str(baseline_report_path) if baseline_report_path is not None else None
                drift, guardrail_status, review_recommendations = _build_drift_summary(payload, baseline_payload)
                payload["drift"] = drift
                payload["guardrail_status"] = guardrail_status
                payload["review_recommendations"] = review_recommendations
                payload["review_targets"] = _review_targets(corpus_id, payload)
                report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                results.append(
                    {
                        "corpus_id": corpus_id,
                        "count": count,
                        "exit_code": exit_code,
                        "report_path": str(report_path),
                        "baseline_report_path": str(baseline_report_path) if baseline_report_path is not None else None,
                        "elapsed_ms": payload.get("elapsed_ms"),
                        "refresh_status": ((payload.get("refresh") or {}).get("refresh_status") if isinstance(payload.get("refresh"), dict) else None),
                        "guardrail_status": guardrail_status,
                        "review_recommendations": review_recommendations,
                    }
                )
                print(
                    f"[bench-matrix] corpus={corpus_id} count={count} exit={exit_code} "
                    f"status={results[-1]['refresh_status']} review={len(review_recommendations)} report={report_path}"
                )

    summary = {
        "manifest": str(args.manifest),
        "output_dir": str(output_dir),
        "run_count": len(results),
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
