import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sensiblaw.db import MigrationRunner
from sensiblaw.db.dao import LegalSourceDAO


@pytest.fixture()
def connection():
    conn = sqlite3.connect(":memory:")
    MigrationRunner(conn).apply_all()
    yield conn
    conn.close()


def test_upsert_updates_existing_record(connection):
    dao = LegalSourceDAO(connection)
    first_id = dao.upsert_source(
        legal_system_code="AU.COMMON",
        norm_source_category_code="STATUTE",
        citation="[2001] HCA 1",
        title="Initial Title",
        summary="Original",
    )

    second_id = dao.upsert_source(
        legal_system_code="AU.COMMON",
        norm_source_category_code="STATUTE",
        citation="[2001] HCA 1",
        title="Updated Title",
        summary="Updated",
    )

    assert first_id == second_id
    record = dao.get_by_citation(legal_system_code="AU.COMMON", citation="[2001] HCA 1")
    assert record
    assert record.title == "Updated Title"
    assert record.summary == "Updated"


def test_list_sources_respects_filters(connection):
    dao = LegalSourceDAO(connection)
    dao.upsert_source(
        legal_system_code="AU.COMMON",
        norm_source_category_code="STATUTE",
        citation="[1992] HCA 23",
        title="Mabo",
    )
    dao.upsert_source(
        legal_system_code="NZ.TIKANGA",
        norm_source_category_code="CUSTOM",
        citation="WAI 2601",
    )

    australian = dao.list_sources(legal_system_code="AU.COMMON")
    assert [item.citation for item in australian] == ["[1992] HCA 23"]

    customs = dao.list_sources(norm_source_category_code="CUSTOM")
    assert [item.legal_system_code for item in customs] == ["NZ.TIKANGA"]
