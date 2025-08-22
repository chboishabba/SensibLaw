"""CLI helpers for receipt operations."""

from __future__ import annotations

import argparse
import json
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


def _handle_build(args: argparse.Namespace) -> None:
    data: Dict[str, Any] = json.loads(args.data)
    receipt = build_receipt(data)
    print(json.dumps(receipt))


def _handle_verify(args: argparse.Namespace) -> None:
    receipt: Dict[str, Any] = json.loads(args.receipt)
    ok = verify_receipt(receipt)
    print("valid" if ok else "invalid")


__all__ = ["register"]
