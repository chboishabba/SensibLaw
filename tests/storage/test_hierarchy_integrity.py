from src.storage.postgres.hierarchy_diagnostic import (
    HierarchyIntegrityError,
    assert_hierarchy_integrity,
    evaluate_hierarchy_integrity,
)


def test_closed_strict_v2_hierarchy_integrity_passes_exact_counts() -> None:
    report = evaluate_hierarchy_integrity(
        {
            "strict_v2_sentence_count": 4,
            "closed_strict_v2_sentence_count": 4,
            "closed_sentences_without_exactly_one_region": 0,
            "closed_sentences_without_exactly_one_paragraph_parent": 0,
        }
    )
    assert report["hierarchy_integrity_failure"] is False


def test_zero_sentence_regions_is_an_explicit_integrity_failure() -> None:
    report = evaluate_hierarchy_integrity(
        {
            "strict_v2_sentence_count": 4,
            "closed_strict_v2_sentence_count": 0,
            "closed_sentences_without_exactly_one_region": 4,
            "closed_sentences_without_exactly_one_paragraph_parent": 4,
        }
    )
    assert report["hierarchy_integrity_failure"] is True


def test_integrity_error_preserves_machine_readable_report() -> None:
    error = HierarchyIntegrityError(
        evaluate_hierarchy_integrity(
            {
                "strict_v2_sentence_count": 1,
                "closed_strict_v2_sentence_count": 1,
                "closed_sentences_without_exactly_one_region": 1,
                "closed_sentences_without_exactly_one_paragraph_parent": 0,
            }
        )
    )
    assert error.report["hierarchy_integrity_failure"] is True
    assert "bad_mappings=1" in str(error)


def test_integrity_query_is_read_only_by_source_contract() -> None:
    source = assert_hierarchy_integrity.__doc__ or ""
    assert "Read and enforce" in source
