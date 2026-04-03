from __future__ import annotations

from src.sources.parliamentary_sources import canonical_parliamentary_sources


def test_parliamentary_sources_non_binding() -> None:
    sources = canonical_parliamentary_sources()
    assert all(source["binding_nature"] == "interpretive" for source in sources)
    kinds = {source["source_kind"] for source in sources}
    assert "debate_transcript" in kinds
    assert "committee_report" in kinds
    families = {source["source_family"] for source in sources}
    assert "uk_parliament" in families
    assert all(source["proof_context"].startswith("Iraq/Brexit") for source in sources)
