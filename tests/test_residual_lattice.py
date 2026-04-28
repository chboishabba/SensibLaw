from __future__ import annotations

from src.sensiblaw.interfaces import (
    CandidateResidual,
    PredicateAtom,
    PredicateIndex,
    PredicatePNF,
    QualifierState,
    Residual,
    ResidualLevel,
    RoleState,
    TypedArg,
    WrapperState,
    build_predicate_index,
    build_predicate_ref_map,
    coerce_predicate_atom,
    comparable,
    compute_indexed_residual,
    compute_residual,
    join_role_states,
    join_residual,
    meet_atom,
)
from src.text.residual_lattice import (
    collect_candidate_predicate_refs,
    collect_candidate_residuals,
    join_typed_args,
)


def test_coerce_predicate_atom_normalizes_explicit_mapping() -> None:
    atom = coerce_predicate_atom(
        {
            "predicate_key": "provide",
            "roles": {"subject": "poh", "object": "time"},
            "modifiers": {"negation": False},
            "provenance": ("doc:1",),
            "id": "a7",
            "domain": "technical",
        }
    )

    assert atom == PredicateAtom(
        predicate="provide",
        structural_signature="provide",
        roles={
            "subject": TypedArg(value="poh", provenance=("doc:1",)),
            "object": TypedArg(value="time", provenance=("doc:1",)),
        },
        qualifiers=QualifierState(polarity="positive"),
        wrapper=WrapperState(),
        modifiers={"negation": False},
        provenance=("doc:1",),
        atom_id="a7",
        domain="technical",
    )


def test_meet_atom_returns_exact_for_same_predicate_and_roles() -> None:
    query = PredicateAtom(
        predicate="provide",
        structural_signature="provide",
        roles={"subject": TypedArg(value="poh"), "object": TypedArg(value="time")},
        provenance=("q:1",),
    )
    candidate = PredicateAtom(
        predicate="provide",
        structural_signature="provide",
        roles={"subject": TypedArg(value="poh"), "object": TypedArg(value="time")},
        provenance=("d:1",),
    )

    residual = meet_atom(query, candidate)

    assert residual == Residual(
        level=ResidualLevel.EXACT,
        shared_roles={
            "subject": TypedArg(value="poh", provenance=("d:1",)),
            "object": TypedArg(value="time", provenance=("d:1",)),
        },
        provenance=("d:1",),
    )


def test_meet_atom_returns_partial_when_candidate_is_missing_query_role() -> None:
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader"),
            "object": TypedArg(value="transactions"),
            "recipient": TypedArg(value="verifiers"),
        },
    )
    candidate = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={"actor": TypedArg(value="leader"), "object": TypedArg(value="transactions")},
        provenance=("d:2",),
    )

    residual = meet_atom(query, candidate)

    assert residual.level is ResidualLevel.PARTIAL
    assert residual.shared_roles == {
        "actor": TypedArg(value="leader", provenance=("d:2",)),
        "object": TypedArg(value="transactions", provenance=("d:2",)),
    }
    assert residual.missing_roles == ("recipient",)
    assert residual.provenance == ("d:2",)


def test_meet_atom_returns_no_typed_meet_for_unrelated_atoms() -> None:
    query = PredicateAtom(
        predicate="provide",
        structural_signature="provide",
        roles={"subject": TypedArg(value="poh"), "object": TypedArg(value="time")},
    )
    candidate = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={"actor": TypedArg(value="leader"), "object": TypedArg(value="transactions")},
    )

    residual = meet_atom(query, candidate)

    assert residual == Residual(level=ResidualLevel.NO_TYPED_MEET)
    assert not comparable(query, candidate)


def test_meet_atom_returns_contradiction_only_for_direct_role_collision() -> None:
    query = PredicateAtom(
        predicate="offer",
        structural_signature="offer",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="tokens")},
    )
    candidate = PredicateAtom(
        predicate="offer",
        structural_signature="offer",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="shares")},
        provenance=("d:3",),
    )

    residual = meet_atom(query, candidate)

    assert residual.level is ResidualLevel.CONTRADICTION
    assert residual.contradictions == ("role conflict: object",)
    assert residual.provenance == ("d:3",)


