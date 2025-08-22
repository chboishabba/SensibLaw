"""HTML section diffing utilities.

This module provides a simple HTML redline generator that aligns sections
between two statute versions and highlights textual changes. Sections are
matched by normalised headings (stripping numbering and extra whitespace)
before computing word-level diffs.
"""
from __future__ import annotations

import html
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple


_heading_re = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")


def _normalise_heading(text: str) -> str:
    text = html.unescape(text)
    # remove leading numbering like "1", "1.", "1A" etc
    text = re.sub(r"^\s*\d+[A-Za-z]*[.)]?\s*", "", text)
    return " ".join(text.split())


def _split_sections(doc: str) -> Dict[str, Tuple[str, str]]:
    """Split an HTML document into sections keyed by normalised heading.

    Returns a mapping of section key to a tuple of (display heading, body).
    """
    sections: Dict[str, Tuple[str, str]] = {}
    pattern = re.compile(r"(<h[1-6][^>]*>.*?</h[1-6]>)(.*?)(?=<h[1-6][^>]*>|$)", re.I | re.S)
    for heading_html, body in pattern.findall(doc):
        heading = _heading_re.search(heading_html)
        if not heading:
            continue
        raw_heading = heading.group(1)
        display_heading = html.unescape(re.sub(r"<[^>]+>", "", raw_heading)).strip()
        key = _slugify(_normalise_heading(display_heading))
        body_text = html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        sections[key] = (display_heading, body_text)
    return sections


def _normalise_body(text: str) -> List[str]:
    # strip numbering at line starts and collapse whitespace
    lines = []
    for line in html.unescape(text).splitlines():
        line = re.sub(r"^\s*\d+[A-Za-z]*[.)]?\s*", "", line)
        lines.append(line.strip())
    normalised = " ".join(" ".join(lines).split())
    return normalised.split()


def _diff_words(old: str, new: str) -> str:
    old_words = _normalise_body(old)
    new_words = _normalise_body(new)
    sm = SequenceMatcher(None, old_words, new_words)
    parts: List[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(old_words[i1:i2]))
        elif tag == "delete":
            parts.append(f'<span class="del">{" ".join(old_words[i1:i2])}</span>')
        elif tag == "insert":
            parts.append(f'<span class="ins">{" ".join(new_words[j1:j2])}</span>')
        elif tag == "replace":
            parts.append(f'<span class="del">{" ".join(old_words[i1:i2])}</span>')
            parts.append(f'<span class="ins">{" ".join(new_words[j1:j2])}</span>')
    return " ".join(parts)


def redline(old: str, new: str, old_ref: str = "old", new_ref: str = "new") -> str:
    """Generate an HTML redline comparing two statute versions.

    Parameters
    ----------
    old, new:
        HTML strings for the old and new statute versions.
    old_ref, new_ref:
        Base URLs or paths used for section anchor links.
    """
    old_secs = _split_sections(old)
    new_secs = _split_sections(new)
    keys = sorted(set(old_secs) | set(new_secs))
    out: List[str] = ["<html><body>"]
    for key in keys:
        old_sec = old_secs.get(key, ("", ""))
        new_sec = new_secs.get(key, ("", ""))
        heading = old_sec[0] or new_sec[0] or key
        diff_html = _diff_words(old_sec[1], new_sec[1])
        out.append(f'<section id="{key}">')
        out.append(f"<h2>{heading}</h2>")
        out.append(
            f'<a href="{old_ref}#{key}">old</a> | <a href="{new_ref}#{key}">new</a>'
        )
        if diff_html:
            out.append(f"<p>{diff_html}</p>")
        out.append("</section>")
    out.append("</body></html>")
    return "\n".join(out)
