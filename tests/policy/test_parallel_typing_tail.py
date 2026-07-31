from __future__ import annotations

from src.language.semantic_reductions import (
    diagnose_untyped_mentions as canonical_diagnose_untyped_mentions,
    derive_relational_type_hypotheses as canonical_derive_relational_type_hypotheses,
)
from src.policy import corpus_compilation as legacy
from src.policy.entity_resolution import (
    MentionSpan,
    build_local_typing_carrier as canonical_build_local_typing_carrier,
)
from src.policy.parallel_semantic_execution import (
    SemanticExecutionContext,
    _CONTEXT,
)


def _context(tmp_path) -> SemanticExecutionContext:
    return SemanticExecutionContext(
        document_ref="document:typing-tail",
        source_sha256="source-sha",
        parser_contract_ref="parser:test",
        build_key_sha256="build-key",
        typing_workers=4,
        leaf_capacity=1,
        hierarchy_arity=2,
        checkpoint_root=tmp_path,
        resource_ledger=None,
        run_ref="semantic-execution:test",
    )


def _mentions() -> tuple[MentionSpan, ...]:
    return (
        MentionSpan(
            mention_ref="mention:one",
            source_ref="source:1",
            document_ref="document:typing-tail",
            start_char=0,
            end_char=3,
            canonical_surface="One",
            generation_reason="named_entity_shape",
        ),
        MentionSpan(
            mention_ref="mention:two",
            source_ref="source:1",
            document_ref="document:typing-tail",
            start_char=4,
            end_char=7,
            canonical_surface="Two",
            generation_reason="named_entity_shape",
        ),
    )


def test_structural_hypothesis_leaves_preserve_canonical_output(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")
    monkeypatch.setenv("SENSIBLAW_TYPING_RELATION_LEAF_SIZE", "1")
    declarations = legacy.default_semantic_reduction_declarations()
    bundle = {
        "relations": [
            {
                "id": "relation:subject",
                "type": "subject",
                "source": "source:1",
                "roles": [
                    {"role": "head", "atom": "atom:predicate"},
                    {"role": "dependent", "atom": "atom:subject"},
                ],
                "metadata": {},
            },
            {
                "id": "relation:object",
                "type": "object",
                "source": "source:1",
                "roles": [
                    {"role": "head", "atom": "atom:predicate"},
                    {"role": "dependent", "atom": "atom:object"},
                ],
                "metadata": {},
            },
        ]
    }
    atom_mentions = {
        "atom:predicate": ("mention:predicate",),
        "atom:subject": ("mention:one",),
        "atom:object": ("mention:two",),
    }
    canonical = canonical_derive_relational_type_hypotheses(
        bundle=bundle,
        atom_mention_refs=atom_mentions,
        declarations=declarations,
    )
    context = _context(tmp_path)
    token = _CONTEXT.set(context)
    try:
        partitioned = legacy.derive_relational_type_hypotheses(
            bundle=bundle,
            atom_mention_refs=atom_mentions,
            declarations=declarations,
        )
    finally:
        _CONTEXT.reset(token)

    assert partitioned == canonical
    receipt = context.typing_receipts["structural_hypothesis_derivation"]
    assert receipt["leaf_count"] == 2
    assert receipt["descendant_bytes_reconstructed"] == 0
    assert receipt["flattening_free"] is True


def test_local_type_carrier_leaves_preserve_canonical_identity(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")
    monkeypatch.setenv("SENSIBLAW_TYPING_MENTION_LEAF_SIZE", "1")
    structural = (
        {
            "mention_ref": "mention:one",
            "semantic_family": "entity",
            "local_type": "agentive_entity",
            "derivation_basis": "public_structural_annotation",
            "evidence_refs": ("relation:one",),
        },
        {
            "mention_ref": "mention:two",
            "semantic_family": "entity",
            "local_type": "patient_entity",
            "derivation_basis": "public_structural_annotation",
            "evidence_refs": ("relation:two",),
        },
    )
    canonical = canonical_build_local_typing_carrier(
        mentions=_mentions(),
        forms=(),
        structural_hypotheses=structural,
    )
    context = _context(tmp_path)
    token = _CONTEXT.set(context)
    try:
        partitioned = legacy.build_local_typing_carrier(
            mentions=_mentions(),
            forms=(),
            structural_hypotheses=structural,
        )
    finally:
        _CONTEXT.reset(token)

    assert partitioned == canonical
    receipt = context.typing_receipts["local_type_carrier_build"]
    assert receipt["leaf_count"] == 2
    assert receipt["logical_typing_ref"]
    assert receipt["descendant_bytes_reconstructed"] == 0


def test_diagnostic_leaves_preserve_canonical_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")
    monkeypatch.setenv("SENSIBLAW_TYPING_MENTION_LEAF_SIZE", "1")
    local_typing = canonical_build_local_typing_carrier(
        mentions=_mentions(),
        forms=(),
        structural_hypotheses=(
            {
                "mention_ref": "mention:one",
                "semantic_family": "entity",
                "local_type": "agentive_entity",
                "derivation_basis": "public_structural_annotation",
                "evidence_refs": ("relation:one",),
            },
        ),
    )
    bundle = {"relations": []}
    parser_refs = {
        "mention:one": ("parser:one",),
        "mention:two": ("parser:two",),
    }
    capabilities = {"dependency": True}
    canonical = canonical_diagnose_untyped_mentions(
        mentions=[row.to_dict() for row in _mentions()],
        local_typing=local_typing,
        bundle=bundle,
        atom_mention_refs={},
        parser_observation_refs=parser_refs,
        parser_capabilities=capabilities,
    )
    context = _context(tmp_path)
    token = _CONTEXT.set(context)
    try:
        partitioned = legacy.diagnose_untyped_mentions(
            mentions=[row.to_dict() for row in _mentions()],
            local_typing=local_typing,
            bundle=bundle,
            atom_mention_refs={},
            parser_observation_refs=parser_refs,
            parser_capabilities=capabilities,
        )
    finally:
        _CONTEXT.reset(token)

    assert partitioned == canonical
    receipt = context.typing_receipts["untyped_diagnostic_generation"]
    assert receipt["leaf_count"] == 2
    assert receipt["flattening_free"] is True


def test_typing_tail_second_pass_reuses_all_leaf_checkpoints(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")
    monkeypatch.setenv("SENSIBLAW_TYPING_MENTION_LEAF_SIZE", "1")
    structural = (
        {
            "mention_ref": "mention:one",
            "semantic_family": "entity",
            "local_type": "agentive_entity",
            "derivation_basis": "public_structural_annotation",
            "evidence_refs": ("relation:one",),
        },
        {
            "mention_ref": "mention:two",
            "semantic_family": "entity",
            "local_type": "patient_entity",
            "derivation_basis": "public_structural_annotation",
            "evidence_refs": ("relation:two",),
        },
    )

    receipts = []
    for _ in range(2):
        context = _context(tmp_path)
        token = _CONTEXT.set(context)
        try:
            legacy.build_local_typing_carrier(
                mentions=_mentions(),
                forms=(),
                structural_hypotheses=structural,
            )
        finally:
            _CONTEXT.reset(token)
        receipts.append(context.typing_receipts["local_type_carrier_build"])

    assert receipts[0]["computed_leaf_count"] == 2
    assert receipts[1]["computed_leaf_count"] == 0
    assert receipts[1]["reused_leaf_count"] == 2
    assert receipts[0]["logical_typing_ref"] == receipts[1]["logical_typing_ref"]
