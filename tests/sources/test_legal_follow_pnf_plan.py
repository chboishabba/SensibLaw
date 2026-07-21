from __future__ import annotations

from io import StringIO

from src.pnf.legal_adjunct import LegalSourcePlan
from src.sources.legal_follow import follow_legal_source_plan, select_legal_endpoints


class Response:
    status_code = 200

    def __init__(self, url: str, content: bytes) -> None:
        self.url = url
        self.content = content
        self.headers = {"Content-Type": "text/html"}

    def raise_for_status(self) -> None:
        return None


class Session:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get(self, url, **_kwargs):
        self.calls.append(url)
        return self.rows[url]


def _plan(**overrides) -> LegalSourcePlan:
    values = {
        "demand_ref": "demand:1",
        "plan_key": "plan:1",
        "jurisdiction_ref": "AU",
        "source_role_refs": ("primary_legislation",),
        "authority_level_refs": ("official",),
        "provider_profile_refs": (),
        "requested_legal_facets": ("conduct_prohibition",),
        "temporal_refs": ("2024-07-09",),
        "state": "ready",
        "blocked_reasons": (),
    }
    values.update(overrides)
    return LegalSourcePlan(**values)


def test_typed_plan_selects_only_matching_role_and_authority() -> None:
    endpoints = select_legal_endpoints(_plan())

    assert [row.endpoint_ref for row in endpoints] == [
        "au:federal-register-api",
        "au:federal-register",
    ]
    assert all(row.source_role == "primary_legislation" for row in endpoints)
    assert all(row.authority_level == "official" for row in endpoints)


def test_provider_ref_can_narrow_to_one_declared_endpoint() -> None:
    endpoints = select_legal_endpoints(
        _plan(provider_profile_refs=("au:federal-register",))
    )

    assert [row.endpoint_ref for row in endpoints] == ["au:federal-register"]


def test_blocked_plan_performs_no_follow() -> None:
    result = follow_legal_source_plan(
        _plan(state="blocked_missing_context", blocked_reasons=("jurisdiction_unresolved",))
    )

    assert result is None


def test_typed_follow_does_not_expand_to_supporting_research_index() -> None:
    seed = "https://www.legislation.gov.au/"
    second = "https://www.legislation.gov.au/document/Test"
    session = Session(
        {
            seed: Response(
                seed,
                b'<main><a href="/document/Test">Test Act</a>'
                b'<a href="https://www.austlii.edu.au/Test">Research</a></main>',
            ),
            second: Response(second, b"<main>Test Act text</main>"),
        }
    )

    result = follow_legal_source_plan(
        _plan(provider_profile_refs=("au:federal-register",)),
        max_depth=1,
        max_documents=2,
        session=session,
        progress_stream=StringIO(),
    )

    assert result is not None
    assert session.calls == [seed, second]
    assert all("austlii" not in url for url in session.calls)
