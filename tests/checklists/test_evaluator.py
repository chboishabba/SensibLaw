import json
from pathlib import Path

from src.checklists.run import evaluate


BASE = Path(__file__).parent


def load(name: str):
    return json.loads((BASE / f"{name}.json").read_text())


def test_basic_pass_and_fail():
    checklist = load("basic")
    tags_pass = {"a", "b"}
    tags_fail = {"a"}
    res_pass = evaluate(checklist, tags_pass)
    res_fail1 = evaluate(checklist, tags_fail)
    res_fail2 = evaluate(checklist, tags_fail)
    assert res_pass["passed"] is True
    assert res_fail1 == res_fail2  # deterministic
    assert res_fail1["passed"] is False
    factors = {f["id"]: f["passed"] for f in res_fail1["factors"]}
    assert factors["has_a"] is True
    assert factors["has_b"] is False


def test_any_or_logic():
    checklist = load("any")
    tags = {"y"}
    result = evaluate(checklist, tags)
    assert result["passed"] is True
    factors = {f["id"]: f["passed"] for f in result["factors"]}
    assert factors["has_x"] is False
    assert factors["has_y"] is True
