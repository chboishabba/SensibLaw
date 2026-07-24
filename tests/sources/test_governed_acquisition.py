from src.sources.governed_acquisition import (
    AcquisitionPolicy,
    AcquisitionRequest,
    FetchedSource,
    acquire_legal_source,
)


def _request(url: str = "https://example.test/act.txt") -> AcquisitionRequest:
    return AcquisitionRequest(
        requested_url=url,
        operator_authorization_ref="operator-authorization:1",
        provider_profile_ref="provider:test:v1",
        source_role="primary_legislation",
        jurisdiction_ref="AU-QLD",
        authority_level="primary",
    )


def _policy() -> AcquisitionPolicy:
    return AcquisitionPolicy(
        provider_profile_ref="provider:test:v1",
        allowed_hosts=("example.test",),
        maximum_bytes=1024,
        allowed_media_types=("text/plain",),
    )


def test_acquisition_requires_explicit_policy_and_returns_candidate_revision() -> None:
    request = _request()
    policy = _policy()

    receipt, payload = acquire_legal_source(
        request,
        policy=policy,
        fetch=lambda url, limit: FetchedSource(
            final_url=url,
            media_type="text/plain",
            raw_bytes=b"A person must stop.",
            canonical_text="A person must stop.",
        ),
    )

    assert receipt.state == "persisted"
    assert receipt.operator_authorization_ref == "operator-authorization:1"
    assert payload is not None
    assert payload["source_revision_ref"] == receipt.source_revision_ref
    assert receipt.to_dict()["semantic_state_promoted"] is False
    assert receipt.to_dict()["legal_truth_closed"] is False


def test_acquisition_rejects_unapproved_host_without_fetching() -> None:
    calls = 0

    def fetch(url: str, limit: int) -> FetchedSource:
        nonlocal calls
        calls += 1
        raise AssertionError((url, limit))

    try:
        acquire_legal_source(
            _request("https://other.test/act.txt"),
            policy=_policy(),
            fetch=fetch,
        )
    except ValueError as error:
        assert "outside the acquisition policy" in str(error)
    else:
        raise AssertionError("unapproved host must fail before fetching")
    assert calls == 0


def test_acquisition_rejects_redirect_to_unapproved_host() -> None:
    receipt, payload = acquire_legal_source(
        _request(),
        policy=_policy(),
        fetch=lambda url, limit: FetchedSource(
            final_url="https://other.test/act.txt",
            media_type="text/plain",
            raw_bytes=b"A person must stop.",
            canonical_text="A person must stop.",
        ),
    )

    assert payload is None
    assert receipt.state == "rejected"
    assert "redirected host is outside" in str(receipt.failure_reason)
