from SensibLaw.src.sources.state_statute_portal import canonical_state_statute_portals


def test_canonical_portals_have_unique_states() -> None:
    portals = canonical_state_statute_portals()
    state_codes = {portal.state_code for portal in portals}
    assert len(state_codes) == len(portals)


def test_portal_portal_url_trimmed_slash() -> None:
    portal = canonical_state_statute_portals()[0]
    assert portal.portal_url().startswith(portal.base_url)


def test_build_search_payload_contains_metadata() -> None:
    portal = canonical_state_statute_portals()[1]
    payload = portal.build_search_payload("climate change")
    assert payload["source_label"].startswith("state_statutes")
    assert payload["metadata"]["state_code"] == portal.state_code
