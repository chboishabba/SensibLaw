"""Audit projection of the closed numeric semantic leaf graph.

The projection is intentionally ephemeral: it is a benchmark inspection aid,
not a replacement for the portable publication receipt or a persistence model.
Structural occurrence keys deliberately exclude the semantic leaf digest and
post-resolution state so cross-version correspondence can be established before
semantic equality is tested.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from src.pnf.numeric_hyperfabric import TargetKind, numeric_digest
from src.storage.postgres.numeric_semantic_receipt import (
    _demand_leaves,
    _factor_leaves,
    _object_leaves,
    _proof_leaves,
)


def _tag(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def _hex(value: bytes) -> str:
    return bytes(value).hex()


def _shape(*values: Any) -> str:
    """Stable audit-only discriminator; it never participates in a receipt."""

    return sha256(repr(values).encode("utf-8")).hexdigest()


def _bytes(value: Any) -> bytes | None:
    return bytes(value) if value is not None else None


def project_numeric_semantic_leaf_audit(
    cursor: Any, *, run_ref: str, document_ref: str
) -> dict[str, Any]:
    """Project receipt leaves and their direct provenance/dependency edges.

    Database ids are used only while reading the authority. The returned node
    references are digest-derived, audit-local coordinates. ``occurrence_key``
    contains producer-side structure only; semantic value remains in
    ``digest_sha256`` and is compared only after correspondence is established.
    """

    objects = _object_leaves(cursor, run_ref=run_ref, document_ref=document_ref)
    factors = _factor_leaves(
        cursor, run_ref=run_ref, document_ref=document_ref, object_leaves=objects
    )
    demands = _demand_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
        factor_leaves=factors,
    )
    raw: dict[str, dict[str, Any]] = {}

    def add(
        family: str,
        local_id: int,
        digest: bytes,
        spans=(),
        dependencies=(),
        shape="",
        occurrence_key="",
    ) -> None:
        raw[f"{family}:{local_id}"] = {
            "family": family,
            "digest_sha256": _hex(digest),
            "source_spans": sorted({(int(start), int(end)) for start, end in spans}),
            "dependencies": [
                value
                for value in dependencies
                if value in raw
                or value.startswith(("object:", "factor:", "residual:"))
            ],
            "shape": shape,
            "occurrence_key": occurrence_key or shape,
        }

    cursor.execute(
        """
        SELECT object.object_id, token.start_char, token.end_char
          FROM execution.semantic_pnf_object AS object
          LEFT JOIN execution.semantic_pnf_object_token_support AS support
            ON support.object_id=object.object_id
          LEFT JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=object.region_id
         WHERE region.run_ref=%s AND region.document_ref=%s
        """,
        (run_ref, document_ref),
    )
    object_spans: dict[int, list[tuple[int, int]]] = {key: [] for key in objects}
    for object_id, start, end in cursor.fetchall():
        if start is not None:
            object_spans[int(object_id)].append((int(start), int(end)))

    cursor.execute(
        """
        SELECT object.object_id, object_kind.symbol_digest,
               support.ordinal, lemma.symbol_digest, dependency.symbol_digest
          FROM execution.semantic_pnf_object AS object
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=object.region_id
          JOIN execution.semantic_symbol AS object_kind
            ON object_kind.symbol_id=object.object_kind_symbol_id
          LEFT JOIN execution.semantic_pnf_object_token_support AS support
            ON support.object_id=object.object_id
          LEFT JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
          LEFT JOIN execution.semantic_symbol AS lemma
            ON lemma.symbol_id=token.lemma_symbol_id
          LEFT JOIN execution.semantic_symbol AS dependency
            ON dependency.symbol_id=token.dependency_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
         ORDER BY object.object_id, support.ordinal, token.start_char, token.end_char
        """,
        (run_ref, document_ref),
    )
    object_kind: dict[int, bytes | None] = {}
    object_support_shape: dict[int, list[tuple[Any, ...]]] = {key: [] for key in objects}
    for object_id, kind_digest, ordinal, lemma_digest, dependency_digest in cursor.fetchall():
        key = int(object_id)
        object_kind[key] = _bytes(kind_digest)
        if ordinal is not None:
            object_support_shape[key].append(
                (int(ordinal), _bytes(lemma_digest), _bytes(dependency_digest))
            )
    for object_id, digest in objects.items():
        add(
            "object",
            object_id,
            digest,
            object_spans[object_id],
            shape=_shape("object", len(object_spans[object_id])),
            occurrence_key=_shape(
                "object-occurrence:v1",
                object_kind.get(object_id),
                tuple(object_support_shape[object_id]),
            ),
        )

    cursor.execute(
        """
        SELECT factor.factor_id, token.start_char, token.end_char, edge.object_id
          FROM execution.semantic_pnf_factor AS factor
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=factor.region_id
          LEFT JOIN execution.semantic_pnf_factor_token_support AS support
            ON support.factor_id=factor.factor_id
          LEFT JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
          LEFT JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id=factor.factor_id
         WHERE region.run_ref=%s AND region.document_ref=%s
        """,
        (run_ref, document_ref),
    )
    factor_spans: dict[int, list[tuple[int, int]]] = {key: [] for key in factors}
    factor_dependencies: dict[int, set[str]] = {key: set() for key in factors}
    for factor_id, start, end, object_id in cursor.fetchall():
        factor_id = int(factor_id)
        if start is not None:
            factor_spans[factor_id].append((int(start), int(end)))
        if object_id is not None:
            factor_dependencies[factor_id].add(f"object:{int(object_id)}")

    cursor.execute(
        """
        SELECT factor.factor_id, factor_type.symbol_digest, predicate.symbol_digest,
               edge.slot_ordinal, role.symbol_digest, edge.required
          FROM execution.semantic_pnf_factor AS factor
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=factor.region_id
          JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id=factor.factor_type_symbol_id
          JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id=factor.predicate_symbol_id
          LEFT JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id=factor.factor_id
          LEFT JOIN execution.semantic_symbol AS role
            ON role.symbol_id=edge.role_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
         ORDER BY factor.factor_id, edge.slot_ordinal
        """,
        (run_ref, document_ref),
    )
    factor_head: dict[int, tuple[bytes | None, bytes | None]] = {}
    factor_roles: dict[int, list[tuple[Any, ...]]] = {key: [] for key in factors}
    for factor_id, factor_type, predicate, slot, role, required in cursor.fetchall():
        key = int(factor_id)
        factor_head[key] = (_bytes(factor_type), _bytes(predicate))
        if slot is not None:
            factor_roles[key].append((int(slot), _bytes(role), bool(required)))
    for factor_id, digest in factors.items():
        add(
            "factor",
            factor_id,
            digest,
            factor_spans[factor_id],
            factor_dependencies[factor_id],
            _shape("factor", len(factor_spans[factor_id]), len(factor_dependencies[factor_id])),
            _shape(
                "factor-occurrence:v1",
                factor_head.get(factor_id),
                tuple(factor_roles[factor_id]),
            ),
        )

    # Demand occurrence identity is producer-side. Migration 135 records exact
    # trigger/target/evidence token occurrences while producer structure exists.
    # resolved_target_* and demand state remain semantic outcomes and are absent
    # from the occurrence key.
    cursor.execute(
        """
        SELECT demand.demand_id, region.start_char, region.end_char,
               demand.source_object_id, demand.expected_target_kind,
               expected_factor.symbol_digest, expected_object.symbol_digest,
               lexical.symbol_digest, role.symbol_digest, residual.symbol_digest,
               demand.resolved_target_kind, demand.resolved_target_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
          LEFT JOIN execution.semantic_symbol AS expected_factor
            ON expected_factor.symbol_id=demand.expected_factor_type_symbol_id
          LEFT JOIN execution.semantic_symbol AS expected_object
            ON expected_object.symbol_id=demand.expected_object_kind_symbol_id
          LEFT JOIN execution.semantic_symbol AS lexical
            ON lexical.symbol_id=demand.lexical_symbol_id
          LEFT JOIN execution.semantic_symbol AS role
            ON role.symbol_id=demand.role_symbol_id
          LEFT JOIN execution.semantic_symbol AS residual
            ON residual.symbol_id=demand.residual_type_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
        """,
        (run_ref, document_ref),
    )
    demand_rows = tuple(cursor.fetchall())
    demand_ids = [int(row[0]) for row in demand_rows]
    provenance: dict[int, list[tuple[Any, ...]]] = {key: [] for key in demand_ids}
    if demand_ids:
        cursor.execute(
            """
            SELECT provenance.demand_id, provenance.occurrence_role,
                   provenance.ordinal,
                   token.start_char-region.start_char,
                   token.end_char-region.start_char,
                   lemma.symbol_digest, dependency.symbol_digest,
                   provenance.object_id
              FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id=provenance.demand_id
              JOIN execution.semantic_pnf_region AS region
                ON region.region_id=demand.source_region_id
              JOIN execution.semantic_parser_token AS token
                ON token.token_id=provenance.token_id
              LEFT JOIN execution.semantic_symbol AS lemma
                ON lemma.symbol_id=token.lemma_symbol_id
              LEFT JOIN execution.semantic_symbol AS dependency
                ON dependency.symbol_id=token.dependency_symbol_id
             WHERE provenance.demand_id=ANY(%s)
             ORDER BY provenance.demand_id, provenance.occurrence_role,
                      provenance.ordinal, token.start_char, token.end_char
            """,
            (demand_ids,),
        )
        for (
            demand_id,
            occurrence_role,
            occurrence_ordinal,
            relative_start,
            relative_end,
            lemma_digest,
            dependency_digest,
            occurrence_object_id,
        ) in cursor.fetchall():
            occurrence_object_key = None
            if occurrence_object_id is not None:
                occurrence_object_key = raw.get(
                    f"object:{int(occurrence_object_id)}", {}
                ).get("occurrence_key")
            provenance[int(demand_id)].append(
                (
                    int(occurrence_role),
                    int(occurrence_ordinal),
                    int(relative_start),
                    int(relative_end),
                    _bytes(lemma_digest),
                    _bytes(dependency_digest),
                    occurrence_object_key,
                )
            )

    for row in demand_rows:
        (
            demand_id,
            start,
            end,
            source_object_id,
            expected_target_kind,
            expected_factor_digest,
            expected_object_digest,
            lexical_digest,
            role_digest,
            residual_digest,
            resolved_target_kind,
            resolved_target_id,
        ) = row
        demand_id = int(demand_id)
        dependencies: list[str] = []
        source_object_occurrence_key = None
        if source_object_id is not None:
            source_ref = f"object:{int(source_object_id)}"
            dependencies.append(source_ref)
            source_object_occurrence_key = raw.get(source_ref, {}).get("occurrence_key")
        if resolved_target_kind is not None and resolved_target_id is not None:
            family = {
                int(TargetKind.OBJECT): "object",
                int(TargetKind.FACTOR): "factor",
                int(TargetKind.DEMAND): "residual",
            }.get(int(resolved_target_kind))
            if family:
                dependencies.append(f"{family}:{int(resolved_target_id)}")
        structural_head = (
            int(expected_target_kind),
            _bytes(expected_factor_digest),
            _bytes(expected_object_digest),
            _bytes(lexical_digest),
            _bytes(role_digest),
            _bytes(residual_digest),
        )
        residual_shape = _shape("residual-structural:v2", structural_head)
        add(
            "residual",
            demand_id,
            demands[demand_id],
            ((int(start), int(end)),),
            dependencies,
            residual_shape,
            _shape(
                "residual-occurrence:v2",
                source_object_occurrence_key,
                structural_head,
                tuple(provenance[demand_id]),
            ),
        )

    # Source-free exports inherit occurrence identity from their uniquely paired
    # target plus the producer slot. Key/residual/rank/score remain value.
    cursor.execute(
        """
        SELECT export.export_kind, export.target_kind, key_symbol.symbol_digest,
               residual.symbol_digest, export.rank, export.promotion_score,
               export.target_id
          FROM execution.semantic_pnf_interface_export AS export
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id=export.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=interface.region_id
          LEFT JOIN execution.semantic_symbol AS key_symbol
            ON key_symbol.symbol_id=export.key_symbol_id
          LEFT JOIN execution.semantic_symbol AS residual
            ON residual.symbol_id=export.residual_type_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
           AND region.region_kind=10 AND region.closure_state=3
         ORDER BY export.export_kind, export.target_kind, export.target_id,
                  export.rank, key_symbol.symbol_digest, residual.symbol_digest
        """,
        (run_ref, document_ref),
    )
    for ordinal, (
        export_kind,
        target_kind,
        key,
        residual,
        rank,
        score,
        target_id,
    ) in enumerate(cursor.fetchall()):
        family = {
            int(TargetKind.OBJECT): "object",
            int(TargetKind.FACTOR): "factor",
            int(TargetKind.DEMAND): "residual",
        }.get(int(target_kind))
        if family is None:
            continue
        target = {"object": objects, "factor": factors, "residual": demands}[
            family
        ].get(int(target_id))
        if target is None:
            continue
        digest = numeric_digest(
            _tag("root-export:v1"),
            int(export_kind),
            int(target_kind),
            bytes(key) if key is not None else None,
            bytes(residual) if residual is not None else None,
            int(rank),
            float(score),
            target,
        )
        add(
            "export",
            ordinal,
            digest,
            (),
            (f"{family}:{int(target_id)}",),
            _shape("export-value-shape:v2", export_kind, target_kind, key, residual, rank),
            _shape("export-occurrence:v2", int(export_kind), int(target_kind)),
        )

    # Reproduce the receipt proof query exactly so each returned digest remains
    # paired with the same derivation row even though the receipt root itself is
    # order-insensitive. Producer rule/slot structure is correspondence identity;
    # epistemic/result state and entity selection remain semantic value.
    proof_leaves = _proof_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
        factor_leaves=factors,
    )
    cursor.execute(
        """
        SELECT DISTINCT derivation.derivation_id, derivation.rule_ref,
               derivation.derivation_kind, derivation.derivation_state,
               derivation.epistemic_level, derivation.authority_class,
               factor_type.symbol_digest, predicate.symbol_digest,
               derivation.modal_state, derivation.temporal_state
          FROM execution.semantic_pnf_factor_derivation AS derivation
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise
            ON premise.derivation_id=derivation.derivation_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id=premise.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=factor.region_id
          LEFT JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id=derivation.conclusion_factor_type_symbol_id
          LEFT JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id=derivation.conclusion_predicate_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
           AND derivation.derivation_state=2
        """,
        (run_ref, document_ref),
    )
    proof_rows = tuple(cursor.fetchall())
    proof_ids = [int(row[0]) for row in proof_rows]
    proof_premise_shape: dict[int, list[int]] = {key: [] for key in proof_ids}
    proof_argument_shape: dict[int, list[tuple[Any, ...]]] = {key: [] for key in proof_ids}
    proof_dependencies: dict[int, list[str]] = {key: [] for key in proof_ids}
    if proof_ids:
        cursor.execute(
            """
            SELECT premise.derivation_id, premise.premise_ordinal, premise.factor_id
              FROM execution.semantic_pnf_factor_derivation_premise AS premise
             WHERE premise.derivation_id=ANY(%s)
             ORDER BY premise.derivation_id, premise.premise_ordinal
            """,
            (proof_ids,),
        )
        for proof_id, premise_ordinal, factor_id in cursor.fetchall():
            key = int(proof_id)
            proof_premise_shape[key].append(int(premise_ordinal))
            if int(factor_id) in factors:
                proof_dependencies[key].append(f"factor:{int(factor_id)}")
        cursor.execute(
            """
            SELECT argument.derivation_id, argument.slot_ordinal,
                   role.symbol_digest, argument.source_object_id,
                   argument.local_object_id
              FROM execution.semantic_pnf_factor_derivation_argument AS argument
              JOIN execution.semantic_symbol AS role
                ON role.symbol_id=argument.role_symbol_id
             WHERE argument.derivation_id=ANY(%s)
             ORDER BY argument.derivation_id, argument.slot_ordinal
            """,
            (proof_ids,),
        )
        for proof_id, slot, role_digest, source_object_id, local_object_id in cursor.fetchall():
            key = int(proof_id)
            proof_argument_shape[key].append(
                (int(slot), _bytes(role_digest), local_object_id is not None)
            )
            if int(source_object_id) in objects:
                proof_dependencies[key].append(f"object:{int(source_object_id)}")
            if local_object_id is not None and int(local_object_id) in objects:
                proof_dependencies[key].append(f"object:{int(local_object_id)}")

    if len(proof_rows) != len(proof_leaves):
        raise RuntimeError("proof audit row count disagrees with numeric receipt")
    for ordinal, (row, digest) in enumerate(zip(proof_rows, proof_leaves, strict=True)):
        proof_id = int(row[0])
        producer_shape = _shape(
            "proof-occurrence:v2",
            _tag(str(row[1])),
            int(row[2]),
            _bytes(row[6]),
            _bytes(row[7]),
            tuple(proof_premise_shape[proof_id]),
            tuple(proof_argument_shape[proof_id]),
        )
        add(
            "proof",
            ordinal,
            digest,
            (),
            proof_dependencies[proof_id],
            producer_shape,
            producer_shape,
        )

    refs: dict[str, str] = {}
    used: dict[str, int] = {}
    for old, node in sorted(
        raw.items(),
        key=lambda item: (item[1]["family"], item[1]["digest_sha256"], item[0]),
    ):
        base = f"{node['family']}:{node['digest_sha256'][:16]}"
        count = used.get(base, 0)
        used[base] = count + 1
        refs[old] = base if count == 0 else f"{base}:{count}"
    nodes = []
    for old, node in raw.items():
        nodes.append(
            {
                "ref": refs[old],
                "family": node["family"],
                "digest_sha256": node["digest_sha256"],
                "shape": node["shape"],
                "occurrence_key": node["occurrence_key"],
                "source_spans": [list(span) for span in node["source_spans"]],
                "dependencies": sorted(
                    refs[value] for value in node["dependencies"] if value in refs
                ),
            }
        )
    cursor.execute(
        "SELECT start_char,end_char FROM execution.semantic_parser_sentence "
        "WHERE run_ref=%s AND document_ref=%s ORDER BY start_char,end_char",
        (run_ref, document_ref),
    )
    return {
        "schema_version": "sensiblaw.numeric-semantic-leaf-audit.v1",
        "transport_authority": "audit_boundary_only",
        "correspondence_basis": "source-edit-transport+producer-structural-occurrence:v2",
        "nodes": sorted(nodes, key=lambda node: node["ref"]),
        "parser_sentence_spans": [
            [int(start), int(end)] for start, end in cursor.fetchall()
        ],
    }


__all__ = ["project_numeric_semantic_leaf_audit"]
