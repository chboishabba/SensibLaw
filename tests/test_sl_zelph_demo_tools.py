import subprocess
import sys
import sqlite3
import json
import os
from pathlib import Path
import pytest

# Path to the demo tools
DEMO_DIR = Path(__file__).parent.parent / "sl_zelph_demo"
PYTHON_EXE = sys.executable

def test_compile_db_smoke(tmp_path):
    # Create a mock database
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE rule_atoms (doc_id TEXT, stable_id TEXT, party TEXT, role TEXT, modality TEXT, action TEXT, scope TEXT)")
    conn.execute("INSERT INTO rule_atoms VALUES ('d1', 's1', 'party1', 'role1', 'modality.must', 'action1', 'scope1')")
    conn.commit()
    conn.close()

    output_zlp = tmp_path / "output.zlp"
    script_path = DEMO_DIR / "compile_db.py"

    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(db_path), str(output_zlp)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Successfully exported" in result.stdout
    assert output_zlp.exists()
    content = output_zlp.read_text()
    
    # Verify Zelph atom format
    assert 'db_atom_0 "from document" doc_d1' in content
    assert 'db_atom_0 "has modality" "modality.must"' in content
    
    # Verify hardcoded rules exist
    assert "=> (P \"has obligation\" A)" in content
    assert "=> (P \"has permission\" A)" in content
    
    # Verify queries exist
    assert 'P "has obligation" A' in content
    assert 'P "has permission" A' in content

def test_wikidata_extract_smoke(tmp_path):
    input_txt = tmp_path / "input.txt"
    input_txt.write_text("Alice slipped at Woolworths.")
    
    script_path = DEMO_DIR / "wikidata_extract.py"
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(input_txt)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "extracted structured facts" in result.stdout
    
    output_json = tmp_path / "wikidata_sl_output.json"
    assert output_json.exists()
    data = json.loads(output_json.read_text())
    assert "facts" in data
    assert "wikidata_enrichment" in data
    assert data["wikidata_enrichment"][0]["entity"] == "woolworths"
    # Deeper assertions
    assert data["facts"][0]["event_id"] == "slip_event"
    assert data["wikidata_enrichment"][0]["properties"][0]["value_label"] == "supermarket"

def test_sl_extract_smoke(tmp_path):
    input_txt = tmp_path / "input.txt"
    input_txt.write_text("Alice slipped on a wet floor.")
    
    script_path = DEMO_DIR / "sl_extract.py"
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(input_txt)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "extracted structured facts" in result.stdout
    
    output_json = tmp_path / "sl_output.json"
    assert output_json.exists()
    data = json.loads(output_json.read_text())
    assert len(data["facts"]) == 6
    assert data["facts"][0]["id"] == "f1"

def test_lex_to_zelph_smoke(tmp_path):
    wiki_json = tmp_path / "wiki.json"
    wiki_json.write_text(json.dumps({
        "title": "Slip and fall",
        "rows": [
            {"revid": "123", "user": "Alice", "comment": "Fixed typo"}
        ]
    }))
    
    output_zlp = tmp_path / "wiki.zlp"
    script_path = DEMO_DIR / "lex_to_zelph.py"
    
    # We need to make sure src is in PYTHONPATH because lex_to_zelph.py imports from it
    env = {**os.environ, "PYTHONPATH": str(DEMO_DIR.parent / "src")}
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(wiki_json), str(output_zlp)],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0
    assert "Successfully lexed" in result.stdout
    assert output_zlp.exists()
    assert output_zlp.exists()
    content = output_zlp.read_text()
    assert 'rev_123 "is a" "wikipedia revision"' in content
    assert 'lex_7479706f "has text" "typo"' in content

def test_wikidata_extract_missing_file(tmp_path):
    script_path = DEMO_DIR / "wikidata_extract.py"
    missing_file = tmp_path / "nonexistent.txt"
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(missing_file)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0
    assert "File not found" in result.stdout

def test_compile_ontology_smoke(tmp_path):
    # Use existing data from SensibLaw/data/ontology
    ontology_dir = Path(__file__).parent.parent / "data" / "ontology"
    output_zlp = tmp_path / "ontology.zlp"
    script_path = DEMO_DIR / "compile_ontology.py"

    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(ontology_dir), str(output_zlp)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Successfully compiled" in result.stdout
    assert output_zlp.exists()
    content = output_zlp.read_text()
    # Check for some expected content from the ontology files
    assert "Wikidata Bridge Bodies" in content or "AU Semantic Linkage" in content or "Wrong Type Catalog" in content

