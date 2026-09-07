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


def test_partial_scan_walks_chunks_until_all_qids_resolve() -> None:
    calls: list[str] = []

    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        calls.append(payload)
        if "nodeOfName=3" in payload:
            return 0, "SL_NAT_RESOLVE|Q1|123\nSL_NAT_RESOLVE|Q2|nil\n"
        if "nodeOfName=7" in payload:
            return 0, "SL_NAT_RESOLVE|Q2|456\n"
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
    assert receipt["unresolved_qids"] == []
    assert receipt["chunk_count_scanned"] == 2
    assert receipt["route_index_required"] is False
    assert receipt["full_graph_loaded"] is False
    assert receipt["network_performed"] is True
    assert len(calls) == 2


def test_partial_scan_is_partial_when_qid_never_resolves() -> None:
    def fake_runner(_binary: str, _payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        return 0, "SL_NAT_RESOLVE|Q1|nil\n"

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["status"] == "partial"
    assert receipt["resolved_qids"] == {}
    assert receipt["unresolved_qids"] == ["Q1"]
    assert receipt["chunk_count_scanned"] == 2


def test_missing_zelph_binary_is_receipted_without_claiming_network() -> None:
    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest(),
        ["Q1"],
        zelph_bin="",
        repl_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    assert receipt["status"] == "zelph_binary_unavailable"
    assert receipt["network_performed"] is False
