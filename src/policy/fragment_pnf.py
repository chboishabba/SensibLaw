from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from src.text.residual_lattice import ResidualLevel


# ── Finite ordered component types ──────────────────────────────────────────

class ConnectednessLevel(str, Enum):
    isolated = "isolated"
    linked = "linked"
    clustered = "clustered"
    braid_connected = "braid_connected"


class ReferentialityLevel(str, Enum):
    single_source = "single_source"
    same_family_multi_span = "same_family_multi_span"
    multi_family = "multi_family"
    cross_source = "cross_source"


class DepthLevel(str, Enum):
    flat = "flat"
    fragment_depth = "fragment_depth"
    sentence_depth = "sentence_depth"
    document_depth = "document_depth"
    braid_depth = "braid_depth"


class PNFClosureLevel(str, Enum):
    open = "open"
    partial = "partial"
    role_closed = "role_closed"
    role_time_closed = "role_time_closed"
    span_receipt_closed = "span_receipt_closed"


class PredicateFrame(str, Enum):
    """Abstract structural PNF shape for fragment-level extractions.

    This is the user-facing / review-surface category.  Grammar IDs are
    recognizer provenance; fragment_subclass is a domain-specific hint;
    predicate_frame is the abstract role-bearing shape that appears in
    triage and human-review surfaces.
    """

    role_occupancy_range = "role_occupancy_range"
    affiliation_or_membership_range = "affiliation_or_membership_range"
    ownership_or_control_range = "ownership_or_control_range"
    declarative_act = "declarative_act"
    credential_or_training_event = "credential_or_training_event"
    life_event = "life_event"
    legal_or_legislative_act = "legal_or_legislative_act"
    generic_relation = "generic_relation"


# Stable mapping from grammar ID → PredicateFrame
GRAMMAR_TO_PREDICATE_FRAME: dict[str, PredicateFrame] = {
    "office_range_grammar_v0": PredicateFrame.role_occupancy_range,
    "proclamation_grammar_v0": PredicateFrame.declarative_act,
    "ownership_grammar_v0": PredicateFrame.ownership_or_control_range,
    "education_grammar_v0": PredicateFrame.credential_or_training_event,
    "marriage_grammar_v0": PredicateFrame.life_event,
    "birth_grammar_v0": PredicateFrame.life_event,
    "fallback_grammar_v0": PredicateFrame.generic_relation,
}


class ResidualCompatibilityLevel(str, Enum):
    """Residual comparison outcome, aligned with residual_lattice.ResidualLevel.

    This is a string enum mirror of the IntEnum in residual_lattice, kept
    separate to avoid shadowing the formal type and to live cleanly in
    pipeline-level dicts/receipts.

    ``not_evaluated`` means residual comparison has not been run (pending).
    It is not a blocking outcome — the row may still be blocked by other
    gates, but residual cannot be the reason.
    """

    exact = "exact"
    partial = "partial"
    not_evaluated = "not_evaluated"
    no_typed_meet = "no_typed_meet"
    contradiction = "contradiction"


class ProjectionBasisLevel(str, Enum):
    grammar_projected = "grammar_projected"
    fallback_projected = "fallback_projected"
    partial_projected = "partial_projected"
    unprojectable = "unprojectable"


class LinkageDepthLevel(str, Enum):
    flat_shortcut = "flat_shortcut"
    source_span = "source_span"
    fragment_pnf = "fragment_pnf"
    sentence_pnf = "sentence_pnf"
    document_pnf = "document_pnf"
    braid_node = "braid_node"


class SourceSpanLevel(str, Enum):
    missing = "missing"
    normalized_only = "normalized_only"
    raw_span = "raw_span"
    raw_and_normalized_span = "raw_and_normalized_span"
    receipt_backed_span = "receipt_backed_span"


class ExportClass(str, Enum):
    blocked = "blocked"
    candidate_only = "candidate_only"
    reviewable = "reviewable"
    exportable = "exportable"
    high_confidence_exportable = "high_confidence_exportable"


class GrammarMatchStrength(str, Enum):
    exact_pattern = "exact_pattern"
    normalized_pattern = "normalized_pattern"
    fallback_bundle = "fallback_bundle"
    weak_fallback = "weak_fallback"


# ── Explicit rank maps for ordered comparison ──────────────────────────────

CONNECTEDNESS_RANK: dict[ConnectednessLevel, int] = {
    ConnectednessLevel.isolated: 0,
    ConnectednessLevel.linked: 1,
    ConnectednessLevel.clustered: 2,
    ConnectednessLevel.braid_connected: 3,
}

