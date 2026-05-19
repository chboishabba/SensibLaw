#!/usr/bin/env python3
"""CLI for compiling and reducing Conversation VM artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sensiblaw.conversation_vm import build_context_payload, build_proof_surface, compile_turn, empty_state, step_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile-turn", help="Compile one JSON/text turn into Delta_t")
    compile_parser.add_argument("--input", "-i", type=Path, help="Input JSON file. Reads stdin when omitted.")
    compile_parser.add_argument("--output", "-o", type=Path, help="Output delta JSON file. Writes stdout when omitted.")
    compile_parser.add_argument("--text", action="store_true", help="Treat input as plain text instead of JSON.")

    step_parser = subparsers.add_parser("step", help="Apply a delta to a VM state artifact")
    step_parser.add_argument("--state", type=Path, help="Existing state JSON. Uses empty state when omitted or missing.")
    step_parser.add_argument("--delta", type=Path, required=True, help="Delta JSON from compile-turn.")
    step_parser.add_argument("--output", "-o", type=Path, help="Output state JSON file. Writes stdout when omitted.")

    query_parser = subparsers.add_parser("query-surface", help="Emit proof surface or compact context payload")
    query_parser.add_argument("--state", type=Path, required=True, help="State JSON file.")
    query_parser.add_argument("--query", "-q", help="Optional predicate/argument substring filter.")
    query_parser.add_argument("--context", action="store_true", help="Emit compact context payload instead of proof surface.")
    query_parser.add_argument("--limit", type=int, default=12, help="Context item limit.")
    query_parser.add_argument("--output", "-o", type=Path, help="Output JSON file. Writes stdout when omitted.")

    args = parser.parse_args(argv)
    if args.command == "compile-turn":
        raw = _read(args.input)
        payload: Any = raw if args.text else json.loads(raw)
        return _write(args.output, compile_turn(payload))
    if args.command == "step":
        state = _load_optional_state(args.state)
        delta = json.loads(args.delta.read_text(encoding="utf-8"))
        return _write(args.output, step_state(state, delta))
    if args.command == "query-surface":
        state = json.loads(args.state.read_text(encoding="utf-8"))
        payload = (
            build_context_payload(state, query=args.query, limit=args.limit)
            if args.context
            else build_proof_surface(state, query=args.query)
        )
        return _write(args.output, payload)
    return 2


def _read(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def _load_optional_state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_state()
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path | None, payload: dict[str, Any]) -> int:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
