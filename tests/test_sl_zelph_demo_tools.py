import subprocess
import sys
import sqlite3
import json
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