def test_meet_atom_detects_negation_conflict_on_comparable_atoms() -> None:
    query = PredicateAtom(
        predicate="guarantee",
        structural_signature="guarantee",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="token_value")},
        qualifiers=QualifierState(polarity="positive"),
    )
    candidate = PredicateAtom(
        predicate="guarantee",
        structural_signature="guarantee",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="token_value")},
        qualifiers=QualifierState(polarity="negative"),
        provenance=("d:4",),
    )

    residual = meet_atom(query, candidate)

    assert residual.level is ResidualLevel.CONTRADICTION
    assert residual.contradictions == ("polarity conflict",)
    assert residual.provenance == ("d:4",)


def test_join_residual_keeps_contradiction_absorbing() -> None:
    contradiction = Residual(
        level=ResidualLevel.CONTRADICTION,
        contradictions=("negation conflict",),
        provenance=("d:4",),
    )
    partial = Residual(
        level=ResidualLevel.PARTIAL,
        shared_roles={"subject": TypedArg(value="whitepaper")},
        missing_roles=("object",),
    )

    result = join_residual(contradiction, partial)

    assert result.level is ResidualLevel.CONTRADICTION
    assert result.shared_roles == {"subject": TypedArg(value="whitepaper")}
    assert result.missing_roles == ("object",)
    assert result.contradictions == ("negation conflict",)
    assert result.provenance == ("d:4",)


def test_join_typed_args_refines_unresolved_to_bound_value() -> None:
    unresolved = TypedArg(value="asset", status="unresolved", provenance=("q:1",))
    bound = TypedArg(
        value="bitcoin",
        entity_type="token",
        status="bound",
        provenance=("d:7",),
    )

    joined, error = join_typed_args(unresolved, bound)

    assert error is None
    assert joined == TypedArg(
        value="bitcoin",
        entity_type="token",
        status="bound",
        provenance=("d:7", "q:1"),
    )


def test_join_role_states_tracks_refinement_without_losing_typed_args() -> None:
    left = RoleState(
        bindings={"object": TypedArg(value="asset", status="unresolved", provenance=("q:2",))}
    )
    right = RoleState(
        bindings={
            "object": TypedArg(
                value="bitcoin",
                entity_type="token",
                status="bound",
                provenance=("d:9",),
            )
        }
    )

    joined = join_role_states(left, right)

    assert joined.bindings == {
        "object": TypedArg(
            value="bitcoin",
            entity_type="token",
            provenance=("d:9", "q:2"),
            status="bound",
        )
    }
    assert joined.residuals == ("role refined: object",)
    assert joined.contradictions == ()


def test_join_role_states_tracks_slotwise_conflict() -> None:
    left = RoleState(bindings={"actor": TypedArg(value="court", status="bound")})
    right = RoleState(bindings={"actor": TypedArg(value="defendant", status="bound")})

    joined = join_role_states(left, right)

    assert joined.bindings == {"actor": TypedArg(value="court", status="bound")}
    assert joined.contradictions == ("role conflict: actor",)


def test_join_typed_args_rejects_incompatible_bound_values() -> None:
    left = TypedArg(value="bitcoin", status="bound")
    right = TypedArg(value="ethereum", status="bound")

    joined, error = join_typed_args(left, right)

    assert joined is None
    assert error == "value conflict"


def test_join_typed_args_allows_multi_cardinality_union() -> None:
    left = TypedArg(value="court", entity_type="person", status="bound", cardinality="multi")
    right = TypedArg(value="judge", entity_type="person", status="bound", cardinality="multi")

    joined, error = join_typed_args(left, right)

    assert error is None
    assert joined == TypedArg(
        value="court",
        entity_type="person",
        status="bound",
        cardinality="multi",
        members=("court", "judge"),
    )


