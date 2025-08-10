import json
import logging
import re
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

try:  # pragma: no cover - optional dependency
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from .models import Document, DocumentMetadata, Provision

logger = logging.getLogger(__name__)

# Base directory for storing downloaded data
BASE_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "austlii"
JUDGMENT_DIR = BASE_DATA_DIR / "judgments"
LEGISLATION_DIR = BASE_DATA_DIR / "legislation"

# Ensure the directories exist at import time so that users of the client do
# not need to worry about creating them manually.
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
        if requests is not None:
            self.session = requests.Session()
            # A descriptive user agent is polite when accessing free services.
            self.session.headers.update(
                {"User-Agent": "SensibLawBot/0.1 (+https://github.com/)"}
            )
        else:  # pragma: no cover - requests missing in minimal environments
            self.session = None

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------
    def _get(self, url: str) -> Any:
        """Perform a GET request with very simple retry logic."""
        if self.session is None:
            raise RuntimeError("requests library is required for network operations")

        attempt = 0
        while True:
            try:
                logger.debug("Fetching %s", url)
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except Exception as exc:
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
        root = ET.fromstring(response.content)
        entries: List[Dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = item.findtext("title", default="")
            link = item.findtext("link", default="")
            entries.append({"title": title, "link": link})
        return entries

    def fetch_judgment(self, url: str) -> Document:
        """Download, parse, and persist a judgment page from AustLII."""

        logger.info("Fetching judgment %s", url)
        response = self._get(url)
        doc = self.parse_document(url, response.content)
        filename = JUDGMENT_DIR / f"{doc.metadata.canonical_id}.json"
        self._write_json(filename, doc.to_dict())
        return doc

    def fetch_legislation(self, url: str) -> Document:
        """Download, parse, and persist a legislation page from AustLII."""

        logger.info("Fetching legislation %s", url)
        response = self._get(url)
        doc = self.parse_document(url, response.content)
        filename = LEGISLATION_DIR / f"{doc.metadata.canonical_id}.json"
        self._write_json(filename, doc.to_dict())
        return doc

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def parse_document(self, url: str, content: bytes | str) -> Document:
        """Parse an AustLII HTML page into a :class:`Document`."""

        html = content.decode("utf-8") if isinstance(content, bytes) else content

        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"<.*?>", "", title_match.group(1)).strip() if title_match else ""

        date_match = re.search(
            r"<span[^>]*class=['\"]date['\"][^>]*>(.*?)</span>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if date_match:
            try:
                doc_date = datetime.fromisoformat(
                    re.sub(r"<.*?>", "", date_match.group(1)).strip()
                ).date()
            except ValueError:
                doc_date = date.today()
        else:
            doc_date = date.today()

        section_pattern = re.compile(
            r"<(?:p|div|li)[^>]*>(\d+(?:\.\d+)*)\s+([^<]+)</(?:p|div|li)>",
            re.IGNORECASE,
        )
        sections = section_pattern.findall(html)

        provisions = self._build_hierarchy(sections)
        body = "\n".join([f"{num} {txt}" for num, txt in sections])
        canonical_id = self._slugify(title) or str(int(time.time()))
        metadata = DocumentMetadata(
            jurisdiction="AU",
            citation=title,
            date=doc_date,
            canonical_id=canonical_id,
            provenance=url,
        )
        return Document(metadata=metadata, body=body, provisions=provisions)

    @staticmethod
    def _build_hierarchy(sections: List[tuple[str, str]]) -> List[Provision]:
        """Build a hierarchy of :class:`Provision` objects from numbered sections."""

        root: List[Provision] = []
        stack: List[tuple[int, List[Provision]]] = [(0, root)]
        for num, text in sections:
            level = num.count(".") + 1
            prov = Provision(text=text, identifier=num)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack[-1][1].append(prov)
            stack.append((level, prov.children))
        return root

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
