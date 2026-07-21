"""Direct PostgreSQL persistence for the generic compiler substrate.

The store accepts a DB-API connection supplied by the application, keeping the
semantic compiler independent of a particular PostgreSQL driver. It is not a
SQLite parity adapter.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol

from src.policy.carriers.canonical import canonical_sha256


class PostgresConnection(Protocol):
    def cursor(self) -> Any: ...

    def commit(self) -> None: ...


class PostgresCompilerStore:
    """Persist immutable compiler projections through migration 007 tables."""

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection

    @classmethod
    def connect(cls, connection_string: str) -> "PostgresCompilerStore":
        """Open the direct PostgreSQL store when the optional driver is installed."""

        try:
            import psycopg
        except ModuleNotFoundError as error:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "install SensibLaw with the postgres extra to use PostgresCompilerStore.connect"
            ) from error
        return cls(psycopg.connect(connection_string))

    @staticmethod
    def build_key(
        *, document_ref: str, content_sha256: str, context: Mapping[str, Any]
    ) -> str:
        return canonical_sha256(
            {
                "document_ref": document_ref,
                "content_sha256": content_sha256,
                "context": context,
                "compiler_contract": "postgres-semantic-compiler:v0_3",
            }
        )

    def load_completed(
        self, *, document_ref: str, build_key_sha256: str
    ) -> Mapping[str, Any] | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload FROM compiler_build
                WHERE document_ref = %s AND build_stage = 'demand_projection'
                  AND build_key_sha256 = %s AND status = 'completed'
                """,
                (document_ref, build_key_sha256),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        payload = row[0]
        return payload if isinstance(payload, Mapping) else json.loads(payload)

    def persist(
        self,
        *,
        compilation: Mapping[str, Any],
        context: Mapping[str, Any],
        build_key_sha256: str,
    ) -> None:
        """Write a complete immutable compilation and its dependency chain."""

        document_ref = str(compilation["document_ref"])
        artifacts = compilation["artifacts"]
        with self._connection.cursor() as cursor:
            self._upsert_document(cursor, compilation, context)
            declaration_refs = self._upsert_declarations(cursor, artifacts)
            build_refs = self._upsert_builds(
                cursor,
                document_ref=document_ref,
                compilation=compilation,
                context=context,
                declaration_refs=declaration_refs,
                build_key_sha256=build_key_sha256,
            )
            self._upsert_annotations(
                cursor, document_ref, artifacts, build_refs["annotation"]
            )
            self._upsert_pnf(
                cursor, document_ref, artifacts, build_refs["pnf_construction"]
            )
            self._upsert_meets_refinements_demands(cursor, document_ref, artifacts)
        self._connection.commit()

    def _upsert_document(
        self, cursor: Any, compilation: Mapping[str, Any], context: Mapping[str, Any]
    ) -> None:
        artifacts = compilation["artifacts"]
        cursor.execute(
            """
            INSERT INTO compiler_document
              (document_ref, content_sha256, media_type, canonical_text, canonicalisation_ref)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (document_ref) DO NOTHING
            """,
            (
                compilation["document_ref"],
                compilation["content_sha256"],
                compilation["media_type"],
                artifacts["canonical_text"],
                context["media_normalization_ref"],
            ),
        )

    def _upsert_declarations(
        self, cursor: Any, artifacts: Mapping[str, Any]
    ) -> tuple[str, ...]:
        refs: list[str] = []
        declarations = (
            artifacts.get("compiler_declarations")
            or artifacts.get("semantic_reduction_declarations")
            or ()
        )
        for declaration in declarations:
            declaration_ref = str(declaration["declaration_ref"])
            declaration_kind = str(declaration.get("declaration_kind") or "grammar")
            cursor.execute(
                """
                INSERT INTO compiler_declaration
                  (declaration_ref, declaration_kind, revision_sha256, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (declaration_ref) DO NOTHING
                """,
                (
                    declaration_ref,
                    declaration_kind,
                    canonical_sha256(declaration),
                    json.dumps(declaration, sort_keys=True),
                ),
            )
            refs.append(declaration_ref)
        return tuple(sorted(refs))

    def _upsert_builds(
        self,
        cursor: Any,
        *,
        document_ref: str,
        compilation: Mapping[str, Any],
        context: Mapping[str, Any],
        declaration_refs: tuple[str, ...],
        build_key_sha256: str,
    ) -> dict[str, str]:
        stages = (
            "canonicalisation",
            "tokenisation",
            "annotation",
            "reduction",
            "pnf_construction",
            "local_meet_planning",
            "typed_meet",
            "factor_refinement",
            "demand_projection",
        )
        refs: dict[str, str] = {}
        prior_ref: str | None = None
        for stage in stages:
            build_ref = f"compiler-build:{document_ref}:{stage}:{build_key_sha256}"
            payload = {"compilation": compilation, "context": context, "stage": stage}
            cursor.execute(
                """
                INSERT INTO compiler_build
                  (build_ref, document_ref, build_stage, build_key_sha256, input_sha256, output_sha256, status, payload)
                VALUES (%s, %s, %s, %s, %s, %s, 'completed', %s::jsonb)
                ON CONFLICT (document_ref, build_stage, build_key_sha256) DO NOTHING
                """,
                (
                    build_ref,
                    document_ref,
                    stage,
                    build_key_sha256,
                    canonical_sha256(context),
                    canonical_sha256(payload),
                    json.dumps(payload, sort_keys=True),
                ),
            )
            if prior_ref:
                cursor.execute(
                    """INSERT INTO compiler_build_dependency (build_ref, dependency_kind, dependency_ref)
                    VALUES (%s, 'build', %s) ON CONFLICT DO NOTHING""",
                    (build_ref, prior_ref),
                )
            if stage == "reduction":
                for declaration_ref in declaration_refs:
                    cursor.execute(
                        """INSERT INTO compiler_build_dependency (build_ref, dependency_kind, dependency_ref)
                        VALUES (%s, 'declaration', %s) ON CONFLICT DO NOTHING""",
                        (build_ref, declaration_ref),
                    )
            refs[stage] = build_ref
            prior_ref = build_ref
        return refs

    def _upsert_annotations(
        self,
        cursor: Any,
        document_ref: str,
        artifacts: Mapping[str, Any],
        build_ref: str,
    ) -> None:
        for layer_key in ("annotation_layer", "semantic_annotation_layer"):
            layer = artifacts.get(layer_key)
            if not layer:
                continue
            cursor.execute(
                """INSERT INTO compiler_annotation_layer
                (layer_ref, document_ref, build_ref, tokenizer_ref, text_sha256, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (layer_ref) DO NOTHING""",
                (
                    layer["layer_ref"],
                    document_ref,
                    build_ref,
                    layer["tokenizer_ref"],
                    layer["text_sha256"],
                    json.dumps(layer, sort_keys=True),
                ),
            )
            for token in layer.get("token_annotations") or ():
                cursor.execute(
                    """INSERT INTO compiler_annotation_token
                    (layer_ref, token_index, annotation_type, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (layer_ref, token_index, annotation_type) DO NOTHING""",
                    (
                        token["layer_ref"]
                        if "layer_ref" in token
                        else layer["layer_ref"],
                        token["token_index"],
                        token["annotation_type"],
                        json.dumps(token, sort_keys=True),
                    ),
                )
            for span in layer.get("span_annotations") or ():
                cursor.execute(
                    """INSERT INTO compiler_annotation_span
                    (span_ref, layer_ref, start_token, end_token, annotation_type, payload)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (span_ref) DO NOTHING""",
                    (
                        span["span_ref"],
                        layer["layer_ref"],
                        span["start_token"],
                        span["end_token"],
                        span["annotation_type"],
                        json.dumps(span, sort_keys=True),
                    ),
                )
            for relation in layer.get("relation_annotations") or ():
                cursor.execute(
                    """INSERT INTO compiler_annotation_relation
                    (relation_ref, layer_ref, relation_type, left_ref, right_ref, payload)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (relation_ref) DO NOTHING""",
                    (
                        relation["relation_ref"],
                        layer["layer_ref"],
                        relation["relation_type"],
                        relation["left_ref"],
                        relation["right_ref"],
                        json.dumps(relation, sort_keys=True),
                    ),
                )

    def _upsert_pnf(
        self,
        cursor: Any,
        document_ref: str,
        artifacts: Mapping[str, Any],
        build_ref: str,
    ) -> None:
        graph = artifacts["pnf_graph"]
        cursor.execute(
            """INSERT INTO compiler_pnf_graph (graph_ref, document_ref, build_ref, payload)
            VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT (graph_ref) DO NOTHING""",
            (
                graph["graph_ref"],
                document_ref,
                build_ref,
                json.dumps(graph, sort_keys=True),
            ),
        )
        for factor in graph.get("factors") or ():
            cursor.execute(
                """INSERT INTO compiler_pnf_factor (factor_ref, graph_ref, factor_type, payload)
                VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT (factor_ref) DO NOTHING""",
                (
                    factor["factor_ref"],
                    graph["graph_ref"],
                    factor["factor_type"],
                    json.dumps(factor, sort_keys=True),
                ),
            )
            revision_ref = "factor-revision:" + canonical_sha256(factor)
            cursor.execute(
                """INSERT INTO compiler_factor_revision
                (factor_revision_ref, factor_ref, revision_sha256, closure_state, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT (factor_ref, revision_sha256) DO NOTHING""",
                (
                    revision_ref,
                    factor["factor_ref"],
                    canonical_sha256(factor),
                    factor["closure_state"],
                    json.dumps(factor, sort_keys=True),
                ),
            )

    def _upsert_meets_refinements_demands(
        self, cursor: Any, document_ref: str, artifacts: Mapping[str, Any]
    ) -> None:
        for meet in artifacts.get("typed_meets") or ():
            cursor.execute(
                """INSERT INTO compiler_typed_meet
                (meet_ref, document_ref, left_ref, right_ref, meet_type, meet_state, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (meet_ref) DO NOTHING""",
                (
                    meet["meet_ref"],
                    document_ref,
                    meet["left_ref"],
                    meet["right_ref"],
                    meet["meet_type"],
                    meet["state"],
                    json.dumps(meet, sort_keys=True),
                ),
            )
        for refinement in artifacts.get("factor_refinements") or ():
            prior, result = refinement["prior_factor"], refinement["resulting_factor"]
            prior_ref = "factor-revision:" + canonical_sha256(prior)
            result_ref = str(
                result.get("metadata", {}).get("factor_revision_ref")
                or "factor-revision:" + canonical_sha256(result)
            )
            for revision_ref, factor, parent in (
                (prior_ref, prior, None),
                (result_ref, result, prior_ref),
            ):
                cursor.execute(
                    """INSERT INTO compiler_factor_revision
                    (factor_revision_ref, factor_ref, prior_factor_revision_ref, revision_sha256, closure_state, payload)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (factor_ref, revision_sha256) DO NOTHING""",
                    (
                        revision_ref,
                        factor["factor_ref"],
                        parent,
                        canonical_sha256(factor),
                        factor["closure_state"],
                        json.dumps(factor, sort_keys=True),
                    ),
                )
            cursor.execute(
                """INSERT INTO compiler_factor_refinement
                (refinement_ref, document_ref, factor_ref, prior_factor_revision_ref, resulting_factor_revision_ref, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (refinement_ref) DO NOTHING""",
                (
                    refinement["refinement_ref"],
                    document_ref,
                    prior["factor_ref"],
                    prior_ref,
                    result_ref,
                    json.dumps(refinement, sort_keys=True),
                ),
            )
        factors = {
            row["factor_ref"]: row for row in artifacts["refined_pnf_graph"]["factors"]
        }
        for demand in artifacts.get("resolution_demands") or ():
            factor = factors[demand["factor_ref"]]
            factor_revision_ref = str(
                factor.get("metadata", {}).get("factor_revision_ref")
                or "factor-revision:" + canonical_sha256(factor)
            )
            cursor.execute(
                """INSERT INTO compiler_resolution_demand
                (demand_ref, document_ref, factor_revision_ref, subject_kind, formal_role, semantic_key_sha256, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (demand_ref) DO NOTHING""",
                (
                    demand["demand_ref"],
                    document_ref,
                    factor_revision_ref,
                    demand["factor_type"],
                    None,
                    canonical_sha256(demand["semantic_key"]),
                    json.dumps(demand, sort_keys=True),
                ),
            )


__all__ = ["PostgresCompilerStore", "PostgresConnection"]