def test_join_role_states_allows_multi_occupant_slot_without_contradiction() -> None:
    left = RoleState(
        bindings={
            "actor": TypedArg(
                value="court",
                entity_type="person",
                status="bound",
                cardinality="multi",
            )
        }
    )
    right = RoleState(
        bindings={
            "actor": TypedArg(
                value="judge",
                entity_type="person",
                status="bound",
                cardinality="multi",
            )
        }
    )

    joined = join_role_states(left, right)

    assert joined.bindings == {
        "actor": TypedArg(
            value="court",
            entity_type="person",
            status="bound",
            cardinality="multi",
            members=("court", "judge"),
        )
    }
    assert joined.contradictions == ()
    assert joined.residuals == ("role refined: actor",)


def test_meet_atom_refines_variable_role_instead_of_requiring_equality() -> None:
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader"),
            "object": TypedArg(value="asset", status="variable"),
        },
    )
    candidate = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
        provenance=("d:8",),
    )

    residual = meet_atom(query, candidate)

    assert residual.level is ResidualLevel.EXACT
    assert residual.shared_roles == {
        "actor": TypedArg(value="leader", provenance=("d:8",)),
        "object": TypedArg(
            value="transactions",
            entity_type="document",
            provenance=("d:8",),
            status="bound",
        ),
    }
    assert residual.provenance == ("d:8",)


def test_join_residual_uses_slotwise_role_join_for_shared_roles() -> None:
    left = Residual(
        level=ResidualLevel.PARTIAL,
        shared_roles={
            "object": TypedArg(value="asset", status="unresolved", provenance=("q:2",))
        },
    )
    right = Residual(
        level=ResidualLevel.PARTIAL,
        shared_roles={
            "object": TypedArg(
                value="bitcoin",
                entity_type="token",
                status="bound",
                provenance=("d:9",),
            )
        },
    )

    joined = join_residual(left, right)

    assert joined.shared_roles == {
        "object": TypedArg(
            value="bitcoin",
            entity_type="token",
            provenance=("d:9", "q:2"),
            status="bound",
        )
    }
    assert joined.contradictions == ()


def test_compute_residual_returns_no_typed_meet_when_no_atom_is_comparable() -> None:
    query = PredicateAtom(
        predicate="provide",
        structural_signature="provide",
        roles={"subject": TypedArg(value="poh"), "object": TypedArg(value="time")},
    )
    atoms = (
        PredicateAtom(predicate="publish", structural_signature="publish", roles={"actor": TypedArg(value="leader"), "object": TypedArg(value="transactions")}),
        PredicateAtom(predicate="verify", structural_signature="verify", roles={"subject": TypedArg(value="poh"), "object": TypedArg(value="order")}),
    )

    residual = compute_residual(query, atoms)

    assert residual == Residual(level=ResidualLevel.NO_TYPED_MEET)


def test_compute_residual_is_monotone_and_preserves_contradiction() -> None:
    query = PredicateAtom(
        predicate="guarantee",
        structural_signature="guarantee",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="token_value")},
        qualifiers=QualifierState(polarity="positive"),
    )
    partial = PredicateAtom(
        predicate="guarantee",
        structural_signature="guarantee",
        roles={"subject": TypedArg(value="whitepaper")},
        qualifiers=QualifierState(polarity="positive"),
        provenance=("d:5",),
    )
    contradiction = PredicateAtom(
        predicate="guarantee",
        structural_signature="guarantee",
        roles={"subject": TypedArg(value="whitepaper"), "object": TypedArg(value="token_value")},
        qualifiers=QualifierState(polarity="negative"),
        provenance=("d:6",),
    )

    first = compute_residual(query, (partial,))
    second = compute_residual(query, (partial, contradiction))

    assert first.level is ResidualLevel.PARTIAL
    assert second.level is ResidualLevel.CONTRADICTION
    assert int(second.level) >= int(first.level)


