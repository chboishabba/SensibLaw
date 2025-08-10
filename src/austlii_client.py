import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Base directory for storing downloaded data
BASE_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "austlii"
JUDGMENT_DIR = BASE_DATA_DIR / "judgments"
LEGISLATION_DIR = BASE_DATA_DIR / "legislation"

for directory in (JUDGMENT_DIR, LEGISLATION_DIR):
    directory.mkdir(parents=True, exist_ok=True)


class AustLIIClient:
    """Simple client for interacting with the AustLII website or API.

    This client respects AustLII's terms of use by keeping requests minimal
    and providing a user agent string. It also includes very small retry
    logic so transient network failures do not cause the process to stop.
    """

    def __init__(
        self,
        base_url: str = "https://www.austlii.edu.au",
        timeout: int = 10,
        max_retries: int = 3,
        backoff: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.session = requests.Session()
        # A descriptive user agent is polite when accessing free services.
        self.session.headers.update(
            {"User-Agent": "SensibLawBot/0.1 (+https://github.com/)"}
        )

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------
    def _get(self, url: str) -> requests.Response:
        """Perform a GET request with very simple retry logic."""
        attempt = 0
        while True:
            try:
                logger.debug("Fetching %s", url)
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                attempt += 1
                logger.warning(
                    "Error fetching %s (attempt %s/%s): %s",
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.backoff * attempt)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------
    def fetch_rss(self, feed_url: str) -> List[Dict[str, Any]]:
        """Fetch and parse an AustLII RSS feed.

        Parameters
        ----------
        feed_url:
            URL pointing to the RSS feed.

        Returns
        -------
        A list of dictionaries containing the title and link for each entry.
        """

        logger.info("Fetching RSS feed %s", feed_url)
        response = self._get(feed_url)
        soup = BeautifulSoup(response.content, "xml")
        entries: List[Dict[str, Any]] = []
        for item in soup.find_all("item"):
            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""
            entries.append({"title": title, "link": link})
        return entries

    def fetch_judgment(self, url: str) -> Dict[str, Any]:
        """Download and parse a judgment page from AustLII.

        The extracted title and raw text are written to a JSON file within
        ``data/austlii/judgments`` and returned as a dictionary.
        """

        logger.info("Fetching judgment %s", url)
        response = self._get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
        text = soup.get_text(" ", strip=True)
        data = {"url": url, "title": title, "text": text}
        filename = JUDGMENT_DIR / f"{self._slugify(title) or int(time.time())}.json"
        self._write_json(filename, data)
        return data

    def fetch_legislation(self, url: str) -> Dict[str, Any]:
        """Download and parse a legislation page from AustLII.

        The extracted title and raw text are written to a JSON file within
        ``data/austlii/legislation`` and returned as a dictionary.
        """

        logger.info("Fetching legislation %s", url)
        response = self._get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
        text = soup.get_text(" ", strip=True)
        data = {"url": url, "title": title, "text": text}
        filename = LEGISLATION_DIR / f"{self._slugify(title) or int(time.time())}.json"
        self._write_json(filename, data)
        return data

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write *data* to *path* in JSON format."""
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    @staticmethod
    def _slugify(text: str) -> str:
        """Return a filesystem-friendly slug for *text*."""
        import re

        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        return re.sub(r"[-\s]+", "-", text)
