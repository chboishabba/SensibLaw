"""CLI helpers for receipt operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.receipts.build import build_receipt
from src.receipts.verify import verify_receipt


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``receipts`` command."""
    parser = subparsers.add_parser("receipts", help="Receipt utilities")
    sub = parser.add_subparsers(dest="receipt_command")

    build = sub.add_parser("build", help="Build a receipt from JSON data")
    build.add_argument("data", help="JSON encoded receipt data")
    build.set_defaults(func=_handle_build)

    verify = sub.add_parser("verify", help="Verify a receipt")
    verify.add_argument("receipt", help="JSON encoded receipt")
    verify.set_defaults(func=_handle_verify)

    diff = sub.add_parser("diff", help="Compare two text files")
    diff.add_argument("--old", type=Path, required=True, help="Original text file")
    diff.add_argument("--new", type=Path, required=True, help="Revised text file")
    diff.set_defaults(func=_handle_diff)


def _handle_build(args: argparse.Namespace) -> None:
    data: Dict[str, Any] = json.loads(args.data)
    receipt = build_receipt(data)
    print(json.dumps(receipt))


def _handle_verify(args: argparse.Namespace) -> None:
    receipt: Dict[str, Any] = json.loads(args.receipt)
    ok = verify_receipt(receipt)
    print("valid" if ok else "invalid")


def _handle_diff(args: argparse.Namespace) -> None:
    from src.text import similarity

    old_text = Path(args.old).read_text()
    new_text = Path(args.new).read_text()
    if similarity.simhash(old_text) == similarity.simhash(new_text):
        print("cosmetic")
    else:
        print("substantive")


__all__ = ["register"]
