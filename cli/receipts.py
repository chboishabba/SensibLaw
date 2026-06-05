"""CLI helpers for receipt operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.sensiblaw.interfaces import (
    build_classification_discovery_lattice,
    render_classification_discovery_lattice_png,
)
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

    classification_lattice = sub.add_parser(
        "classification-discovery-lattice",
        help="Build classification discovery lattice payload from story PNF receipt JSON",
    )
    classification_lattice.add_argument("story_pnf_payload", type=Path, help="Path to story_pnf_receipts JSON payload")
    classification_lattice.add_argument("--json-out", type=Path, help="Write lattice payload JSON")
    classification_lattice.add_argument(
        "--png-out",
        type=Path,
        help="Render classification lattice PNG",
    )
    classification_lattice.set_defaults(func=_handle_classification_discovery_lattice)


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


def _handle_classification_discovery_lattice(args: argparse.Namespace) -> None:
    payload = json.loads(args.story_pnf_payload.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("story_pnf_payload must be a JSON object")
    emission_receipts = payload.get("emission_receipts")
    if not isinstance(emission_receipts, list):
        raise SystemExit("story_pnf_payload missing 'emission_receipts' list")

    lattice = build_classification_discovery_lattice(
        emission_receipts,
        class_relation_witnesses=payload.get("class_relation_witnesses", ()),
        context=payload,
    )

    if args.json_out is None and args.png_out is None:
        print(json.dumps(lattice, sort_keys=True))
        return

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(lattice, sort_keys=True), encoding="utf-8")
    if args.png_out is not None:
        if lattice is None:
            raise SystemExit("no classification lattice can be built from payload")
        render_classification_discovery_lattice_png(lattice, args.png_out)


__all__ = ["register"]
