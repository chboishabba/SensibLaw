"""Read-only Wong 2022 paper evidence -> existing external world-model carriers.

This is an attribution-first external ontology adapter, not a second compiler.
No genetic constructs, fermentation protocol, assay optimisation or procedure.
The article is source evidence. It does not supply identity, clinical, kinetics,
or public-ontology edit authority.

Source: Wong et al. (2022), Nature Communications 13:712,
DOI 10.1038/s41467-022-28386-6.
"""

from __future__ import annotations

from src.policy.external_graph_bridge import (
    build_external_bridge_candidate,
    build_external_pressure_result,
    build_graph_view,
)
from src.policy.world_model import build_state_node, build_world_model

DOI = "10.1038/s41467-022-28386-6"
DOI_REF = f"doi:{DOI}"
PAPER_URL = f"https://doi.org/{DOI}"
VERSION_OF_RECORD = "2022-02-07"

# These are public database identifiers, not an approved specimen-matching
# or chemical equivalence certificate for a measured paper sample.
DLA_PUBCHEM_REF = "PubChem:6717"
DLA_CHEBI_REF = "CHEBI:6604"
RELATED_LSD_PUBCHEM_REF = "PubChem:5761"

_ARTICLE_SOURCE = {
    "source_ref": DOI_REF,
    "authors": (
        "Garrett Wong; Li Rong Lim; Yong Quan Tan; Maybelle Kho Go; "
        "David J. Bell; Paul S. Freemont; Wen Shan Yew"
    ),
    "venue": "Nature Communications 13:712 (2022)",
    "url": PAPER_URL,
    "version_of_record": VERSION_OF_RECORD,
    "license": "CC BY 4.0 (article; check third-party credits separately)",
}


def _reported_claim(*, key: str, label: str, location: str, value: str | None = None) -> dict:
    metadata = {
        "observation_role": "primary_author_report",
        "source_scope": "not_independently_reanalysed",
        "source_locator": location,
        "source_ref": DOI_REF,
        "scientific_truth_authority": False,
        "clinical_authority": False,
        "commercial_scale_authority": False,
    }
    if value is not None:
        metadata["reported_text"] = value
    return build_state_node(
        node_id=f"wong2022:claim:{key}",
        node_kind="claim",
        label=label,
        status="candidate",
        source_anchor_ids=[DOI_REF, f"{DOI_REF}#{location}"],
        metadata=metadata,
    )


