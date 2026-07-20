"""Compile the full GWB corpus twice and emit a corpus-scoped binding ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_binding_candidate_storage import (  # noqa: E402
    collect_binding_report,
)
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.postgres_corpus_compilation import (  # noqa: E402
    compile_directory_postgres,
)
from src.storage.postgres import PostgresCompilerStore  # noqa: E402


DEFAULT_GWB_CORPUS = ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "raw"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL; defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_GWB_CORPUS,
        help="Full GWB corpus directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test-results/gwb-binding-baseline.json"),
    )
    parser.add_argument("--expected-documents", type=int, default=6)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _compile(store: PostgresCompilerStore, input_dir: Path):
    return compile_directory_postgres(
        input_dir,
        context=default_compiler_context(),
        store=store,
        execution_phase="local",
    )


def _report(store: PostgresCompilerStore, corpus_ref: str) -> dict[str, Any]:
    with store.transaction() as cursor:
        return collect_binding_report(cursor, corpus_ref=corpus_ref)


def _coordinate_report(
    store: PostgresCompilerStore, corpus_ref: str
) -> dict[str, int]:
    """Measure source/canonical separation and persisted span/token parity."""

    with store.transaction() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE document.media_type = 'text/html'),
                COUNT(*) FILTER (WHERE source.payload = canonical.payload),
                COUNT(*) FILTER (
                    WHERE document.media_type = 'text/html'
                      AND convert_from(canonical.payload, 'UTF8') ~*
                          '<[[:space:]]*/?[[:space:]]*'
                          '(html|head|body|script|style|div|span|a|li)'
                          '([[:space:]]|>|/)'
                )
            FROM corpus.document AS document
            JOIN corpus.binary_content AS source
              ON source.content_ref = document.source_content_ref
            JOIN corpus.canonical_content AS canonical
              ON canonical.canonical_ref = document.canonical_ref
            WHERE document.document_ref IN (
                SELECT DISTINCT occurrence.document_ref
                FROM corpus.document_occurrence AS occurrence
                WHERE occurrence.corpus_ref = %s
            )
            """,
            (corpus_ref,),
        )
        (
            document_count,
            html_document_count,
            source_equals_canonical_count,
            canonical_markup_document_count,
        ) = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE substring(
                        convert_from(canonical.payload, 'UTF8')
                        FROM span.start_char + 1
                        FOR span.end_char - span.start_char
                    ) <> COALESCE(node.value_ref, '')
                ),
                COUNT(*) FILTER (
                    WHERE COALESCE(node.value_ref, '') ~
                          '^[[:space:]]*(<|</|class=|href=|data-)'
                )
            FROM corpus.span AS span
            JOIN corpus.document AS document
              ON document.document_ref = span.document_ref
            JOIN corpus.canonical_content AS canonical
              ON canonical.canonical_ref = document.canonical_ref
            JOIN language.annotation_node AS node
              ON node.span_ref = span.span_ref
             AND node.annotation_type_ref = 'licensed_mention'
            WHERE span.span_type_ref = 'licensed_mention'
              AND span.document_ref IN (
                  SELECT DISTINCT occurrence.document_ref
                  FROM corpus.document_occurrence AS occurrence
                  WHERE occurrence.corpus_ref = %s
              )
            """,
            (corpus_ref,),
        )
        mention_count, mention_mismatch_count, markup_mention_count = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(DISTINCT lexeme.lexeme_id)
            FROM language.tokenizer_run AS run
            JOIN language.token_stream_chunk AS chunk
              ON chunk.tokenizer_run_ref = run.tokenizer_run_ref
            JOIN language.codec_symbol AS symbol
              ON symbol.codec_ref = chunk.codec_ref
            JOIN language.lexeme AS lexeme
              ON lexeme.lexeme_id = symbol.lexeme_id
            WHERE run.document_ref IN (
                SELECT DISTINCT occurrence.document_ref
                FROM corpus.document_occurrence AS occurrence
                WHERE occurrence.corpus_ref = %s
            )
              AND lexeme.normalized_text ~ '[<>]'
            """,
            (corpus_ref,),
        )
        markup_lexeme_count = int(cursor.fetchone()[0])

    return {
        "documents": int(document_count),
        "html_documents": int(html_document_count),
        "source_equals_canonical_documents": int(source_equals_canonical_count),
        "canonical_markup_documents": int(canonical_markup_document_count),
        "licensed_mentions": int(mention_count),
        "licensed_mention_surface_mismatches": int(mention_mismatch_count),
        "markup_fragment_mentions": int(markup_mention_count),
        "markup_lexemes": markup_lexeme_count,
    }


