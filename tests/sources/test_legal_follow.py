from __future__ import annotations

from io import StringIO

from src.sources.legal_follow import (
    AU_PROFILE,
    GB_PROFILE,
    US_PROFILE,
    follow_legal_sources,
    profile_for,
)


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


def test_all_jurisdictions_share_the_same_follow_capability_contract() -> None:
    profiles = (AU_PROFILE, GB_PROFILE, US_PROFILE)

    assert {profile.jurisdiction for profile in profiles} == {"AU", "GB", "US"}
    assert all(profile.max_depth == 1 for profile in profiles)
    assert all(profile.max_documents == 20 for profile in profiles)
    assert all(
        any(endpoint.authority_level == "official" for endpoint in profile.endpoints)
        for profile in profiles
    )
    assert profile_for("UK") is GB_PROFILE
    assert profile_for("USA") is US_PROFILE


def test_au_follow_uses_shared_fetch_and_link_receipts() -> None:
    seed = "https://www.legislation.gov.au/"
    second = "https://www.legislation.gov.au/document/Test"
    session = Session(
        {
            seed: Response(seed, b'<main><a href="/document/Test">Test Act</a></main>'),
            second: Response(second, b"<main>Test Act text</main>"),
        }
    )

    result = follow_legal_sources(
        "AU",
        seed_urls=(seed,),
        max_depth=1,
        max_documents=2,
        session=session,
        progress_stream=StringIO(),
    )

    assert len(result.documents) == 2
    assert result.documents[0].links[0].target_url == second
    assert all(row.status == "fetched" for row in result.receipts)
