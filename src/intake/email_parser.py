from __future__ import annotations

import imaplib
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse


def fetch_messages(mailbox: str) -> List[EmailMessage]:
    """Fetch email messages from an IMAP server or local directory.

    The *mailbox* argument may be one of:
    - an ``imap://`` URL pointing to an IMAP server.  The URL may include
      username, password and mailbox path, e.g.
      ``imap://user:pass@host/INBOX``.
    - a filesystem path or ``file://`` URL pointing to a directory containing
      ``.eml`` files.  This mode is primarily used for tests.
    """

    parsed = urlparse(mailbox)
    scheme = parsed.scheme
    # Local directory mode for tests / offline use
    if scheme in {"", "file"}:
        directory = Path(parsed.path)
        messages: List[EmailMessage] = []
        for eml in sorted(directory.glob("*.eml")):
            with eml.open("rb") as f:
                msg = BytesParser(policy=policy.default).parse(f)
                messages.append(msg)
        return messages

    if scheme != "imap":
        raise ValueError(f"Unsupported mailbox scheme: {scheme}")

    host = parsed.hostname or "localhost"
    username = parsed.username or ""
    password = parsed.password or ""
    mailbox_name = parsed.path.lstrip("/") or "INBOX"

    with imaplib.IMAP4_SSL(host) as imap:
        if username:
            imap.login(username, password)
        imap.select(mailbox_name)
        typ, data = imap.search(None, "ALL")
        messages: List[EmailMessage] = []
        for num in data[0].split():
            typ, msg_data = imap.fetch(num, "(RFC822)")
            msg = BytesParser(policy=policy.default).parsebytes(msg_data[0][1])
            messages.append(msg)
        imap.logout()
    return messages


def _extract_fields(text: str, subject: str) -> Dict[str, str]:
    combined = subject + "\n" + text

    parties: List[str] = []
    m = re.search(r"Parties:\s*(.+)", combined, re.IGNORECASE)
    if m:
        parties = [p.strip() for p in re.split(r"[;,]", m.group(1)) if p.strip()]
    else:
        m = re.search(r"Case:\s*(.+)", combined, re.IGNORECASE)
        if m:
            case_line = m.group(1)
            m2 = re.search(r"(.+?)\s+v(?:s\.?|\.)?\s+(.+)", case_line, re.IGNORECASE)
            if m2:
                parties = [m2.group(1).strip(), m2.group(2).strip()]
    if not parties:
        m = re.search(r"(.+?)\s+v(?:s\.?|\.)?\s+(.+)", combined, re.IGNORECASE)
        if m:
            parties = [m.group(1).strip(), m.group(2).strip()]

    jurisdiction = ""
    m = re.search(r"Jurisdiction:\s*(.+)", combined, re.IGNORECASE)
    if m:
        jurisdiction = m.group(1).strip()
    else:
        m = re.search(r"\b(NSW|VIC|QLD|SA|WA|TAS|NT|ACT)\b", subject)
        if m:
            jurisdiction = m.group(1)

    summary = ""
    m = re.search(r"Summary:\s*(.+)", combined, re.IGNORECASE | re.DOTALL)
    if m:
        summary = m.group(1).strip()
    else:
        # Use first non-empty line as summary fallback
        for line in text.splitlines():
            line = line.strip()
            if line:
                summary = line
                break

    return {
        "parties": parties,
        "jurisdiction": jurisdiction,
        "summary": summary,
    }


def parse_email(msg: EmailMessage) -> Dict[str, str]:
    """Parse an ``EmailMessage`` into structured data."""
    if msg.is_multipart():
        parts: List[str] = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                parts.append(payload.decode(charset, errors="ignore"))
        body = "\n".join(parts)
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="ignore") if payload else ""

    subject = msg.get("Subject", "")
    return _extract_fields(body, subject)
