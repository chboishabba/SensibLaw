"""Expose already-measured strict numeric kernel timings to durable progress."""

from __future__ import annotations


_INSTALL_MARKER = "_numeric_kernel_timing_execution_installed"
_KERNEL_FIELDS = (
    # Existing parser receipt counts are carried alongside timing so benchmark
    # consumers get the canonical cross-document denominator without another
    # PostgreSQL COUNT(*) pass.
    "token_count",
    "sentence_count",
    "partition_count",
    "spacy_parser_work_ns",
    "numeric_projection_worker_work_ns",
    "sentence_closure_worker_work_ns",
    "sentence_closure_coordinator_ns",
    "sentence_adjacency_ns",
    "hierarchy_work_ns",
    "paragraph_adjacency_ns",
    "lookup_publication_ns",
    "summary_work_ns",
    "post_parser_worker_work_ns",
    "post_parser_coordinator_ns",
    "post_parser_work_ns",
    "timing_basis",
)


def install_numeric_kernel_timing_execution() -> bool:
    from src.policy import numeric_pnf_compilation as numeric

    if getattr(numeric, _INSTALL_MARKER, False):
        return False
    # compile_numeric_pnf_document reads this module-level tuple dynamically.
    # Extending it therefore changes only observability projection; no parser,
    # semantic, or publication work is added.
    numeric._NUMERIC_TIMING_FIELDS = _KERNEL_FIELDS
    setattr(numeric, _INSTALL_MARKER, True)
    return True


__all__ = ["install_numeric_kernel_timing_execution"]
