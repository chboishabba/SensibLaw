from src.runtime.partial_execution_timing import aggregate_partial_timing


def _row(document: str, stage: str, kernel: str, monotonic: int, cpu: int, rss: int):
    return {
        "document_ref": document,
        "active_stage": stage,
        "current_kernel": kernel,
        "resources": {
            "rss_bytes": rss,
            "process_tree_rss_bytes": rss * 2,
        },
        "partial_timing": {
            "observed_monotonic_ns": monotonic,
            "process_cpu_elapsed_ns": cpu,
        },
    }


def test_intervals_belong_to_previous_observed_owner() -> None:
    report = aggregate_partial_timing(
        [
            _row("d", "parser_annotation", "parser_fibre_execution", 100, 10, 5),
            _row("d", "parser_annotation", "parser_fibre_execution", 300, 80, 7),
            _row("d", "foreground", "sentence_closure", 500, 130, 11),
        ]
    )
    buckets = {
        (row["stage"], row["current_kernel"]): row for row in report["buckets"]
    }
    parser = buckets[("parser_annotation", "parser_fibre_execution")]
    assert parser["wall_ns"] == 400
    assert parser["process_cpu_ns"] == 120
    assert parser["interval_count"] == 2
    assert parser["peak_rss_bytes"] == 7
    assert parser["peak_process_tree_rss_bytes"] == 14


def test_partial_timing_can_never_satisfy_acceptance_gate() -> None:
    report = aggregate_partial_timing([])
    assert report["state"] == "partial_diagnostic_only"
    assert report["acceptance_eligible"] is False
    assert report["parser_relative_gate_eligible"] is False
    assert report["semantic_authority_effect"] == "none"
    assert report["concurrent_bucket_wall_ns_must_not_be_summed"] is True


def test_documents_do_not_form_cross_document_intervals() -> None:
    report = aggregate_partial_timing(
        [
            _row("a", "parser", "fibre", 10, 1, 1),
            _row("a", "parser", "fibre", 20, 2, 1),
            _row("b", "parser", "fibre", 1000, 1, 1),
            _row("b", "parser", "fibre", 1010, 2, 1),
        ]
    )
    assert report["document_count"] == 2
    assert report["buckets"][0]["wall_ns"] == 20
    assert report["unattributed_prefix_documents"] == 2
    assert report["open_tail_documents"] == 2
