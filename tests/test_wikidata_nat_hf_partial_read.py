from __future__ import annotations

from src.ontology.wikidata_nat_hf_partial_read import (
    node_of_name_chunks,
    resolve_qids_via_hosted_partial_scan,
)


def _manifest() -> dict:
    return {
        "sections": {
            "nodeOfName": {
                "chunks": [
                    {
                        "chunkIndex": 8,
                        "lang": "en",
                        "objectPath": "hf://en/8",
                        "length": 5,
                    },
                    {
                        "chunkIndex": 3,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/3",
                        "length": 10,
                    },
                    {
                        "chunkIndex": 7,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/7",
                        "length": 20,
                    },
                ]
            }
        }
    }


def test_node_of_name_chunks_select_only_wikidata_and_sort() -> None:
    chunks = node_of_name_chunks(_manifest())
    assert [row["chunkIndex"] for row in chunks] == [3, 7]


def test_partial_scan_accepts_plain_node_id_from_reverse_map_only_view() -> None:
    calls: list[str] = []

    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        calls.append(payload)
        assert "zelph/resolve" not in payload
        assert ".quit" in payload
        assert ".exit" not in payload
        if "nodeOfName=3" in payload:
            return (
                0,
                "SL_NAT_PROBE|Q1|\nNode ID: 123\n"
                "SL_NAT_PROBE|Q2|\nError in line: No node found with name 'Q2'\n",
            )
        if "nodeOfName=7" in payload:
            return 0, "SL_NAT_PROBE|Q2|\nNode ID: 456\n"
        raise AssertionError(payload)

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1", "Q2"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["status"] == "complete"
    assert receipt["resolved_qids"] == {"Q1": 123, "Q2": 456}
    assert receipt["resolved_qid_chunks"] == {"Q1": 3, "Q2": 7}
    assert receipt["qid_route_cache_seed"] == {
        "Q1": {"zelph_node_id": 123, "node_of_name_chunk": 3},
        "Q2": {"zelph_node_id": 456, "node_of_name_chunk": 7},
    }
    assert receipt["unresolved_qids"] == []
    assert receipt["chunk_count_scanned"] == 2
    assert receipt["route_index_required"] is False
    assert receipt["full_graph_loaded"] is False
    assert receipt["network_performed"] is True
    assert receipt["name_probe"] == "dot_node_non_creating"
    assert receipt["node_id_success_surface"] == "marker_scoped_Node_ID"
    assert len(calls) == 2


def test_resolved_to_node_id_remains_accepted_for_compatible_surfaces() -> None:
    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        del payload, timeout_seconds
        return 0, "SL_NAT_PROBE|Q1|\nResolved to node ID: 321\n"

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        max_chunks=1,
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["resolved_qids"] == {"Q1": 321}
    assert receipt["resolved_qid_chunks"] == {"Q1": 3}


def test_partial_scan_is_partial_when_qid_never_resolves() -> None:
    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        assert "zelph/resolve" not in payload
        return 0, "SL_NAT_PROBE|Q1|\nError in line: No node found with name 'Q1'\n"

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["status"] == "partial"
    assert receipt["resolved_qids"] == {}
    assert receipt["resolved_qid_chunks"] == {}
    assert receipt["qid_route_cache_seed"] == {}
    assert receipt["unresolved_qids"] == ["Q1"]
    assert receipt["chunk_count_scanned"] == 2


def test_marker_does_not_steal_plain_node_id_from_previous_or_next_probe() -> None:
    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        del payload, timeout_seconds
        return (
            0,
            "Node ID: 999\n"
            "SL_NAT_PROBE|Q1|\nError in line: No node found with name 'Q1'\n"
            "SL_NAT_PROBE|Q2|\nNode ID: 222\n",
        )

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1", "Q2"],
        zelph_bin="/fixture/zelph",
        max_chunks=1,
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["resolved_qids"] == {"Q2": 222}
    assert receipt["resolved_qid_chunks"] == {"Q2": 3}
    assert receipt["unresolved_qids"] == ["Q1"]


def test_missing_zelph_binary_is_receipted_without_claiming_network(monkeypatch) -> None:
    monkeypatch.delenv("ZELPH_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1"],
        zelph_bin="",
        repl_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    assert receipt["status"] == "zelph_binary_unavailable"
    assert receipt["resolved_qid_chunks"] == {}
    assert receipt["qid_route_cache_seed"] == {}
    assert receipt["network_performed"] is False
