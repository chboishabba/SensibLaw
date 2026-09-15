"""Canonical progressive-reading specimen for the Mabo proof-graph lane.

This module is a projection contract over existing reviewed SensibLaw objects.
It does not parse text, decide legal truth, or turn Wiki/Wikidata navigation
into legal authority.  Its purpose is to retain enough typed coordinates for a
reader to move reversibly from a bounded lay explanation to source/proof
inspection without creating a second semantic graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.pnf.mabo_legal_proof_graph_specimen import MABO_FIXTURE_SOURCE_PATH


MABO_WIKIDATA_QID = "Q1501525"


class LegalChangeKind(str, Enum):
    REJECTED = "rejected"
    QUALIFIED = "qualified"
    DISTINGUISHED = "distinguished"
    OVERRULED = "overruled"
    DISPLACED = "displaced"
    REINTERPRETED = "reinterpreted"
    LEFT_OPEN = "left_open"


class ProofRole(str, Enum):
    SUPPORT = "support"
    DEFEATER = "defeater"
    COMPARATOR = "comparator"
    RESIDUAL = "residual"


class ReadingDepth(str, Enum):
    READ = "read"
    INSPECT = "inspect"
    TRACE = "trace"
    PROVE = "prove"


class PNFReadingQuestion(str, Enum):
    WHO_DID_IT = "who_did_it"
    WHAT_HAPPENED = "what_happened"
    TO_WHAT = "to_what"
    HOW_CERTAIN = "how_certain"
    ASSERTED_OR_QUOTED = "asserted_or_quoted"
    WHEN = "when"
    WHO_DOES_THIS_REFER_TO = "who_does_this_refer_to"


class TranslationLossKind(str, Enum):
    ASPECT = "aspect"
    EVIDENTIALITY = "evidentiality"
    MODALITY = "modality"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class InspectableHandle:
    identity_ref: str
    source_ref: str
    span_ref: str
    proof_ref: str
    provenance_ref: str
    lazy_expansion: bool = True


@dataclass(frozen=True, slots=True)
class SourceIdentityStrip:
    title: str
    court_or_instrument: str
    year: int
    source_role: str
    wikidata_qid: str
    wikipedia_available: bool
    materialisation_state: str
    verified_source_ref: str
    wikidata_identity_is_legal_authority: bool = False
    wikipedia_is_primary_authority: bool = False
    full_primary_source_required_for_payment: bool = True


@dataclass(frozen=True, slots=True)
class MultilingualSurface:
    language: str
    text: str
    qid: str
    qid_identity_paid: bool
    semantic_equivalence_paid: bool
    role_carrier_compatible: bool
    translation_losses: tuple[TranslationLossKind, ...] = ()


@dataclass(frozen=True, slots=True)
class PNFReadingLens:
    """Pedagogical projection of existing PNF roles; never a new parser."""

    role_projection_claims_truth: bool = False

    def answer_role(self, question: PNFReadingQuestion) -> str:
        return {
            PNFReadingQuestion.WHO_DID_IT: "actor",
            PNFReadingQuestion.WHAT_HAPPENED: "predicate",
            PNFReadingQuestion.TO_WHAT: "patient",
            PNFReadingQuestion.HOW_CERTAIN: "modality",
            PNFReadingQuestion.ASSERTED_OR_QUOTED: "attribution",
            PNFReadingQuestion.WHEN: "temporal",
            PNFReadingQuestion.WHO_DOES_THIS_REFER_TO: "coreference",
        }[question]

    def align_surface(self, surface: MultilingualSurface) -> MultilingualSurface:
        """Retain an already-reviewed multilingual carrier without upgrading it.

        QID identity and role-carrier compatibility are deliberately orthogonal
        to semantic equivalence.  Translation losses stay explicit.
        """

        return surface


@dataclass(frozen=True, slots=True)
class ReadingConeNode:
    role: str
    title: str
    explanation: str
    handle: InspectableHandle


@dataclass(frozen=True, slots=True)
class MaboProofLink:
    source_ref: str
    target_ref: str
    role: ProofRole


@dataclass(frozen=True, slots=True)
class MaboProofSpecimen:
    schema_version: str
    literal_formulation: str
    inferred_issue: str
    change_kind: LegalChangeKind
    nodes: tuple[ReadingConeNode, ...]
    links: tuple[MaboProofLink, ...]
    source_identity: SourceIdentityStrip
    reading_lens: PNFReadingLens
    world_truth_claimed: bool
    legal_conclusion_claimed: bool
    progressive_disclosure_mutates_proof_state: bool


@dataclass(frozen=True, slots=True)
class ReadingProjection:
    depth: ReadingDepth
    visible_nodes: tuple[ReadingConeNode, ...]
    internal_ids_visible: bool
    proof_graph_visible: bool
    context_navigation_visible: bool
    hidden_information_discarded: bool
    semantic_state_mutated: bool


def _handle(identity: str, source: str, span: str, proof: str) -> InspectableHandle:
    return InspectableHandle(
        identity_ref=identity,
        source_ref=source,
        span_ref=span,
        proof_ref=proof,
        provenance_ref=f"provenance:{source}",
    )


def build_flagship_mabo_proof_specimen() -> MaboProofSpecimen:
    """Build the bounded five-node reader specimen.

    This is intentionally a read-model specimen.  The repository's short Mabo
    fixture and statutory-preamble alignment orient the graph, but do not stand
    in for the verified full High Court source required to pay a strict
    primary-authority obligation.
    """

    source = "source:mabo-fixture-summary"
    primary = "source:mabo-no2-primary:required"
    nodes = (
        ReadingConeNode(
            role="challenged_premise",
            title="The challenged premise",
            explanation="A prior legal account treated acquisition of sovereignty as incompatible with surviving native title.",
            handle=_handle("concept:challenged-premise", source, "span:premise", "proof:premise"),
        ),
        ReadingConeNode(
            role="historical_input",
            title="Historical/common-law input",
            explanation="The reader can inspect the historical and common-law propositions on which that account depended.",
            handle=_handle("concept:historical-input", source, "span:historical-input", "proof:historical-input"),
        ),
        ReadingConeNode(
            role="authority_proposition",
            title="What Mabo changed",
            explanation="The reviewed fixture records recognition of native title and rejection of the terra-nullius doctrine; exact legal payment still requires the full primary judgment and passage.",
            handle=_handle(MABO_WIKIDATA_QID, primary, "span:primary-authority-required", "proof:mabo-change"),
        ),
        ReadingConeNode(
            role="immediate_implication",
            title="Immediate implication",
            explanation="Recognition makes continued Indigenous rights a live common-law question rather than excluding them at the threshold.",
            handle=_handle("concept:native-title-implication", primary, "span:implication-required", "proof:implication"),
        ),
        ReadingConeNode(
            role="downstream_application",
            title="Later law/application",
            explanation="Later legislation and cases can be traced as downstream applications without being collapsed into the Mabo holding itself.",
            handle=_handle("concept:downstream-application", "source:native-title-act-preamble", "span:downstream", "proof:downstream"),
        ),
    )

    return MaboProofSpecimen(
        schema_version="sl.mabo_proof_specimen.v0_1",
        literal_formulation=(
            "The High Court recognised native title in Australia and rejected "
            "the doctrine of terra nullius."
        ),
        inferred_issue=(
            "Whether the prior common-law account excluded recognition of "
            "surviving native title after acquisition of sovereignty."
        ),
        change_kind=LegalChangeKind.REJECTED,
        nodes=nodes,
        links=(
            MaboProofLink(nodes[1].handle.proof_ref, nodes[2].handle.proof_ref, ProofRole.SUPPORT),
            MaboProofLink(nodes[2].handle.proof_ref, nodes[4].handle.proof_ref, ProofRole.COMPARATOR),
            MaboProofLink(nodes[2].handle.proof_ref, "residual:full-primary-authority", ProofRole.RESIDUAL),
        ),
        source_identity=SourceIdentityStrip(
            title="Mabo v Queensland (No 2)",
            court_or_instrument="High Court of Australia",
            year=1992,
            source_role="primary_legal_source_target",
            wikidata_qid=MABO_WIKIDATA_QID,
            wikipedia_available=True,
            materialisation_state="skeleton_plus_reference",
            verified_source_ref=MABO_FIXTURE_SOURCE_PATH,
        ),
        reading_lens=PNFReadingLens(),
        world_truth_claimed=False,
        legal_conclusion_claimed=False,
        progressive_disclosure_mutates_proof_state=False,
    )


def minimum_adequate_projection(
    specimen: MaboProofSpecimen,
    depth: ReadingDepth,
) -> ReadingProjection:
    """Project visibility only; never mutate the canonical specimen."""

    if depth is ReadingDepth.READ:
        return ReadingProjection(
            depth=depth,
            visible_nodes=specimen.nodes,
            internal_ids_visible=False,
            proof_graph_visible=False,
            context_navigation_visible=False,
            hidden_information_discarded=False,
            semantic_state_mutated=False,
        )
    if depth is ReadingDepth.INSPECT:
        return ReadingProjection(
            depth=depth,
            visible_nodes=specimen.nodes,
            internal_ids_visible=False,
            proof_graph_visible=False,
            context_navigation_visible=True,
            hidden_information_discarded=False,
            semantic_state_mutated=False,
        )
    if depth is ReadingDepth.TRACE:
        return ReadingProjection(
            depth=depth,
            visible_nodes=specimen.nodes,
            internal_ids_visible=False,
            proof_graph_visible=True,
            context_navigation_visible=True,
            hidden_information_discarded=False,
            semantic_state_mutated=False,
        )
    return ReadingProjection(
        depth=depth,
        visible_nodes=specimen.nodes,
        internal_ids_visible=True,
        proof_graph_visible=True,
        context_navigation_visible=True,
        hidden_information_discarded=False,
        semantic_state_mutated=False,
    )


__all__ = [
    "InspectableHandle",
    "LegalChangeKind",
    "MABO_WIKIDATA_QID",
    "MaboProofLink",
    "MaboProofSpecimen",
    "MultilingualSurface",
    "PNFReadingLens",
    "PNFReadingQuestion",
    "ProofRole",
    "ReadingConeNode",
    "ReadingDepth",
    "ReadingProjection",
    "SourceIdentityStrip",
    "TranslationLossKind",
    "build_flagship_mabo_proof_specimen",
    "minimum_adequate_projection",
]
