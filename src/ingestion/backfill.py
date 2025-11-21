from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from src.ingestion.anchors import AnchorResult, NormalizedOntologyStore
from src.models.document import Document
from src.models.provision import Provision, RuleAtom


@dataclass(frozen=True)
class BackfillSummary:
    """Summary of a backfill run for reporting."""

    documents_processed: int
    rules_migrated: int
    legal_sources_created: int


def _extract_rule_atoms(document: Document) -> List[RuleAtom]:
    atoms: List[RuleAtom] = []
    for provision in getattr(document, "provisions", []):
        if isinstance(provision, Provision):
            atoms.extend(list(provision.rule_atoms))
    legacy_atoms = getattr(document, "rule_atoms", None)
    if isinstance(legacy_atoms, Iterable):
        atoms.extend([atom for atom in legacy_atoms if isinstance(atom, RuleAtom)])
    return atoms


def backfill_documents(
    documents: Sequence[Document],
    *,
    db_path: Path,
    default_category: Optional[str] = None,
) -> BackfillSummary:
    """Migrate legacy rule atoms/documents into the normalized ontology tables."""

    legal_source_count = 0
    rule_count = 0
    with NormalizedOntologyStore(db_path) as store:
        for document in documents:
            atoms = _extract_rule_atoms(document)
            if not atoms:
                continue
            store.upsert_legal_source(document, category=default_category)
            legal_source_count += 1
            results: List[AnchorResult] = store.anchor_rule_atoms(
                document, atoms, category=default_category
            )
            rule_count += len(results)
    return BackfillSummary(
        documents_processed=len(documents),
        rules_migrated=rule_count,
        legal_sources_created=legal_source_count,
    )


__all__ = ["BackfillSummary", "backfill_documents"]
