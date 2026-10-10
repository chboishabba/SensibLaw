from pathlib import Path

from src.ontology.wikimedia_world_walk import (
    EdgeCandidate,
    WorldWalkPolicy,
    build_publishable_bucket_manifest,
    walk_world,
)
from src.storage.postgres.world_bucket_store import (
    MaterialisationReceipt,
    append_materialisation_receipt,
    persist_world_bucket,
)


class FakeCursor:
    def __init__(self, statements: list[tuple[str, tuple[object, ...]]]) -> None:
        self.statements = statements

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.statements.append((sql, params))


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.statements)

    def commit(self) -> None:
        self.commits += 1


def _result_and_projection():
    fixtures = {
        "mabo": [EdgeCandidate("mabo", "hca-1992", "source_reference", "citation", 10)],
        "hca-1992": [],
    }
    result = walk_world(
        seed="mabo",
        policy=WorldWalkPolicy(hop_budget=1, selections_per_hop=1),
        expand=lambda source: fixtures[source],
    )
    projection = build_publishable_bucket_manifest(
        result,
        selected_node_ids={"mabo", "hca-1992"},
        parent_bucket_cids=("bafy-parent",),
        compiler_version="world-walk-v0_1",
    )
    return result, projection


def test_persist_world_bucket_uses_only_idempotent_inserts() -> None:
    result, projection = _result_and_projection()
    connection = FakeConnection()

    receipt = persist_world_bucket(connection, result=result, projection=projection)

    assert receipt.bucket_id.startswith("world-bucket-state:sha256:")
    assert receipt.projection_id == projection.logical_shard_id
    assert receipt.nodes_written == 2
    assert receipt.growth_receipts_written == 1
    assert receipt.projection_members_written == 2
    assert receipt.projection_parents_written == 1
    assert connection.commits == 1

    sql = "\n".join(statement for statement, _ in connection.statements).lower()
    assert sql.count("insert into") == 8
    assert sql.count("on conflict do nothing") == 8
    assert "insert into sl_world_bucket_projection_parent" in sql
    assert " update " not in f" {sql} "
    assert " delete " not in f" {sql} "
    assert "json" not in sql


def test_persist_world_bucket_replay_uses_same_identity() -> None:
    result, projection = _result_and_projection()
    first = FakeConnection()
    second = FakeConnection()

    first_receipt = persist_world_bucket(first, result=result, projection=projection)
    second_receipt = persist_world_bucket(second, result=result, projection=projection)

    assert first_receipt.bucket_id == second_receipt.bucket_id
    assert first_receipt.projection_id == second_receipt.projection_id
    assert first.statements == second.statements


def test_materialisation_receipt_is_append_only_and_authority_neutral() -> None:
    connection = FakeConnection()
    receipt = MaterialisationReceipt(
        receipt_id="materialisation:mabo:hca-1992:skeleton:v1",
        bucket_id="world-bucket-state:sha256:" + "00" * 32,
        object_id="hca-1992",
        materialisation_state="skeleton",
        content_digest="sha256:" + "11" * 32,
        source_locator="https://eresources.hcourt.gov.au/showCase/1992/HCA/23",
        reason="retain proof/source skeleton; reacquire bytes on exact-source demand",
        candidate_only=True,
        semantic_promotion=False,
    )

    append_materialisation_receipt(connection, receipt)

    assert connection.commits == 1
    assert len(connection.statements) == 1
    sql, params = connection.statements[0]
    lowered = sql.lower()
    assert "insert into sl_world_materialisation_receipt" in lowered
    assert "on conflict do nothing" in lowered
    assert "update" not in lowered
    assert "delete" not in lowered
    assert params[2] == "hca-1992"
    assert params[3] == "skeleton"
    assert params[-2:] == (True, False)


def test_store_module_has_no_json_or_regex_dependency() -> None:
    source = Path("src/storage/postgres/world_bucket_store.py").read_text(encoding="utf-8")
    assert "import json" not in source
    assert "import re" not in source
    assert "json." not in source
    assert "re." not in source
