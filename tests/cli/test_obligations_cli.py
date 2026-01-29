import json
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src import cli  # noqa: E402
from src.obligation_projections import PROJECTION_SCHEMA_VERSION  # noqa: E402
from src.obligation_views import EXPLANATION_SCHEMA_VERSION  # noqa: E402


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()


def test_obligations_cli_emits_projections_and_explanations(monkeypatch, capsys):
    text = "The operator must keep records within 7 days."
    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "obligations",
            "--text",
            text,
            "--emit-projections",
            "actor",
            "timeline",
            "--emit-explanation",
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "obligations" in data
    assert "projections" in data
    assert data["projections"]["actor"]["version"] == PROJECTION_SCHEMA_VERSION
    assert data["projections"]["timeline"]["view"] == "timeline"
    assert data["explanations"]["version"] == EXPLANATION_SCHEMA_VERSION


def test_obligations_cli_alignment(monkeypatch, capsys, tmp_path):
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("The operator must keep records.")
    new.write_text("The operator must keep records.\nThe licence holder must notify on commencement.")

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "obligations",
            "--text-file",
            str(old),
            "--diff-text-file",
            str(new),
            "--emit-obligation-alignment",
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "obligation_alignment" in data
    assert data["obligation_alignment"]["added"]


def test_obligations_cli_activation(monkeypatch, capsys, tmp_path):
    text_file = tmp_path / "text.txt"
    facts_file = tmp_path / "facts.json"
    text_file.write_text("The licence holder must notify upon commencement.")
    facts_file.write_text(json.dumps({"version": "fact.envelope.v1", "facts": [{"key": "upon commencement", "value": True}]}))

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "obligations",
            "--text-file",
            str(text_file),
            "--simulate-activation",
            "--facts",
            str(facts_file),
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "obligation_activation" in data
    assert data["obligation_activation"]["active"]