REFERENTIALITY_RANK: dict[ReferentialityLevel, int] = {
    ReferentialityLevel.single_source: 0,
    ReferentialityLevel.same_family_multi_span: 1,
    ReferentialityLevel.multi_family: 2,
    ReferentialityLevel.cross_source: 3,
}

DEPTH_RANK: dict[DepthLevel, int] = {
    DepthLevel.flat: 0,
    DepthLevel.fragment_depth: 1,
    DepthLevel.sentence_depth: 2,
    DepthLevel.document_depth: 3,
    DepthLevel.braid_depth: 4,
}

PNF_CLOSURE_RANK: dict[PNFClosureLevel, int] = {
    PNFClosureLevel.open: 0,
    PNFClosureLevel.partial: 1,
    PNFClosureLevel.role_closed: 2,
    PNFClosureLevel.role_time_closed: 3,
    PNFClosureLevel.span_receipt_closed: 4,
}

RESIDUAL_COMPATIBILITY_RANK: dict[ResidualCompatibilityLevel, int] = {
    ResidualCompatibilityLevel.not_evaluated: -1,
    ResidualCompatibilityLevel.exact: 0,
    ResidualCompatibilityLevel.partial: 1,
    ResidualCompatibilityLevel.no_typed_meet: 2,
    ResidualCompatibilityLevel.contradiction: 3,
}

PROJECTION_BASIS_RANK: dict[ProjectionBasisLevel, int] = {
    ProjectionBasisLevel.grammar_projected: 0,
    ProjectionBasisLevel.fallback_projected: 1,
    ProjectionBasisLevel.partial_projected: 2,
    ProjectionBasisLevel.unprojectable: 3,
}

LINKAGE_DEPTH_RANK: dict[LinkageDepthLevel, int] = {
    LinkageDepthLevel.flat_shortcut: 0,
    LinkageDepthLevel.source_span: 1,
    LinkageDepthLevel.fragment_pnf: 2,
    LinkageDepthLevel.sentence_pnf: 3,
    LinkageDepthLevel.document_pnf: 4,
    LinkageDepthLevel.braid_node: 5,
}

SOURCE_SPAN_RANK: dict[SourceSpanLevel, int] = {
    SourceSpanLevel.missing: 0,
    SourceSpanLevel.normalized_only: 1,
    SourceSpanLevel.raw_span: 2,
    SourceSpanLevel.raw_and_normalized_span: 3,
    SourceSpanLevel.receipt_backed_span: 4,
}

EXPORT_CLASS_RANK: dict[ExportClass, int] = {
    ExportClass.blocked: 0,
    ExportClass.candidate_only: 1,
    ExportClass.reviewable: 2,
    ExportClass.exportable: 3,
    ExportClass.high_confidence_exportable: 4,
}


# ── Helper value types ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class TypedRole:
    canonical_key: str | None = None
    canonical_label: str | None = None
    raw_text: str = ""
    source_span_offset: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"raw_text": self.raw_text}
        if self.canonical_key is not None:
            payload["canonical_key"] = self.canonical_key
        if self.canonical_label is not None:
            payload["canonical_label"] = self.canonical_label
        if self.source_span_offset is not None:
            payload["source_span_offset"] = list(self.source_span_offset)
        return payload


@dataclass(frozen=True)
class TimeAnchor:
    start_date: str | None = None
    end_date: str | None = None
    precision: str = "unknown"
    raw_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"precision": self.precision}
        if self.start_date is not None:
            payload["start_date"] = self.start_date
        if self.end_date is not None:
            payload["end_date"] = self.end_date
        if self.raw_text is not None:
            payload["raw_text"] = self.raw_text
        return payload


@dataclass(frozen=True)
class SourceSpanRef:
    parent_event_id: str
    atom_id: str
    fragment_surface_text: str
    raw_start: int | None = None
    raw_end: int | None = None
    normalized_start: int | None = None
    normalized_end: int | None = None
    surface_text_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parent_event_id": self.parent_event_id,
            "atom_id": self.atom_id,
            "fragment_surface_text": self.fragment_surface_text,
            "surface_text_hash": self.surface_text_hash,
        }
        if self.raw_start is not None:
            payload["raw_start"] = self.raw_start
        if self.raw_end is not None:
            payload["raw_end"] = self.raw_end
        if self.normalized_start is not None:
            payload["normalized_start"] = self.normalized_start
        if self.normalized_end is not None:
            payload["normalized_end"] = self.normalized_end
        return payload


# ── Fragment-surface taxonomy ──────────────────────────────────────────────

