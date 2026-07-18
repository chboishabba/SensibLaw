"""Direct PostgreSQL persistence for the generic corpus/compiler runtime.

The store writes normalized rows and compact byte streams.  It does not create
semantic JSON files, select identities, or promote claims.  JSON remains an
explicit interchange/export concern outside this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Iterator, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.token_codec import CorpusCodec, encode_delta_sequence


def _digest_bytes(hex_digest: str) -> bytes:
    try:
        return bytes.fromhex(hex_digest)
    except ValueError as error:
        raise ValueError("expected hexadecimal SHA-256 digest") from error


def _stable_bytes(value: Any) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _require_psycopg() -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PostgreSQL corpus compilation requires the 'postgres' extra "
            "(psycopg[binary]>=3.1)."
        ) from error
    return psycopg


@dataclass(frozen=True)
class PersistedCompilation:
    corpus_ref: str
    document_refs: tuple[str, ...]
    demand_refs: tuple[str, ...]
    failure_refs: tuple[str, ...]


class PostgresCompilerStore:
    """One operational PostgreSQL model for corpus, PNF, and resolution state."""

    def __init__(self, connection: Any):
        self.connection = connection

    @classmethod
    def connect(cls, database_url: str) -> "PostgresCompilerStore":
        psycopg = _require_psycopg()
        return cls(psycopg.connect(database_url))

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                yield cursor

    @contextmanager
    def savepoint(self) -> Iterator[Any]:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                yield cursor

    def persist_context(self, cursor: Any, context: Mapping[str, Any]) -> None:
        ref = str(context["context_ref"])
        cursor.execute(
            """
            INSERT INTO algebra.declaration
                (declaration_ref, declaration_kind, version_ref, content_sha256)
            VALUES (%s, 'compiler_context', %s, %s)
            ON CONFLICT (declaration_ref) DO NOTHING
            """,
            (ref, str(context["compiler_version"]), _stable_bytes(context)),
        )

    def persist_manifest(self, cursor: Any, manifest: Mapping[str, Any]) -> None:
        cursor.execute(
            """
            INSERT INTO corpus.corpus
                (corpus_ref, root_ref, compiler_context_ref, manifest_sha256)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (corpus_ref) DO NOTHING
            """,
            (
                str(manifest["corpus_ref"]),
                str(manifest["root_ref"]),
                str(manifest["compiler_context_ref"]),
                _digest_bytes(str(manifest["manifest_sha256"])),
            ),
        )

    def persist_source_document(
        self,
        cursor: Any,
        *,
        document_ref: str,
        media_type: str,
        content_sha256: str,
        source_bytes: bytes,
        canonical_text: str,
        adapter_ref: str,
        adapter_version: str,
        compiler_context_ref: str,
        normalization_ref: str,
    ) -> None:
        source_ref = f"source-content:{content_sha256}"
        canonical_sha = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
        canonical_ref = f"canonical-content:{canonical_sha}:{normalization_ref}"
        cursor.execute(
            """
            INSERT INTO corpus.binary_content
                (content_ref, content_sha256, media_type, payload,
                 uncompressed_byte_length)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (content_ref) DO NOTHING
            """,
            (source_ref, _digest_bytes(content_sha256), media_type, source_bytes, len(source_bytes)),
        )
        encoded = canonical_text.encode("utf-8")
        cursor.execute(
            """
            INSERT INTO corpus.canonical_content
                (canonical_ref, content_sha256, encoding_ref, normalization_ref,
                 payload, uncompressed_byte_length)
            VALUES (%s, %s, 'utf-8', %s, %s, %s)
            ON CONFLICT (canonical_ref) DO NOTHING
            """,
            (canonical_ref, _digest_bytes(canonical_sha), normalization_ref, encoded, len(encoded)),
        )
        cursor.execute(
            """
            INSERT INTO corpus.document
                (document_ref, source_content_ref, canonical_ref, media_type,
                 adapter_ref, adapter_version, compiler_context_ref, document_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_ref) DO NOTHING
            """,
            (
                document_ref,
                source_ref,
                canonical_ref,
                media_type,
                adapter_ref,
                adapter_version,
                compiler_context_ref,
                _stable_bytes(
                    {
                        "document_ref": document_ref,
                        "content_sha256": content_sha256,
                        "media_type": media_type,
                        "normalization_ref": normalization_ref,
                    }
                ),
            ),
        )

    def persist_occurrence(
        self,
        cursor: Any,
        *,
        corpus_ref: str,
        relative_path: str,
        document_ref: str,
        state: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO corpus.document_occurrence
                (corpus_ref, relative_path, document_ref, occurrence_state)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (corpus_ref, relative_path)
            DO UPDATE SET document_ref = EXCLUDED.document_ref,
                          occurrence_state = EXCLUDED.occurrence_state
            """,
            (corpus_ref, relative_path, document_ref, state),
        )

    def persist_tokens(
        self,
        cursor: Any,
        *,
        document_ref: str,
        tokenizer_ref: str,
        tokenizer_version: str,
        tokens: Sequence[tuple[str, int, int]],
        language_ref: str = "und",
        lexical_kind_ref: str = "surface",
    ) -> str:
        run_ref = "tokenizer-run:" + canonical_sha256(
            {
                "document_ref": document_ref,
                "tokenizer_ref": tokenizer_ref,
                "tokenizer_version": tokenizer_version,
                "tokens": tokens,
            }
        )
        lexeme_ids: list[int] = []
        starts: list[int] = []
        ends: list[int] = []
        for surface, start, end in tokens:
            normalized = surface.casefold()
            cursor.execute(
                """
                INSERT INTO language.lexeme
                    (language_ref, normalized_text, lexical_kind_ref)
                VALUES (%s, %s, %s)
                ON CONFLICT (language_ref, normalized_text, lexical_kind_ref)
                DO UPDATE SET normalized_text = EXCLUDED.normalized_text
                RETURNING lexeme_id
                """,
                (language_ref, normalized, lexical_kind_ref),
            )
            lexeme_ids.append(int(cursor.fetchone()[0]))
            starts.append(start)
            ends.append(end)
        output_sha = _stable_bytes({"lexeme_ids": lexeme_ids, "starts": starts, "ends": ends})
        cursor.execute(
            """
            INSERT INTO language.tokenizer_run
                (tokenizer_run_ref, document_ref, tokenizer_ref, tokenizer_version,
                 token_count, output_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tokenizer_run_ref) DO NOTHING
            """,
            (run_ref, document_ref, tokenizer_ref, tokenizer_version, len(tokens), output_sha),
        )
        codec = CorpusCodec.from_lexeme_ids(lexeme_ids)
        codec_ref = "codec:" + canonical_sha256(
            {"run_ref": run_ref, "mapping": codec.logical_to_symbol}
        )
        cursor.execute(
            """
            INSERT INTO language.codec
                (codec_ref, codec_kind_ref, codec_version, dictionary_sha256)
            VALUES (%s, 'frequency-ranked-uvarint', 'v0_1', %s)
            ON CONFLICT (codec_ref) DO NOTHING
            """,
            (codec_ref, _stable_bytes(codec.logical_to_symbol)),
        )
        frequency = {value: lexeme_ids.count(value) for value in set(lexeme_ids)}
        ranked = sorted(frequency, key=lambda value: (-frequency[value], value))
        for rank, lexeme_id in enumerate(ranked):
            cursor.execute(
                """
                INSERT INTO language.codec_symbol
                    (codec_ref, symbol_code, lexeme_id, frequency_rank)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (codec_ref, symbol_code) DO NOTHING
                """,
                (codec_ref, codec.logical_to_symbol[lexeme_id], lexeme_id, rank),
            )
        encoded_symbols = codec.encode(lexeme_ids)
        encoded_offsets = encode_delta_sequence(
            [value for pair in zip(starts, ends, strict=True) for value in pair]
        )
        cursor.execute(
            """
            INSERT INTO language.token_stream_chunk
                (tokenizer_run_ref, chunk_index, first_token_index, token_count,
                 codec_ref, encoded_symbols, encoded_offsets, content_sha256)
            VALUES (%s, 0, 0, %s, %s, %s, %s, %s)
            ON CONFLICT (tokenizer_run_ref, chunk_index) DO NOTHING
            """,
            (
                run_ref,
                len(tokens),
                codec_ref,
                encoded_symbols,
                encoded_offsets,
                hashlib.sha256(encoded_symbols + encoded_offsets).digest(),
            ),
        )
        return run_ref

    def persist_annotation_layer(
        self, cursor: Any, *, document_ref: str, layer: Mapping[str, Any]
    ) -> None:
        layer_ref = str(layer["layer_ref"])
        cursor.execute(
            """
            INSERT INTO language.annotation_layer
                (annotation_layer_ref, document_ref, backend_ref, backend_version,
                 input_sha256, output_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (annotation_layer_ref) DO NOTHING
            """,
            (
                layer_ref,
                document_ref,
                str(layer.get("tokenizer_ref") or "unknown"),
                "v0_1",
                _digest_bytes(str(layer["text_sha256"])),
                _stable_bytes(layer),
            ),
        )
        for token in layer.get("token_annotations") or ():
            node_ref = f"{layer_ref}:token:{token['token_index']}"
            cursor.execute(
                """
                INSERT INTO language.annotation_node
                    (annotation_node_ref, annotation_layer_ref, annotation_type_ref,
                     value_ref)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (annotation_node_ref) DO NOTHING
                """,
                (node_ref, layer_ref, str(token["annotation_type"]), str(token["value"])),
            )
        for span in layer.get("span_annotations") or ():
            cursor.execute(
                """
                INSERT INTO language.annotation_node
                    (annotation_node_ref, annotation_layer_ref, annotation_type_ref,
                     value_ref)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (annotation_node_ref) DO NOTHING
                """,
                (
                    str(span["span_ref"]),
                    layer_ref,
                    str(span["annotation_type"]),
                    str((span.get("value") or {}).get("surface") or ""),
                ),
            )

    def persist_pnf_graph(
        self, cursor: Any, *, document_ref: str, graph: Mapping[str, Any]
    ) -> None:
        graph_ref = str(graph["graph_ref"])
        factors = graph.get("factors") or ()
        graph_state = "locally_closed" if all(
            row.get("closure_state") in {"locally_closed", "closed", "not_required"}
            for row in factors
        ) else "open"
        cursor.execute(
            """
            INSERT INTO pnf.graph
                (graph_ref, document_ref, graph_type_ref, schema_version_ref,
                 closure_state_ref, graph_sha256)
            VALUES (%s, %s, 'generic.factor_graph', 'v0_1', %s, %s)
            ON CONFLICT (graph_ref) DO NOTHING
            """,
            (graph_ref, document_ref, graph_state, _stable_bytes(graph)),
        )
        for factor in factors:
            factor_ref = str(factor["factor_ref"])
            cursor.execute(
                """
                INSERT INTO algebra.factor
                    (factor_ref, document_ref, factor_type_ref, closure_state_ref,
                     factor_sha256)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (factor_ref) DO NOTHING
                """,
                (
                    factor_ref,
                    document_ref,
                    str(factor["factor_type"]),
                    str(factor["closure_state"]),
                    _stable_bytes(factor),
                ),
            )
            cursor.execute(
                """
                INSERT INTO pnf.graph_factor (graph_ref, factor_ref, graph_role_ref)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (graph_ref, factor_ref, str(factor["factor_type"])),
            )
            for alternative in factor.get("alternatives") or ():
                alternative_ref = str(alternative["alternative_ref"])
                value = alternative.get("value")
                cursor.execute(
                    """
                    INSERT INTO algebra.alternative
                        (alternative_ref, type_ref, value_ref, value_literal,
                         authority_state_ref, alternative_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (alternative_ref) DO NOTHING
                    """,
                    (
                        alternative_ref,
                        str(alternative["type_ref"]),
                        str(value.get("mention_ref")) if isinstance(value, Mapping) and value.get("mention_ref") else None,
                        None if isinstance(value, Mapping) else str(value),
                        str(alternative.get("authority_state") or "candidate_only"),
                        _stable_bytes(alternative),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO algebra.factor_alternative
                        (factor_ref, alternative_ref, alternative_state_ref)
                    VALUES (%s, %s, 'alternative')
                    ON CONFLICT DO NOTHING
                    """,
                    (factor_ref, alternative_ref),
                )
            for residual in factor.get("residuals") or ():
                residual_ref = f"{factor_ref}:residual:{residual}"
                cursor.execute(
                    """
                    INSERT INTO algebra.residual
                        (residual_ref, target_ref, residual_type_ref,
                         residual_state_ref, residual_sha256)
                    VALUES (%s, %s, %s, 'open', %s)
                    ON CONFLICT (residual_ref) DO NOTHING
                    """,
                    (residual_ref, factor_ref, str(residual), _stable_bytes({"factor": factor_ref, "residual": residual})),
                )

    def persist_resolution_artifacts(
        self,
        cursor: Any,
        *,
        demands: Sequence[Mapping[str, Any]],
        evidence: Sequence[Mapping[str, Any]],
        meets: Sequence[Mapping[str, Any]],
        refinements: Sequence[Mapping[str, Any]],
    ) -> tuple[str, ...]:
        demand_refs: list[str] = []
        for row in evidence:
            cursor.execute(
                """
                INSERT INTO evidence.local_evidence
                    (evidence_ref, document_ref, evidence_type_ref, relation_ref,
                     evidence_sha256)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (evidence_ref) DO NOTHING
                """,
                (
                    str(row["evidence_ref"]),
                    str(row["document_ref"]),
                    str(row["evidence_type"]),
                    str(row.get("relation") or ""),
                    _stable_bytes(row),
                ),
            )
            for subject_ref in row.get("subject_refs") or ():
                cursor.execute(
                    """
                    INSERT INTO evidence.local_evidence_subject (evidence_ref, subject_ref)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """,
                    (str(row["evidence_ref"]), str(subject_ref)),
                )
        for row in demands:
            demand_ref = str(row["demand_ref"])
            demand_refs.append(demand_ref)
            cursor.execute(
                """
                INSERT INTO resolution.demand
                    (demand_ref, factor_ref, subject_kind_ref, formal_role_ref,
                     scope_ref, semantic_key_sha256, budget_class_ref,
                     demand_state_ref)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
                ON CONFLICT (demand_ref) DO NOTHING
                """,
                (
                    demand_ref,
                    str(row["factor_ref"]),
                    str(row.get("subject_kind") or row.get("factor_type") or "unknown"),
                    row.get("formal_role"),
                    str(row.get("scope_ref") or row.get("document_ref") or "document_local"),
                    _stable_bytes(row.get("semantic_key") or row),
                    str(row.get("budget_class") or "default"),
                ),
            )
            for facet in row.get("requested_facets") or ():
                cursor.execute(
                    "INSERT INTO resolution.demand_facet VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (demand_ref, str(facet)),
                )
        for row in meets:
            cursor.execute(
                """
                INSERT INTO resolution.typed_meet
                    (meet_ref, left_ref, right_ref, meet_type_ref, meet_state_ref,
                     meet_sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (meet_ref) DO NOTHING
                """,
                (
                    str(row["meet_ref"]),
                    str(row["left_ref"]),
                    str(row["right_ref"]),
                    str(row["meet_type"]),
                    str(row["state"]),
                    _stable_bytes(row),
                ),
            )
            for evidence_ref in row.get("evidence_refs") or ():
                cursor.execute(
                    "INSERT INTO resolution.meet_evidence VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (str(row["meet_ref"]), str(evidence_ref)),
                )
        for row in refinements:
            cursor.execute(
                """
                INSERT INTO resolution.refinement
                    (refinement_ref, prior_factor_ref, resulting_factor_ref,
                     refinement_sha256)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (refinement_ref) DO NOTHING
                """,
                (
                    str(row["refinement_ref"]),
                    str(row["prior_factor_ref"]),
                    str(row["resulting_factor_ref"]),
                    _stable_bytes(row),
                ),
            )
        return tuple(sorted(demand_refs))

    def persist_failure(
        self, cursor: Any, *, target_ref: str, phase_ref: str, error: Exception
    ) -> str:
        identity = {
            "target_ref": target_ref,
            "phase_ref": phase_ref,
            "failure_type_ref": type(error).__name__,
            "detail": str(error),
        }
        failure_ref = "failure:" + canonical_sha256(identity)
        cursor.execute(
            """
            INSERT INTO execution.failure_receipt
                (failure_ref, target_ref, phase_ref, failure_type_ref, detail,
                 failure_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (failure_ref) DO NOTHING
            """,
            (
                failure_ref,
                target_ref,
                phase_ref,
                type(error).__name__,
                str(error),
                _stable_bytes(identity),
            ),
        )
        return failure_ref

    def document_summary(self, document_ref: str) -> Mapping[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM corpus.v_document_summary WHERE document_ref = %s",
                (document_ref,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            names = [column.name for column in cursor.description]
            return dict(zip(names, row, strict=True))

    def unresolved_demands(self, corpus_ref: str) -> tuple[Mapping[str, Any], ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM resolution.v_unresolved_demand
                WHERE corpus_ref = %s
                ORDER BY semantic_key_sha256, demand_ref
                """,
                (corpus_ref,),
            )
            names = [column.name for column in cursor.description]
            return tuple(dict(zip(names, row, strict=True)) for row in cursor.fetchall())
