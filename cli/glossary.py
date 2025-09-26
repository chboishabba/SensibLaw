"""CLI helpers for glossary operations."""

from __future__ import annotations

import argparse

from src.glossary.service import lookup


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``glossary`` command."""
    parser = subparsers.add_parser("glossary", help="Glossary lookups")
    parser.add_argument("term", help="Term to lookup")
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> None:
    entry = lookup(args.term)
    if entry is None:
        print(args.term)
    else:
        print(entry.text)


__all__ = ["register"]
