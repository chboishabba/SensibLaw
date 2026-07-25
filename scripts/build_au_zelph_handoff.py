#!/usr/bin/env python3
"""Build an AU Zelph handoff from the relational PostgreSQL follow projection."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage.postgres.follow_projection_store import query_follow_projection
from src.zelph_bridge import run_zelph_inference
from src.zelph_execution import assess_zelph_execution

ARTIFACT_VERSION = "au_public_handoff_v2"
REQUIRED_OUTPUT_PREDICATES = ("au_procedural_fact",)


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("AU Zelph handoff requires psycopg") from exc
    return psycopg.connect(database_url)


def _sanitize(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def _facts_from_projection(result) -> str:
    lines: list[str] = []
    for row in result.nodes:
        node_ref = str(row.get("node_ref") or "")
        node_id = "node_" + _sanitize(node_ref)
        lines.append(f'{node_id} "kind" "{row.get("node_kind")}"')
        lines.append(f'{node_id} "label" "{str(row.get("label") or "").replace(chr(34), chr(39))}"')
    for row in result.edges:
        source_id = "node_" + _sanitize(str(row.get("source_node_ref") or ""))
        target_id = "node_" + _sanitize(str(row.get("target_node_ref") or ""))
        predicate = str(row.get("relation_kind") or "follows")
        lines.append(f'{source_id} "{predicate}" "{target_id}"')
        lines.append(
            f'{source_id} "edge_admissibility" "{row.get("admissibility_state")}"'
        )
    return "\n".join(dict.fromkeys(lines)) + "\n"


def _rules() -> str:
    return (
        "# AU PostgreSQL follow-projection handoff rules\n\n"
        '(X "node_kind" "semantic.procedural_outcome") => (X "au_procedural_fact" "true")\n'
        '(X "relation_kind" "applies") => (X "au_procedural_fact" "true")\n'
        'X "au_procedural_fact" "true"\n'
    )


def build_handoff_artifact(
    *,
    database_url: str,
    projection_ref: str,
    output_dir: Path,
) -> dict[str, Any]:
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("AU Zelph handoff requires PostgreSQL DATABASE_URL")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            projection = query_follow_projection(cursor, projection_ref)
    facts_text = _facts_from_projection(projection)
    rules_text = _rules()
    engine_payload = run_zelph_inference(facts_text, rules_text)
    execution = assess_zelph_execution(
        profile_ref="profile:au-zelph-handoff-postgres:v0_1",
        engine_payload=engine_payload,
        required_predicates=REQUIRED_OUTPUT_PREDICATES,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "facts_path": output_dir / f"{ARTIFACT_VERSION}.facts.zlp",
        "rules_path": output_dir / f"{ARTIFACT_VERSION}.rules.zlp",
        "engine_path": output_dir / f"{ARTIFACT_VERSION}.engine.json",
        "receipt_path": output_dir / f"{ARTIFACT_VERSION}.execution.json",
        "presentation_path": output_dir / f"{ARTIFACT_VERSION}.presentation.json",
    }
    paths["facts_path"].write_text(facts_text, encoding="utf-8")
    paths["rules_path"].write_text(rules_text, encoding="utf-8")
    paths["engine_path"].write_text(
        json.dumps(engine_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["receipt_path"].write_text(
        json.dumps(execution.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["presentation_path"].write_text(
        json.dumps(projection.presentation_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "projection_ref": projection_ref,
        "execution": execution.to_dict(),
        "successful_handoff": execution.successful_handoff,
        "required_output_predicates": list(REQUIRED_OUTPUT_PREDICATES),
        "postgresql_semantic_authority": True,
        "json_presentation_only": True,
        **{key: str(value) for key, value in paths.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build AU Zelph handoff from PostgreSQL follow projection."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
    )
    parser.add_argument("--projection-ref", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/fixtures/zelph") / ARTIFACT_VERSION,
    )
    args = parser.parse_args(argv)
    result = build_handoff_artifact(
        database_url=args.database_url,
        projection_ref=args.projection_ref,
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["successful_handoff"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
