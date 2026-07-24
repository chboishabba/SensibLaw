from src.sources.governed_acquisition import (
    AcquisitionPolicy,
    AcquisitionRequest,
    FetchedSource,
    acquire_legal_source,
)


def test_acquisition_requires_explicit_policy_and_returns_candidate_revision() -> None:
    request = AcquisitionRequest(
        requested_url="https://example.test/act.txt",
        operator_authorization_ref="operator-authorization:1",
        provider_profile_ref="provider:test:v1",
        source_role="primary_legislation",
        jurisdiction_ref="AU-QLD",
        authority_level="primary",
    )
    policy = AcquisitionPolicy(
        provider_profile_ref="provider:test:v1",
        allowed_hosts=("example.test",),
        maximum_bytes=1024,
        allowed_media_types=("text/plain",),
    )

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

    request = AcquisitionRequest(
        requested_url="https://other.test/act.txt",
        operator_authorization_ref="operator-authorization:1",
        provider_profile_ref="provider:test:v1",
        source_role="primary_legislation",
        jurisdiction_ref="AU-QLD",
        authority_level="primary",
    )
    policy = AcquisitionPolicy(
        provider_profile_ref="provider:test:v1",
        allowed_hosts=("example.test",),
        maximum_bytes=1024,
    )

    try:
        acquire_legal_source(request, policy=policy, fetch=fetch)
    except ValueError as error:
        assert "outside the acquisition policy" in str(error)
    else:
        raise AssertionError("unapproved host must fail before fetching")
    assert calls == 0
