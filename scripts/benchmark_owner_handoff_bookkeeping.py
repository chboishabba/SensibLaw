#!/usr/bin/env python3
"""Compare legacy cumulative replay bookkeeping with the v3 append journal.

No parser, PostgreSQL, provider, or semantic closure work is performed.  This
isolates the physical replay-history bookkeeping that appeared in the live
owner_admission_batch / closure_handoff profile.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic_ns

# Importing src.policy normally installs the full execution strategy stack.  This
# probe needs only the physical journal function.
os.environ.setdefault("SENSIBLAW_BOUNDED_DOCUMENT_EXECUTION", "0")

from src.policy.owner_handoff_performance import _append_journal_event  # noqa: E402


class _Context:
    def __init__(self, root: Path) -> None:
        self.closure_activation_checkpoint_root = root
        self.build_key_sha256 = "benchmark"
        self.reconstructing_owner = False
        self.closure_activation: dict[str, object] = {}
        self.closure_counters: Counter[str] = Counter()
        self.lock = Lock()


def _legacy(events: int) -> tuple[int, int]:
    activation: dict[str, object] = {}
    started = monotonic_ns()
    copied_rows = 0
    for ordinal in range(events):
        artifact_ref = f"artifact:{ordinal}"
        refs = list(activation.get("proposal_batch_artifact_refs") or ())
        copied_rows += len(refs)
        refs.append(artifact_ref)
        activation["proposal_batch_artifact_refs"] = tuple(refs)
        replay = list(activation.get("replay_events") or ())
        copied_rows += len(replay)
        replay.append(
            {"artifact_kind": "proposal_batch", "artifact_ref": artifact_ref}
        )
        activation["replay_events"] = tuple(replay)
        # Model the old handoff writer's repeated serialization of cumulative
        # history, without filesystem latency.
        json.dumps(
            {
                "proposal_batch_artifact_refs": refs,
                "replay_events": replay,
            },
            separators=(",", ":"),
        )
    return monotonic_ns() - started, copied_rows


def _v3(events: int, root: Path) -> tuple[int, int]:
    context = _Context(root)
    started = monotonic_ns()
    for ordinal in range(events):
        _append_journal_event(
            context,
            artifact_kind="proposal_batch",
            artifact_ref=f"artifact:{ordinal}",
        )
    elapsed = monotonic_ns() - started
    return elapsed, int(context.closure_counters["handoff_journal_events"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events",
        type=int,
        nargs="+",
        default=[128, 256, 512, 1024, 2048],
    )
    args = parser.parse_args()
    if any(value <= 0 for value in args.events):
        parser.error("--events values must be positive")

    rows = []
    with TemporaryDirectory(prefix="sensiblaw-handoff-benchmark-") as temp:
        root = Path(temp)
        for event_count in args.events:
            legacy_ns, legacy_copied = _legacy(event_count)
            v3_root = root / str(event_count)
            v3_ns, v3_appends = _v3(event_count, v3_root)
            rows.append(
                {
                    "events": event_count,
                    "legacy_elapsed_ns": legacy_ns,
                    "legacy_cumulative_rows_copied": legacy_copied,
                    "v3_elapsed_ns": v3_ns,
                    "v3_journal_rows_appended": v3_appends,
                    "legacy_to_v3_elapsed_ratio": (
                        legacy_ns / v3_ns if v3_ns else None
                    ),
                    "semantic_work_performed": False,
                    "provider_io_performed": False,
                }
            )
    print(json.dumps({"rows": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
