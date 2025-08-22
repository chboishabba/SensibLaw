import json
import json
import subprocess
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.storage import TextIndex


def setup_index(tmp_path: Path) -> str:
    db = tmp_path / "search.db"
    index = TextIndex(str(db))
    index.index_node("case1", "case", "A case about a dog and a cat")
    index.index_node("prov1", "provision", "Provision related to dogs and animals")
    index.index_node("ext1", "extrinsic", "Debate mentioning the dog policy")
    index.index_node("story1", "story", "Story of the dog in the law")
    index.close()
    return str(db)


def test_text_index_search(tmp_path: Path):
    db_path = setup_index(tmp_path)
    index = TextIndex(db_path)
    results = index.search("dog")
    types = {r["type"] for r in results}
    assert types == {"case", "provision", "extrinsic", "story"}
    for r in results:
        assert r["subgraph"]["nodes"][0]["id"] == r["id"]
        assert r["subgraph"]["edges"] == []
    index.close()


def test_cli_search(tmp_path: Path):
    db_path = setup_index(tmp_path)
    cmd = ["python", "-m", "src.cli", "search", "dog", "--db", db_path]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    assert any(r["type"] == "case" for r in data)
