"""Audit projection of the closed numeric semantic leaf graph.

The projection is intentionally ephemeral: it is a benchmark inspection aid,
not a replacement for the portable publication receipt or a persistence model.
Structural occurrence keys deliberately exclude the semantic leaf digest so
cross-version correspondence can be tested independently of semantic equality.
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
    references are digest-derived, audit-local coordinates. `occurrence_key`
    contains stable structural/provenance shape only; semantic value remains in
    `digest_sha256` and is compared only after correspondence is established.
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
    ):
        raw[f"{family}:{local_id}"] = {
            "family": family,
            "digest_sha256": _hex(digest),
            "source_spans": sorted({(int(start), int(end)) for start, end in spans}),
            "dependencies": [
                value
                for value in dependencies
                if value in raw or value.startswith(("object:", "factor:", "residual:"))
            ],
            "shape": shape,
            "occurrence_key": occurrence_key or shape,
        }

    cursor.execute(
        """
        SELECT object.object_id, token.start_char, token.end_char
          FROM execution.semantic_pnf_object AS object
          LEFT JOIN execution.semantic_pnf_object_token_support AS support
            ON support.object_id = object.object_id
          LEFT JOIN execution.semantic_parser_token AS token ON token.token_id = support.token_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id = object.region_id
         WHERE region.run_ref=%s AND region.document_ref=%s
        """,
        (run_ref, document_ref),
    )
    object_spans: dict[int, list[tuple[int, int]]] = {key: [] for key in objects}
    for object_id, start, end in cursor.fetchall():
        if start is not None:
            object_spans[int(object_id)].append((int(start), int(end)))

    # Structural object identity is independent of promotion scores/state and of
    # the final receipt digest. Ordered support role plus parser lemma/dependency
    # symbols distinguish repeated same-span objects without using DB-local ids.
    cursor.execute(
        """
        SELECT object.object_id, object_kind.symbol_digest,
               support.ordinal, lemma.symbol_digest, dependency.symbol_digest
          FROM execution.semantic_pnf_object AS object
          JOIN execution.semantic_pnf_region AS region ON region.region_id=object.region_id
          JOIN execution.semantic_symbol AS object_kind ON object_kind.symbol_id=object.object_kind_symbol_id
          LEFT JOIN execution.semantic_pnf_object_token_support AS support ON support.object_id=object.object_id
          LEFT JOIN execution.semantic_parser_token AS token ON token.token_id=support.token_id
          LEFT JOIN execution.semantic_symbol AS lemma ON lemma.symbol_id=token.lemma_symbol_id
          LEFT JOIN execution.semantic_symbol AS dependency ON dependency.symbol_id=token.dependency_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
         ORDER BY object.object_id, support.ordinal, token.start_char, token.end_char
        """,
        (run_ref, document_ref),
    )
    object_kind: dict[int, bytes | None] = {}
    object_support_shape: dict[int, list[tuple[Any, ...]]] = {
        key: [] for key in objects
    }
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
          JOIN execution.semantic_pnf_region AS region ON region.region_id=factor.region_id
          LEFT JOIN execution.semantic_pnf_factor_token_support AS support ON support.factor_id=factor.factor_id
          LEFT JOIN execution.semantic_parser_token AS token ON token.token_id=support.token_id
          LEFT JOIN execution.semantic_pnf_hyperedge AS edge ON edge.factor_id=factor.factor_id
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
               edge.slot_ordinal, role.symbol_digest, edge.resolution_state, edge.required
          FROM execution.semantic_pnf_factor AS factor
          JOIN execution.semantic_pnf_region AS region ON region.region_id=factor.region_id
          JOIN execution.semantic_symbol AS factor_type ON factor_type.symbol_id=factor.factor_type_symbol_id
          JOIN execution.semantic_symbol AS predicate ON predicate.symbol_id=factor.predicate_symbol_id
          LEFT JOIN execution.semantic_pnf_hyperedge AS edge ON edge.factor_id=factor.factor_id
          LEFT JOIN execution.semantic_symbol AS role ON role.symbol_id=edge.role_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s
         ORDER BY factor.factor_id, edge.slot_ordinal
        """,
        (run_ref, document_ref),
    )
    factor_head: dict[int, tuple[bytes | None, bytes | None]] = {}
    factor_roles: dict[int, list[tuple[Any, ...]]] = {key: [] for key in factors}
    for factor_id, factor_type, predicate, slot, role, resolution, required in cursor.fetchall():
        key = int(factor_id)
        factor_head[key] = (_bytes(factor_type), _bytes(predicate))
        if slot is not None:
            factor_roles[key].append(
                (int(slot), _bytes(role), int(resolution), bool(required))
            )
    for factor_id, digest in factors.items():
        add(
            "factor",
            factor_id,
            digest,
            factor_spans[factor_id],
            factor_dependencies[factor_id],
            _shape(
                "factor",
                len(factor_spans[factor_id]),
                len(factor_dependencies[factor_id]),
            ),
            _shape(
                "factor-occurrence:v1",
                factor_head.get(factor_id),
                tuple(factor_roles[factor_id]),
            ),
        )

    cursor.execute(
        """
        SELECT demand.demand_id, region.start_char, region.end_char,
               demand.source_object_id, demand.resolved_target_kind, demand.resolved_target_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE region.run_ref=%s AND region.document_ref=%s
        """,
        (run_ref, document_ref),
    )
    for (
        demand_id,
        start,
        end,
        source_object_id,
        target_kind,
        target_id,
    ) in cursor.fetchall():
        dependencies: list[str] = []
        if source_object_id is not None:
            dependencies.append(f"object:{int(source_object_id)}")
        if target_kind is not None and target_id is not None:
            family = {
                int(TargetKind.OBJECT): "object",
                int(TargetKind.FACTOR): "factor",
                int(TargetKind.DEMAND): "residual",
            }.get(int(target_kind))
            if family:
                dependencies.append(f"{family}:{int(target_id)}")
        residual_shape = _shape("residual", source_object_id is not None, target_kind)
        add(
            "residual",
            int(demand_id),
            demands[int(demand_id)],
            ((int(start), int(end)),),
            dependencies,
            residual_shape,
            _shape(
                "residual-occurrence:v1",
                source_object_id is not None,
                int(target_kind) if target_kind is not None else None,
                len(dependencies),
            ),
        )

    cursor.execute(
        """
        SELECT export.export_kind, export.target_kind, key_symbol.symbol_digest,
               residual.symbol_digest, export.rank, export.promotion_score, export.target_id
          FROM execution.semantic_pnf_interface_export AS export
          JOIN execution.semantic_pnf_interface AS interface ON interface.interface_id=export.interface_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=interface.region_id
          LEFT JOIN execution.semantic_symbol AS key_symbol ON key_symbol.symbol_id=export.key_symbol_id
          LEFT JOIN execution.semantic_symbol AS residual ON residual.symbol_id=export.residual_type_symbol_id
         WHERE region.run_ref=%s AND region.document_ref=%s AND region.region_kind=10 AND region.closure_state=3
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
        export_shape = _shape("export", export_kind, target_kind, key, residual, rank)
        add(
            "export",
            ordinal,
            digest,
            (),
            (f"{family}:{int(target_id)}",),
            export_shape,
            export_shape,
        )

    # Proof leaves are exact receipt leaves. Their factor/object dependencies are
    # projected where available; entity identity remains part of the exact digest
    # and is not reinterpreted by this audit layer.
    proof_leaves = _proof_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
        factor_leaves=factors,
    )
    cursor.execute(
        """
        SELECT DISTINCT derivation.derivation_id
          FROM execution.semantic_pnf_factor_derivation AS derivation
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise ON premise.derivation_id=derivation.derivation_id
          JOIN execution.semantic_pnf_factor AS factor ON factor.factor_id=premise.factor_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=factor.region_id
         WHERE region.run_ref=%s AND region.document_ref=%s AND derivation.derivation_state=2
         ORDER BY derivation.derivation_id
        """,
        (run_ref, document_ref),
    )
    proof_ids = [int(row[0]) for row in cursor.fetchall()]
    for ordinal, (proof_id, digest) in enumerate(
        zip(proof_ids, proof_leaves, strict=True)
    ):
        cursor.execute(
            """
            SELECT 'factor', factor_id FROM execution.semantic_pnf_factor_derivation_premise WHERE derivation_id=%s
            UNION
            SELECT 'object', source_object_id FROM execution.semantic_pnf_factor_derivation_argument WHERE derivation_id=%s
            UNION
            SELECT 'object', local_object_id FROM execution.semantic_pnf_factor_derivation_argument WHERE derivation_id=%s AND local_object_id IS NOT NULL
            """,
            (proof_id, proof_id, proof_id),
        )
        dependencies = []
        for family, value in cursor.fetchall():
            if str(family) == "factor" and int(value) in factors:
                dependencies.append(f"factor:{int(value)}")
            elif str(family) == "object" and int(value) in objects:
                dependencies.append(f"object:{int(value)}")
        proof_shape = _shape("proof", len(dependencies))
        add(
            "proof",
            ordinal,
            digest,
            (),
            dependencies,
            proof_shape,
            proof_shape,
        )

    # Replace database-local references with deterministic audit-local refs.
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
        "SELECT start_char,end_char FROM execution.semantic_parser_sentence WHERE run_ref=%s AND document_ref=%s ORDER BY start_char,end_char",
        (run_ref, document_ref),
    )
    return {
        "schema_version": "sensiblaw.numeric-semantic-leaf-audit.v1",
        "transport_authority": "audit_boundary_only",
        "correspondence_basis": "source-edit-transport+structural-occurrence:v1",
        "nodes": sorted(nodes, key=lambda node: node["ref"]),
        "parser_sentence_spans": [
            [int(start), int(end)] for start, end in cursor.fetchall()
        ],
    }


__all__ = ["project_numeric_semantic_leaf_audit"]
