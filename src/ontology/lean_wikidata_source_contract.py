from __future__ import annotations

from dataclasses import dataclass


ARISTOTLE_REQUEST_ID = "ae06ae06-2580-422a-8fc3-92aeaaca8762"

SOURCE_SHA256 = {
    "RequestProject.ClassAlgebra": "6ee3b2371498d67c159fe97389c9ca1e06144ad530e17554cb3f87968c9f899a",
    "RequestProject.Rdf": "11a4d3fc6b152a022016d7c8639b89805d45352c9e08c16ec2a8172a2610f3cf",
}


@dataclass(frozen=True)
class TheoremBackedChecker:
    relation_kind: str
    module_name: str
    checker_name: str
    theorem_name: str


SOURCE_CHECKER_CONTRACTS = (
    TheoremBackedChecker(
        relation_kind="union_of",
        module_name="RequestProject.ClassAlgebra",
        checker_name="Wikidata.KB.unionOk",
        theorem_name="Wikidata.KB.isUnion_of_unionOk",
    ),
    TheoremBackedChecker(
        relation_kind="intersection_of",
        module_name="RequestProject.ClassAlgebra",
        checker_name="Wikidata.KB.interOk",
        theorem_name="Wikidata.KB.isIntersection_of_interOk",
    ),
)

SOURCE_THEOREMS_WITHOUT_BOOLEAN_CHECKER = {
    ("subclass_of", "RequestProject.Rdf", "Wikidata.Rdf.entails_iff_isSubclassOf"),
    ("rdf_entailment", "RequestProject.Rdf", "Wikidata.Rdf.entails_sound"),
    ("rdf_entailment", "RequestProject.Rdf", "Wikidata.Rdf.entails_sub_iff"),
    ("rdf_entailment", "RequestProject.Rdf", "Wikidata.Rdf.entails_inst_iff"),
}


def checker_contract_is_source_backed(
    *, relation_kind: str, module_name: str, checker_name: str, theorem_name: str
) -> bool:
    return any(
        contract.relation_kind == relation_kind
        and contract.module_name == module_name
        and contract.checker_name == checker_name
        and contract.theorem_name == theorem_name
        for contract in SOURCE_CHECKER_CONTRACTS
    )
