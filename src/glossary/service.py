"""Glossary service helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "glossary"
_DEFAULT_DATA_FILE = _DATA_DIR / "offence_gloss.yaml"


def _normalise_key(term: str) -> str:
    """Normalise a lookup *term* for matching against curated data."""

    return " ".join(term.lower().strip(" \t\n,.!?;:'\"()").split())


@dataclass(frozen=True)
class GlossEntry:
    """Curated gloss definition and optional metadata."""

    phrase: str
    text: str
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover - exercised indirectly
        return self.text


def _coerce_metadata(meta: Any) -> Optional[Dict[str, Any]]:
    if meta is None:
        return None
    if isinstance(meta, Mapping):
        return dict(meta)
    raise TypeError("Gloss metadata must be a mapping or null")


def _coerce_entry(phrase: str, value: Any) -> Optional[GlossEntry]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return GlossEntry(phrase=phrase, text=text)
    if isinstance(value, Mapping):
        text = str(value.get("text") or value.get("gloss") or "").strip()
        if not text:
            return None
        metadata = _coerce_metadata(value.get("metadata"))
        return GlossEntry(phrase=phrase, text=text, metadata=metadata)
    raise TypeError(f"Unsupported glossary entry type for '{phrase}': {type(value)!r}")


def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".json":
            data = json.load(handle)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(handle)
        else:
            raise ValueError(f"Unsupported glossary format: {path.suffix}")
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise TypeError("Glossary file must contain a mapping of phrases to entries")
    # Allow files to nest entries under an "elements" key for readability.
    if "elements" in data and isinstance(data["elements"], Mapping):
        return dict(data["elements"])
    return dict(data)


@lru_cache(maxsize=None)
def _load_glossary(path: Path = _DEFAULT_DATA_FILE) -> Dict[str, GlossEntry]:
    raw = _load_raw(path)
    entries: Dict[str, GlossEntry] = {}
    for phrase, value in raw.items():
        normalised_phrase = " ".join(str(phrase).split())
        entry = _coerce_entry(normalised_phrase, value)
        if entry is None:
            continue
        entries[_normalise_key(normalised_phrase)] = entry
    return entries


def lookup(term: str, *, path: Optional[Path] = None) -> Optional[GlossEntry]:
    """Return the curated gloss entry for *term* if available."""

    if not term:
        return None
    glossary = _load_glossary(path or _DEFAULT_DATA_FILE)
    return glossary.get(_normalise_key(term))


__all__ = ["lookup", "GlossEntry"]