FRAGMENT_SURFACE_CLASSES = frozenset({
    "cv_cell",
    "list_entry",
    "caption_fragment",
    "title_range",
    "prose_fragment",
    "fallback",
})

FRAGMENT_SUBCLASSES = frozenset({
    "office_range",
    "ownership_range",
    "proclamation",
    "education",
    "birth_date",
    "marriage_event",
    "death_date",
    "legislative_ref",
    "generic_relation",
})


# ── FragmentPNF — candidate extraction receipt ─────────────────────────────

@dataclass(frozen=True)
class FragmentPNF:
    """Pipeline-local extraction receipt over fragment-level evidence.

    This is *not* a formal PredicatePNF. It is a candidate-only structural
    snapshot produced by a FragmentGrammar.  Residual-comparison authority
    belongs to PredicateAtom / PredicatePNF; the bridge is recorded by
    FragmentPNFProjectionReceipt.
    """

    fragment_id: str
    parent_event_id: str
    fragment_surface: str
    fragment_surface_class: str
    fragment_subclass: str
    grammar_id: str
    grammar_match_strength: GrammarMatchStrength
    subject_role: TypedRole | None = None
    predicate_spine: str | None = None
    object_role: TypedRole | None = None
    time_anchor: TimeAnchor | None = None
    modifiers: tuple[TypedRole, ...] = ()
    source_span: SourceSpanRef | None = None
    pnf_basis: tuple[str, ...] = ()
    fallback_used: bool = False
    authority_status: str = "candidate_only"
    semantic_authority: bool = False
    export_authority: bool = False
    predicate_frame: PredicateFrame | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fragment_id": self.fragment_id,
            "parent_event_id": self.parent_event_id,
            "fragment_surface": self.fragment_surface,
            "fragment_surface_class": self.fragment_surface_class,
            "fragment_subclass": self.fragment_subclass,
            "grammar_id": self.grammar_id,
            "grammar_match_strength": self.grammar_match_strength.value,
            "authority_status": self.authority_status,
            "semantic_authority": self.semantic_authority,
            "export_authority": self.export_authority,
            "fallback_used": self.fallback_used,
        }
        if self.predicate_frame is not None:
            payload["predicate_frame"] = self.predicate_frame.value
        if self.subject_role is not None:
            payload["subject_role"] = self.subject_role.to_dict()
        if self.predicate_spine is not None:
            payload["predicate_spine"] = self.predicate_spine
        if self.object_role is not None:
            payload["object_role"] = self.object_role.to_dict()
        if self.time_anchor is not None:
            payload["time_anchor"] = self.time_anchor.to_dict()
        if self.modifiers:
            payload["modifiers"] = [m.to_dict() for m in self.modifiers]
        if self.source_span is not None:
            payload["source_span"] = self.source_span.to_dict()
        if self.pnf_basis:
            payload["pnf_basis"] = list(self.pnf_basis)
        return payload


# ── FragmentPNFProjectionReceipt — bridge to formal PredicatePNF ───────────

@dataclass(frozen=True)
class FragmentPNFProjectionReceipt:
    """Records whether/how a FragmentPNF projects to PredicatePNF.

    The fragment itself is never mutated — projection is always a separate
    artifact.
    """

    schema_version: ClassVar[str] = "sl.fragment_pnf_projection_receipt.v0_1"

    fragment_id: str
    projection_status: ProjectionBasisLevel
    residual_level: ResidualLevel | None = None
    predicate_atom_ref: str | None = None
    predicate_pnf_ref: str | None = None
    projection_basis: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "fragment_id": self.fragment_id,
            "projection_status": self.projection_status.value,
        }
        if self.residual_level is not None:
            payload["residual_level"] = self.residual_level.name.lower()
        if self.predicate_atom_ref is not None:
            payload["predicate_atom_ref"] = self.predicate_atom_ref
        if self.predicate_pnf_ref is not None:
            payload["predicate_pnf_ref"] = self.predicate_pnf_ref
        if self.projection_basis:
            payload["projection_basis"] = list(self.projection_basis)
        if self.blocked_reasons:
            payload["blocked_reasons"] = list(self.blocked_reasons)
        return payload


# ── FragmentPNFDepthReceipt — anti-flatness check ──────────────────────────

