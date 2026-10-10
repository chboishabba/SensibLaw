from __future__ import annotations

import src.ontology.wikidata_nat_source_support as source
from src.ontology.wikidata_nat_source_support_dispatch import dispatch_source_fetch_plan


def _row(row_ref: str, qid: str, statement: str) -> dict:
    return {
        "row_ref": row_ref,
        "qid": qid,
        "statement_reference": statement,
        "source_property": "P5991",
        "target_property": "P14143",
    }


def _p854(url: str) -> dict:
    return {
        "P854": [
            {
                "snaktype": "value",
                "datavalue": {"type": "string", "value": url},
            }
        ]
    }


def _batch() -> dict:
    return {
        "batch_ref": "batch:1",
        "rows": [
            _row("row:1", "Q1", "Q1$S1"),
            _row("row:2", "Q1", "Q1$S2"),
            _row("row:3", "Q2", "Q2$S1"),
        ],
    }


def _coverage_dispatch() -> dict:
    shared_url = "https://example.com/report.pdf"
    return {
        "dispatch_ref": "coverage:1",
        "coverage_residual_paid_count": 3,
        "coverage_residual_still_open_count": 0,
        "results": [
            {
                "outputs": {
                    "reference_snaks": {
                        "Q1": {
                            "Q1$S1": [_p854(shared_url)],
                            "Q1$S2": [_p854(shared_url)],
                        },
                        "Q2": {"Q2$S1": []},
                    }
                }
            }
        ],
    }


def test_source_plan_joins_exact_statement_and_deduplicates_url() -> None:
    plan = source.build_source_fetch_plan(_batch(), _coverage_dispatch())
    assert plan["source_residual_count"] == 3
    assert plan["distinct_url_count"] == 1
    assert plan["residuals_without_p854_count"] == 1
    demand = plan["fetch_demands"][0]
    assert demand["url"] == "https://example.com/report.pdf"
    assert len(demand["consumer_residual_refs"]) == 2
    assert demand["source_support_payment_claimed"] is False


def test_source_plan_refuses_to_advance_while_coverage_open() -> None:
    dispatch = _coverage_dispatch()
    dispatch["coverage_residual_paid_count"] = 2
    dispatch["coverage_residual_still_open_count"] = 1
    try:
        source.build_source_fetch_plan(_batch(), dispatch)
    except ValueError as exc:
        assert "zero open coverage residuals" in str(exc)
    else:
        raise AssertionError("open coverage residual must block source-support planning")


class _Response:
    status_code = 200
    headers = {"Content-Type": "application/pdf"}

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, *, chunk_size: int):
        assert chunk_size == 65536
        yield b"abc"
        yield b"def"


def test_content_fetch_receipt_records_exact_transport_not_source_support(monkeypatch) -> None:
    monkeypatch.setattr(source, "_public_http_url", lambda _url: (True, "public_http_origin"))
    calls = []

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        return _Response()

    receipt = source.fetch_source_content(
        {"fetch_ref": "fetch:1", "url": "https://example.com/report.pdf"},
        http_get=fake_get,
    )
    assert receipt["status"] == "content_acquired"
    assert receipt["bytes_received"] == 6
    assert receipt["http_request_count"] == 1
    assert receipt["cache_hits"] == 0
    assert receipt["cache_misses"] == 1
    assert receipt["content_digest"].startswith("sha256:")
    assert receipt["source_support_paid"] is False
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["stream"] is True


def test_shared_dispatch_fetches_one_url_once_for_two_residuals() -> None:
    plan = source.build_source_fetch_plan(_batch(), _coverage_dispatch())
    calls = []

    def fake_fetch(demand: dict) -> dict:
        calls.append(demand["url"])
        return {
            "receipt_ref": "receipt:1",
            "url": demand["url"],
            "status": "content_acquired",
            "network_performed": True,
            "bytes_received": 100,
            "http_request_count": 1,
            "cache_hits": 0,
            "cache_misses": 1,
            "content_digest": "sha256:abc",
            "content_acquired": True,
            "source_support_paid": False,
        }

    class NoWaitLimiter:
        cfg = type("Cfg", (), {"rps": 1.0, "burst": 1})()

        def acquire(self, tokens: float = 1.0) -> None:
            assert tokens == 1.0

    dispatch = dispatch_source_fetch_plan(
        plan,
        fetcher=fake_fetch,
        worker_budget=4,
        rate_limiter=NoWaitLimiter(),
    )
    assert calls == ["https://example.com/report.pdf"]
    assert dispatch["fetch_call_count"] == 1
    assert dispatch["source_support_recomputation_count"] == 3
    assert dispatch["reference_present_count"] == 2
    assert dispatch["content_acquired_residual_count"] == 2
    assert dispatch["source_support_paid_count"] == 0
    assert dispatch["source_support_still_open_count"] == 3
    assert dispatch["bytes_received"] == 100
    assert dispatch["http_request_count"] == 1
    assert dispatch["consumer_verification_performed"] is False
    assert dispatch["semantic_promotion_performed"] is False


def test_private_network_reference_is_rejected_without_request() -> None:
    receipt = source.fetch_source_content(
        {"fetch_ref": "fetch:private", "url": "http://127.0.0.1/private"},
        http_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private URL must be rejected before HTTP")
        ),
    )
    assert receipt["status"] == "rejected_by_network_policy"
    assert receipt["network_performed"] is False
    assert receipt["content_acquired"] is False
    assert receipt["source_support_paid"] is False
