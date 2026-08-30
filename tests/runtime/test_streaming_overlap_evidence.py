from src.runtime.streaming_overlap_evidence import partition_aware_eof_overlap


def test_tiny_final_partition_does_not_fake_overlap() -> None:
    receipt = partition_aware_eof_overlap(
        partition_sentence_counts=(168, 73, 5, 1),
        semantic_sentences_at_parser_eof=246,
    )

    assert receipt.total_semantic_sentences == 247
    assert receipt.pre_final_partition_sentences == 246
    assert receipt.serial_eof_floor_fraction == 246 / 247
    assert receipt.observed_eof_completion_fraction == 246 / 247
    assert receipt.overlap_completion_gain_sentences == 0
    assert receipt.overlap_completion_gain_fraction == 0.0
    assert receipt.raw_eof_fraction_is_overlap_evidence is False


def test_completion_of_final_partition_before_eof_is_overlap_gain() -> None:
    receipt = partition_aware_eof_overlap(
        partition_sentence_counts=(50, 50, 50, 50),
        semantic_sentences_at_parser_eof=175,
    )

    assert receipt.pre_final_partition_sentences == 150
    assert receipt.overlap_completion_gain_sentences == 25
    assert receipt.overlap_completion_gain_fraction == 0.125
    assert receipt.raw_eof_fraction_is_overlap_evidence is True


def test_partition_shape_is_reported_separately_from_overlap() -> None:
    receipt = partition_aware_eof_overlap(
        partition_sentence_counts=(168, 73, 5, 1),
        semantic_sentences_at_parser_eof=247,
    )

    assert receipt.largest_partition_fraction == 168 / 247
    assert receipt.final_partition_fraction == 1 / 247
    assert receipt.overlap_completion_gain_sentences == 1