@dataclass(frozen=True)
class FragmentPNFDepthReceipt:
    """Depth-preservation receipt verifying no flat token→timeline shortcut."""

    schema_version: ClassVar[str] = "sl.fragment_pnf_depth_receipt.v0_1"

    source_span_present: bool = False
    token_span_present: bool = False
    fragment_pnf_present: bool = False
    sentence_pnf_present: bool = False
    document_pnf_present: bool = False
    braid_attachment_present: bool = False
    role_erasure_detected: bool = False
    flat_shortcut_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_span_present": self.source_span_present,
            "token_span_present": self.token_span_present,
            "fragment_pnf_present": self.fragment_pnf_present,
            "sentence_pnf_present": self.sentence_pnf_present,
            "document_pnf_present": self.document_pnf_present,
            "braid_attachment_present": self.braid_attachment_present,
            "role_erasure_detected": self.role_erasure_detected,
            "flat_shortcut_detected": self.flat_shortcut_detected,
        }

    @classmethod
    def from_atom(
        cls,
        atom: dict[str, Any],
        *,
        has_source_span: bool = False,
        has_token_span: bool = False,
        has_fragment_pnf: bool = False,
        has_sentence_pnf: bool = False,
        has_document_pnf: bool = False,
        has_braid_attachment: bool = False,
    ) -> FragmentPNFDepthReceipt:
        """Build a depth receipt from pipeline signals, detecting flat shortcuts."""
        flat = bool(
            has_source_span
            and not has_fragment_pnf
            and not has_sentence_pnf
            and not has_braid_attachment
        )
        return cls(
            source_span_present=has_source_span,
            token_span_present=has_token_span,
            fragment_pnf_present=has_fragment_pnf,
            sentence_pnf_present=has_sentence_pnf,
            document_pnf_present=has_document_pnf,
            braid_attachment_present=has_braid_attachment,
            flat_shortcut_detected=flat,
            role_erasure_detected=bool(
                has_fragment_pnf and not has_sentence_pnf and not has_document_pnf
            ),
        )


# ── Blocked reasons (stable enum-like strings, not thresholds) ─────────────

BLOCKED_REASON_SOURCE_SPAN_MISSING = "source_span_missing"
BLOCKED_REASON_RECEIPT_MISSING = "receipt_missing"
BLOCKED_REASON_FRAGMENT_PNF_MISSING = "fragment_pnf_missing"
BLOCKED_REASON_FLAT_SHORTCUT = "flat_token_to_timeline_shortcut"
BLOCKED_REASON_TIME_NOT_BOUND = "time_not_bound"
BLOCKED_REASON_PNF_NOT_CLOSED = "pnf_closure_insufficient"
BLOCKED_REASON_LINKAGE_DEPTH_INSUFFICIENT = "linkage_depth_insufficient"
BLOCKED_REASON_RESIDUAL_BLOCKED = "residual_compatibility_blocked"
BLOCKED_REASON_RESIDUAL_NOT_EVALUATED = "residual_evaluation_missing"
BLOCKED_REASON_PROJECTION_MISSING = "formal_projection_missing"
BLOCKED_REASON_REFERENTIALITY_INSUFFICIENT = "referentiality_insufficient"
BLOCKED_REASON_REQUIRED_BRAID_DEPTH_MISSING = "required_braid_depth_missing"

BLOCKED_REASONS_STABLE = frozenset({
    BLOCKED_REASON_SOURCE_SPAN_MISSING,
    BLOCKED_REASON_RECEIPT_MISSING,
    BLOCKED_REASON_FRAGMENT_PNF_MISSING,
    BLOCKED_REASON_FLAT_SHORTCUT,
    BLOCKED_REASON_TIME_NOT_BOUND,
    BLOCKED_REASON_PNF_NOT_CLOSED,
    BLOCKED_REASON_LINKAGE_DEPTH_INSUFFICIENT,
    BLOCKED_REASON_RESIDUAL_BLOCKED,
    BLOCKED_REASON_RESIDUAL_NOT_EVALUATED,
    BLOCKED_REASON_PROJECTION_MISSING,
    BLOCKED_REASON_REFERENTIALITY_INSUFFICIENT,
    BLOCKED_REASON_REQUIRED_BRAID_DEPTH_MISSING,
})


# ── BraidRelevanceReceipt — product of typed components, not scalar ────────

