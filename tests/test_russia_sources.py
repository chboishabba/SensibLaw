from SensibLaw.src.sources.russia_sources import canonical_russian_legal_sources


def test_unique_source_ids():
    sources = canonical_russian_legal_sources()
    ids = {s.source_id for s in sources}
    assert len(ids) == len(sources)


def test_payload_contains_language_and_layer():
    source = canonical_russian_legal_sources()[0]
    payload = source.build_source_payload("federal assembly powers")
    metadata = payload["metadata"]
    assert metadata["language"].startswith("r")
    assert "authority_layer" in metadata
