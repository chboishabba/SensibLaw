import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main
from sensiblaw.db.dao import LegalSourceDAO, ensure_database
from src.ontology import enrichment as ontology_enrichment


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError()

    def json(self):
        return self._payload


def test_ontology_lookup_cli(monkeypatch, capsys):
    payload = [
        {"id": "a", "label": "Consent", "aliases": ["permission"]},
        {"id": "b", "label": "Consultation"},
    ]

    def fake_get(url, params=None):
        assert url == "https://ontology.test/lookup"
        assert params == {"q": "consent"}
        return _FakeResponse(payload)

    monkeypatch.setattr(cli_main.requests, "get", fake_get)

    cli_main.main(
        [
            "ontology",
            "lookup",
            "--term",
            "consent",
            "--url",
            "https://ontology.test/lookup",
            "--threshold",
            "0.5",
            "--limit",
            "1",
        ]
    )
    stdout = capsys.readouterr().out
    results = json.loads(stdout)
    assert results[0]["id"] == "a"
    assert results[0]["score"] >= 0.9


def test_ontology_concepts_enrich_cli_emits_provider_candidates(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "ontology.db"
    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("CONSENT", "Consent", "TOPIC", "seed"),
        )
        connection.commit()
    finally:
        connection.close()

    def fake_get(url, params=None, headers=None, timeout=None):
        if "wikidata.org" in url:
            assert params["search"] == "CONSENT"
            return _FakeResponse(
                {
                    "search": [
                        {
                            "id": "Q1",
                            "label": "Consent",
                            "description": "Consent concept",
                            "score": 0.91,
                        }
                    ]
                }
            )
        assert "dbpedia.org" in url
        return _FakeResponse(
            {
                "docs": [
                    {
                        "resource": ["http://dbpedia.org/resource/Consent"],
                        "label": ["Consent"],
                        "comment": ["Consent concept"],
                    }
                ]
            }
        )

    monkeypatch.setattr(ontology_enrichment.requests, "get", fake_get)

    out_path = tmp_path / "candidates.json"
    cli_main.main(
        [
            "ontology",
            "concepts-enrich",
            "--db",
            str(db_path),
            "--providers",
            "wikidata",
            "dbpedia",
            "--limit",
            "1",
            "--out",
            str(out_path),
        ]
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload[0]["code"] == "CONSENT"
    assert payload[0]["candidates"]["wikidata"][0]["external_id"] == "Q1"
    assert payload[0]["candidates"]["dbpedia"][0]["external_id"].endswith("/Consent")


def test_ontology_actors_enrich_cli_interactive_upsert(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "ontology.db"
    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", "Example Org"))
        connection.commit()
    finally:
        connection.close()

    def fake_get(url, params=None, headers=None, timeout=None):
        assert "wikidata.org" in url
        assert params["search"] == "Example Org"
        return _FakeResponse(
            {
                "search": [
                    {
                        "id": "Q123",
                        "label": "Example Org",
                        "description": "Example organization",
                        "score": 0.87,
                    }
                ]
            }
        )

    monkeypatch.setattr(ontology_enrichment.requests, "get", fake_get)
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")

    cli_main.main(
        [
            "ontology",
            "actors-enrich",
            "--db",
            str(db_path),
            "--providers",
            "wikidata",
            "--limit",
            "1",
            "--interactive",
        ]
    )
    capsys.readouterr()

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT provider, external_id FROM actor_external_refs ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("wikidata", "Q123")]


def test_ontology_upsert_cli(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    cli_main.main(
        [
            "ontology",
            "upsert",
            "--db",
            str(db_path),
            "--legal-system",
            "AU.COMMON",
            "--category",
            "STATUTE",
            "--citation",
            "[2024] HCA 99",
            "--title",
            "Sample Title",
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["citation"] == "[2024] HCA 99"

    connection = sqlite3.connect(db_path)
    try:
        dao = LegalSourceDAO(connection)
        record = dao.get_by_citation(
            legal_system_code="AU.COMMON", citation="[2024] HCA 99"
        )
        assert record
        assert record.title == "Sample Title"
    finally:
        connection.close()


def test_bridge_batch_emitter_roundtrips_into_external_refs_cli(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        actor_ids = {}
        for label in [
            "United Nations",
            "United Nations Security Council",
            "International Criminal Court",
            "International Court of Justice",
        ]:
            cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", label))
            actor_ids[label] = int(cur.lastrowid)
        connection.commit()
    finally:
        connection.close()

    anchor_map_path = tmp_path / "anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "institution:united_nations": {"actor_id": actor_ids["United Nations"]},
                "institution:united_nations_security_council": {
                    "actor_id": actor_ids["United Nations Security Council"]
                },
                "court:international_criminal_court": {
                    "actor_id": actor_ids["International Criminal Court"]
                },
                "court:international_court_of_justice": {
                    "actor_id": actor_ids["International Court of Justice"]
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    batch_path = tmp_path / "bridge_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            "UN inspectors briefed the United Nations Security Council while the ICC and ICJ were discussed.",
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
        ],
        check=True,
        cwd=str(ROOT),
    )

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["actor_external_refs"] == 4
    assert payload["concept_external_refs"] == 0

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT actor_id, provider, external_id FROM actor_external_refs ORDER BY actor_id, external_id"
        ).fetchall()
        assert {(row[0], row[1], row[2]) for row in rows} == {
            (actor_ids["United Nations"], "wikidata", "Q1065"),
            (actor_ids["United Nations Security Council"], "wikidata", "Q37470"),
            (actor_ids["International Criminal Court"], "wikidata", "Q47488"),
            (actor_ids["International Court of Justice"], "wikidata", "Q7801"),
        }
    finally:
        connection.close()


def test_ontology_bridge_import_and_report_cli(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "wikidata_bridge_bodies_gwb_v1.json"

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["slice_name"] == "seeded_body_refs_v1"
    assert payload["entity_count"] == 12

    cli_main.main(
        [
            "ontology",
            "bridge-report",
            "--db",
            str(db_path),
            "--slice-name",
            "seeded_body_refs_v1",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["slice_name"] == "seeded_body_refs_v1"
    assert report["entity_count"] == 12
    assert report["entities_by_kind"]["court_ref"] >= 5
    assert report["entities_by_kind"]["institution_ref"] >= 7


def test_ontology_bridge_report_includes_provider_and_duplicate_stats(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    cli_main.main(
        [
            "ontology",
            "bridge-report",
            "--db",
            str(db_path),
            "--slice-name",
            "prepopulation_core_refs_v1",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["entities_by_provider"] == {
        "austlii": 2,
        "dbpedia": 4,
        "hcourt_au": 2,
        "legislation_gov_au": 1,
        "nsw_legislation": 2,
        "nswlr": 1,
        "wikidata": 8,
    }
    assert report["entities_by_kind"]["jurisdiction_ref"] == 4
    assert report["entities_by_kind"]["organization_ref"] == 2
    assert report["entities_by_kind"]["case_ref"] == 6
    assert report["entities_by_kind"]["legislation_ref"] == 4
    assert report["duplicate_alias_count"] >= 1
    assert report["missing_external_url_count"] == 0
    assert report["duplicate_external_id_reuse"][0]["provider"] == "dbpedia"
    assert report["duplicate_external_id_reuse"][0]["external_id"] == "http://dbpedia.org/resource/Australia"


def test_bridge_batch_emitter_emits_multi_provider_actor_and_concept_rows(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = tmp_path / "multi_provider_bridge.json"
    bridge_file.write_text(
        json.dumps(
            {
                "slice": {
                    "name": "multi_provider_emit_v1",
                    "source_version": "test",
                    "policy_version": "entity_bridge_v1",
                    "notes": "test-only multi-provider bridge slice",
                },
                "entities": [
                    {
                        "canonical_ref": "institution:united_nations",
                        "canonical_kind": "institution_ref",
                        "provider": "wikidata",
                        "external_id": "Q1065",
                        "canonical_label": "United Nations",
                        "aliases": ["UN", "United Nations"],
                    },
                    {
                        "canonical_ref": "institution:united_nations",
                        "canonical_kind": "institution_ref",
                        "provider": "dbpedia",
                        "external_id": "http://dbpedia.org/resource/United_Nations",
                        "canonical_label": "United Nations",
                        "aliases": ["UN", "United Nations"],
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "multi_provider_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "multi_provider_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "institution:united_nations": {"actor_id": 101, "concept_code": "INTL_UN"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            "United Nations observers returned to the UN complex.",
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "multi_provider_emit_v1",
        },
    )
    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert payload["meta"]["coverage"]["resolved_bridge_refs"] == 1
    assert payload["meta"]["coverage"]["emitted_actor_rows"] == 2
    assert payload["meta"]["coverage"]["emitted_concept_rows"] == 2
    actor_refs = {(row["provider"], row["external_id"]) for row in payload["actor_external_refs"]}
    concept_refs = {(row["provider"], row["external_id"]) for row in payload["concept_external_refs"]}
    assert actor_refs == {
        ("wikidata", "Q1065"),
        ("dbpedia", "http://dbpedia.org/resource/United_Nations"),
    }
    assert concept_refs == actor_refs


def test_bridge_batch_emitter_resolves_au_branch_prepopulation_refs(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", "High Court of Australia"))
        hca_actor_id = int(cur.lastrowid)
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("PERSON", "Eddie Mabo"))
        mabo_actor_id = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_JURIS_COMMONWEALTH", "Commonwealth of Australia", "jurisdiction", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_MABO", "Mabo v Queensland (No 2)", "case", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_ACT_NATIVE_TITLE", "Native Title Act 1993", "legislation", "test"),
        )
        connection.commit()
    finally:
        connection.close()

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "au_branch_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "au_branch_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "case:mabo_v_queensland_no_2": {"concept_code": "AU_CASE_MABO"},
                "court:high_court_of_australia": {"actor_id": hca_actor_id},
                "jurisdiction:commonwealth_of_australia": {"concept_code": "AU_JURIS_COMMONWEALTH"},
                "legislation:native_title_act_1993": {"concept_code": "AU_ACT_NATIVE_TITLE"},
                "person:eddie_mabo": {"actor_id": mabo_actor_id},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "In Mabo v Queensland (No 2), Eddie Mabo and the High Court of Australia "
                "reframed native title in the Commonwealth of Australia under the Native Title Act 1993."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "prepopulation_core_refs_v1",
        },
    )

    batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch_payload["meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert batch_payload["meta"]["coverage"]["skipped_no_bridge_match"] == 0
    assert batch_payload["meta"]["coverage"]["skipped_no_anchor"] == 0
    assert batch_payload["meta"]["coverage"]["emitted_actor_rows"] == 3
    assert batch_payload["meta"]["coverage"]["emitted_concept_rows"] == 4

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["input_meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert payload["actor_external_refs"] == 3
    assert payload["concept_external_refs"] == 4


def test_bridge_batch_emitter_resolves_gwb_branch_refs_via_seeded_slice(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        actor_ids = {}
        for label in [
            "United States Senate",
            "United States House of Representatives",
            "United States Department of Defense",
            "Supreme Court of the United States",
            "Central Intelligence Agency",
        ]:
            cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", label))
            actor_ids[label] = int(cur.lastrowid)
        connection.commit()
    finally:
        connection.close()

    batch_path = tmp_path / "gwb_branch_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "gwb_branch_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "institution:u_s_house_of_representatives": {"actor_id": actor_ids["United States House of Representatives"]},
                "institution:u_s_senate": {"actor_id": actor_ids["United States Senate"]},
                "institution:united_states_department_of_defense": {"actor_id": actor_ids["United States Department of Defense"]},
                "court:u_s_supreme_court": {"actor_id": actor_ids["Supreme Court of the United States"]},
                "institution:central_intelligence_agency": {"actor_id": actor_ids["Central Intelligence Agency"]},
                "institution:nonexistent_review_target": {"actor_id": actor_ids["Central Intelligence Agency"]},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "The U.S. Senate and House of Representatives consulted the Department of Defense "
                "before the U.S. Supreme Court considered the matter."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
            "--record-receipts",
        ],
        check=True,
        cwd=str(ROOT),
        env={**os.environ, "ITIR_DB_PATH": str(db_path)},
    )

    batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch_payload["meta"]["coverage"]["resolved_bridge_refs"] == 4
    assert batch_payload["meta"]["coverage"]["skipped_no_bridge_match"] == 1
    assert batch_payload["meta"]["coverage"]["skipped_no_anchor"] == 0
    statuses = {
        (row["canonical_ref"], row["resolution_status"])
        for row in batch_payload["meta"]["match_receipts"]
    }
    assert ("institution:u_s_senate", "resolved") in statuses
    assert ("institution:central_intelligence_agency", "abstain_no_alias") in statuses
    assert ("institution:nonexistent_review_target", "abstain_no_bridge") in statuses

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["input_meta"]["coverage"]["resolved_bridge_refs"] == 4
    assert payload["input_meta"]["coverage"]["skipped_no_bridge_match"] == 1
    assert payload["input_meta"]["coverage"]["skipped_no_anchor"] == 0
    assert payload["actor_external_refs"] == 4
    assert payload["concept_external_refs"] == 0

    cli_main.main(
        [
            "ontology",
            "bridge-receipts-report",
            "--db",
            str(db_path),
        ]
    )
    receipt_payload = json.loads(capsys.readouterr().out)
    assert receipt_payload["ok"] is True
    assert receipt_payload["counts_by_status"]["resolved"] >= 4
    assert receipt_payload["counts_by_status"]["abstain_no_alias"] >= 1
    assert receipt_payload["counts_by_status"]["abstain_no_bridge"] >= 1


def test_gwb_bridge_receipts_remain_seeded_when_au_prepopulation_slice_is_also_imported(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    prepopulation_bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        actor_ids = {}
        for label in [
            "United States Senate",
            "United States House of Representatives",
            "United States Department of Defense",
            "Supreme Court of the United States",
        ]:
            cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", label))
            actor_ids[label] = int(cur.lastrowid)
        connection.commit()
    finally:
        connection.close()

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(prepopulation_bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "gwb_seeded_isolation_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "gwb_seeded_isolation_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "institution:u_s_house_of_representatives": {"actor_id": actor_ids["United States House of Representatives"]},
                "institution:u_s_senate": {"actor_id": actor_ids["United States Senate"]},
                "institution:united_states_department_of_defense": {"actor_id": actor_ids["United States Department of Defense"]},
                "court:u_s_supreme_court": {"actor_id": actor_ids["Supreme Court of the United States"]},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "The U.S. Senate and House of Representatives consulted the Department of Defense "
                "before the U.S. Supreme Court considered the matter."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
            "--record-receipts",
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "seeded_body_refs_v1",
        },
    )

    batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch_payload["meta"]["slice_name"] == "seeded_body_refs_v1"
    assert all(
        row["canonical_ref"].startswith(("institution:u_s_", "institution:united_states_", "court:u_s_"))
        for row in batch_payload["meta"]["match_receipts"]
        if row["resolution_status"] == "resolved"
    )

    cli_main.main(
        [
            "ontology",
            "bridge-receipts-report",
            "--db",
            str(db_path),
            "--slice-name",
            "seeded_body_refs_v1",
        ]
    )
    receipt_payload = json.loads(capsys.readouterr().out)
    assert receipt_payload["ok"] is True
    assert receipt_payload["slice_name"] == "seeded_body_refs_v1"
    assert receipt_payload["counts_by_status"]["resolved"] >= 4
    assert all(
        row["canonical_ref"].startswith(("institution:u_s_", "institution:united_states_", "court:u_s_"))
        for row in receipt_payload["receipts"]
        if row["resolution_status"] == "resolved"
    )


def test_bridge_batch_emitter_resolves_nsw_branch_refs_from_reviewed_slice(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", "High Court of Australia"))
        hca_actor_id = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_JURIS_NSW", "New South Wales", "jurisdiction", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_HOUSE", "House v The King", "case", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_LEPORE", "New South Wales v Lepore", "case", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_ACT_CLA_NSW", "Civil Liability Act 2002 (NSW)", "legislation", "test"),
        )
        connection.commit()
    finally:
        connection.close()

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "nsw_branch_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "nsw_branch_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "court:high_court_of_australia": {"actor_id": hca_actor_id},
                "jurisdiction:state_of_new_south_wales": {"concept_code": "AU_JURIS_NSW"},
                "case:house_v_the_king": {"concept_code": "AU_CASE_HOUSE"},
                "case:new_south_wales_v_lepore": {"concept_code": "AU_CASE_LEPORE"},
                "legislation:civil_liability_act_2002_nsw": {"concept_code": "AU_ACT_CLA_NSW"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "House v The King and New South Wales v Lepore were discussed in New South Wales "
                "while the High Court of Australia considered the Civil Liability Act 2002 (NSW)."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "prepopulation_core_refs_v1",
        },
    )

    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert payload["meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert payload["meta"]["coverage"]["skipped_no_bridge_match"] == 0
    assert payload["meta"]["coverage"]["skipped_no_anchor"] == 0
    assert payload["meta"]["coverage"]["emitted_actor_rows"] == 2
    assert payload["meta"]["coverage"]["emitted_concept_rows"] == 5

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
            "--dry-run",
        ]
    )
    upsert_payload = json.loads(capsys.readouterr().out)
    assert upsert_payload["ok"] is True
    assert upsert_payload["input_meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert upsert_payload["actor_external_refs"] == 2
    assert upsert_payload["concept_external_refs"] == 5


def test_bridge_batch_emitter_resolves_judicial_review_branch_refs_from_reviewed_slice(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", "High Court of Australia"))
        hca_actor_id = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_S157", "Plaintiff S157/2002 v Commonwealth of Australia", "case", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_ACT_MIGRATION", "Migration Act 1958", "legislation", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_ACT_NATIVE_TITLE_NSW", "Native Title (New South Wales) Act 1994", "legislation", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_JURIS_NSW", "New South Wales", "jurisdiction", "test"),
        )
        connection.commit()
    finally:
        connection.close()

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "judicial_review_branch_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "judicial_review_branch_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "case:plaintiff_s157_2002_v_commonwealth_of_australia": {"concept_code": "AU_CASE_S157"},
                "court:high_court_of_australia": {"actor_id": hca_actor_id},
                "legislation:migration_act_1958_cth": {"concept_code": "AU_ACT_MIGRATION"},
                "legislation:native_title_new_south_wales_act_1994": {"concept_code": "AU_ACT_NATIVE_TITLE_NSW"},
                "jurisdiction:state_of_new_south_wales": {"concept_code": "AU_JURIS_NSW"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "In Plaintiff S157/2002 v Commonwealth of Australia, the High Court held that the Migration Act 1958 "
                "privative clause could not block judicial review. Later, the Native Title (New South Wales) Act 1994 "
                "was challenged in New South Wales."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
            "--record-receipts",
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "prepopulation_core_refs_v1",
        },
    )

    batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch_payload["meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert batch_payload["meta"]["coverage"]["skipped_no_bridge_match"] == 0
    assert batch_payload["meta"]["coverage"]["skipped_no_anchor"] == 0
    assert batch_payload["meta"]["coverage"]["emitted_actor_rows"] == 2
    assert batch_payload["meta"]["coverage"]["emitted_concept_rows"] == 5
    statuses = {
        (row["canonical_ref"], row["resolution_status"])
        for row in batch_payload["meta"]["match_receipts"]
    }
    assert ("case:plaintiff_s157_2002_v_commonwealth_of_australia", "resolved") in statuses
    assert ("legislation:migration_act_1958_cth", "resolved") in statuses
    assert ("legislation:native_title_new_south_wales_act_1994", "resolved") in statuses

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["input_meta"]["coverage"]["resolved_bridge_refs"] == 5
    assert payload["actor_external_refs"] == 2
    assert payload["concept_external_refs"] == 5


def test_bridge_batch_emitter_resolves_liability_branch_refs_from_reviewed_slice(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    bridge_file = ROOT / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"

    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", "High Court of Australia"))
        hca_actor_id = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_INTROVIGNE", "Commonwealth v Introvigne", "case", "test"),
        )
        cur.execute(
            "INSERT INTO concepts(code, label, concept_type, source) VALUES (?,?,?,?)",
            ("AU_CASE_NAIDU", "Nationwide News Pty Ltd v Naidu", "case", "test"),
        )
        connection.commit()
    finally:
        connection.close()

    cli_main.main(
        [
            "ontology",
            "bridge-import",
            "--db",
            str(db_path),
            "--file",
            str(bridge_file),
        ]
    )
    capsys.readouterr()

    batch_path = tmp_path / "liability_branch_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    anchor_map_path = tmp_path / "liability_branch_anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "case:commonwealth_v_introvigne": {"concept_code": "AU_CASE_INTROVIGNE"},
                "case:nationwide_news_pty_ltd_v_naidu": {"concept_code": "AU_CASE_NAIDU"},
                "court:high_court_of_australia": {"actor_id": hca_actor_id},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            (
                "In Commonwealth v Introvigne and Nationwide News Pty Ltd v Naidu, the High Court of Australia "
                "considered vicarious liability and non-delegable duties."
            ),
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
            "--record-receipts",
        ],
        check=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            "ITIR_DB_PATH": str(db_path),
            "ITIR_WIKIDATA_BRIDGE_SLICE": "prepopulation_core_refs_v1",
        },
    )

    batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch_payload["meta"]["coverage"]["resolved_bridge_refs"] == 3
    assert batch_payload["meta"]["coverage"]["skipped_no_bridge_match"] == 0
    assert batch_payload["meta"]["coverage"]["skipped_no_anchor"] == 0
    assert batch_payload["meta"]["coverage"]["emitted_actor_rows"] == 2
    assert batch_payload["meta"]["coverage"]["emitted_concept_rows"] == 2
    statuses = {
        (row["canonical_ref"], row["resolution_status"])
        for row in batch_payload["meta"]["match_receipts"]
    }
    assert ("case:commonwealth_v_introvigne", "resolved") in statuses
    assert ("case:nationwide_news_pty_ltd_v_naidu", "resolved") in statuses

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["input_meta"]["coverage"]["resolved_bridge_refs"] == 3
    assert payload["actor_external_refs"] == 2
    assert payload["concept_external_refs"] == 2
