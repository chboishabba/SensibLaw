from __future__ import annotations

import json
from pathlib import Path

from scripts.wiki_random_page_samples import build_random_sample_manifest, main


def test_build_random_sample_manifest_writes_revision_locked_snapshots(tmp_path: Path, monkeypatch) -> None:
    from scripts import wiki_random_page_samples as mod

    monkeypatch.setattr(
        mod,
        "_fetch_random_titles",
        lambda **_: ["Donald Trump", "Mabo v Queensland (No 2)"],
    )

    def _fake_fetch_latest_wikitext(**kwargs):
        from scripts.wiki_pull_api import PageSnapshot

        title = kwargs["title"]
        return PageSnapshot(
            wiki="enwiki",
            title=title,
            pageid=1,
            revid=123 if title == "Donald Trump" else 456,
            rev_timestamp="2026-03-15T00:00:00Z",
            source_url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            api_url="https://example.test/api",
            fetched_at="2026-03-15T00:00:01Z",
            categories=[],
            links=[],
            wikitext=f"Sample text for {title}",
            warnings=[],
        )

    monkeypatch.setattr(mod.wiki_pull_api, "_fetch_latest_wikitext", _fake_fetch_latest_wikitext)

    manifest = build_random_sample_manifest(
        wiki="enwiki",
        count=2,
        namespace=0,
        out_dir=tmp_path / "snapshots",
        timeout_s=10,
        wiki_rps=5.0,
        max_links=10,
        max_categories=10,
        include_wikitext=True,
    )

    assert manifest["schema_version"] == "wiki_random_page_sample_manifest_v0_1"
    assert manifest["sampled_count"] == 2
    assert len(manifest["samples"]) == 2
    for row in manifest["samples"]:
        snapshot_path = Path(row["snapshot_path"])
        assert snapshot_path.exists()
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert payload["revid"] in {123, 456}


def test_build_random_sample_manifest_includes_one_hop_followed_pages(tmp_path: Path, monkeypatch) -> None:
    from scripts import wiki_random_page_samples as mod

    monkeypatch.setattr(mod, "_fetch_random_titles", lambda **_: ["Root Page"])

    def _fake_fetch_latest_wikitext(**kwargs):
        from scripts.wiki_pull_api import PageSnapshot

        title = kwargs["title"]
        return PageSnapshot(
            wiki="enwiki",
            title=title,
            pageid=1,
            revid=111 if title == "Root Page" else 222,
            rev_timestamp="2026-03-15T00:00:00Z",
            source_url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            api_url="https://example.test/api",
            fetched_at="2026-03-15T00:00:01Z",
            categories=["Category:Example"],
            links=["Follow One", "Follow One"] if title == "Root Page" else [],
            wikitext=f"Sample text for {title}",
            warnings=[],
        )

    monkeypatch.setattr(mod.wiki_pull_api, "_fetch_latest_wikitext", _fake_fetch_latest_wikitext)

    manifest = build_random_sample_manifest(
        wiki="enwiki",
        count=1,
        namespace=0,
        out_dir=tmp_path / "snapshots",
        timeout_s=10,
        wiki_rps=5.0,
        max_links=10,
        max_categories=10,
        include_wikitext=True,
        follow_hops=1,
        max_follow_links_per_page=2,
    )

    row = manifest["samples"][0]
    assert manifest["follow_hops"] == 1
    assert manifest["max_follow_links_per_page"] == 2
    assert row["link_count"] == 2
    assert row["category_count"] == 1
    assert row["followed_snapshot_count"] == 1
    assert row["followed_samples"][0]["title"] == "Follow One"


def test_build_random_sample_manifest_supports_recursive_follow_hops(tmp_path: Path, monkeypatch) -> None:
    from scripts import wiki_random_page_samples as mod

    monkeypatch.setattr(mod, "_fetch_random_titles", lambda **_: ["Root Page"])

    def _fake_fetch_latest_wikitext(**kwargs):
        from scripts.wiki_pull_api import PageSnapshot

        title = kwargs["title"]
        links = []
        if title == "Root Page":
            links = ["Follow One"]
        elif title == "Follow One":
            links = ["Follow Two"]
        return PageSnapshot(
            wiki="enwiki",
            title=title,
            pageid=1,
            revid=111 if title == "Root Page" else 222 if title == "Follow One" else 333,
            rev_timestamp="2026-03-15T00:00:00Z",
            source_url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            api_url="https://example.test/api",
            fetched_at="2026-03-15T00:00:01Z",
            categories=["Category:Example"],
            links=links,
            wikitext=f"Sample text for {title}",
            warnings=[],
        )

    monkeypatch.setattr(mod.wiki_pull_api, "_fetch_latest_wikitext", _fake_fetch_latest_wikitext)

    manifest = build_random_sample_manifest(
        wiki="enwiki",
        count=1,
        namespace=0,
        out_dir=tmp_path / "snapshots",
        timeout_s=10,
        wiki_rps=5.0,
        max_links=10,
        max_categories=10,
        include_wikitext=True,
        follow_hops=2,
        max_follow_links_per_page=1,
    )

    row = manifest["samples"][0]
    assert row["followed_snapshot_count"] == 1
    assert row["followed_samples"][0]["title"] == "Follow One"
    assert row["followed_samples"][0]["followed_snapshot_count"] == 1
    assert row["followed_samples"][0]["followed_samples"][0]["title"] == "Follow Two"


def test_random_sample_main_writes_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    from scripts import wiki_random_page_samples as mod

    monkeypatch.setattr(
        mod,
        "build_random_sample_manifest",
        lambda **_: {
            "schema_version": "wiki_random_page_sample_manifest_v0_1",
            "wiki": "enwiki",
            "requested_count": 1,
            "sampled_count": 1,
            "namespace": 0,
            "include_wikitext": True,
            "wiki_rps": 1.0,
            "generated_at": "2026-03-15T00:00:00Z",
            "samples": [{"title": "Example", "snapshot_path": str(tmp_path / "example.json")}],
        },
    )
    manifest_path = tmp_path / "manifest.json"
    exit_code = main(["--out-manifest", str(manifest_path)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert manifest_path.exists()
    assert payload["sampled_count"] == 1
