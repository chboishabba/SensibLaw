import json
import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.concepts import ConceptMatcher


def test_concept_matcher_basic():
    matcher = ConceptMatcher()
    text = "Hello dog, hi there"
    hits = matcher.match(text)
    found = {(h.concept_id, text[h.start:h.end].lower()) for h in hits}
    assert ("greeting", "hello") in found
    assert ("greeting", "hi") in found
    assert ("animal", "dog") in found


def test_concepts_cli():
    cmd = [
        "python",
        "-m",
        "src.cli",
        "concepts",
        "match",
        "--text",
        "Hello dog, hi there",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    ids = {d["concept_id"] for d in data}
    assert {"greeting", "animal"} <= ids