def test_predicate_pnf_to_dict_separates_q_and_w_from_identity() -> None:
    pnf = PredicatePNF(
        predicate="publish",
        structural_signature="publish",
        roles={"argument": TypedArg(value="transactions", entity_type="document")},
        qualifiers=QualifierState(polarity="positive", modality="asserted"),
        wrapper=WrapperState(status="structural_projection", evidence_only=True),
        provenance=("doc:2",),
    )

    payload = pnf.to_dict()

    assert payload["structural_signature"] == "publish"
    assert payload["roles"]["argument"]["entity_type"] == "document"
    assert payload["qualifiers"]["modality"] == "asserted"
    assert payload["wrapper"]["status"] == "structural_projection"


def test_build_predicate_index_tracks_natural_index_dimensions() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="validator", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={"actor": TypedArg(value="validator", entity_type="person")},
            atom_id="p3",
        ),
    )

    index = build_predicate_index(atoms)

    assert index.by_structural_sig == {
        "publish": ("p1", "p2"),
        "verify": ("p3",),
    }
    assert index.by_role_slot == {
        "actor": ("p1", "p2", "p3"),
        "object": ("p1", "p2"),
    }
    assert index.by_argval["document:transactions"] == ("p1", "p2")
    assert index.by_argval["person:validator"] == ("p2", "p3")
    assert index.by_role_arg[("actor", "person:validator")] == ("p2", "p3")
    assert index.by_role_arg[("object", "document:transactions")] == ("p1", "p2")


def test_build_predicate_index_generates_stable_refs_without_atom_ids() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"object": TypedArg(value="transactions", entity_type="document")},
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"object": TypedArg(value="orders", entity_type="document")},
        ),
    )

    index = build_predicate_index(atoms)

    assert index.by_structural_sig["publish"] == ("pnf:0", "pnf:1")


def test_collect_candidate_predicate_refs_gates_on_structural_signature() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p2",
        ),
    )

    refs = collect_candidate_predicate_refs(
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
        ),
        build_predicate_index(atoms),
    )

    assert refs == ("p1",)


def test_collect_candidate_predicate_refs_narrows_on_required_role_slots_only() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p2",
        ),
    )

    refs = collect_candidate_predicate_refs(
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
        ),
        build_predicate_index(atoms),
    )

    assert refs == ("p1",)
    assert meet_atom(
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
        ),
        atoms[0],
    ).level in {ResidualLevel.EXACT, ResidualLevel.PARTIAL}


def test_collect_candidate_predicate_refs_narrows_bound_role_args_without_scoring() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="validator", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="orders", entity_type="document"),
            },
            atom_id="p3",
        ),
    )

    refs = collect_candidate_predicate_refs(
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
        ),
        build_predicate_index(atoms),
    )

    assert refs == ("p1",)


def test_collect_candidate_predicate_refs_does_not_overprune_unresolved_or_variable_query_args() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="validator", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
    )
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="?", entity_type="person", status="unresolved"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    refs = collect_candidate_predicate_refs(query, build_predicate_index(atoms))

    assert refs == ("p1", "p2")
    assert meet_atom(query, atoms[0]).level is ResidualLevel.EXACT
    assert meet_atom(query, atoms[1]).level is ResidualLevel.EXACT

    variable_query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="$actor", entity_type="person", status="variable"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    variable_refs = collect_candidate_predicate_refs(variable_query, build_predicate_index(atoms))

    assert variable_refs == ("p1", "p2")


def test_collect_candidate_predicate_refs_is_only_a_narrowing_superset_helper() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
                "recipient": TypedArg(value="verifiers", entity_type="group"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p3",
        ),
    )
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )
    index = build_predicate_index(atoms)

    refs = collect_candidate_predicate_refs(query, index)
    valid_matches = {
        atom.atom_id
        for atom in atoms
        if comparable(query, atom) and meet_atom(query, atom).level is not ResidualLevel.NO_TYPED_MEET
    }

    assert set(refs).issuperset(valid_matches)
    assert refs == ("p1", "p2")


def test_collect_candidate_predicate_refs_uses_structural_signature_first() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p2",
        ),
    )
    index = build_predicate_index(atoms)
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={"actor": TypedArg(value="leader", entity_type="person")},
    )

    candidates = collect_candidate_predicate_refs(query, index)

    assert candidates == ("p1",)


