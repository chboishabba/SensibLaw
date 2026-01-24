from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring, parse

DB_PATH = Path(os.environ.get("LEDGER_DB", "corrections.db"))
FEED_PATH = Path(os.environ.get("LEDGER_FEED", "corrections/feed.atom"))


def build_feed() -> None:
    """Build an Atom feed of corrections ordered by insertion."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT node_id, before_hash, after_hash, reason, reporter, prev_hash, this_hash FROM corrections ORDER BY rowid"
        ).fetchall()

    feed = Element("feed", xmlns="http://www.w3.org/2005/Atom")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    SubElement(feed, "title").text = "Corrections"
    SubElement(feed, "updated").text = now
    SubElement(feed, "id").text = "urn:sensiblaw:corrections"

    for row in rows:
        entry = SubElement(feed, "entry")
        SubElement(entry, "id").text = row["this_hash"]
        SubElement(entry, "title").text = f"Correction for {row['node_id']}"
        SubElement(entry, "updated").text = now
        body = "|".join(
            [
                row["node_id"],
                row["before_hash"],
                row["after_hash"],
                row["reason"],
                row["reporter"],
                row["prev_hash"] or "",
            ]
        )
        SubElement(entry, "content").text = body

    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEED_PATH.write_bytes(tostring(feed, encoding="utf-8", xml_declaration=True))


def verify_feed(path: Path | None = None) -> None:
    """Verify that each entry's ``prev_hash`` matches the previous entry.

    Raises:
        ValueError: If a ``prev_hash`` does not match the prior ``entry``'s ``id``.
    """

    feed_file = path or FEED_PATH
    tree = parse(feed_file)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    prev_id = None
    for entry in tree.findall("atom:entry", ns):
        entry_id = entry.findtext("atom:id", namespaces=ns)
        content = entry.findtext("atom:content", namespaces=ns) or ""
        prev_hash = content.split("|")[-1]
        if prev_id and prev_hash != prev_id:
            raise ValueError("hash chain integrity error")
        prev_id = entry_id
