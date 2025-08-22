import json
from pathlib import Path

from src.harm.index import compute_harm


def test_delay_increases_score(tmp_path: Path) -> None:
    low = {"delay_months": 1, "lost_evidence_items": 0, "flags": []}
    high = {"delay_months": 6, "lost_evidence_items": 0, "flags": []}

    assert compute_harm(high)["score"] > compute_harm(low)["score"]


def test_cli_compute(tmp_path: Path) -> None:
    story = {"delay_months": 4, "lost_evidence_items": 1, "flags": ["intimidation"]}
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps(story))

    from subprocess import run, PIPE

    result = run(
        ["python", "-m", "src.cli", "harm", "compute", "--story", str(story_path)],
        stdout=PIPE,
        check=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert data["level"] in {"Low", "Medium", "High"}
