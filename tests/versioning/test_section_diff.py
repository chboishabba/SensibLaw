import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.versioning.section_diff import redline


def test_only_changed_spans():
    old = (ROOT / "tests/fixtures/statute_v1.html").read_text()
    new = (ROOT / "tests/fixtures/statute_v2.html").read_text()

    html = redline(old, new, old_ref="old.html", new_ref="new.html")

    assert '<span class="del">2020' in html
    assert '<span class="ins">2021' in html

    match = re.search(
        r"<h2>Section 2 - Purpose</h2>.*?<p>(.*?)</p>", html, re.S
    )
    assert match is not None
    body = match.group(1)
    assert "<span" not in body
