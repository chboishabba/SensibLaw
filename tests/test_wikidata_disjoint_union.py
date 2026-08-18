from src.ontology.wikidata_disjoint_union import (
    DISJOINT_UNION_ANALYSIS_SCHEMA_VERSION,
    project_wikidata_disjoint_union_payload,
)


def _bundle(subject: str, prop: str, value: str, *, qualifiers=None):
    row = {
        "subject": subject,
        "property": prop,
        "rank": "preferred",
        "value": value,
    }
    if qualifiers is not None:
        row["qualifiers"] = qualifiers
    return row


def _payload(rows):
    return {
        "metadata": {
            "label_map": {
                "QH": "holder",
                "QA": "member A",
                "QB": "member B",
                "QC": "other child",
                "Qx": "x",
                "Qy": "y",
            }
        },
        "windows": [{"id": "dun-v1", "statement_bundles": rows}],
    }


def _dun_statement():
    return _bundle(
        "QH",
        "P2738",
        "Q23766486",
        qualifiers={"P11260": ["QA", "QB"]},
    )


def test_complete_finite_disjoint_union_passes_all_three_obligations() -> None:
    report = project_wikidata_disjoint_union_payload(
        _payload(
            [
                _dun_statement(),
                _bundle("QA", "P279", "QH"),
                _bundle("QB", "P279", "QH"),
                _bundle("Qx", "P31", "QA"),
                _bundle("Qy", "P31", "QB"),
            ]
        )
    )

    assert report["schema_version"] == DISJOINT_UNION_ANALYSIS_SCHEMA_VERSION
    assert report["semantics_scope"].startswith("known-entity finite-KB coverage")
    assert report["summary"] == {
        "disjoint_union_count": 1,
        "finite_dun_ok_count": 1,
        "component_not_subclass_count": 0,
        "union_exhaustivity_failure_count": 0,
        "pairwise_disjointness_failure_count": 0,
    }
    status = report["disjoint_unions"][0]
    assert status["components_subclass_holder_ok"] is True
    assert status["known_union_exhaustive_ok"] is True
    assert status["pairwise_known_disjoint_ok"] is True
    assert status["finite_dun_ok"] is True


def test_component_not_subclass_is_independent_failure() -> None:
    report = project_wikidata_disjoint_union_payload(
        _payload(
            [
                _dun_statement(),
                _bundle("QA", "P279", "QH"),
            ]
        )
    )

    assert report["summary"]["component_not_subclass_count"] == 1
    assert report["component_not_subclass_of_union"][0]["member_qid"] == "QB"
    status = report["disjoint_unions"][0]
    assert status["known_union_exhaustive_ok"] is True
    assert status["pairwise_known_disjoint_ok"] is True
    assert status["finite_dun_ok"] is False


def test_known_instance_exhaustivity_is_checked_separately() -> None:
    report = project_wikidata_disjoint_union_payload(
        _payload(
            [
                _dun_statement(),
                _bundle("QA", "P279", "QH"),
                _bundle("QB", "P279", "QH"),
                _bundle("QC", "P279", "QH"),
                _bundle("Qx", "P31", "QC"),
            ]
        )
    )

    assert report["summary"]["union_exhaustivity_failure_count"] == 1
    failure = report["union_exhaustivity_failures"][0]
    assert failure["qid"] == "Qx"
    assert failure["listed_members"] == ["QA", "QB"]
    status = report["disjoint_unions"][0]
    assert status["components_subclass_holder_ok"] is True
    assert status["pairwise_known_disjoint_ok"] is True
    assert status["known_union_exhaustive_ok"] is False
    assert status["finite_dun_ok"] is False


def test_pairwise_disjointness_failure_reuses_existing_instance_diagnostic() -> None:
    report = project_wikidata_disjoint_union_payload(
        _payload(
            [
                _dun_statement(),
                _bundle("QA", "P279", "QH"),
                _bundle("QB", "P279", "QH"),
                _bundle("Qx", "P31", "QA"),
                _bundle("Qx", "P31", "QB"),
            ]
        )
    )

    assert report["summary"]["pairwise_disjointness_failure_count"] == 1
    failure = report["pairwise_disjointness_failures"][0]
    assert failure["violation_kind"] == "instance"
    assert failure["witness_qid"] == "Qx"
    status = report["disjoint_unions"][0]
    assert status["components_subclass_holder_ok"] is True
    assert status["known_union_exhaustive_ok"] is True
    assert status["pairwise_known_disjoint_ok"] is False
    assert status["finite_dun_ok"] is False