@dataclass(frozen=True)
class BraidRelevanceReceipt:
    """Product-ordered relevance receipt.

    Export class is determined by hard gates over the typed component levels,
    never by a weighted scalar score.
    """

    schema_version: ClassVar[str] = "sl.braid_relevance_receipt.v0_1"

    connectedness_level: ConnectednessLevel = ConnectednessLevel.isolated
    referentiality_level: ReferentialityLevel = ReferentialityLevel.single_source
    depth_level: DepthLevel = DepthLevel.flat
    pnf_closure_level: PNFClosureLevel = PNFClosureLevel.open
    residual_compatibility_level: ResidualCompatibilityLevel = (
        ResidualCompatibilityLevel.no_typed_meet
    )
    projection_basis_level: ProjectionBasisLevel = ProjectionBasisLevel.unprojectable
    linkage_depth_level: LinkageDepthLevel = LinkageDepthLevel.flat_shortcut
    source_span_level: SourceSpanLevel = SourceSpanLevel.missing
    export_class: ExportClass = ExportClass.blocked
    blocked_reasons: tuple[str, ...] = ()
    basis: tuple[str, ...] = ()

    # Diagnostics — never authoritative, never gate export:
    connected_component_size: int | None = None
    source_family_count: int | None = None
    longest_path_len: int | None = None
    closed_role_count: int | None = None
    total_role_count: int | None = None
    fallback_field_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "connectedness_level": self.connectedness_level.value,
            "referentiality_level": self.referentiality_level.value,
            "depth_level": self.depth_level.value,
            "pnf_closure_level": self.pnf_closure_level.value,
            "residual_compatibility_level": self.residual_compatibility_level.value,
            "projection_basis_level": self.projection_basis_level.value,
            "linkage_depth_level": self.linkage_depth_level.value,
            "source_span_level": self.source_span_level.value,
            "export_class": self.export_class.value,
        }
        if self.blocked_reasons:
            payload["blocked_reasons"] = list(self.blocked_reasons)
        if self.basis:
            payload["basis"] = list(self.basis)
        if self.connected_component_size is not None:
            payload["connected_component_size"] = self.connected_component_size
        if self.source_family_count is not None:
            payload["source_family_count"] = self.source_family_count
        if self.longest_path_len is not None:
            payload["longest_path_len"] = self.longest_path_len
        if self.closed_role_count is not None:
            payload["closed_role_count"] = self.closed_role_count
        if self.total_role_count is not None:
            payload["total_role_count"] = self.total_role_count
        if self.fallback_field_count is not None:
            payload["fallback_field_count"] = self.fallback_field_count
        return payload


# ── ExportGateReceipt — hard-gated admissibility ───────────────────────────

@dataclass(frozen=True)
class ExportGateReceipt:
    """Receipt produced by the hard-gated export gate.

    No scalar threshold, no weighted score — only finite-level gates checked
    against a lane policy.
    """

    schema_version: ClassVar[str] = "sl.export_gate_receipt.v0_1"

    exportable: bool = False
    export_class: ExportClass = ExportClass.blocked
    pnf_closed: bool = False
    time_bound: bool = False
    source_spanned: bool = False
    has_fragment_pnf_path: bool = False
    has_formal_projection: bool = False
    residual_not_blocked: bool = False
    referentiality_adequate: bool = False
    blocked_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "exportable": self.exportable,
            "export_class": self.export_class.value,
            "pnf_closed": self.pnf_closed,
            "time_bound": self.time_bound,
            "source_spanned": self.source_spanned,
            "has_fragment_pnf_path": self.has_fragment_pnf_path,
            "has_formal_projection": self.has_formal_projection,
            "residual_not_blocked": self.residual_not_blocked,
            "referentiality_adequate": self.referentiality_adequate,
        }
        if self.blocked_reasons:
            payload["blocked_reasons"] = list(self.blocked_reasons)
        return payload


# ── ExportLanePolicy ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExportLanePolicy:
    """Lane-specific publication/export parameters.

    These are policy constants, not universal formalism — they let different
    lanes require different referentiality, projection, or depth before export.
    """

    lane_id: str
    min_referentiality_level: ReferentialityLevel = ReferentialityLevel.multi_family
    require_braid_node: bool = True
    require_formal_projection: bool = True
    min_projection_basis_level: ProjectionBasisLevel = ProjectionBasisLevel.fallback_projected
    min_pnf_closure_level: PNFClosureLevel = PNFClosureLevel.role_time_closed
    min_linkage_depth_level: LinkageDepthLevel = LinkageDepthLevel.braid_node

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "min_referentiality_level": self.min_referentiality_level.value,
            "require_braid_node": self.require_braid_node,
            "require_formal_projection": self.require_formal_projection,
            "min_projection_basis_level": self.min_projection_basis_level.value,
            "min_pnf_closure_level": self.min_pnf_closure_level.value,
            "min_linkage_depth_level": self.min_linkage_depth_level.value,
        }


