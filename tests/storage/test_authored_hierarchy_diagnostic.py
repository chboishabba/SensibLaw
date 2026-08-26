from src.storage.postgres.hierarchy_diagnostic import classify_hierarchy_diagnostic


def _observation(**values):
    base = {
        "strict_v2_sentence_count": 10,
        "non_strict_sentence_count": 0,
        "sentence_region_count": 10,
        "sentence_region_mapping_count": 10,
        "paragraph_region_count": 2,
        "sentences_parented_to_paragraph": 10,
        "run_document_identity_consistent": True,
    }
    base.update(values)
    return base


def test_diagnostic_classifies_no_mappings_as_producer_mapping_defect():
    assert classify_hierarchy_diagnostic(
        _observation(sentence_region_mapping_count=0)
    ) == "producer/mapping_defect"


def test_diagnostic_classifies_orphan_regions_as_wrong_authoritative_relation():
    assert classify_hierarchy_diagnostic(
        _observation(sentences_parented_to_paragraph=0)
    ) == "wrong_authoritative_relation"


def test_diagnostic_classifies_valid_paragraph_parents():
    assert classify_hierarchy_diagnostic(_observation()) == "valid_authored_hierarchy"


def test_diagnostic_classifies_mismatched_generation_or_identity():
    assert classify_hierarchy_diagnostic(
        _observation(run_document_identity_consistent=False)
    ) == "incompatible_generation_or_revision"
    assert classify_hierarchy_diagnostic(
        _observation(strict_v2_sentence_count=0, non_strict_sentence_count=10)
    ) == "incompatible_generation_or_revision"


def test_diagnostic_classifies_missing_producer_hierarchy():
    assert classify_hierarchy_diagnostic(
        _observation(paragraph_region_count=0, sentence_region_count=0)
    ) == "producer_never_run"
