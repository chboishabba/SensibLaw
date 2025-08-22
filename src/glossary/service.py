"""Glossary service helpers."""

from __future__ import annotations


def lookup(term: str) -> str:
    """Return a definition for *term*.

    The current implementation is a placeholder that simply echoes the term.
    """
    return term


__all__ = ["lookup"]
