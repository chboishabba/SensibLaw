from __future__ import annotations

from pathlib import Path

from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    build_structural_partitions,
    byte_offsets,
    read_partition_text,
    write_source,
)


def test_byte_offsets_resolve_unicode_boundaries_without_dense_index() -> None:
    text = "alpha βeta 🐕 gamma"
    offsets = (0, 5, 6, 10, len(text))

    resolved = byte_offsets(text, offsets)

    for char_offset in offsets:
        assert resolved[char_offset] == len(text[:char_offset].encode("utf-8"))


def test_structural_partitions_have_exact_owner_coverage_and_bounded_context(
    tmp_path: Path,
) -> None:
    text = "\n\n".join(
        f"Section {index}. The café must retain record {index}."
        for index in range(140)
    )
    source_ref, source_path, _digest, _byte_count = write_source(text, tmp_path)
    policy = ParserStreamingPolicy(
        target_chars=1_024,
        context_chars=128,
        batch_size=2,
        cache_docbin=False,
    )

    partitions = build_structural_partitions(
        run_ref="run:parser:test",
        document_ref="document:parser:test",
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref="parser:test:v1",
        canonical_text=text,
        policy=policy,
    )

    assert partitions
    assert partitions[0].owner_start_char == 0
    assert partitions[-1].owner_end_char == len(text)
    assert all(
        left.owner_end_char == right.owner_start_char
        for left, right in zip(partitions, partitions[1:])
    )
    for partition in partitions:
        assert partition.context_start_char <= partition.owner_start_char
        assert partition.context_end_char >= partition.owner_end_char
        assert read_partition_text(partition) == text[
            partition.context_start_char : partition.context_end_char
        ]
        assert partition.context_text_byte_count <= len(
            text[partition.context_start_char : partition.context_end_char].encode(
                "utf-8"
            )
        )


def test_partition_identity_ignores_worker_and_completion_order(tmp_path: Path) -> None:
    text = ("A duty applies.\n\n" * 100).strip()
    source_ref, source_path, _digest, _byte_count = write_source(text, tmp_path)
    policy = ParserStreamingPolicy(target_chars=1_024, context_chars=64)

    first = build_structural_partitions(
        run_ref="run:stable",
        document_ref="document:stable",
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref="parser:stable:v1",
        canonical_text=text,
        policy=policy,
    )
    second = build_structural_partitions(
        run_ref="run:stable",
        document_ref="document:stable",
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref="parser:stable:v1",
        canonical_text=text,
        policy=policy,
    )

    assert [row.partition_ref for row in first] == [
        row.partition_ref for row in second
    ]
