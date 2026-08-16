import pytest

from src.ontology.lean_wikidata_certificate import (
    CONTRACT,
    LeanCertificateError,
    LeanOntologyCertificate,
    compare_external_relation,
    load_certificate_packet,
)
from src.ontology.ontology_issue_detector import detect_ontology_issues


def _certificate_row(**overrides):
    row = {
        "request_id": "ae06ae06-2580-422a-8fc3-92aeaaca8762",
        "module_name": "RequestProject.ClassAlgebra",
        "theorem_name": "unionOk_sound",
        "checker_name": "unionOk",
        "source_snapshot": "wikidata-fragment:artist-painter-sculptor",
        "subject_ref": "wd:artist",
        "predicate_ref": "wdt:P2737",
        "object_ref": "wd:painter|wd:sculptor",
        "relation_kind": "union_of",
        "source_references": ["aristotle:ae06ae06-2580-422a-8fc3-92aeaaca8762"],
        "checker_accepted": True,
        "theorem_backed": True,
    }
    row.update(overrides)
    return row


def test_positive_theorem_backed_checker_projects_to_supported_without_authority() -> None:
    certificate = LeanOntologyCertificate.from_mapping(_certificate_row())

    assert certificate.epistemic_state == "supported"
    receipt = certificate.to_receipt()
    assert receipt["truth_authority"] is False
    assert receipt["edit_authority"] is False
    assert receipt["checker_name"] == "unionOk"


def test_failed_checker_is_unresolved_not_contradicted() -> None:
    certificate = LeanOntologyCertificate.from_mapping(
        _certificate_row(checker_accepted=False)
    )

    assert certificate.epistemic_state == "unresolved"
    comparison = compare_external_relation(certificate, external_state="supported")
    assert comparison.disposition == "unresolved"


def test_unbacked_checker_is_unresolved() -> None:
    certificate = LeanOntologyCertificate.from_mapping(
        _certificate_row(theorem_backed=False)
    )

    assert certificate.epistemic_state == "unresolved"


def test_supported_pair_replicates_and_explicit_opposition_conflicts() -> None:
    certificate = LeanOntologyCertificate.from_mapping(_certificate_row())

    replicated = compare_external_relation(certificate, external_state="supported")
    conflicting = compare_external_relation(
        certificate,
        external_state="contradicted",
        external_references=["sio:SIO_000593-not-subclass-example"],
    )

    assert replicated.disposition == "replicated"
    assert conflicting.disposition == "conflicting"


def test_only_explicit_cross_ontology_conflict_becomes_review_issue() -> None:
    certificate = LeanOntologyCertificate.from_mapping(_certificate_row())
    conflict = compare_external_relation(
        certificate,
        external_state="contradicted",
        external_references=["external-ontology:explicit-incompatibility"],
    ).to_receipt()

    issues = detect_ontology_issues(formal_relation_comparisons=[conflict])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "cross_ontology_explicit_relation_conflict"
    assert issue.status == "review_required"
    assert issue.confidence_band == "high"
    assert issue.details["checker_name"] == "unionOk"
    assert issue.details["truth_authority"] is False
    assert "external-ontology:explicit-incompatibility" in issue.evidence_refs


def test_replication_and_unresolved_comparisons_do_not_become_issues() -> None:
    supported = LeanOntologyCertificate.from_mapping(_certificate_row())
    failed = LeanOntologyCertificate.from_mapping(
        _certificate_row(checker_accepted=False)
    )

    comparisons = [
        compare_external_relation(supported, external_state="supported").to_receipt(),
        compare_external_relation(failed, external_state="supported").to_receipt(),
    ]

    assert detect_ontology_issues(formal_relation_comparisons=comparisons) == []


def test_packet_loader_is_strict_and_deterministic() -> None:
    packet = {"contract": CONTRACT, "certificates": [_certificate_row()]}

    loaded = load_certificate_packet(packet)

    assert len(loaded) == 1
    assert loaded[0].theorem_name == "unionOk_sound"


def test_unknown_relation_kind_fails_closed() -> None:
    with pytest.raises(LeanCertificateError):
        LeanOntologyCertificate.from_mapping(_certificate_row(relation_kind="maybe_related"))
