"""Helpers for consolidating glossary links across structured data."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Protocol

from src.glossary.service import GlossEntry
from src.models.provision import GlossaryLink


class GlossaryRegistryProtocol(Protocol):
    """Subset of :class:`GlossaryRegistry` used for linking."""

    def register_definition(
        self,
        term: str,
        definition: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        ...

    def resolve(self, term: Optional[str]) -> Optional[Any]:
        ...


def _clone_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if metadata is None:
        return None
    return dict(metadata)


def _normalise_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return " ".join(value.strip().split()).lower() or None

class GlossaryLinker:
    """Deduplicate glossary lookups and return shared link instances."""

    def __init__(self, registry: Optional[GlossaryRegistryProtocol] = None):
        self._registry = registry
        self._links: Dict[str, GlossaryLink] = {}

    def link(
        self,
        *,
        candidates: Iterable[Optional[str]] = (),
        glossary_entry: Optional[GlossEntry] = None,
        fallback_text: Optional[str] = None,
        fallback_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[GlossaryLink]:
        """Return a shared glossary link for the supplied inputs."""

        record = None
        if self._registry is not None and glossary_entry is not None:
            record = self._registry.register_definition(
                glossary_entry.phrase,
                glossary_entry.text,
                glossary_entry.metadata,
            )

        if record is None and self._registry is not None:
            for candidate in candidates:
                if not candidate:
                    continue
                record = self._registry.resolve(candidate)
                if record is not None:
                    break

        text: Optional[str] = None
        metadata: Optional[Dict[str, Any]] = None
        glossary_id: Optional[int] = None
        cache_key: Optional[str] = None

        if record is not None:
            text = getattr(record, "definition", None)
            metadata = _clone_metadata(getattr(record, "metadata", None))
            glossary_id = getattr(record, "id", None)
            cache_key = f"id:{glossary_id}"
        elif glossary_entry is not None:
            text = glossary_entry.text
            metadata = _clone_metadata(glossary_entry.metadata)
            cache_key = f"entry:{_normalise_text(glossary_entry.text)}"
        else:
            text = fallback_text
            metadata = _clone_metadata(fallback_metadata)
            normalised = _normalise_text(text)
            cache_key = f"text:{normalised}" if normalised is not None else None

        if text is None and glossary_id is None:
            return None

        if cache_key is not None and cache_key in self._links:
            link = self._links[cache_key]
            if text is not None:
                link.text = text
            if metadata is not None:
                link.metadata = _clone_metadata(metadata)
            if glossary_id is not None:
                link.glossary_id = glossary_id
            return link

        link = GlossaryLink(
            text=text,
            metadata=_clone_metadata(metadata),
            glossary_id=glossary_id,
        )
        if cache_key is not None:
            self._links[cache_key] = link
        return link


__all__ = ["GlossaryLinker"]