# Default policy for GWB public review
DEFAULT_GWB_LANE_POLICY = ExportLanePolicy(
    lane_id="gwb_public_review",
    min_referentiality_level=ReferentialityLevel.multi_family,
    require_braid_node=True,
    require_formal_projection=True,
    min_projection_basis_level=ProjectionBasisLevel.fallback_projected,
    min_pnf_closure_level=PNFClosureLevel.role_time_closed,
    min_linkage_depth_level=LinkageDepthLevel.braid_node,
)

# Internal/triage policy — lower bar for review queue
INTERNAL_REVIEW_LANE_POLICY = ExportLanePolicy(
    lane_id="internal_review",
    min_referentiality_level=ReferentialityLevel.single_source,
    require_braid_node=False,
    require_formal_projection=False,
    min_projection_basis_level=ProjectionBasisLevel.partial_projected,
    min_pnf_closure_level=PNFClosureLevel.partial,
    min_linkage_depth_level=LinkageDepthLevel.fragment_pnf,
)


# ── Classification helpers ─────────────────────────────────────────────────

def classify_connectedness(
    component_size: int,
    has_braid_attachment: bool,
    residual_support_edge_count: int,
) -> ConnectednessLevel:
    if component_size <= 1 and not has_braid_attachment:
        return ConnectednessLevel.isolated
    if component_size >= 2 and not has_braid_attachment:
        return ConnectednessLevel.linked
    if has_braid_attachment and residual_support_edge_count >= 2:
        return ConnectednessLevel.clustered
    if has_braid_attachment:
        return ConnectednessLevel.braid_connected
    return ConnectednessLevel.isolated


def classify_referentiality(
    source_family_count: int,
    total_span_count: int,
    independent_receipt_count: int,
) -> ReferentialityLevel:
    if source_family_count >= 2 and independent_receipt_count >= 2:
        return ReferentialityLevel.cross_source
    if source_family_count >= 2:
        return ReferentialityLevel.multi_family
    if source_family_count == 1 and total_span_count >= 2:
        return ReferentialityLevel.same_family_multi_span
    if source_family_count == 1:
        return ReferentialityLevel.single_source
    return ReferentialityLevel.single_source


def classify_depth(
    has_fragment_pnf: bool,
    has_sentence_pnf: bool,
    has_document_pnf: bool,
    has_braid_node: bool,
) -> DepthLevel:
    if has_braid_node:
        return DepthLevel.braid_depth
    if has_document_pnf:
        return DepthLevel.document_depth
    if has_sentence_pnf:
        return DepthLevel.sentence_depth
    if has_fragment_pnf:
        return DepthLevel.fragment_depth
    return DepthLevel.flat


def classify_pnf_closure(
    subject_filled: bool,
    predicate_filled: bool,
    object_filled: bool,
    time_filled: bool,
    has_source_span: bool,
    has_receipt: bool,
) -> PNFClosureLevel:
    filled = sum([subject_filled, predicate_filled, object_filled])
    if filled < 2:
        return PNFClosureLevel.open
    if filled == 2:
        return PNFClosureLevel.partial
    if filled == 3 and not time_filled:
        return PNFClosureLevel.role_closed
    if filled == 3 and time_filled and not (has_source_span and has_receipt):
        return PNFClosureLevel.role_time_closed
    if filled == 3 and time_filled and has_source_span and has_receipt:
        return PNFClosureLevel.span_receipt_closed
    return PNFClosureLevel.partial


def classify_source_span(
    has_raw_span: bool,
    has_normalized_span: bool,
    has_receipt: bool,
) -> SourceSpanLevel:
    if has_receipt:
        return SourceSpanLevel.receipt_backed_span
    if has_raw_span and has_normalized_span:
        return SourceSpanLevel.raw_and_normalized_span
    if has_raw_span:
        return SourceSpanLevel.raw_span
    if has_normalized_span:
        return SourceSpanLevel.normalized_only
    return SourceSpanLevel.missing


def residual_level_to_compatibility(
    level: ResidualLevel,
) -> ResidualCompatibilityLevel:
    mapping = {
        ResidualLevel.EXACT: ResidualCompatibilityLevel.exact,
        ResidualLevel.PARTIAL: ResidualCompatibilityLevel.partial,
        ResidualLevel.NO_TYPED_MEET: ResidualCompatibilityLevel.no_typed_meet,
        ResidualLevel.CONTRADICTION: ResidualCompatibilityLevel.contradiction,
    }
    return mapping.get(level, ResidualCompatibilityLevel.no_typed_meet)


def projection_basis_from_fallback(
    fallback_used: bool,
    roles_filled: int,
) -> ProjectionBasisLevel:
    if not fallback_used and roles_filled >= 3:
        return ProjectionBasisLevel.grammar_projected
    if fallback_used and roles_filled >= 3:
        return ProjectionBasisLevel.fallback_projected
    if roles_filled >= 1:
        return ProjectionBasisLevel.partial_projected
    return ProjectionBasisLevel.unprojectable