def _refs_sha256(refs: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for ref in refs:
        digest.update(ref.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _compile_summary(compilation: Any) -> dict[str, object]:
    return {
        "corpus_ref": compilation.corpus_ref,
        "documents": len(compilation.document_refs),
        "open_demands": len(compilation.demand_refs),
        "failures": len(compilation.failure_refs),
        "document_refs": list(compilation.document_refs),
        "demand_refs_sha256": _refs_sha256(compilation.demand_refs),
        "failure_refs": list(compilation.failure_refs),
    }


def _assert_first_run(
    compilation: Any,
    report: dict[str, Any],
    coordinate_report: dict[str, int],
    *,
    expected_documents: int,
) -> None:
    documents = report["documents"]
    binding = report["semantic_metrics"]["binding"]
    demands = report["semantic_metrics"]["demands"]
    execution = report["execution_metrics"]
    assert len(compilation.document_refs) == expected_documents, (
        len(compilation.document_refs),
        expected_documents,
    )
    assert not compilation.failure_refs, compilation.failure_refs
    assert documents["document_occurrences"] == expected_documents
    assert documents["documents"] == expected_documents
    assert binding["candidate_sets"] > 0
    assert binding["candidate_set_builds"] == binding["candidate_sets"]
    assert demands["demands"] == len(compilation.demand_refs)
    assert demands["open_demands"] == len(compilation.demand_refs)
    assert demands["demands_missing_factor_revision"] == 0
    assert execution["pairwise_binding_evidence_rows"] == 0
    assert execution["occurrence_states"] == {"compiled": expected_documents}

    assert coordinate_report["documents"] == expected_documents
    assert coordinate_report["html_documents"] == expected_documents
    assert coordinate_report["source_equals_canonical_documents"] == 0
    assert coordinate_report["canonical_markup_documents"] == 0
    assert coordinate_report["licensed_mentions"] > 0
    assert coordinate_report["licensed_mention_surface_mismatches"] == 0
    assert coordinate_report["markup_fragment_mentions"] == 0
    assert coordinate_report["markup_lexemes"] == 0


def _assert_reuse(
    first: Any,
    second: Any,
    first_report: dict[str, Any],
    second_report: dict[str, Any],
    first_coordinate_report: dict[str, int],
    second_coordinate_report: dict[str, int],
    *,
    expected_documents: int,
) -> dict[str, object]:
    first_binding = first_report["semantic_metrics"]["binding"]
    second_binding = second_report["semantic_metrics"]["binding"]
    first_factors = first_report["semantic_metrics"]["factors"]
    second_factors = second_report["semantic_metrics"]["factors"]
    first_demands = first_report["semantic_metrics"]["demands"]
    second_demands = second_report["semantic_metrics"]["demands"]
    second_execution = second_report["execution_metrics"]

    checks = {
        "same_corpus_ref": second.corpus_ref == first.corpus_ref,
        "same_document_refs": second.document_refs == first.document_refs,
        "same_demand_refs": second.demand_refs == first.demand_refs,
        "no_second_run_failures": not second.failure_refs,
        "candidate_sets_unchanged": (
            second_binding["candidate_sets"] == first_binding["candidate_sets"]
        ),
        "candidate_members_unchanged": (
            second_binding["candidate_members"] == first_binding["candidate_members"]
        ),
        "candidate_builds_unchanged": (
            second_binding["candidate_set_builds"]
            == first_binding["candidate_set_builds"]
        ),
        "factor_revisions_unchanged": (
            second_factors["factor_revisions"] == first_factors["factor_revisions"]
        ),
        "refinements_unchanged": (
            second_factors["refinements"] == first_factors["refinements"]
        ),
        "demands_unchanged": (
            second_demands["demands"] == first_demands["demands"]
        ),
        "canonical_coordinates_unchanged": (
            second_coordinate_report == first_coordinate_report
        ),
        "all_occurrences_reused": (
            second_execution["occurrence_states"]
            == {"reused_compilation": expected_documents}
        ),
        "document_build_count_unchanged": (
            second_execution["document_compilation_builds"]
            == first_report["execution_metrics"]["document_compilation_builds"]
        ),
        "pairwise_binding_evidence_absent": (
            second_execution["pairwise_binding_evidence_rows"] == 0
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    assert not failed, failed
    return checks


def _relative_input_dir(input_dir: Path) -> str:
    try:
        return str(input_dir.relative_to(ROOT))
    except ValueError:
        return str(input_dir)


def main() -> int:
    args = _parse_args()
    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"GWB corpus directory not found: {input_dir}")
    source_files = sorted(path for path in input_dir.rglob("*") if path.is_file())
    if len(source_files) != args.expected_documents:
        raise SystemExit(
            "GWB corpus file count disagrees with acceptance contract: "
            f"found={len(source_files)} expected={args.expected_documents}"
        )

    store = PostgresCompilerStore.connect(args.database_url)
    try:
        first = _compile(store, input_dir)
        first_report = _report(store, first.corpus_ref)
        first_coordinate_report = _coordinate_report(store, first.corpus_ref)
        _assert_first_run(
            first,
            first_report,
            first_coordinate_report,
            expected_documents=args.expected_documents,
        )

        second = _compile(store, input_dir)
        second_report = _report(store, second.corpus_ref)
        second_coordinate_report = _coordinate_report(store, second.corpus_ref)
        reuse_checks = _assert_reuse(
            first,
            second,
            first_report,
            second_report,
            first_coordinate_report,
            second_coordinate_report,
            expected_documents=args.expected_documents,
        )
    finally:
        store.close()

    output = {
        "proof": "full-gwb-local-pnf-binding-baseline:v0_2",
        "input_dir": _relative_input_dir(input_dir),
        "source_files": [str(path.relative_to(input_dir)) for path in source_files],
        "expected_documents": args.expected_documents,
        "first_compile": _compile_summary(first),
        "second_compile": _compile_summary(second),
        "first_report": first_report,
        "second_report": second_report,
        "first_coordinate_integrity": first_coordinate_report,
        "second_coordinate_integrity": second_coordinate_report,
        "reuse_checks": reuse_checks,
        "authority_boundary": {
            "candidate_membership_is_not_identity_closure": True,
            "singleton_candidate_set_is_not_resolution": True,
            "zero_member_candidate_set_is_not_expletivity": True,
            "statistics_do_not_rank_or_select_antecedents": True,
            "external_evidence_invoked": False,
            "readiness_or_promotion_invoked": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(output, indent=2, sort_keys=True)
    args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
