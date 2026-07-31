"""Bounded execution telemetry for ownership calibration.

The ledger is deliberately observational.  It never walks an object graph,
materialises an artifact, changes a resource limit, or participates in
semantic identity.  Callers provide already-known counters at lifecycle
boundaries and the ledger records process resources beside them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
from time import monotonic_ns
from typing import Any, Mapping, Sequence


LEDGER_SCHEMA_VERSION = "sensiblaw.execution-resource-ledger.v1"
DEFAULT_BATCH_SIZE = 256


def _proc_bytes(name: str) -> int | None:
    """Read one byte-valued field from Linux's smaps rollup when available."""

    try:
        for line in (
            Path("/proc/self/smaps_rollup").read_text(encoding="ascii").splitlines()
        ):
            key, _, value = line.partition(":")
            if key.strip() == name:
                return int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _rss_bytes() -> int:
    try:
        pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
        return pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError, AttributeError):
        # ru_maxrss is a high-water fallback.  It is preferable to omitting
        # RSS on non-Linux hosts, and the field is marked by the source below.
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * (1024 if sys.platform != "darwin" else 1)


def sample_process_resources() -> dict[str, int | str]:
    """Return RSS/PSS/USS with deterministic fallbacks and provenance."""

    rss = _rss_bytes()
    pss = _proc_bytes("Pss")
    uss = _proc_bytes("Private_Clean")
    private_dirty = _proc_bytes("Private_Dirty")
    if uss is not None:
        uss += private_dirty or 0
    else:
        uss = rss
    return {
        "rss_bytes": rss,
        "pss_bytes": pss if pss is not None else rss,
        "uss_bytes": uss,
        "resource_source": "proc_smaps_rollup"
        if pss is not None
        else "resource_rusage_fallback",
        "kernel": platform.release(),
    }


def environment_fingerprint() -> dict[str, Any]:
    """Identify the execution environment without including volatile paths."""

    payload = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "compiler": platform.python_compiler(),
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


@dataclass(frozen=True)
class LedgerSample:
    sequence: int
    stage: str
    kernel: str
    elapsed_ns: int
    rss_bytes: int
    pss_bytes: int
    uss_bytes: int
    batch_rows: int = 0
    payload_bytes: int = 0
    gc_counts: tuple[int, int, int] = (0, 0, 0)
    semantic_counts: Mapping[str, int] = field(default_factory=dict)
    phase: str = "sample"
    details: Mapping[str, Any] = field(default_factory=dict)
    post_gc: bool = False
    resource_source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["gc_counts"] = list(self.gc_counts)
        value["semantic_counts"] = dict(sorted(self.semantic_counts.items()))
        value["details"] = dict(self.details)
        return value


class ExecutionResourceLedger:
    """In-process, bounded sampler shared by compiler and persistence seams."""

    def __init__(
        self,
        *,
        run_ref: str,
        document_ref: str | None = None,
        environment: Mapping[str, Any] | None = None,
    ) -> None:
        self.run_ref = str(run_ref)
        self.document_ref = document_ref
        self.started_ns = monotonic_ns()
        self.environment = dict(environment or environment_fingerprint())
        self.samples: list[LedgerSample] = []
        self._counter_values: dict[str, int] = {}

    @property
    def elapsed_ns(self) -> int:
        return monotonic_ns() - self.started_ns

    def sample(
        self,
        stage: str,
        *,
        phase: str = "sample",
        batch_rows: int = 0,
        payload_bytes: int = 0,
        semantic_counts: Mapping[str, int] | None = None,
        details: Mapping[str, Any] | None = None,
        collect_gc: bool = False,
    ) -> LedgerSample:
        if batch_rows < 0 or payload_bytes < 0:
            raise ValueError("batch rows and payload bytes must be non-negative")
        counts = {
            str(key): int(value) for key, value in (semantic_counts or {}).items()
        }
        if any(value < 0 for value in counts.values()):
            raise ValueError("semantic counters must be non-negative")
        # Counter values are cumulative ownership observations.  Rejecting a
        # decrease catches accidental reuse of a stage-local counter while
        # keeping live-family counts explicit in the sample details.
        for key, value in counts.items():
            prior = self._counter_values.get(key)
            if prior is not None and value < prior:
                raise ValueError(f"semantic counter decreased: {key}")
            self._counter_values[key] = value
        if collect_gc:
            gc.collect()
        resources = sample_process_resources()
        row = LedgerSample(
            sequence=len(self.samples),
            stage=str(stage),
            kernel=str(resources["kernel"]),
            elapsed_ns=self.elapsed_ns,
            rss_bytes=int(resources["rss_bytes"]),
            pss_bytes=int(resources["pss_bytes"]),
            uss_bytes=int(resources["uss_bytes"]),
            batch_rows=int(batch_rows),
            payload_bytes=int(payload_bytes),
            gc_counts=tuple(gc.get_count()),
            semantic_counts=counts,
            phase=str(phase),
            details=dict(details or {}),
            post_gc=collect_gc,
            resource_source=str(resources["resource_source"]),
        )
        self.samples.append(row)
        return row

    def handoff(
        self, family: str, *, semantic_counts: Mapping[str, int] | None = None
    ) -> None:
        self.sample(
            f"artifact_handoff:{family}",
            phase="artifact_handoff",
            semantic_counts=semantic_counts,
        )

    def batch(
        self,
        stage: str,
        *,
        rows: int,
        payload_bytes: int = 0,
        semantic_counts: Mapping[str, int] | None = None,
        post_gc: bool = False,
    ) -> None:
        self.sample(
            stage,
            phase="batch",
            batch_rows=rows,
            payload_bytes=payload_bytes,
            semantic_counts=semantic_counts,
            collect_gc=post_gc,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "environment": self.environment,
            "samples": [sample.to_dict() for sample in self.samples],
        }

    def write_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema_version": LEDGER_SCHEMA_VERSION,
                        "run_ref": self.run_ref,
                        "document_ref": self.document_ref,
                        "environment": self.environment,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            for sample in self.samples:
                handle.write(json.dumps(sample.to_dict(), sort_keys=True) + "\n")

    def write_report(self, path: str | Path) -> dict[str, Any]:
        """Persist the deterministic single-trial report beside the raw stream."""

        report = build_ownership_report(self)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return report


