#!/usr/bin/env python3
"""Generate a proof-relevant factor report for arbitrary entity surfaces."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.storage.postgres.epistemic_factor_report import (
    collect_epistemic_entity_report,
    render_epistemic_entity_report,
)
from src.storage.postgres.spacy_parser_model import connect


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an epistemically stratified factor report without using "
            "co-occurrence or paragraph co-presence as identity evidence."
        )
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection URL.",
    )
    parser.add_argument(
        "--surface",
        action="append",
        required=True,
        help=(
            "Exact surface identity to include (case-insensitive). Repeat for "
            "aliases that should be treated only as report-entry surfaces."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional Markdown output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--refresh-run-id",
        type=int,
        help=(
            "Optional numeric run id. When supplied with --refresh-document-id, "
            "materialise proof-relevant identity/derivation rows before reading."
        ),
    )
    parser.add_argument(
        "--refresh-document-id",
        type=int,
        help="Optional numeric document id paired with --refresh-run-id.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if (args.refresh_run_id is None) != (args.refresh_document_id is None):
        raise SystemExit(
            "--refresh-run-id and --refresh-document-id must be supplied together"
        )

    with connect(args.database_url) as connection:
        if args.refresh_run_id is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                      FROM execution.refresh_numeric_pnf_semantic_derivations(
                          %s, %s
                      )
                    """,
                    (args.refresh_run_id, args.refresh_document_id),
                )
                cursor.fetchone()
            connection.commit()

        report = collect_epistemic_entity_report(connection, args.surface)
        rendered = render_epistemic_entity_report(report)

    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
