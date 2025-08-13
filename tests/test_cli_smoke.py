import os
import subprocess
from pathlib import Path


def run_sensiblaw(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "fastapi.py").write_text(
        "class HTTPException(Exception):\n"
        "    def __init__(self, status_code: int, detail: str):\n"
        "        self.status_code = status_code\n"
        "        self.detail = detail\n"
        "class APIRouter:\n"
        "    def __init__(self):\n"
        "        pass\n"
        "    def get(self, *a, **k):\n"
        "        def deco(fn):\n"
        "            return fn\n"
        "        return deco\n"
        "    def post(self, *a, **k):\n"
        "        def deco(fn):\n"
        "            return fn\n"
        "        return deco\n"
        "def Query(*a, **k):\n"
        "    return None\n"
    )
    (stubs / "pydantic.py").write_text(
        "class BaseModel:\n"
        "    pass\n"
        "def Field(default, **kwargs):\n"
        "    return default\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{stubs}:{env.get('PYTHONPATH', '')}"
    cmd = ["python", "-m", "src.cli", *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_concepts_match_requires_patterns(tmp_path: Path):
    completed = run_sensiblaw(tmp_path, "concepts", "match")
    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr


def test_graph_subgraph_unreadable_graph_file(tmp_path: Path):
    graph_file = tmp_path / "graph.json"
    graph_file.write_text("{}")
    graph_file.chmod(0)
    completed = run_sensiblaw(
        tmp_path,
        "graph",
        "subgraph",
        "--graph-file",
        str(graph_file),
        "--seed",
        "seed",
    )
    assert completed.returncode != 0
    assert "--graph-file" in completed.stderr or "unrecognized arguments" in completed.stderr


def test_tests_run_missing_tests_file(tmp_path: Path):
    story = tmp_path / "story.json"
    story.write_text("{}")
    completed = run_sensiblaw(
        tmp_path,
        "tests",
        "run",
        "--tests-file",
        "missing.json",
        "--ids",
        "t1",
        "--story",
        str(story),
    )
    assert completed.returncode != 0
    assert "--tests-file" in completed.stderr


def test_tests_run_missing_story_file(tmp_path: Path):
    missing_story = tmp_path / "missing.json"
    completed = run_sensiblaw(
        tmp_path,
        "tests",
        "run",
        "--ids",
        "t1",
        "--story",
        str(missing_story),
    )
    assert completed.returncode != 0
    assert "No such file" in completed.stderr or "No such file or directory" in completed.stderr