def test_zelph_demo_rules_integrity():
    # Verify that the core demo rules exist and have the right logic
    rules_path = DEMO_DIR / "rules.zlp"
    content = rules_path.read_text()
    
    # Rule 1 — Hazard without mitigation
    assert "hazard_unmitigated(Location) :-" in content
    assert "condition_at(wet_floor, Location, T)," in content
    assert "not(warning_sign_present(Location, T))." in content
    
    # Rule 2 — Knowledge + hazard => duty trigger
    assert "duty_of_care(Bob, Location) :-" in content
    assert "knows(Bob, wet_floor, T)," in content
    
    # Rule 3 — Breach
    assert "breach(Bob) :-" in content
    assert "duty_of_care(Bob, Location)," in content
    
    # Rule 4 — Causation
    assert "caused_injury(Bob, Alice) :-" in content
    assert "breach(Bob)," in content

def test_zelph_facts_template_match():
    # Verify the demo facts fixture structure
    facts_path = DEMO_DIR / "zelph_facts.zlp"
    content = facts_path.read_text()
    
    assert '(actor Alice)' in content
    assert '(actor Bob)' in content
    assert '(location slip_event supermarket)' in content
    assert '(condition wet_floor)' in content

def test_ontology_demo_structure():
    # Verify the ontology demo projection
    onto_demo_path = DEMO_DIR / "ontology_demo.zph"
    content = onto_demo_path.read_text()
    
    assert "international court" in content
    assert "US federal institution" in content
    assert "constitutional high court matter" in content
def test_compile_db_extended(tmp_path):
    # Create a mock database with special characters and missing fields
    db_path = tmp_path / "extended.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE rule_atoms (doc_id TEXT, stable_id TEXT, party TEXT, role TEXT, modality TEXT, action TEXT, scope TEXT)")
    # Test case 1: Special characters and all fields
    conn.execute("INSERT INTO rule_atoms VALUES ('d2', 's2', '\"Party A\"', 'Role & B', 'modality.must', 'Action (X)', 'Scope [Y]')")
    # Test case 2: Missing optional fields
    conn.execute("INSERT INTO rule_atoms VALUES ('d3', 's3', 'Party B', NULL, 'modality.may', 'Action Z', NULL)")
    conn.commit()
    conn.close()

    output_zlp = tmp_path / "output_extended.zlp"
    script_path = DEMO_DIR / "compile_db.py"

    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(db_path), str(output_zlp)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    content = output_zlp.read_text()
    
    # Verify escaping and quoting
    assert 'db_atom_0 "has party" "\\"Party A\\""' in content
    assert 'db_atom_0 "has role" "Role & B"' in content
    assert 'db_atom_0 "has action" "Action (X)"' in content
    assert 'db_atom_0 "has scope" "Scope [Y]"' in content
    
    # Verify missing fields are not emitted
    assert 'db_atom_1 "has party" "Party B"' in content
    assert 'db_atom_1 "has role"' not in content
    assert 'db_atom_1 "has scope"' not in content
    assert 'db_atom_1 "has action" "Action Z"' in content

def test_wikidata_extract_deep(tmp_path):
    input_txt = tmp_path / "input.txt"
    input_txt.write_text("Mock input for deep test.")
    
    script_path = DEMO_DIR / "wikidata_extract.py"
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(input_txt)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    output_json = tmp_path / "wikidata_sl_output.json"
    data = json.loads(output_json.read_text())
    
    # Verify the new properties I added
    enrichment = next(e for e in data["wikidata_enrichment"] if e["entity"] == "woolworths")
    properties = {p["property_label"]: p["value_label"] for p in enrichment["properties"]}
    
    assert properties["instance_of"] == "supermarket"
    assert properties["country"] == "Australia"
    assert properties["located_in_admin_entity"] == "New South Wales"

def test_sl_extract_facts_content(tmp_path):
    input_txt = tmp_path / "input.txt"
    input_txt.write_text("Alice slipped.")
    
    script_path = DEMO_DIR / "sl_extract.py"
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(input_txt)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    output_json = tmp_path / "sl_output.json"
    data = json.loads(output_json.read_text())
    
    # Verify specific facts
    facts = data["facts"]
    assert any(f["type"] == "event_occurred" and f["event_id"] == "slip_event" for f in facts)
    assert any(f["type"] == "condition" and f["condition_id"] == "wet_floor" for f in facts)

def test_lex_to_zelph_patterns(tmp_path):
    wiki_json = tmp_path / "wiki.json"
    wiki_json.write_text(json.dumps({
        "title": "Slip and fall",
        "rows": [
            {"revid": "999", "user": "Charlie", "comment": "Verification test"}
        ]
    }))
    
    output_zlp = tmp_path / "wiki.zlp"
    script_path = DEMO_DIR / "lex_to_zelph.py"
    env = {**os.environ, "PYTHONPATH": str(DEMO_DIR.parent / "src")}
    
    result = subprocess.run(
        [PYTHON_EXE, str(script_path), str(wiki_json), str(output_zlp)],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0
    content = output_zlp.read_text()
    
    # Verify exact predicate patterns
    assert 'rev_999 "is a" "wikipedia revision"' in content
    assert 'rev_999 "has comment" <lex_566572696669636174696f6e' in content
    assert 'rev_999 "by user" "Charlie"' in content
