from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.materialize_wikidata_migration_pack import (
    _discover_qid_rows,
    _load_qids_from_file,
    _resolve_qid_rows,
)


def test_load_qids_from_file_supports_text_lines(tmp_path: Path) -> None:
    path = tmp_path / "qids.txt"
    path.write_text("Q1\n# comment\nQ2, Q3\n", encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2", "Q3"]


def test_load_qids_from_file_supports_json_array(tmp_path: Path) -> None:
    path = tmp_path / "qids.json"
    path.write_text(json.dumps(["Q1", "Q2"]), encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2"]


def test_resolve_qid_rows_merges_explicit_file_and_discovered(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "qids.txt"
    path.write_text("Q2\nQ3\n", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._discover_qid_rows",
        lambda **_: [
            {"qid": "Q3", "label": "Q3", "source": "discovered"},
            {"qid": "Q4", "label": "Item 4", "source": "discovered"},
        ],
    )

    args = argparse.Namespace(
        qid=["Q1", "Q2"],
        qid_file=path,
        discover_qids=True,
        source_property="P5991",
        candidate_limit=5,
        query_timeout=60,
    )

    assert _resolve_qid_rows(args) == [
        {"qid": "Q1", "label": "Q1", "source": "explicit"},
        {"qid": "Q2", "label": "Q2", "source": "explicit"},
        {"qid": "Q3", "label": "Q3", "source": "file"},
        {"qid": "Q4", "label": "Item 4", "source": "discovered"},
    ]


def test_discover_qid_rows_parses_sparql_bindings(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._fetch_json",
        lambda *args, **kwargs: {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q10"},
                        "itemLabel": {"value": "Thing 10"},
                        "statementCount": {"value": "2"},
                        "qualifierCount": {"value": "4"},
                    }
                ]
            }
        },
    )

    assert _discover_qid_rows(
        source_property="P5991",
        candidate_limit=5,
        timeout_seconds=30,
    ) == [
        {
            "qid": "Q10",
            "label": "Thing 10",
            "statement_count": 2,
            "qualifier_count": 4,
            "source": "discovered",
        }
    ]


def test_parse_args_accepts_optional_openrefine_csv(monkeypatch, tmp_path: Path) -> None:
    out_dir = tmp_path / "pack"
    csv_path = tmp_path / "pack.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "materialize_wikidata_migration_pack.py",
            "--qid",
            "Q1",
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--out-dir",
            str(out_dir),
            "--openrefine-csv",
            str(csv_path),
        ],
    )
    from scripts.materialize_wikidata_migration_pack import _parse_args

    args = _parse_args()
    assert args.openrefine_csv == csv_path