def classify_export_class(
    pnf_closure_level: PNFClosureLevel,
    projection_basis_level: ProjectionBasisLevel,
    residual_compatibility_level: ResidualCompatibilityLevel,
    linkage_depth_level: LinkageDepthLevel,
    referentiality_level: ReferentialityLevel,
    policy: ExportLanePolicy,
) -> tuple[ExportClass, list[str]]:
    reasons: list[str] = []

    if pnf_closure_level == PNFClosureLevel.open:
        reasons.append(BLOCKED_REASON_PNF_NOT_CLOSED)
    elif PNF_CLOSURE_RANK[pnf_closure_level] < PNF_CLOSURE_RANK[policy.min_pnf_closure_level]:
        reasons.append(BLOCKED_REASON_PNF_NOT_CLOSED)

    if linkage_depth_level == LinkageDepthLevel.flat_shortcut:
        reasons.append(BLOCKED_REASON_FLAT_SHORTCUT)
    elif LINKAGE_DEPTH_RANK[linkage_depth_level] < LINKAGE_DEPTH_RANK[policy.min_linkage_depth_level]:
        reasons.append(BLOCKED_REASON_REQUIRED_BRAID_DEPTH_MISSING)

    if residual_compatibility_level == ResidualCompatibilityLevel.not_evaluated:
        reasons.append(BLOCKED_REASON_RESIDUAL_NOT_EVALUATED)
    elif residual_compatibility_level in (
        ResidualCompatibilityLevel.no_typed_meet,
        ResidualCompatibilityLevel.contradiction,
    ):
        reasons.append(BLOCKED_REASON_RESIDUAL_BLOCKED)

    if REFERENTIALITY_RANK[referentiality_level] < REFERENTIALITY_RANK[policy.min_referentiality_level]:
        reasons.append(BLOCKED_REASON_REFERENTIALITY_INSUFFICIENT)

    if policy.require_formal_projection and PROJECTION_BASIS_RANK[projection_basis_level] >= PROJECTION_BASIS_RANK[ProjectionBasisLevel.unprojectable]:
        reasons.append(BLOCKED_REASON_PROJECTION_MISSING)

    if reasons:
        return ExportClass.blocked, reasons

    # Determine export class from combination of levels
    try:
        is_high_conf = (
            pnf_closure_level == PNFClosureLevel.span_receipt_closed
            and projection_basis_level == ProjectionBasisLevel.grammar_projected
            and residual_compatibility_level == ResidualCompatibilityLevel.exact
            and linkage_depth_level == LinkageDepthLevel.braid_node
            and referentiality_level == ReferentialityLevel.cross_source
        )
    except Exception:
        is_high_conf = False

    if is_high_conf:
        return ExportClass.high_confidence_exportable, []
    if not reasons:
        return ExportClass.exportable, []

    return ExportClass.blocked, reasons


# ── Build complete braid relevance receipt ─────────────────────────────────

def build_braid_relevance_receipt(
    *,
    connectedness_level: ConnectednessLevel | None = None,
    referentiality_level: ReferentialityLevel | None = None,
    depth_level: DepthLevel | None = None,
    pnf_closure_level: PNFClosureLevel | None = None,
    residual_compatibility_level: ResidualCompatibilityLevel | None = None,
    projection_basis_level: ProjectionBasisLevel | None = None,
    linkage_depth_level: LinkageDepthLevel | None = None,
    source_span_level: SourceSpanLevel | None = None,
    policy: ExportLanePolicy = DEFAULT_GWB_LANE_POLICY,
    # diagnostics
    connected_component_size: int | None = None,
    source_family_count: int | None = None,
    longest_path_len: int | None = None,
    closed_role_count: int | None = None,
    total_role_count: int | None = None,
    fallback_field_count: int | None = None,
) -> BraidRelevanceReceipt:
    c = connectedness_level or ConnectednessLevel.isolated
    rf = referentiality_level or ReferentialityLevel.single_source
    d = depth_level or DepthLevel.flat
    p = pnf_closure_level or PNFClosureLevel.open
    rc = residual_compatibility_level or ResidualCompatibilityLevel.no_typed_meet
    pb = projection_basis_level or ProjectionBasisLevel.unprojectable
    ld = linkage_depth_level or LinkageDepthLevel.flat_shortcut
    ss = source_span_level or SourceSpanLevel.missing

    export_class, reasons = classify_export_class(p, pb, rc, ld, rf, policy)

    basis_parts: list[str] = []
    if c == ConnectednessLevel.braid_connected:
        basis_parts.append("braid_position")
    if pb != ProjectionBasisLevel.unprojectable:
        basis_parts.append("projection_basis")
    if rc == ResidualCompatibilityLevel.exact or rc == ResidualCompatibilityLevel.partial:
        basis_parts.append("residual_compatibility")
    if ld != LinkageDepthLevel.flat_shortcut:
        basis_parts.append("linkage_depth")

    return BraidRelevanceReceipt(
        connectedness_level=c,
        referentiality_level=rf,
        depth_level=d,
        pnf_closure_level=p,
        residual_compatibility_level=rc,
        projection_basis_level=pb,
        linkage_depth_level=ld,
        source_span_level=ss,
        export_class=export_class,
        blocked_reasons=tuple(reasons),
        basis=tuple(basis_parts),
        connected_component_size=connected_component_size,
        source_family_count=source_family_count,
        longest_path_len=longest_path_len,
        closed_role_count=closed_role_count,
        total_role_count=total_role_count,
        fallback_field_count=fallback_field_count,
    )


