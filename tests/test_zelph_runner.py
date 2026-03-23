from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.zelph_runner import main


def _derived(payload: dict) -> list[dict[str, str]]:
    return payload["engine"]["derived_triples"]


def test_zelph_runner_bundle_mode_derives_expected_triples(tmp_path, capsys) -> None:
    bundle_path = tmp_path / "bundle.zlp"
    bundle_path.write_text(
        "\n".join(
            [
                'rev_1 "by user" "Sentinel33"',
                'rev_1 "has comment lexeme" "reverted"',
                '(R "has comment lexeme" "reverted") => (R "signal_class" "reversion_edit")',
                '(R "by user" U, R "signal_class" "reversion_edit") => (U "is" "wiki sentinel")',
                'R "signal_class" "reversion_edit"',
                'U "is" "wiki sentinel"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["bundle", "--bundle-path", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["engine"]["status"] == "ok"
    assert {"subject": "rev_1", "predicate": "signal_class", "object": "reversion_edit"} in _derived(payload)
    assert {"subject": "Sentinel33", "predicate": "is", "object": "wiki sentinel"} in _derived(payload)


def test_zelph_runner_db_mode_compiles_and_runs_queries(tmp_path, capsys) -> None:
    db_path = tmp_path / "ingest.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE rule_atoms (doc_id TEXT, stable_id TEXT, party TEXT, role TEXT, modality TEXT, action TEXT, scope TEXT)"
    )
    conn.execute(
        "INSERT INTO rule_atoms VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("d1", "s1", "party1", "role1", "modality.must", "action1", "scope1"),
    )
    conn.commit()
    conn.close()

    exit_code = main(["db", "--db-path", str(db_path), "--save-bundle-path", str(tmp_path / "db_bundle.zlp")])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["compile"]["returncode"] == 0
    assert payload["engine"]["status"] == "ok"
    assert Path(payload["engine"]["bundle_path"]).exists()
    assert {"subject": "party1", "predicate": "has obligation", "object": "db_atom_0"} in _derived(payload)


def test_zelph_runner_text_mode_builds_programmatic_wiki_fixture(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "text",
            "--title",
            "Slip and fall",
            "--revid",
            "999",
            "--user",
            "BD2412",
            "--comment",
            "Reverted archive vandalism",
            "--save-bundle-path",
            str(tmp_path / "wiki_bundle.zlp"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["lex"]["returncode"] == 0
    assert payload["engine"]["status"] == "ok"
    assert Path(payload["engine"]["bundle_path"]).exists()
    assert {"subject": "BD2412", "predicate": "is", "object": "wiki sentinel"} in _derived(payload)
