"""Wiki timeline ingestion/extraction helpers.

This package is intentionally small: wiki timeline extraction scripts emit JSON
artifacts for UI/fixtures, but canonical persistence is DB-first (SQLite) per
`docs/wiki_timeline_storage_contract.md`.
"""

from .sqlite_store import persist_wiki_timeline_aoo_run  # noqa: F401

