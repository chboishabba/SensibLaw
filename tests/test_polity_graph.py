from SensibLaw.src.follow.polity_graph import POLITY_GRAPH


def test_polity_graph_includes_expected_parents():
    expected_parents = {"EU", "RU", "PIF", "GCC", "US", "AU"}
    assert expected_parents.issubset(set(POLITY_GRAPH.keys()))


def test_polity_graph_child_adjudication_pairs():
    edge = POLITY_GRAPH["EU"]["national_gov"]
    assert edge.parent == "EU"
    assert edge.child == "national_gov"
    assert edge.adjudication == "CJEU opinion"
