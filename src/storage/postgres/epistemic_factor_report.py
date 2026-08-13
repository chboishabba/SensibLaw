"""Proof-relevant entity/factor reporting over the numeric PNF store.

This module deliberately has no co-occurrence query.  A factor enters an entity
report only through a direct surface-object hyperedge or an admitted identity
projection/derivation.  Structural composition candidates are reported as
candidates, never silently promoted to propositions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class FactorArgument:
    role: str
    surface: str
    source_object_id: int
    identity_entity_ref: str | None = None
    identity_authority: str | None = None
    identity_witness_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class FactorRecord:
    factor_id: int
    factor_type: str
    predicate: str
    modal_state: int
    temporal_state: int
    document_id: int
    start_char: int
    end_char: int
    epistemic_level: int
    authority_class: str | None
    derivation_id: int | None
    arguments: tuple[FactorArgument, ...]


@dataclass(frozen=True)
class CanonicalEntityRecord:
    entity_id: int
    entity_ref: str
    authority_class: str
    world_canonical: bool
    canonical_surface: str | None


@dataclass(frozen=True)
class IdentityWitnessRecord:
    witness_id: int
    source_object_id: int
    source_surface: str
    target_entity_id: int
    target_entity_ref: str
    witness_kind: str
    authority_class: str
    world_canonical: bool
    demand_id: int | None
    candidate_count: int
    constraint_count: int


@dataclass(frozen=True)
class CompositionCandidateRecord:
    candidate_id: int
    left_factor_id: int
    right_factor_id: int
    left_role: str
    right_role: str
    bridge_surface: str | None
    bridge_entity_ref: str | None
    identity_authority: str | None
    candidate_rank: int


@dataclass(frozen=True)
class EpistemicEntityReport:
    surfaces: tuple[str, ...]
    symbol_ids: tuple[int, ...]
    direct_object_ids: tuple[int, ...]
    canonical_entities: tuple[CanonicalEntityRecord, ...]
    witnesses: tuple[IdentityWitnessRecord, ...]
    direct_factors: tuple[FactorRecord, ...]
    derived_factors: tuple[FactorRecord, ...]
    composition_candidates: tuple[CompositionCandidateRecord, ...]

    @property
    def has_world_identity(self) -> bool:
        return any(entity.world_canonical for entity in self.canonical_entities)


def _fetchall(cursor: Any, query: str, params: Sequence[object] = ()) -> tuple[Any, ...]:
    cursor.execute(query, params)
    return tuple(cursor.fetchall())


def _factor_records(
    cursor: Any,
    factor_ids: Sequence[int],
    *,
    epistemic_level: int,
) -> tuple[FactorRecord, ...]:
    if not factor_ids:
        return ()
    rows = _fetchall(
        cursor,
        """
        SELECT factor.factor_id,
               factor_type.symbol_text,
               predicate.symbol_text,
               factor.modal_state,
               factor.temporal_state,
               region.document_id,
               region.start_char,
               region.end_char,
               edge.slot_ordinal,
               role.symbol_text,
               object.object_id,
               head.symbol_text
          FROM execution.semantic_pnf_factor AS factor
          JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id = factor.factor_type_symbol_id
          JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id = factor.predicate_symbol_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id = factor.factor_id
          JOIN execution.semantic_symbol AS role
            ON role.symbol_id = edge.role_symbol_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = edge.object_id
          JOIN execution.semantic_symbol AS head
            ON head.symbol_id = object.head_symbol_id
         WHERE factor.factor_id = ANY(%s)
         ORDER BY factor.factor_id, edge.slot_ordinal
        """,
        (list(factor_ids),),
    )
    grouped: dict[int, dict[str, object]] = {}
    for row in rows:
        factor_id = int(row[0])
        record = grouped.setdefault(
            factor_id,
            {
                "factor_type": str(row[1]),
                "predicate": str(row[2]),
                "modal_state": int(row[3]),
                "temporal_state": int(row[4]),
                "document_id": int(row[5]),
                "start_char": int(row[6]),
                "end_char": int(row[7]),
                "arguments": [],
            },
        )
        arguments = record["arguments"]
        assert isinstance(arguments, list)
        arguments.append(
            FactorArgument(
                role=str(row[9]),
                surface=str(row[11]),
                source_object_id=int(row[10]),
            )
        )
    return tuple(
        FactorRecord(
            factor_id=factor_id,
            factor_type=str(record["factor_type"]),
            predicate=str(record["predicate"]),
            modal_state=int(record["modal_state"]),
            temporal_state=int(record["temporal_state"]),
            document_id=int(record["document_id"]),
            start_char=int(record["start_char"]),
            end_char=int(record["end_char"]),
            epistemic_level=epistemic_level,
            authority_class=None,
            derivation_id=None,
            arguments=tuple(record["arguments"]),
        )
        for factor_id, record in sorted(grouped.items())
    )


def _derived_factor_records(
    cursor: Any,
    entity_ids: Sequence[int],
) -> tuple[FactorRecord, ...]:
    if not entity_ids:
        return ()
    rows = _fetchall(
        cursor,
        """
        SELECT derivation.derivation_id,
               premise.factor_id,
               factor_type.symbol_text,
               predicate.symbol_text,
               derivation.modal_state,
               derivation.temporal_state,
               region.document_id,
               region.start_char,
               region.end_char,
               authority.authority_name,
               argument.slot_ordinal,
               role.symbol_text,
               argument.source_object_id,
               source_head.symbol_text,
               argument.identity_entity_id,
               entity.entity_ref,
               argument.identity_witness_ids
          FROM execution.semantic_pnf_factor_derivation AS derivation
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise
            ON premise.derivation_id = derivation.derivation_id
           AND premise.premise_ordinal = 0
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = premise.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
          JOIN execution.semantic_symbol AS factor_type
            ON factor_type.symbol_id = derivation.conclusion_factor_type_symbol_id
          JOIN execution.semantic_symbol AS predicate
            ON predicate.symbol_id = derivation.conclusion_predicate_symbol_id
          LEFT JOIN execution.semantic_pnf_identity_authority_class AS authority
            ON authority.authority_class = derivation.authority_class
          JOIN execution.semantic_pnf_factor_derivation_argument AS argument
            ON argument.derivation_id = derivation.derivation_id
          JOIN execution.semantic_symbol AS role
            ON role.symbol_id = argument.role_symbol_id
          JOIN execution.semantic_pnf_object AS source_object
            ON source_object.object_id = argument.source_object_id
          JOIN execution.semantic_symbol AS source_head
            ON source_head.symbol_id = source_object.head_symbol_id
          LEFT JOIN execution.semantic_pnf_canonical_entity AS entity
            ON entity.entity_id = argument.identity_entity_id
         WHERE derivation.derivation_state = 2
           AND derivation.rule_ref = 'identity-substitution:v1'
           AND EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_factor_derivation_argument AS target_arg
                WHERE target_arg.derivation_id = derivation.derivation_id
                  AND target_arg.identity_entity_id = ANY(%s)
           )
         ORDER BY derivation.derivation_id, argument.slot_ordinal
        """,
        (list(entity_ids),),
    )
    grouped: dict[int, dict[str, object]] = {}
    for row in rows:
        derivation_id = int(row[0])
        record = grouped.setdefault(
            derivation_id,
            {
                "factor_id": int(row[1]),
                "factor_type": str(row[2]),
                "predicate": str(row[3]),
                "modal_state": int(row[4]),
                "temporal_state": int(row[5]),
                "document_id": int(row[6]),
                "start_char": int(row[7]),
                "end_char": int(row[8]),
                "authority": None if row[9] is None else str(row[9]),
                "arguments": [],
            },
        )
        witness_ids = () if row[16] is None else tuple(int(value) for value in row[16])
        arguments = record["arguments"]
        assert isinstance(arguments, list)
        arguments.append(
            FactorArgument(
                role=str(row[11]),
                surface=str(row[13]),
                source_object_id=int(row[12]),
                identity_entity_ref=None if row[15] is None else str(row[15]),
                identity_authority=None if row[9] is None else str(row[9]),
                identity_witness_ids=witness_ids,
            )
        )
    return tuple(
        FactorRecord(
            factor_id=int(record["factor_id"]),
            factor_type=str(record["factor_type"]),
            predicate=str(record["predicate"]),
            modal_state=int(record["modal_state"]),
            temporal_state=int(record["temporal_state"]),
            document_id=int(record["document_id"]),
            start_char=int(record["start_char"]),
            end_char=int(record["end_char"]),
            epistemic_level=3,
            authority_class=(
                None if record["authority"] is None else str(record["authority"])
            ),
            derivation_id=derivation_id,
            arguments=tuple(record["arguments"]),
        )
        for derivation_id, record in sorted(grouped.items())
    )


def collect_epistemic_entity_report(
    connection: Any,
    surfaces: Sequence[str],
) -> EpistemicEntityReport:
    normalized = tuple(dict.fromkeys(surface.strip() for surface in surfaces if surface.strip()))
    if not normalized:
        raise ValueError("at least one non-empty surface is required")

    lowered = [surface.casefold() for surface in normalized]
    with connection.cursor() as cursor:
        symbol_rows = _fetchall(
            cursor,
            """
            SELECT symbol_id
              FROM execution.semantic_symbol
             WHERE lower(symbol_text) = ANY(%s)
             ORDER BY symbol_id
            """,
            (lowered,),
        )
        symbol_ids = tuple(int(row[0]) for row in symbol_rows)
        if not symbol_ids:
            return EpistemicEntityReport(normalized, (), (), (), (), (), (), ())

        object_rows = _fetchall(
            cursor,
            """
            SELECT object_id
              FROM execution.semantic_pnf_object
             WHERE head_symbol_id = ANY(%s)
             ORDER BY object_id
            """,
            (list(symbol_ids),),
        )
        direct_object_ids = tuple(int(row[0]) for row in object_rows)

        factor_rows = _fetchall(
            cursor,
            """
            SELECT DISTINCT factor_id
              FROM execution.semantic_pnf_hyperedge
             WHERE object_id = ANY(%s)
             ORDER BY factor_id
            """,
            (list(direct_object_ids),),
        ) if direct_object_ids else ()
        direct_factor_ids = tuple(int(row[0]) for row in factor_rows)
        direct_factors = _factor_records(cursor, direct_factor_ids, epistemic_level=1)

        entity_rows = _fetchall(
            cursor,
            """
            SELECT DISTINCT entity.entity_id,
                   entity.entity_ref,
                   authority.authority_name,
                   authority.world_canonical,
                   canonical.symbol_text
              FROM execution.semantic_pnf_identity_fibre_member AS member
              JOIN execution.semantic_pnf_canonical_entity AS entity
                ON entity.entity_id = member.entity_id
              JOIN execution.semantic_pnf_identity_authority_class AS authority
                ON authority.authority_class = entity.authority_class
              LEFT JOIN execution.semantic_symbol AS canonical
                ON canonical.symbol_id = entity.canonical_symbol_id
             WHERE member.object_id = ANY(%s)
             ORDER BY entity.entity_id
            """,
            (list(direct_object_ids),),
        ) if direct_object_ids else ()
        entities = tuple(
            CanonicalEntityRecord(
                entity_id=int(row[0]),
                entity_ref=str(row[1]),
                authority_class=str(row[2]),
                world_canonical=bool(row[3]),
                canonical_surface=None if row[4] is None else str(row[4]),
            )
            for row in entity_rows
        )
        entity_ids = tuple(entity.entity_id for entity in entities)

        witness_rows = _fetchall(
            cursor,
            """
            SELECT witness.witness_id,
                   witness.source_object_id,
                   source_head.symbol_text,
                   witness.target_entity_id,
                   entity.entity_ref,
                   kind.witness_name,
                   authority.authority_name,
                   authority.world_canonical,
                   witness.demand_id,
                   witness.candidate_count,
                   count(constraint_row.constraint_ordinal)
              FROM execution.semantic_pnf_identity_witness AS witness
              JOIN execution.semantic_pnf_identity_witness_admission AS admission
                ON admission.witness_id = witness.witness_id
               AND admission.admission_state = 2
              JOIN execution.semantic_pnf_object AS source_object
                ON source_object.object_id = witness.source_object_id
              JOIN execution.semantic_symbol AS source_head
                ON source_head.symbol_id = source_object.head_symbol_id
              JOIN execution.semantic_pnf_canonical_entity AS entity
                ON entity.entity_id = witness.target_entity_id
              JOIN execution.semantic_pnf_identity_witness_kind AS kind
                ON kind.witness_kind = witness.witness_kind
              JOIN execution.semantic_pnf_identity_authority_class AS authority
                ON authority.authority_class = witness.authority_class
              LEFT JOIN execution.semantic_pnf_identity_witness_constraint AS constraint_row
                ON constraint_row.witness_id = witness.witness_id
             WHERE witness.target_entity_id = ANY(%s)
             GROUP BY witness.witness_id,
                      witness.source_object_id,
                      source_head.symbol_text,
                      witness.target_entity_id,
                      entity.entity_ref,
                      kind.witness_name,
                      authority.authority_name,
                      authority.world_canonical,
                      witness.demand_id,
                      witness.candidate_count
             ORDER BY witness.witness_id
            """,
            (list(entity_ids),),
        ) if entity_ids else ()
        witnesses = tuple(
            IdentityWitnessRecord(
                witness_id=int(row[0]),
                source_object_id=int(row[1]),
                source_surface=str(row[2]),
                target_entity_id=int(row[3]),
                target_entity_ref=str(row[4]),
                witness_kind=str(row[5]),
                authority_class=str(row[6]),
                world_canonical=bool(row[7]),
                demand_id=None if row[8] is None else int(row[8]),
                candidate_count=int(row[9]),
                constraint_count=int(row[10]),
            )
            for row in witness_rows
        )

        derived_factors = _derived_factor_records(cursor, entity_ids)
        relevant_factor_ids = set(direct_factor_ids)
        relevant_factor_ids.update(factor.factor_id for factor in derived_factors)

        composition_rows = _fetchall(
            cursor,
            """
            SELECT candidate.candidate_id,
                   candidate.left_factor_id,
                   candidate.right_factor_id,
                   left_role.symbol_text,
                   right_role.symbol_text,
                   bridge_head.symbol_text,
                   bridge_entity.entity_ref,
                   authority.authority_name,
                   candidate.candidate_rank
              FROM execution.semantic_pnf_factor_composition_candidate AS candidate
              JOIN execution.semantic_symbol AS left_role
                ON left_role.symbol_id = candidate.left_role_symbol_id
              JOIN execution.semantic_symbol AS right_role
                ON right_role.symbol_id = candidate.right_role_symbol_id
              LEFT JOIN execution.semantic_pnf_object AS bridge_object
                ON bridge_object.object_id = candidate.bridge_object_id
              LEFT JOIN execution.semantic_symbol AS bridge_head
                ON bridge_head.symbol_id = bridge_object.head_symbol_id
              LEFT JOIN execution.semantic_pnf_canonical_entity AS bridge_entity
                ON bridge_entity.entity_id = candidate.bridge_entity_id
              LEFT JOIN execution.semantic_pnf_identity_authority_class AS authority
                ON authority.authority_class = candidate.identity_authority_class
             WHERE candidate.left_factor_id = ANY(%s)
                OR candidate.right_factor_id = ANY(%s)
             ORDER BY candidate.candidate_rank, candidate.candidate_id
            """,
            (list(relevant_factor_ids), list(relevant_factor_ids)),
        ) if relevant_factor_ids else ()
        composition_candidates = tuple(
            CompositionCandidateRecord(
                candidate_id=int(row[0]),
                left_factor_id=int(row[1]),
                right_factor_id=int(row[2]),
                left_role=str(row[3]),
                right_role=str(row[4]),
                bridge_surface=None if row[5] is None else str(row[5]),
                bridge_entity_ref=None if row[6] is None else str(row[6]),
                identity_authority=None if row[7] is None else str(row[7]),
                candidate_rank=int(row[8]),
            )
            for row in composition_rows
        )

    return EpistemicEntityReport(
        surfaces=normalized,
        symbol_ids=symbol_ids,
        direct_object_ids=direct_object_ids,
        canonical_entities=entities,
        witnesses=witnesses,
        direct_factors=direct_factors,
        derived_factors=derived_factors,
        composition_candidates=composition_candidates,
    )


def _argument_text(argument: FactorArgument) -> str:
    if argument.identity_entity_ref is None:
        return f"{argument.role}={argument.surface}"
    witness_text = ",".join(str(value) for value in argument.identity_witness_ids)
    return (
        f"{argument.role}={argument.identity_entity_ref} "
        f"[surface={argument.surface}; authority={argument.identity_authority}; "
        f"witnesses={witness_text}]"
    )


def render_epistemic_entity_report(report: EpistemicEntityReport) -> str:
    label = " / ".join(report.surfaces)
    lines = [
        f'# Epistemically Stratified Factor Report: Surface Identity "{label}"',
        "",
        "> **Epistemic constraint**: co-occurrence and paragraph co-presence are not identity evidence. Direct factors require a literal local role argument; substituted factors require admitted identity witnesses.",
        "",
        "## 1. Proof boundary",
        "",
        r"$$G_E = \bigcup_{o,\pi:o\xRightarrow{\pi}E} \operatorname{Neighbourhood}(o)$$",
        "",
        "A direct surface head is Level-0/1 lexical-structural evidence. It is not, by itself, a proof of world identity. World-canonical identity exists only when an admitted `external_authority` entity/witness is present.",
        "",
        f"- Surface symbols found: **{len(report.symbol_ids)}**",
        f"- Direct local objects: **{len(report.direct_object_ids)}**",
        f"- Direct Level-1 factors: **{len(report.direct_factors)}**",
        f"- Admitted canonical entity bases: **{len(report.canonical_entities)}**",
        f"- Admitted identity witnesses: **{len(report.witnesses)}**",
        f"- Level-3 substituted factors: **{len(report.derived_factors)}**",
        f"- Structural composition candidates: **{len(report.composition_candidates)}**",
        f"- World-canonical identity proven: **{'yes' if report.has_world_identity else 'no'}**",
        "",
        "## 2. Identity fibres",
        "",
    ]
    if not report.canonical_entities:
        lines.append("No canonical entity fibre is currently admitted for these local surface objects.")
    else:
        for entity in report.canonical_entities:
            lines.append(
                f"- Entity `{entity.entity_ref}` — authority `{entity.authority_class}`; "
                f"world canonical: `{str(entity.world_canonical).lower()}`; "
                f"canonical surface: `{entity.canonical_surface or 'unspecified'}`"
            )
    lines.extend(["", "### Witnesses", ""])
    if not report.witnesses:
        lines.append("No admitted identity derivation witnesses were found.")
    else:
        for witness in report.witnesses:
            lines.append(
                f"- $\\pi_{{{witness.witness_id}}}$ `{witness.source_surface}` → "
                f"`{witness.target_entity_ref}` via `{witness.witness_kind}`; "
                f"authority `{witness.authority_class}`; candidates "
                f"`{witness.candidate_count}`; typed constraints "
                f"`{witness.constraint_count}`; demand "
                f"`{witness.demand_id if witness.demand_id is not None else 'anchor'}`"
            )

    lines.extend(["", "## 3. Level-1 direct structural facts", ""])
    if not report.direct_factors:
        lines.append("No direct role-labelled factor contains the requested surface identity.")
    for factor in report.direct_factors:
        args = ", ".join(_argument_text(argument) for argument in factor.arguments)
        lines.extend(
            [
                f"### F_{factor.factor_id}",
                f"- Span: `[{factor.start_char} - {factor.end_char}]` (document `{factor.document_id}`)",
                f"- Predicate: `{factor.predicate}` (`{factor.factor_type}`)",
                f"- Modal / temporal: `{factor.modal_state}` / `{factor.temporal_state}`",
                f"- Hyperedge: `[{args}]`",
                "- Epistemic status: direct Level-1 structural fact; surface identity only.",
                "",
            ]
        )

    lines.extend(["## 4. Level-3 witnessed substitutions", ""])
    if not report.derived_factors:
        lines.append("No factor is currently admitted through an identity substitution proof.")
    for factor in report.derived_factors:
        args = ", ".join(_argument_text(argument) for argument in factor.arguments)
        lines.extend(
            [
                f"### D_{factor.derivation_id} from F_{factor.factor_id}",
                f"- Span: `[{factor.start_char} - {factor.end_char}]` (document `{factor.document_id}`)",
                f"- Predicate preserved: `{factor.predicate}` (`{factor.factor_type}`)",
                f"- Authority class: `{factor.authority_class}`",
                f"- Derived hyperedge: `[{args}]`",
                "- Epistemic status: Level-3 substituted proposition. Original factor remains unchanged.",
                "",
            ]
        )

    lines.extend(["## 5. Factor-composition frontier", ""])
    lines.append(
        "The following are **structural candidates only**. Shared arguments or witnessed identity bridges do not themselves license a semantic conclusion."
    )
    lines.append("")
    if not report.composition_candidates:
        lines.append("No bounded local composition candidate touches the admitted factor neighbourhood.")
    for candidate in report.composition_candidates:
        bridge = (
            candidate.bridge_entity_ref
            if candidate.bridge_entity_ref is not None
            else candidate.bridge_surface
        )
        authority = (
            ""
            if candidate.identity_authority is None
            else f" at authority `{candidate.identity_authority}`"
        )
        lines.append(
            f"- C_{candidate.candidate_id}: F_{candidate.left_factor_id} "
            f"(`{candidate.left_role}`) ↔ F_{candidate.right_factor_id} "
            f"(`{candidate.right_role}`) through `{bridge}`{authority}; "
            f"rank `{candidate.candidate_rank}`."
        )

    lines.extend(
        [
            "",
            "## 6. Interpretation boundary",
            "",
            "This report intentionally stops at graph-level propositions and proof-labelled substitutions. Natural-language claims such as event subtype, possession, causation, political partnership, or world-person identity require additional admitted derivations or external authority evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def iter_factor_ids(report: EpistemicEntityReport) -> Iterable[int]:
    yield from (factor.factor_id for factor in report.direct_factors)
    yield from (factor.factor_id for factor in report.derived_factors)
