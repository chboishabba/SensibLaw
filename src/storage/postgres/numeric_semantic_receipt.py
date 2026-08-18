"""Portable hierarchical receipts for strict numeric PNF publication.

The runtime intentionally uses dense database-local BIGINT ids.  Those ids must
never become cross-rebuild semantic identity.  This module projects the closed
numeric authority onto stable source coordinates, stable symbol BYTEA digests,
and typed semantic/proof state, then Merkle-reduces those leaves with the
existing canonical numeric encoder.

No JSON, lexical comparison, elapsed time, PID, lease epoch, cache state, row
allocation order, or database-local surrogate id participates in the receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping

from src.pnf.numeric_hyperfabric import TargetKind, numeric_digest


RECEIPT_VERSION = 1
_RECEIPT_TAG = sha256(b"sensiblaw.numeric-semantic-publication-receipt:v1").digest()


def _tag(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def _hex32(value: str) -> bytes:
    payload = bytes.fromhex(value)
    if len(payload) != 32:
        raise ValueError("semantic receipt SHA-256 coordinate must be 32 bytes")
    return payload


def _bytes(value: Any) -> bytes | None:
    return bytes(value) if value is not None else None


def _root(label: str, leaves: Iterable[bytes]) -> bytes:
    ordered = tuple(sorted(bytes(value) for value in leaves))
    return numeric_digest(_tag(label), ordered)


@dataclass(frozen=True, slots=True)
class NumericSemanticReceipt:
    receipt_sha256: bytes
    parser_root_sha256: bytes
    object_root_sha256: bytes
    factor_root_sha256: bytes
    residual_root_sha256: bytes
    export_root_sha256: bytes
    proof_root_sha256: bytes
    object_leaf_count: int
    factor_leaf_count: int
    residual_leaf_count: int
    export_leaf_count: int
    proof_leaf_count: int

    @property
    def receipt_ref(self) -> str:
        return f"numeric-semantic-receipt:v1:{self.receipt_sha256.hex()}"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": "sensiblaw.numeric-semantic-publication-receipt.v1",
            "receipt_ref": self.receipt_ref,
            "receipt_sha256": self.receipt_sha256.hex(),
            "parser_root_sha256": self.parser_root_sha256.hex(),
            "object_root_sha256": self.object_root_sha256.hex(),
            "factor_root_sha256": self.factor_root_sha256.hex(),
            "residual_root_sha256": self.residual_root_sha256.hex(),
            "export_root_sha256": self.export_root_sha256.hex(),
            "proof_root_sha256": self.proof_root_sha256.hex(),
            "object_leaf_count": self.object_leaf_count,
            "factor_leaf_count": self.factor_leaf_count,
            "residual_leaf_count": self.residual_leaf_count,
            "export_leaf_count": self.export_leaf_count,
            "proof_leaf_count": self.proof_leaf_count,
            "identity_basis": "stable-source-coordinates+symbol-digests+typed-state:v1",
        }


def _object_leaves(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[int, bytes]:
    cursor.execute(
        """
        SELECT object.object_id,
               region.region_kind, region.start_char, region.end_char,
               object_kind.symbol_digest, head.symbol_digest,
               object.promotion_level,
               object.information_gain, object.representation_cost,
               object.ambiguity_cost, object.active,
               object.visibility_start_char, object.visibility_end_char
          FROM execution.semantic_pnf_object AS object
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = object.region_id
          JOIN execution.semantic_symbol AS object_kind
            ON object_kind.symbol_id = object.object_kind_symbol_id
          LEFT JOIN execution.semantic_symbol AS head
            ON head.symbol_id = object.head_symbol_id
         WHERE region.run_ref = %s AND region.document_ref = %s
        """,
        (run_ref, document_ref),
    )
    rows = tuple(cursor.fetchall())
    ids = [int(row[0]) for row in rows]
    support: dict[int, list[tuple[Any, ...]]] = {value: [] for value in ids}
    if ids:
        cursor.execute(
            """
            SELECT support.object_id, support.ordinal,
                   token.start_char, token.end_char,
                   lemma.symbol_digest, dependency.symbol_digest
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_parser_token AS token
                ON token.token_id = support.token_id
              LEFT JOIN execution.semantic_symbol AS lemma
                ON lemma.symbol_id = token.lemma_symbol_id
              LEFT JOIN execution.semantic_symbol AS dependency
                ON dependency.symbol_id = token.dependency_symbol_id
             WHERE support.object_id = ANY(%s)
             ORDER BY support.object_id, support.ordinal,
                      token.start_char, token.end_char
            """,
            (ids,),
        )
        for object_id, ordinal, start, end, lemma_digest, dependency_digest in cursor.fetchall():
            support[int(object_id)].append(
                (
                    int(ordinal),
                    int(start),
                    int(end),
                    _bytes(lemma_digest),
                    _bytes(dependency_digest),
                )
            )
    result: dict[int, bytes] = {}
    for row in rows:
        object_id = int(row[0])
        result[object_id] = numeric_digest(
            _tag("object:v1"),
            int(row[1]),
            int(row[2]),
            int(row[3]),
            _bytes(row[4]),
            _bytes(row[5]),
            int(row[6]),
            float(row[7]),
            float(row[8]),
            float(row[9]),
            bool(row[10]),
            int(row[11]) if row[11] is not None else None,
            int(row[12]) if row[12] is not None else None,
            tuple(support[object_id]),
        )
    return result


def _factor_leaves(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    object_leaves: Mapping[int, bytes],
) -> dict[int, bytes]:
    cursor.execute(
        """
        SELECT factor.factor_id,
               region.region_kind, region.start_char, region.end_char,
               factor_type.symbol_digest, predicate.symbol_digest,
               factor.temporal_state, factor.modal_state,
               factor.promotion_level, factor.support_score, factor.active
          FROM execution.semantic_pnf_factor AS factor
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
          JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id = factor.factor_type_symbol_id
          JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id = factor.predicate_symbol_id
         WHERE region.run_ref = %s AND region.document_ref = %s
        """,
        (run_ref, document_ref),
    )
    rows = tuple(cursor.fetchall())
    ids = [int(row[0]) for row in rows]
    supports: dict[int, list[tuple[Any, ...]]] = {value: [] for value in ids}
    edges: dict[int, list[tuple[Any, ...]]] = {value: [] for value in ids}
    if ids:
        cursor.execute(
            """
            SELECT support.factor_id, support.ordinal,
                   token.start_char, token.end_char,
                   lemma.symbol_digest, dependency.symbol_digest
              FROM execution.semantic_pnf_factor_token_support AS support
              JOIN execution.semantic_parser_token AS token
                ON token.token_id = support.token_id
              LEFT JOIN execution.semantic_symbol AS lemma
                ON lemma.symbol_id = token.lemma_symbol_id
              LEFT JOIN execution.semantic_symbol AS dependency
                ON dependency.symbol_id = token.dependency_symbol_id
             WHERE support.factor_id = ANY(%s)
             ORDER BY support.factor_id, support.ordinal,
                      token.start_char, token.end_char
            """,
            (ids,),
        )
        for factor_id, ordinal, start, end, lemma_digest, dependency_digest in cursor.fetchall():
            supports[int(factor_id)].append(
                (
                    int(ordinal), int(start), int(end),
                    _bytes(lemma_digest), _bytes(dependency_digest),
                )
            )
        cursor.execute(
            """
            SELECT edge.factor_id, edge.slot_ordinal, role.symbol_digest,
                   edge.object_id, edge.resolution_state, edge.required
              FROM execution.semantic_pnf_hyperedge AS edge
              JOIN execution.semantic_symbol AS role
                ON role.symbol_id = edge.role_symbol_id
             WHERE edge.factor_id = ANY(%s)
             ORDER BY edge.factor_id, edge.slot_ordinal
            """,
            (ids,),
        )
        for factor_id, slot, role_digest, object_id, resolution_state, required in cursor.fetchall():
            object_leaf = object_leaves.get(int(object_id))
            if object_leaf is None:
                raise RuntimeError("factor edge references object outside numeric receipt scope")
            edges[int(factor_id)].append(
                (
                    int(slot), _bytes(role_digest), object_leaf,
                    int(resolution_state), bool(required),
                )
            )
    result: dict[int, bytes] = {}
    for row in rows:
        factor_id = int(row[0])
        result[factor_id] = numeric_digest(
            _tag("factor:v1"),
            int(row[1]), int(row[2]), int(row[3]),
            _bytes(row[4]), _bytes(row[5]),
            int(row[6]), int(row[7]), int(row[8]), float(row[9]), bool(row[10]),
            tuple(supports[factor_id]),
            tuple(edges[factor_id]),
        )
    return result


def _demand_leaves(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    object_leaves: Mapping[int, bytes],
    factor_leaves: Mapping[int, bytes],
) -> dict[int, bytes]:
    cursor.execute(
        """
        SELECT demand.demand_id,
               region.region_kind, region.start_char, region.end_char,
               demand.expected_target_kind,
               expected_factor.symbol_digest,
               expected_object.symbol_digest,
               lexical.symbol_digest, role.symbol_digest, residual.symbol_digest,
               demand.recency_class, demand.state, demand.max_candidates,
               demand.resolved_target_kind, demand.resolved_target_id,
               demand.source_object_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = demand.source_region_id
          LEFT JOIN execution.semantic_symbol AS expected_factor
            ON expected_factor.symbol_id = demand.expected_factor_type_symbol_id
          LEFT JOIN execution.semantic_symbol AS expected_object
            ON expected_object.symbol_id = demand.expected_object_kind_symbol_id
          LEFT JOIN execution.semantic_symbol AS lexical
            ON lexical.symbol_id = demand.lexical_symbol_id
          LEFT JOIN execution.semantic_symbol AS role
            ON role.symbol_id = demand.role_symbol_id
          LEFT JOIN execution.semantic_symbol AS residual
            ON residual.symbol_id = demand.residual_type_symbol_id
         WHERE region.run_ref = %s AND region.document_ref = %s
        """,
        (run_ref, document_ref),
    )
    rows = tuple(cursor.fetchall())
    base: dict[int, bytes] = {}
    for row in rows:
        demand_id = int(row[0])
        source_object = (
            object_leaves.get(int(row[15])) if row[15] is not None else None
        )
        if row[15] is not None and source_object is None:
            raise RuntimeError("demand source object lies outside numeric receipt scope")
        base[demand_id] = numeric_digest(
            _tag("demand-base:v1"),
            int(row[1]), int(row[2]), int(row[3]), int(row[4]),
            _bytes(row[5]), _bytes(row[6]), _bytes(row[7]),
            _bytes(row[8]), _bytes(row[9]),
            int(row[10]), int(row[11]), int(row[12]), source_object,
        )
    result: dict[int, bytes] = {}
    for row in rows:
        demand_id = int(row[0])
        target_kind = int(row[13]) if row[13] is not None else None
        target_id = int(row[14]) if row[14] is not None else None
        target_leaf: bytes | None = None
        if target_kind is not None or target_id is not None:
            if target_kind is None or target_id is None:
                raise RuntimeError("numeric demand has a partial resolved target")
            if target_kind == int(TargetKind.OBJECT):
                target_leaf = object_leaves.get(target_id)
            elif target_kind == int(TargetKind.FACTOR):
                target_leaf = factor_leaves.get(target_id)
            elif target_kind == int(TargetKind.DEMAND):
                target_leaf = base.get(target_id)
            else:
                raise RuntimeError(
                    "portable numeric receipt does not admit a local-id-only resolved target"
                )
            if target_leaf is None:
                raise RuntimeError("resolved target lies outside numeric receipt scope")
        result[demand_id] = numeric_digest(
            _tag("demand:v1"), base[demand_id], target_kind, target_leaf
        )
    return result


def _entity_leaves(
    cursor: Any,
    entity_ids: Iterable[int],
    *,
    object_leaves: Mapping[int, bytes],
) -> dict[int, bytes]:
    ids = sorted({int(value) for value in entity_ids})
    if not ids:
        return {}
    cursor.execute(
        """
        SELECT entity.entity_id, entity.authority_class,
               canonical.symbol_digest, entity.anchor_object_id,
               entity.authority_namespace, entity.authority_identifier
          FROM execution.semantic_pnf_canonical_entity AS entity
          LEFT JOIN execution.semantic_symbol AS canonical
            ON canonical.symbol_id = entity.canonical_symbol_id
         WHERE entity.entity_id = ANY(%s)
        """,
        (ids,),
    )
    result: dict[int, bytes] = {}
    for entity_id, authority_class, symbol_digest, anchor_object_id, namespace, identifier in cursor.fetchall():
        anchor = (
            object_leaves.get(int(anchor_object_id))
            if anchor_object_id is not None
            else None
        )
        if anchor_object_id is not None and anchor is None:
            raise RuntimeError("canonical entity anchor lies outside receipt scope")
        result[int(entity_id)] = numeric_digest(
            _tag("entity:v1"),
            int(authority_class),
            _bytes(symbol_digest),
            anchor,
            _tag(str(namespace)) if namespace is not None else None,
            _tag(str(identifier)) if identifier is not None else None,
        )
    if len(result) != len(ids):
        raise RuntimeError("numeric semantic receipt could not resolve canonical entity")
    return result


def _proof_leaves(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    object_leaves: Mapping[int, bytes],
    factor_leaves: Mapping[int, bytes],
) -> tuple[bytes, ...]:
    # Only admitted derivations alter the published proof surface. Candidate and
    # rejected rows remain provenance history but do not change this receipt.
    cursor.execute(
        """
        SELECT DISTINCT derivation.derivation_id, derivation.rule_ref,
               derivation.derivation_kind, derivation.derivation_state,
               derivation.epistemic_level, derivation.authority_class,
               factor_type.symbol_digest, predicate.symbol_digest,
               derivation.modal_state, derivation.temporal_state
          FROM execution.semantic_pnf_factor_derivation AS derivation
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise
            ON premise.derivation_id = derivation.derivation_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = premise.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
          LEFT JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id = derivation.conclusion_factor_type_symbol_id
          LEFT JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id = derivation.conclusion_predicate_symbol_id
         WHERE region.run_ref = %s AND region.document_ref = %s
           AND derivation.derivation_state = 2
        """,
        (run_ref, document_ref),
    )
    rows = tuple(cursor.fetchall())
    ids = [int(row[0]) for row in rows]
    premises: dict[int, list[tuple[int, bytes]]] = {value: [] for value in ids}
    arguments_raw: dict[int, list[tuple[Any, ...]]] = {value: [] for value in ids}
    entity_ids: set[int] = set()
    if ids:
        cursor.execute(
            """
            SELECT premise.derivation_id, premise.premise_ordinal, premise.factor_id
              FROM execution.semantic_pnf_factor_derivation_premise AS premise
             WHERE premise.derivation_id = ANY(%s)
             ORDER BY premise.derivation_id, premise.premise_ordinal
            """,
            (ids,),
        )
        for derivation_id, ordinal, factor_id in cursor.fetchall():
            leaf = factor_leaves.get(int(factor_id))
            if leaf is None:
                raise RuntimeError("derivation premise lies outside receipt scope")
            premises[int(derivation_id)].append((int(ordinal), leaf))
        cursor.execute(
            """
            SELECT argument.derivation_id, argument.slot_ordinal,
                   role.symbol_digest, argument.source_object_id,
                   argument.local_object_id, argument.identity_entity_id
              FROM execution.semantic_pnf_factor_derivation_argument AS argument
              JOIN execution.semantic_symbol AS role
                ON role.symbol_id = argument.role_symbol_id
             WHERE argument.derivation_id = ANY(%s)
             ORDER BY argument.derivation_id, argument.slot_ordinal
            """,
            (ids,),
        )
        for row in cursor.fetchall():
            arguments_raw[int(row[0])].append(tuple(row[1:]))
            if row[5] is not None:
                entity_ids.add(int(row[5]))
    entities = _entity_leaves(cursor, entity_ids, object_leaves=object_leaves)
    leaves: list[bytes] = []
    for row in rows:
        derivation_id = int(row[0])
        args: list[tuple[Any, ...]] = []
        for slot, role_digest, source_object_id, local_object_id, identity_entity_id in arguments_raw[derivation_id]:
            source = object_leaves.get(int(source_object_id))
            local = (
                object_leaves.get(int(local_object_id))
                if local_object_id is not None
                else None
            )
            entity = (
                entities.get(int(identity_entity_id))
                if identity_entity_id is not None
                else None
            )
            if source is None or (local_object_id is not None and local is None):
                raise RuntimeError("derivation argument lies outside receipt scope")
            args.append((int(slot), _bytes(role_digest), source, local, entity))
        leaves.append(
            numeric_digest(
                _tag("proof-derivation:v1"),
                _tag(str(row[1])), int(row[2]), int(row[3]), int(row[4]),
                int(row[5]) if row[5] is not None else None,
                _bytes(row[6]), _bytes(row[7]), int(row[8]), int(row[9]),
                tuple(premises[derivation_id]), tuple(args),
            )
        )
    return tuple(leaves)


def compute_numeric_semantic_receipt(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    canonical_text_sha256: str,
    parser_contract_ref: str,
    compiler_contract_ref: str,
) -> NumericSemanticReceipt:
    objects = _object_leaves(cursor, run_ref=run_ref, document_ref=document_ref)
    factors = _factor_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
    )
    demands = _demand_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
        factor_leaves=factors,
    )

    cursor.execute(
        """
        SELECT export.export_kind, export.target_kind,
               key_symbol.symbol_digest, residual.symbol_digest,
               export.rank, export.promotion_score, export.target_id
          FROM execution.semantic_pnf_interface_export AS export
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id = export.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
          LEFT JOIN execution.semantic_symbol AS key_symbol
            ON key_symbol.symbol_id = export.key_symbol_id
          LEFT JOIN execution.semantic_symbol AS residual
            ON residual.symbol_id = export.residual_type_symbol_id
         WHERE region.run_ref = %s AND region.document_ref = %s
           AND region.region_kind = 10 AND region.closure_state = 3
        """,
        (run_ref, document_ref),
    )
    export_leaves: list[bytes] = []
    for export_kind, target_kind, key_digest, residual_digest, rank, promotion_score, target_id in cursor.fetchall():
        kind = int(target_kind)
        target = int(target_id)
        if kind == int(TargetKind.OBJECT):
            target_leaf = objects.get(target)
        elif kind == int(TargetKind.FACTOR):
            target_leaf = factors.get(target)
        elif kind == int(TargetKind.DEMAND):
            target_leaf = demands.get(target)
        else:
            raise RuntimeError(
                "portable numeric receipt encountered root export with local-id-only target"
            )
        if target_leaf is None:
            raise RuntimeError("root export target lies outside receipt scope")
        export_leaves.append(
            numeric_digest(
                _tag("root-export:v1"), int(export_kind), kind,
                _bytes(key_digest), _bytes(residual_digest), int(rank),
                float(promotion_score), target_leaf,
            )
        )

    proof_leaves = _proof_leaves(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        object_leaves=objects,
        factor_leaves=factors,
    )
    parser_root = numeric_digest(
        _tag("parser-root:v1"),
        _hex32(canonical_text_sha256),
        _tag(parser_contract_ref),
        _tag(compiler_contract_ref),
    )
    object_root = _root("object-root:v1", objects.values())
    factor_root = _root("factor-root:v1", factors.values())
    residual_root = _root("residual-root:v1", demands.values())
    export_root = _root("export-root:v1", export_leaves)
    proof_root = _root("proof-root:v1", proof_leaves)
    receipt_sha256 = numeric_digest(
        _RECEIPT_TAG,
        RECEIPT_VERSION,
        parser_root,
        object_root,
        factor_root,
        residual_root,
        export_root,
        proof_root,
    )
    return NumericSemanticReceipt(
        receipt_sha256=receipt_sha256,
        parser_root_sha256=parser_root,
        object_root_sha256=object_root,
        factor_root_sha256=factor_root,
        residual_root_sha256=residual_root,
        export_root_sha256=export_root,
        proof_root_sha256=proof_root,
        object_leaf_count=len(objects),
        factor_leaf_count=len(factors),
        residual_leaf_count=len(demands),
        export_leaf_count=len(export_leaves),
        proof_leaf_count=len(proof_leaves),
    )


def persist_numeric_semantic_receipt(
    cursor: Any,
    *,
    build_ref: str,
    receipt: NumericSemanticReceipt,
) -> None:
    cursor.execute(
        """
        INSERT INTO execution.numeric_semantic_publication_receipt
            (build_ref, receipt_version, receipt_sha256,
             parser_root_sha256, object_root_sha256, factor_root_sha256,
             residual_root_sha256, export_root_sha256, proof_root_sha256,
             object_leaf_count, factor_leaf_count, residual_leaf_count,
             export_leaf_count, proof_leaf_count)
        VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (build_ref) DO UPDATE SET
            receipt_sha256 = EXCLUDED.receipt_sha256,
            parser_root_sha256 = EXCLUDED.parser_root_sha256,
            object_root_sha256 = EXCLUDED.object_root_sha256,
            factor_root_sha256 = EXCLUDED.factor_root_sha256,
            residual_root_sha256 = EXCLUDED.residual_root_sha256,
            export_root_sha256 = EXCLUDED.export_root_sha256,
            proof_root_sha256 = EXCLUDED.proof_root_sha256,
            object_leaf_count = EXCLUDED.object_leaf_count,
            factor_leaf_count = EXCLUDED.factor_leaf_count,
            residual_leaf_count = EXCLUDED.residual_leaf_count,
            export_leaf_count = EXCLUDED.export_leaf_count,
            proof_leaf_count = EXCLUDED.proof_leaf_count
        """,
        (
            build_ref,
            receipt.receipt_sha256,
            receipt.parser_root_sha256,
            receipt.object_root_sha256,
            receipt.factor_root_sha256,
            receipt.residual_root_sha256,
            receipt.export_root_sha256,
            receipt.proof_root_sha256,
            receipt.object_leaf_count,
            receipt.factor_leaf_count,
            receipt.residual_leaf_count,
            receipt.export_leaf_count,
            receipt.proof_leaf_count,
        ),
    )


def load_numeric_semantic_receipt(cursor: Any, *, build_ref: str) -> NumericSemanticReceipt | None:
    cursor.execute(
        """
        SELECT receipt_sha256, parser_root_sha256, object_root_sha256,
               factor_root_sha256, residual_root_sha256, export_root_sha256,
               proof_root_sha256, object_leaf_count, factor_leaf_count,
               residual_leaf_count, export_leaf_count, proof_leaf_count
          FROM execution.numeric_semantic_publication_receipt
         WHERE build_ref = %s AND receipt_version = 1
        """,
        (build_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return NumericSemanticReceipt(
        receipt_sha256=bytes(row[0]),
        parser_root_sha256=bytes(row[1]),
        object_root_sha256=bytes(row[2]),
        factor_root_sha256=bytes(row[3]),
        residual_root_sha256=bytes(row[4]),
        export_root_sha256=bytes(row[5]),
        proof_root_sha256=bytes(row[6]),
        object_leaf_count=int(row[7]),
        factor_leaf_count=int(row[8]),
        residual_leaf_count=int(row[9]),
        export_leaf_count=int(row[10]),
        proof_leaf_count=int(row[11]),
    )


__all__ = [
    "NumericSemanticReceipt",
    "RECEIPT_VERSION",
    "compute_numeric_semantic_receipt",
    "load_numeric_semantic_receipt",
    "persist_numeric_semantic_receipt",
]
