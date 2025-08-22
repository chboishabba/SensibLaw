"""CLI helpers for frame operations."""

from __future__ import annotations

import argparse

from src.frame.compiler import compile_frame


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``frame`` command."""
    parser = subparsers.add_parser("frame", help="Frame compilation utilities")
    parser.add_argument("source", help="Frame source text")
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> None:
    result = compile_frame(args.source)
    print(result)


__all__ = ["register"]
