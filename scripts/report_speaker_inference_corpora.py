#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _summarize(receipts: list) -> dict:
    by_confidence = Counter(receipt.confidence for receipt in receipts)
    by_reason = Counter(reason for receipt in receipts for reason in receipt.reasons)
    by_speaker = Counter(receipt.inferred_speaker for receipt in receipts if receipt.inferred_speaker)
    abstain = Counter(receipt.abstain_reason for receipt in receipts if receipt.abstained and receipt.abstain_reason)
    return {
        "unit_count": len(receipts),
        "assigned_count": sum(1 for receipt in receipts if not receipt.abstained),
        "abstained_count": sum(1 for receipt in receipts if receipt.abstained),
        "confidence_counts": dict(sorted(by_confidence.items())),
        "reason_counts": dict(sorted(by_reason.items(), key=lambda item: (-item[1], item[0]))),
        "abstain_reason_counts": dict(sorted(abstain.items(), key=lambda item: (-item[1], item[0]))),
        "top_inferred_speakers": [
            {"speaker": speaker, "count": count}
            for speaker, count in by_speaker.most_common(10)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report deterministic speaker-inference outcomes across transcript/chat/message corpora.")
    parser.add_argument("--chat-db")
    parser.add_argument("--messenger-db")
    parser.add_argument("--run-id")
    parser.add_argument("--context-file", action="append", default=[])
    parser.add_argument("--transcript-file", action="append", default=[])
    parser.add_argument("--shell-log", action="append", default=[])
    parser.add_argument("--known-participants", action="append", default=[], help="source_id=name1,name2,...")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.reporting.structure_report import load_chat_units, load_file_units, load_messenger_units  # noqa: PLC0415
    from src.text.speaker_inference import infer_speakers  # noqa: PLC0415

    units = []
    if args.chat_db:
        units.extend(load_chat_units(args.chat_db, args.run_id))
    if args.messenger_db:
        units.extend(load_messenger_units(args.messenger_db, args.run_id))
    for path in args.context_file:
        units.extend(load_file_units(path, "context_file"))
    for path in args.transcript_file:
        units.extend(load_file_units(path, "transcript_file"))
    for path in args.shell_log:
        units.extend(load_file_units(path, "shell_log"))
    if not units:
        raise SystemExit("no corpus inputs provided")

    known_participants_by_source: dict[str, list[str]] = {}
    for item in args.known_participants:
        if "=" not in item:
            continue
        source_id, raw_names = item.split("=", 1)
        known_participants_by_source[source_id] = [name.strip() for name in raw_names.split(",") if name.strip()]

    receipts = infer_speakers(units, known_participants_by_source=known_participants_by_source)
    grouped: dict[str, list] = defaultdict(list)
    for receipt in receipts:
        grouped[receipt.source_id].append(receipt)

    payload = {
        "overall": _summarize(receipts),
        "per_source": [
            {
                "source_id": source_id,
                "source_type": group[0].source_type,
                **_summarize(group),
            }
            for source_id, group in sorted(grouped.items())
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
