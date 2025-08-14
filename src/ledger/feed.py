from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

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
    now = datetime.utcnow().isoformat() + "Z"
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
