from __future__ import annotations

import logging
from datetime import date
from typing import List

from ..austlii_client import AustLIIClient
from ..storage import VersionedStore

logger = logging.getLogger(__name__)


class AustLIIActAdapter:
    """Adapter for fetching legislation sections from AustLII."""

    def __init__(self, client: AustLIIClient, store: VersionedStore) -> None:
        self.client = client
        self.store = store

    # ------------------------------------------------------------------
    def fetch_act(self, base_url: str, sections: List[str]) -> List[str]:
        """Fetch table, notes and specified sections of an Act.

        Parameters
        ----------
        base_url:
            Base URL to the Act on AustLII without the trailing section file.
        sections:
            List of section identifiers such as ``["s5", "s223"]``.

        Returns
        -------
        List of canonical IDs for the fetched sections.
        """

        canonical_ids: List[str] = []

        # Fetch table and notes pages if available
        for extra in ("table", "notes"):
            url = f"{base_url}/{extra}.html"
            try:
                doc = self.client.fetch_legislation(url)
            except Exception as exc:  # pragma: no cover - network issues
                logger.warning("Failed to fetch %s: %s", url, exc)
                continue
            doc_id = self.store.generate_id()
            self.store.add_revision(doc_id, doc, date.today())

        for sec in sections:
            url = f"{base_url}/{sec}.html"
            doc = self.client.fetch_legislation(url)
            doc_id = self.store.generate_id()
            self.store.add_revision(doc_id, doc, date.today())
            canonical_ids.append(doc.metadata.canonical_id or sec)

        return canonical_ids