def test_collect_candidate_predicate_refs_requires_role_slot_presence() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"actor": TypedArg(value="leader", entity_type="person")},
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
    )
    index = build_predicate_index(atoms)
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="asset", status="variable"),
        },
    )

    candidates = collect_candidate_predicate_refs(query, index)

    assert candidates == ("p2",)


def test_collect_candidate_predicate_refs_uses_bound_role_arg_narrowing() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="minutes", entity_type="document"),
            },
            atom_id="p2",
        ),
    )
    index = build_predicate_index(atoms)
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    candidates = collect_candidate_predicate_refs(query, index)

    assert candidates == ("p1",)


def test_collect_candidate_predicate_refs_does_not_over_prune_variable_args() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="minutes", entity_type="document"),
            },
            atom_id="p2",
        ),
    )
    index = build_predicate_index(atoms)
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="asset", status="variable"),
        },
    )

    candidates = collect_candidate_predicate_refs(query, index)

    assert candidates == ("p1", "p2")


def test_collect_candidate_predicate_refs_returns_superset_for_later_algebraic_refinement() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="validator", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p2",
        ),
    )
    index = build_predicate_index(atoms)
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="person", status="variable"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    candidates = collect_candidate_predicate_refs(query, index)

    assert candidates == ("p1", "p2")
    assert meet_atom(query, atoms[0]).level is ResidualLevel.EXACT
    assert meet_atom(query, atoms[1]).level is ResidualLevel.EXACT


def test_build_predicate_ref_map_aligns_with_index_fallback_refs() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"object": TypedArg(value="transactions", entity_type="document")},
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={"object": TypedArg(value="orders", entity_type="document")},
        ),
    )

    ref_map = build_predicate_ref_map(atoms)
    index = build_predicate_index(atoms)

    assert tuple(ref_map) == ("pnf:0", "pnf:1")
    assert index.by_structural_sig["publish"] == ("pnf:0", "pnf:1")


def test_collect_candidate_residuals_uses_only_shortlisted_refs_in_order() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="minutes", entity_type="document"),
            },
            atom_id="p2",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p3",
        ),
    )
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    candidate_residuals = collect_candidate_residuals(
        query,
        build_predicate_index(atoms),
        build_predicate_ref_map(atoms),
    )

    assert candidate_residuals == (
        CandidateResidual(
            ref="p1",
            residual=Residual(
                level=ResidualLevel.EXACT,
                shared_roles={
                    "actor": TypedArg(value="leader", entity_type="person"),
                    "object": TypedArg(value="transactions", entity_type="document"),
                },
                provenance=(),
            ),
        ),
    )


def test_compute_indexed_residual_joins_only_shortlisted_candidate_residuals() -> None:
    atoms = (
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            qualifiers=QualifierState(polarity="positive"),
            atom_id="p1",
        ),
        PredicateAtom(
            predicate="publish",
            structural_signature="publish",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            qualifiers=QualifierState(polarity="negative"),
            atom_id="p2",
        ),
        PredicateAtom(
            predicate="verify",
            structural_signature="verify",
            roles={
                "actor": TypedArg(value="leader", entity_type="person"),
                "object": TypedArg(value="transactions", entity_type="document"),
            },
            atom_id="p3",
        ),
    )
    query = PredicateAtom(
        predicate="publish",
        structural_signature="publish",
        roles={
            "actor": TypedArg(value="leader", entity_type="person"),
            "object": TypedArg(value="transactions", entity_type="document"),
        },
    )

    residual = compute_indexed_residual(
        query,
        build_predicate_index(atoms),
        build_predicate_ref_map(atoms),
    )

    assert residual.level is ResidualLevel.CONTRADICTION
    assert residual.shared_roles == {
        "actor": TypedArg(value="leader", entity_type="person"),
        "object": TypedArg(value="transactions", entity_type="document"),
    }
    assert residual.contradictions == ("polarity conflict",)