def build_wong_2022_candidate_world() -> dict:
    """Project a fixed, incomplete, review-required article slice into SLR.

    The cited source-data workbook and supplement were not independently
    downloaded, hashed, or reanalysed. Missing bytes are an unresolved
    coverage residual, never absence of chemistry or a negative assay.
    """
    graph_id = "wong2022:graph:article-limited"
    subject_ref = "wong2022:entity:reported-d-lysergic-acid"
    graph = build_graph_view(
        graph_view_id=graph_id,
        artifact_id=DOI_REF,
        artifact_revision=f"version-of-record:{VERSION_OF_RECORD}",
        coverage_state="incomplete",
        selected_sections=(
            "article abstract",
            "article Results, Fig. 5",
            "article Results, Fig. 6",
            "article Data availability",
        ),
        selected_chunks=(
            {"source_locator": "Fig. 5", "kind": "author_reported_analytical_evidence"},
            {"source_locator": "Fig. 6", "kind": "author_reported_measurement"},
            {
                "source_locator": "Supplementary Table 12",
                "kind": "article_citation_only_not_reviewed_source_bytes",
            },
        ),
        unresolved_coverage=(
            {"kind": "unverified_source_data_file_sha256", "source": DOI_REF},
            {"kind": "unverified_supplementary_file_sha256", "source": DOI_REF},
            {"kind": "not_independently_reanalysed", "source": DOI_REF},
        ),
        source=_ARTICLE_SOURCE,
        diagnostics={
            "source_bytes_inspected": False,
            "source_digest_verified": False,
            "paper_report_is_not_external_adjudication": True,
        },
    )

    # Reuse the provider-neutral candidate bridge. Even an apparent PubChem /
    # ChEBI cross-reference is not promoted to measured-sample equivalence.
    def registry_candidate(namespace: str, external_ref: str) -> dict:
        return build_external_bridge_candidate(
            bridge_candidate_id=f"wong2022:bridge:{namespace.lower()}",
            subject_ref=subject_ref,
            subject_kind="entity",
            bridge_namespace=namespace,
            external_ref=external_ref,
            attachment_kind="authority_reference",
            graph_view_ref=graph_id,
            candidate_status="review_required",
            basis=(
                {
                    "source_ref": DOI_REF,
                    "external_record": (
                        "https://pubchem.ncbi.nlm.nih.gov/compound/6717"
                    ),
                    "relation_reading": "registry cross-reference candidate; not assay specimen identity",
                },
            ),
            residuals=(
                {
                    "kind": "unreviewed_stereochemistry_charge_sample_match",
                    "required_before": "same_entity",
                },
            ),
            adapter_id="sl.wong2022_primary_article.v1",
        )

    candidates = [
        registry_candidate("PubChem", DLA_PUBCHEM_REF),
        registry_candidate("ChEBI", DLA_CHEBI_REF),
    ]
    pressure = build_external_pressure_result(
        pressure_result_id="wong2022:pressure:source-and-identity",
        target_ref=subject_ref,
        graph_view_ref=graph_id,
        profile_id="source-revision-and-registry-review",
        outcome="abstain",
        residuals=(
            {"kind": "raw_source_data_not_reanalysed"},
            {"kind": "sample_to_registry_same_object_unpaid"},
            {"kind": "biological_flux_and_compartment_unsupported"},
            {"kind": "native_review_admission_not_completed"},
        ),
    )
    entities = [
        build_state_node(
            node_id=subject_ref,
            node_kind="molecule",
            label="D-lysergic acid (as reported by Wong et al. 2022)",
            status="candidate",
            source_anchor_ids=[DOI_REF],
            metadata={
                "paper_reported_product": True,
                "source_registry_candidate_refs": [
                    DLA_PUBCHEM_REF,
                    DLA_CHEBI_REF,
                ],
                "same_entity_as_lysergic_acid_diethylamide": False,
                "related_ligand_reference": RELATED_LSD_PUBCHEM_REF,
                "sample_registry_identity_certified": False,
            },
        )
    ]
    claims = [
        _reported_claim(
            key="pathway-report",
            label="Authors report yeast D-lysergic-acid biosynthesis",
            location="Abstract",
        ),
        _reported_claim(
            key="one-litre-titre",
            label="Authors report 1 L endpoint titre",
            location="Fig. 6; Supplementary Table 12",
            value="1.7 mg/L",
        ),
        _reported_claim(
            key="four-litre-titre",
            label="Authors report 4 L endpoint titre",
            location="Fig. 6; Supplementary Table 12",
            value="1.4 mg/L",
        ),
        _reported_claim(
            key="analytical-evidence",
            label="Authors report analytical product comparisons",
            location="Fig. 5; Supplementary Fig. 14; Supplementary Table 11",
        ),
    ]
    return build_world_model(
        model_id="wong2022:primary-article-candidate-world",
        lane_family="biochemistry_primary_literature",
        model_status="candidate",
        source_mode="source-bounded-read-only",
        entities=entities,
        claims=claims,
        external_graph_views=[graph],
        external_bridge_candidates=candidates,
        external_pressure_results=[pressure],
        residuals=[
            {"kind": "source_data_binary_not_verified", "source_ref": DOI_REF},
            {"kind": "clinical_or_pharmacological_promotion_prohibited"},
        ],
        metadata={
            "original_article_authors": _ARTICLE_SOURCE["authors"],
            "paper_doi": DOI,
            "paper_url": PAPER_URL,
            "source_artifact_sha256": None,
            "source_data_sha256": None,
            "source_digests_verified": False,
            "independent_analysis_performed": False,
            "cross_repo_formal_owner": (
                "DASHI.Biology.Wong2022EvidenceLedgerExact"
            ),
            "storage_and_review_owner": "existing SLR/SensibLaw native pipeline",
            "public_ontology_mutation_allowed": False,
            "identity_authority": False,
            "mechanism_authority": False,
            "clinical_authority": False,
        },
    )


__all__ = [
    "build_wong_2022_candidate_world",
    "DOI",
    "DLA_PUBCHEM_REF",
    "DLA_CHEBI_REF",
]
