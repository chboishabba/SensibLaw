from __future__ import annotations

from src.storage.postgres.enrichment_planner import load_external_lookup_demands


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    def execute(self, sql, params):
        self.sql = " ".join(sql.split())
        self.params = params

    def fetchall(self):
        return self.rows


def test_postgres_planner_projects_named_entities_and_lexical_work() -> None:
    cursor = Cursor(
        [
            (
                "demand:usa",
                "factor:usa",
                "factor-revision:usa",
                "semantic.mention_identity",
                "PROPN",
                "the United States",
                ["named_entity_candidate", "semantic-family:entity"],
                ["external_identity_unresolved"],
            ),
            (
                "demand:he",
                "factor:he",
                "factor-revision:he",
                "semantic.mention_identity",
                "PRON",
                "He",
                ["pronominal_argument"],
                ["external_identity_unresolved"],
            ),
            (
                "demand:bank",
                "factor:bank",
                "factor-revision:bank",
                "semantic.mention_identity",
                "NOUN",
                "bank",
                ["nominal_head"],
                ["external_identity_unresolved"],
            ),
        ]
    )

    demands = load_external_lookup_demands(
        cursor,
        corpus_ref="corpus:gwb",
        limit=50,
    )

    assert cursor.params == ("corpus:gwb", "corpus:gwb", 50)
    assert "resolution.demand" in cursor.sql
    assert "language.annotation_node" in cursor.sql
    assert "corpus.document_occurrence" in cursor.sql
    assert [(row.surface, row.demand_kind) for row in demands] == [
        ("the United States", "entity_identity"),
        ("bank", "lexical_sense"),
    ]
    assert all("postgres-external-lookup-plan:v0_1" in row.provenance_refs for row in demands)


def test_postgres_planner_can_disable_wiktionary_and_enforces_limit() -> None:
    cursor = Cursor(
        [
            (
                "demand:bank",
                "factor:bank",
                "factor-revision:bank",
                "semantic.mention_identity",
                "NOUN",
                "bank",
                ["nominal_head"],
                ["external_identity_unresolved"],
            )
        ]
    )

    assert load_external_lookup_demands(
        cursor,
        include_wiktionary=False,
    ) == ()

    try:
        load_external_lookup_demands(cursor, limit=0)
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("zero plan limit must fail")
