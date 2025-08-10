import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from ..austlii_client import AustLIIClient
except Exception:  # requests may be unavailable during tests
    AustLIIClient = None


def fetch_from_austlii(source: Dict[str, Any]) -> str:
    """Placeholder fetcher for AustLII sources.

    A real implementation would download data via :class:`AustLIIClient`.
    Here we simply initialise the client to demonstrate the hook.
    """

    if AustLIIClient is not None:
        AustLIIClient(base_url=source.get("base_url", "https://www.austlii.edu.au"))
    return "austlii"


def fetch_pdf(source: Dict[str, Any]) -> str:
    """Placeholder PDF fetcher."""

    # Actual PDF handling would extract content using ``pdf_ingest``.
    return "pdf"


def fetch_official_register(source: Dict[str, Any]) -> str:
    """Placeholder fetcher for official register HTML sources."""

    return "official"


class SourceDispatcher:
    """Dispatch ingestion tasks based on ``foundation_sources.json`` config."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        data = json.loads(config_path.read_text())
        self.sources: List[Dict[str, Any]] = data.get("sources", [])

    # ------------------------------------------------------------------
    def _throttle(self, source: Dict[str, Any]) -> None:
        throttle = source.get("throttle", {})
        delay = throttle.get("crawl_delay_sec")
        if delay is None and throttle.get("respect_robots"):
            delay = 1
        if delay:
            time.sleep(delay)

    # ------------------------------------------------------------------
    def dispatch(self, names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Process configured sources.

        Parameters
        ----------
        names:
            Optional list of source names to restrict processing to.
        """

        results: List[Dict[str, Any]] = []
        for source in self.sources:
            if names and source["name"] not in names:
                continue
            self._throttle(source)
            fetchers: List[str] = []
            base_url = source.get("base_url", "")
            formats = [f.upper() for f in source.get("formats", [])]

            if "AUSTLII.EDU.AU" in base_url.upper():
                fetchers.append(fetch_from_austlii(source))
            else:
                if any("HTML" in f for f in formats):
                    fetchers.append(fetch_official_register(source))
                if "PDF" in formats:
                    fetchers.append(fetch_pdf(source))
            results.append({"name": source["name"], "fetchers": fetchers})
        return results
