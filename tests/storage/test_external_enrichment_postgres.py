from __future__ import annotations

import os

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import compile_directory_postgres
from src.storage.postgres import PostgresCompilerStore
from src.storage.postgres.enrichment_planner import load_external_lookup_demands


pytestmark = pytest.mark.live


def test_compiled_corpus_plans_external_lookups_without_network(tmp_path) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")

    source = tmp_path / "source.txt"
    source.write_text(
        "George W. Bush visited Texas. He discussed a policy framework.",
        encoding="utf-8",
    )
    store = PostgresCompilerStore.connect(database_url)
    try:
        compilation = compile_directory_postgres(
            tmp_path,
            context=default_compiler_context(),
            store=store,
        )
        assert compilation.failure_refs == ()
        with store.transaction() as cursor:
            demands = load_external_lookup_demands(
                cursor,
                corpus_ref=compilation.corpus_ref,
                limit=100,
            )

        surfaces = {row.surface for row in demands}
        assert surfaces.intersection({"George W. Bush", "George", "Bush", "Texas"})
        assert all(row.surface != "He" for row in demands)
        assert any(row.demand_kind == "entity_identity" for row in demands)
        assert all(
            "postgres-external-lookup-plan:v0_1" in row.provenance_refs
            for row in demands
        )
    finally:
        store.close()
