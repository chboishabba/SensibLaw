from SensibLaw.src.follow.polity_follow_chain import (
    PolityFollowInput,
    build_polity_follow_chain,
)


def test_polity_follow_chain_maps_authority_graph():
    input_data = PolityFollowInput(
        seed_id="icj:seed:001",
        seed_source_family="icj_cases",
        parent_authority="UNSC Resolution 2270",
        child_implementation="National Sanctions Act",
        adjudication_jurisdiction="domestic_federal",
        adjudication_outcome="proceed with sanctions",
    )
    chain = build_polity_follow_chain(input_data)

    assert chain["seed"]["id"] == "icj:seed:001"
    assert chain["graph"]["parent_authority"]["signal"] == "authority_reference"
    assert chain["graph"]["child_implementation"]["name"] == "National Sanctions Act"
    assert chain["graph"]["adjudication"]["outcome"] == "proceed with sanctions"
    assert chain["polity_alignment"] == "tracked"