def build_ownership_report(
    ledger: ExecutionResourceLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Build one deterministic retained/transient report from a raw ledger."""

    payload = (
        ledger.to_dict()
        if isinstance(ledger, ExecutionResourceLedger)
        else dict(ledger)
    )
    samples = list(payload.get("samples") or ())
    if not samples:
        raise ValueError("ownership report requires at least one sample")
    peak = max(
        samples,
        key=lambda row: (int(row.get("pss_bytes", 0)), int(row.get("sequence", 0))),
    )
    by_stage: dict[str, dict[str, Any]] = {}
    for row in samples:
        stage = str(row.get("stage") or "unknown")
        current = by_stage.setdefault(
            stage,
            {
                "sample_count": 0,
                "peak_pss_bytes": 0,
                "peak_uss_bytes": 0,
                "peak_rss_bytes": 0,
                "semantic_counts": {},
            },
        )
        current["sample_count"] += 1
        for key in ("rss_bytes", "pss_bytes", "uss_bytes"):
            current[f"peak_{key}"] = max(current[f"peak_{key}"], int(row.get(key, 0)))
        for key, value in (row.get("semantic_counts") or {}).items():
            current["semantic_counts"][str(key)] = max(
                current["semantic_counts"].get(str(key), 0), int(value)
            )
    post_gc = [row for row in samples if row.get("post_gc")]
    last = samples[-1]
    peak_stage = str(peak.get("stage") or "unknown")
    transient_drop = max(
        0, int(peak.get("pss_bytes", 0)) - int(last.get("pss_bytes", 0))
    )
    return {
        "schema_version": "sensiblaw.ownership-report.v1",
        "run_ref": payload.get("run_ref"),
        "document_ref": payload.get("document_ref"),
        "environment": payload.get("environment") or {},
        "sample_count": len(samples),
        "peak": dict(peak),
        "peak_stage": peak_stage,
        "final": dict(last),
        "post_gc_sample_count": len(post_gc),
        "transient_peak_pss_bytes": transient_drop,
        "stage_increments": {stage: value for stage, value in sorted(by_stage.items())},
        "classification": "transient_peak"
        if transient_drop
        else "retained_or_unresolved",
    }


def compare_ownership_reports(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare calibrated reports without selecting an optimisation owner."""

    if len(reports) != 3:
        raise ValueError("exact-0008 comparison requires exactly three reports")
    identities = {
        (
            str(report.get("environment", {}).get("fingerprint")),
            str(report.get("document_ref")),
            str(report.get("environment", {}).get("compiler_contract")),
            str(report.get("environment", {}).get("source_projection_sha256")),
        )
        for report in reports
    }
    peak_stages = [str(report.get("peak_stage") or "unknown") for report in reports]
    peak_values = [
        int(report.get("peak", {}).get("pss_bytes", 0)) for report in reports
    ]
    peak_mean = sum(peak_values) / len(peak_values)
    peak_spread = max(peak_values) - min(peak_values)
    return {
        "schema_version": "sensiblaw.ownership-comparison.v1",
        "trial_count": len(reports),
        "matching_identity": len(identities) == 1,
        "repeatable_peak_stage": len(set(peak_stages)) == 1,
        "peak_stage": peak_stages[0] if len(set(peak_stages)) == 1 else None,
        "peak_pss_spread_bytes": peak_spread,
        "peak_pss_mean_bytes": peak_mean,
        "trials": [dict(report) for report in reports],
        "peak_pss_bytes": [
            int(report.get("peak", {}).get("pss_bytes", 0)) for report in reports
        ],
        "classification": "calibration_only",
        "optimisation_owner": None,
        "threshold_selected": False,
    }


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "ExecutionResourceLedger",
    "LEDGER_SCHEMA_VERSION",
    "LedgerSample",
    "build_ownership_report",
    "compare_ownership_reports",
    "environment_fingerprint",
    "sample_process_resources",
]
