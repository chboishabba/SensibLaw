from ._compat import install_src_package_aliases
from .market_news_projector import (
    PROJECTOR_VERSION,
    SUPPORTED_EXTRACTION_PROFILE,
    project_event_text_to_predicate_atoms,
)

install_src_package_aliases()

from . import parser_adapter, shared_reducer, text_adapter
from .parser_adapter import (
    MessageHeader,
    TimeRangeHeader,
    collect_canonical_operational_structure_occurrences,
    parse_canonical_message_header,
    parse_canonical_text,
    parse_canonical_time_range_header,
    split_presemantic_semicolon_clauses,
    split_presemantic_text_clauses,
    split_presemantic_text_segments,
    strip_presemantic_enumeration_prefix,
    tokenize_presemantic_text,
)
from .shared_reducer import (
    CandidateResidual,
    LexemeOccurrence,
    LexemeToken,
    LexemeTokenizerProfile,
    PredicateAtom,
    PredicateIndex,
    PredicatePNF,
    QualifierState,
    RelationalAtom,
    Residual,
    ResidualLevel,
    RoleState,
    StructureOccurrence,
    TypedArg,
    WrapperState,
    build_predicate_index,
    build_predicate_ref_map,
    coerce_predicate_atom,
    collect_candidate_predicate_refs,
    collect_candidate_residuals,
    collect_canonical_lexeme_occurrences,
    collect_canonical_lexeme_occurrences_with_profile,
    collect_canonical_lexeme_terms,
    collect_canonical_predicate_atoms,
    collect_canonical_predicate_atoms_from_units,
    collect_canonical_predicate_pnfs,
    collect_canonical_predicate_pnfs_from_units,
    collect_canonical_relational_bundle,
    collect_canonical_structural_ir_feed,
    collect_canonical_structural_ir_feed_from_units,
    collect_canonical_structure_occurrences,
    comparable,
    compute_indexed_residual,
    compute_residual,
    get_canonical_tokenizer_profile,
    join_residual,
    join_role_states,
    join_typed_args,
    meet_atom,
    tokenize_canonical_detailed,
    tokenize_canonical_with_spans,
)
from .story_importer import StoryImporter
from .text_adapter import build_canonical_conversation_text

_staged_exports = []

try:
    from . import ir_types
    from .ir_types import (
        InteractionMode,
        InteractionProjectionReceipt,
        QueryEdge,
        QueryNode,
        QueryTree,
    )
except ImportError:
    ir_types = None
else:
    _staged_exports.extend(
        [
            "InteractionMode",
            "InteractionProjectionReceipt",
            "QueryEdge",
            "QueryNode",
            "QueryTree",
            "ir_types",
        ]
    )

try:
    from . import ir_adapter
    from .ir_adapter import build_query_tree, project_interaction_mode
except ImportError:
    ir_adapter = None
else:
    _staged_exports.extend(
        [
            "build_query_tree",
            "ir_adapter",
            "project_interaction_mode",
        ]
    )

try:
    from . import signals
    from .signals import (
        SIGNAL_STATE_VERSION,
        SignalAtom,
        SignalSpan,
        SignalState,
        collect_signal_state,
        extract_interaction_signals,
        summarize_signal_state,
    )
except ImportError:
    signals = None
else:
    _staged_exports.extend(
        [
            "SIGNAL_STATE_VERSION",
            "SignalAtom",
            "SignalSpan",
            "SignalState",
            "collect_signal_state",
            "extract_interaction_signals",
            "signals",
            "summarize_signal_state",
        ]
    )

__all__ = [
    "CandidateResidual",
    "InteractionMode",
    "InteractionProjectionReceipt",
    "LexemeOccurrence",
    "LexemeToken",
    "LexemeTokenizerProfile",
    "MessageHeader",
    "PROJECTOR_VERSION",
    "PredicateAtom",
    "PredicateIndex",
    "PredicatePNF",
    "QualifierState",
    "QueryEdge",
    "QueryNode",
    "QueryTree",
    "RelationalAtom",
    "Residual",
    "ResidualLevel",
    "RoleState",
    "SIGNAL_STATE_VERSION",
    "SUPPORTED_EXTRACTION_PROFILE",
    "SignalAtom",
    "SignalSpan",
    "SignalState",
    "StoryImporter",
    "StructureOccurrence",
    "TimeRangeHeader",
    "TypedArg",
    "WrapperState",
    "build_canonical_conversation_text",
    "build_predicate_index",
    "build_predicate_ref_map",
    "build_query_tree",
    "coerce_predicate_atom",
    "collect_candidate_predicate_refs",
    "collect_candidate_residuals",
    "collect_canonical_lexeme_occurrences",
    "collect_canonical_lexeme_occurrences_with_profile",
    "collect_canonical_lexeme_terms",
    "collect_canonical_operational_structure_occurrences",
    "collect_canonical_predicate_atoms",
    "collect_canonical_predicate_atoms_from_units",
    "collect_canonical_predicate_pnfs",
    "collect_canonical_predicate_pnfs_from_units",
    "collect_canonical_relational_bundle",
    "collect_canonical_structural_ir_feed",
    "collect_canonical_structural_ir_feed_from_units",
    "collect_canonical_structure_occurrences",
    "collect_signal_state",
    "comparable",
    "compute_indexed_residual",
    "compute_residual",
    "extract_interaction_signals",
    "get_canonical_tokenizer_profile",
    "ir_adapter",
    "ir_types",
    "join_residual",
    "join_role_states",
    "join_typed_args",
    "meet_atom",
    "parser_adapter",
    "parse_canonical_message_header",
    "parse_canonical_text",
    "parse_canonical_time_range_header",
    "project_event_text_to_predicate_atoms",
    "project_interaction_mode",
    "shared_reducer",
    "signals",
    "split_presemantic_semicolon_clauses",
    "split_presemantic_text_clauses",
    "split_presemantic_text_segments",
    "strip_presemantic_enumeration_prefix",
    "summarize_signal_state",
    "text_adapter",
    "tokenize_canonical_detailed",
    "tokenize_canonical_with_spans",
    "tokenize_presemantic_text",
] + _staged_exports
