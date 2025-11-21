import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sensiblaw.db import ActorMappingDAO, LegalSourceDAO, MigrationRunner
from sensiblaw.db.migrations import MIGRATIONS_DIR


@pytest.fixture()
def db_connection():
    connection = sqlite3.connect(":memory:")
    MigrationRunner(connection).apply_all()
    return connection


def test_seed_priority_legal_systems(db_connection):
    cursor = db_connection.execute("SELECT code, priority FROM legal_systems ORDER BY code")
    systems = {row[0]: row[1] for row in cursor.fetchall()}
    expected = {
        "AU.COMMON",
        "AU.STATE.QLD",
        "PK.ISLAM.HANAFI",
        "NZ.TIKANGA",
        "US.STATE",
        "EU",
    }
    assert expected.issubset(systems.keys())
    assert all(priority == 1 for code, priority in systems.items() if code in expected)


def test_legal_systems_are_country_scoped(db_connection):
    cursor = db_connection.execute(
        """
        SELECT ls.code, country.code as country_code, sub.code as subdivision_code
        FROM legal_systems ls
        JOIN countries country ON country.id = ls.country_id
        LEFT JOIN subdivisions sub ON sub.id = ls.subdivision_id
        ORDER BY ls.code
        """
    )
    mappings = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    assert mappings["AU.COMMON"] == ("AU", None)
    assert mappings["AU.STATE.QLD"] == ("AU", "QLD")
    assert mappings["PK.ISLAM.HANAFI"] == ("PK", None)
    assert mappings["NZ.TIKANGA"] == ("NZ", None)
    assert mappings["US.STATE"] == ("US", None)
    assert mappings["EU"] == ("EU", None)


def test_norm_source_uniqueness(db_connection):
    dao = LegalSourceDAO(db_connection)
    dao.create_source(
        legal_system_code="AU.COMMON",
        norm_source_category_code="STATUTE",
        citation="[1992] HCA 23",
        title="Mabo v Queensland (No 2)",
    )
    with pytest.raises(sqlite3.IntegrityError):
        dao.create_source(
            legal_system_code="AU.COMMON",
            norm_source_category_code="STATUTE",
            citation="[1992] HCA 23",
            title="Duplicate",
        )


def test_upsert_and_lookup(db_connection):
    dao = LegalSourceDAO(db_connection)
    source_id = dao.upsert_source(
        legal_system_code="NZ.TIKANGA",
        norm_source_category_code="CUSTOM",
        citation="WAI 2601",
        title="Te Paparahi o te Raki Inquiry",
        source_url="https://example.test/source",
    )
    record = dao.get_by_citation(legal_system_code="NZ.TIKANGA", citation="WAI 2601")
    assert record
    assert record.id == source_id
    assert record.title == "Te Paparahi o te Raki Inquiry"
    assert record.norm_source_category_code == "CUSTOM"


def test_actor_mapping_prefers_system_specific(db_connection):
    dao = ActorMappingDAO(db_connection)
    nz_mapping = dao.lookup_by_marker("crown", legal_system_code="NZ.TIKANGA")
    assert nz_mapping
    assert nz_mapping.code == "state_actor"

    default_mapping = dao.lookup_by_marker("plaintiff")
    assert default_mapping
    assert default_mapping.code == "individual"


def test_relationship_kinds_include_system_specific(db_connection):
    dao = ActorMappingDAO(db_connection)
    nz_kinds = dao.relationship_kinds(legal_system_code="NZ.TIKANGA")
    assert "communal" in nz_kinds
    assert "contract" in nz_kinds
    hanafi_kinds = dao.relationship_kinds(legal_system_code="PK.ISLAM.HANAFI")
    assert "religious" in hanafi_kinds


def test_addresses_migrate_country_and_subdivision_links():
    connection = sqlite3.connect(":memory:")
    migration_paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    legacy_paths = [
        path for path in migration_paths if path.name != "003_addresses_country_references.sql"
    ]
    address_migration = [
        path for path in migration_paths if path.name == "003_addresses_country_references.sql"
    ]
    MigrationRunner(connection, migration_paths=legacy_paths).apply_all()

    connection.execute(
        """
        INSERT INTO addresses (address_line1, address_line2, city, state_province, postal_code, country_code)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("123 Example St", None, "Brisbane", "QLD", "4000", "AU"),
    )

    MigrationRunner(connection, migration_paths=address_migration).apply_all()

    columns = [row[1] for row in connection.execute("PRAGMA table_info(addresses)")]
    assert "country_code" not in columns
    assert "country_id" in columns
    assert "subdivision_id" in columns

    cursor = connection.execute(
        """
        SELECT addr.country_id, addr.subdivision_id, country.code, sub.code
        FROM addresses addr
        LEFT JOIN countries country ON country.id = addr.country_id
        LEFT JOIN subdivisions sub ON sub.id = addr.subdivision_id
        """
    )
    country_id, subdivision_id, country_code, subdivision_code = cursor.fetchone()

    assert country_code == "AU"
    assert subdivision_code == "QLD"
    assert country_id is not None
    assert subdivision_id is not None
