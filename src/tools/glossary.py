"""Glossary utilities for institutional and movement terms."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
import re

# Path to glossary file relative to repository root
GLOSSARY_PATH = Path(__file__).resolve().parents[2] / "data" / "glossary.yaml"


def load_glossary(path: Path = GLOSSARY_PATH) -> Dict[str, str]:
    """Load glossary mapping institutional terms to movement equivalents.

    A lightweight parser is used instead of a full YAML dependency since the
    glossary only contains simple ``key: value`` pairs.
    """
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        inst, mov = line.split(":", 1)
        mapping[inst.strip()] = mov.strip()
    return mapping


_GLOSSARY = load_glossary()


def lookup(term: str, *, reverse: bool = False) -> Optional[str]:
    """Return movement equivalent for *term* or institutional term if *reverse*.

    Args:
        term: The term to look up.
        reverse: If ``True`` treat ``term`` as a movement equivalent and return
            the institutional term.
    """
    if reverse:
        for inst, mov in _GLOSSARY.items():
            if mov.lower() == term.lower():
                return inst
        return None
    return _GLOSSARY.get(term)


def as_table() -> Iterable[Tuple[str, str]]:
    """Return the glossary as a sorted table of (institutional, movement)."""
    return sorted(_GLOSSARY.items())


class TermRewriter:
    """Rewrite text using glossary mappings."""

    def __init__(self, mapping: Optional[Dict[str, str]] = None) -> None:
        self.mapping = mapping or _GLOSSARY

    def rewrite(self, text: str) -> str:
        result = text
        for inst, mov in self.mapping.items():
            pattern = rf"\b{re.escape(inst)}\b"
            result = re.sub(pattern, mov, result, flags=re.IGNORECASE)
        return result


def rewrite_text(text: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """Convenience wrapper to rewrite *text* using the glossary."""
    return TermRewriter(mapping).rewrite(text)


__all__ = [
    "load_glossary",
    "lookup",
    "as_table",
    "rewrite_text",
    "TermRewriter",
]
