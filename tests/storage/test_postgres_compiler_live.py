from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import compile_directory_postgres
from src.storage.postgres import PostgresCompilerStore


pytestmark = pytest.mark.live


def test_gwb_mini_compiles_into_postgres_without_json_outputs() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "corpora"
        / "gwb-mini"
    )
    if not fixture.exists():
        pytest.skip("gwb-mini fixture is not present on this branch")
    store = PostgresCompilerStore.connect(database_url)
    try:
        first = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        second = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        assert first.corpus_ref == second.corpus_ref
        assert first.document_refs == second.document_refs
        assert first.demand_refs == second.demand_refs
        assert first.failure_refs == ()
        assert store.unresolved_demands(first.corpus_ref)
        for document_ref in first.document_refs:
            summary = store.document_summary(document_ref)
            assert summary is not None
            assert summary["factor_count"] > 0
    finally:
        store.close()
