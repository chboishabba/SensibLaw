from ._compat import install_src_package_aliases

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
    LexemeOccurrence,
    LexemeToken,
    LexemeTokenizerProfile,
    RelationalAtom,
    StructureOccurrence,
    collect_canonical_lexeme_occurrences,
    collect_canonical_lexeme_occurrences_with_profile,
    collect_canonical_relational_bundle,
    collect_canonical_structure_occurrences,
    get_canonical_tokenizer_profile,
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
    "LexemeOccurrence",
    "LexemeToken",
    "LexemeTokenizerProfile",
    "MessageHeader",
    "RelationalAtom",
    "StoryImporter",
    "StructureOccurrence",
    "TimeRangeHeader",
    "build_canonical_conversation_text",
    "collect_canonical_operational_structure_occurrences",
    "collect_canonical_lexeme_occurrences",
    "collect_canonical_lexeme_occurrences_with_profile",
    "collect_canonical_relational_bundle",
    "collect_canonical_structure_occurrences",
    "get_canonical_tokenizer_profile",
    "parser_adapter",
    "parse_canonical_message_header",
    "parse_canonical_text",
    "parse_canonical_time_range_header",
    "shared_reducer",
    "split_presemantic_semicolon_clauses",
    "split_presemantic_text_clauses",
    "split_presemantic_text_segments",
    "strip_presemantic_enumeration_prefix",
    "text_adapter",
    "tokenize_canonical_detailed",
    "tokenize_canonical_with_spans",
    "tokenize_presemantic_text",
] + _staged_exports