def serialize_fragment_pnfs_in_rows(rows: list[dict[str, Any]]) -> None:
    """Convert FragmentPNF objects to dicts in-place on a list of source event rows.

    Mutates each row in-place so that ``row["fragment_pnfs"]`` becomes
    ``list[dict]`` (via ``FragmentPNF.to_dict()``).  Idempotent — rows that
    already hold dicts are left untouched.
    """
    for row in rows:
        fpnfs = row.get("fragment_pnfs")
        if not fpnfs or not isinstance(fpnfs, list):
            continue
        if fpnfs and not isinstance(fpnfs[0], dict):
            row["fragment_pnfs"] = [f.to_dict() for f in fpnfs]


__all__ = [
    "BLOCKED_REASON_FRAGMENT_PNF_MISSING",
    "BLOCKED_REASON_FLAT_SHORTCUT",
    "BLOCKED_REASON_LINKAGE_DEPTH_INSUFFICIENT",
    "BLOCKED_REASON_PNF_NOT_CLOSED",
    "BLOCKED_REASON_PROJECTION_MISSING",
    "BLOCKED_REASON_RECEIPT_MISSING",
    "BLOCKED_REASON_REFERENTIALITY_INSUFFICIENT",
    "BLOCKED_REASON_REQUIRED_BRAID_DEPTH_MISSING",
    "BLOCKED_REASON_RESIDUAL_BLOCKED",
    "BLOCKED_REASON_RESIDUAL_NOT_EVALUATED",
    "BLOCKED_REASON_SOURCE_SPAN_MISSING",
    "BLOCKED_REASON_TIME_NOT_BOUND",
    "BLOCKED_REASONS_STABLE",
    "BraidRelevanceReceipt",
    "CONNECTEDNESS_RANK",
    "ConnectednessLevel",
    "DEFAULT_GWB_LANE_POLICY",
    "DEPTH_RANK",
    "DepthLevel",
    "EXPORT_CLASS_RANK",
    "ExportClass",
    "ExportGateReceipt",
    "ExportLanePolicy",
    "FRAGMENT_SUBCLASSES",
    "FRAGMENT_SURFACE_CLASSES",
    "FragmentPNF",
    "GRAMMAR_TO_PREDICATE_FRAME",
    "FragmentPNFDepthReceipt",
    "FragmentPNFProjectionReceipt",
    "GrammarMatchStrength",
    "INTERNAL_REVIEW_LANE_POLICY",
    "LINKAGE_DEPTH_RANK",
    "LinkageDepthLevel",
    "PNF_CLOSURE_RANK",
    "PNFClosureLevel",
    "PROJECTION_BASIS_RANK",
    "PredicateFrame",
    "ProjectionBasisLevel",
    "REFERENTIALITY_RANK",
    "RESIDUAL_COMPATIBILITY_RANK",
    "ReferentialityLevel",
    "ResidualCompatibilityLevel",
    "serialize_fragment_pnfs_in_rows",
    "SOURCE_SPAN_RANK",
    "SourceSpanLevel",
    "SourceSpanRef",
    "TimeAnchor",
    "TypedRole",
    "build_braid_relevance_receipt",
    "classify_connectedness",
    "classify_depth",
    "classify_export_class",
    "classify_pnf_closure",
    "classify_referentiality",
    "classify_source_span",
    "projection_basis_from_fallback",
    "residual_level_to_compatibility",
]
