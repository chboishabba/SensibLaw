from src.runtime.partial_parser_timing import (
    ParserPartitionTiming,
    summarize_partition_timings,
)


def test_partition_parser_work_is_not_promoted_to_wall_occupancy():
    result = summarize_partition_timings(
        (
            ParserPartitionTiming("partition:a", 1000, 50, 2_000_000_000, 101, 201),
            ParserPartitionTiming("partition:b", 1500, 70, 3_000_000_000, 102, 202),
        )
    )
    assert result["spacy_parser_work_ns"] == 5_000_000_000
    assert result["token_count"] == 2500
    assert result["spacy_parser_wall_occupancy_ns"] is None
    assert result["concurrent_partition_work_ns_must_not_be_treated_as_wall"] is True
    assert result["acceptance_eligible"] is False
    assert result["parser_relative_gate_eligible"] is False


def test_parser_work_throughput_uses_direct_spacy_work_only():
    result = summarize_partition_timings(
        (ParserPartitionTiming("partition:a", 4000, 100, 2_000_000_000, 101, None),)
    )
    assert result["tokens_per_parser_work_second"] == 2000.0
    assert result["max_partition_spacy_ns"] == 2_000_000_000
