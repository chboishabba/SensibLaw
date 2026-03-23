import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sensiblaw.db import MigrationRunner
from sensiblaw.db.migrations import MIGRATIONS_DIR
from fact_intake.read_model import _FACT_INTAKE_MIGRATION_FILES


def test_all_migrations_applied_in_memory():
    """Verify that MigrationRunner applies all files in MIGRATIONS_DIR."""
    connection = sqlite3.connect(":memory:")
    runner = MigrationRunner(connection)
    runner.apply_all()
    
    # Check schema_migrations table
    cursor = connection.execute("SELECT filename FROM schema_migrations")
    applied_files = {row[0] for row in cursor.fetchall()}
    
    expected_files = {p.name for p in MIGRATIONS_DIR.glob("*.sql")}
    
    assert applied_files == expected_files, f"Missing or extra migrations: {expected_files - applied_files} / {applied_files - expected_files}"


def test_read_model_migration_list_sync():
    """Verify that _FACT_INTAKE_MIGRATION_FILES in read_model.py matches 005+ migrations."""
    all_migration_files = sorted([p.name for p in MIGRATIONS_DIR.glob("*.sql")])
    
    # Files starting from 005
    expected_fact_intake_files = [
        f for f in all_migration_files 
        if f >= "005" and "fact_" in f or "event_" in f or "semantic_" in f
    ]
    
    # Note: 20241205_ontology_lookup_log.sql is later, but we focus on the core fact/event sequence prefixes.
    # Actually, let's just compare against the exact list in read_model.py to detect ANY missing 005+ files that look like they belong to fact_intake.
    
    actual_files = list(_FACT_INTAKE_MIGRATION_FILES)
    
    # Check if any new 005+ files exist in the directory that are NOT in _FACT_INTAKE_MIGRATION_FILES
    missing_in_code = [
        f for f in all_migration_files 
        if f.startswith(("005", "006", "007", "008", "009", "010", "011")) 
        and f not in actual_files
    ]
    
    assert not missing_in_code, f"Migrations found in directory but missing from read_model.py _FACT_INTAKE_MIGRATION_FILES: {missing_in_code}"
    
    # Also check if _FACT_INTAKE_MIGRATION_FILES has files that don't exist
    missing_on_disk = [f for f in actual_files if not (MIGRATIONS_DIR / f).exists()]
    assert not missing_on_disk, f"Migrations listed in read_model.py but missing from disk: {missing_on_disk}"
