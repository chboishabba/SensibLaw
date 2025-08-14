from pathlib import Path

import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.storage.core import Storage


def test_as_at_queries(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)

    # create two nodes with finite validity
    n1 = store.insert_node("entity", {}, valid_from="2020-01-01", valid_to="2020-12-31")
    n2 = store.insert_node("entity", {}, valid_from="2020-01-01", valid_to="2020-12-31")

    # two edges representing different valid periods
    e1 = store.insert_edge(
        n1,
        n2,
        "rel",
        {},
        valid_from="2020-01-01",
        valid_to="2020-06-30",
    )
    e2 = store.insert_edge(
        n1,
        n2,
        "rel",
        {},
        valid_from="2020-07-01",
        valid_to="2020-12-31",
    )

    # as-at before edge swap
    edges_may = store.fetch_edges_as_at(n1, "2020-05-01")
    assert {e.id for e in edges_may} == {e1}

    # as-at after edge swap
    edges_aug = store.fetch_edges_as_at(n1, "2020-08-01")
    assert {e.id for e in edges_aug} == {e2}

    # node validity checks
    assert store.fetch_node_as_at(n1, "2020-05-01") is not None
    assert store.fetch_node_as_at(n1, "2021-01-01") is None

    store.close()

