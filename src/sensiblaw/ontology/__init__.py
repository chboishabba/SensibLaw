"""External ontology lookup and ingestion utilities."""

from .clients import ExternalCandidate, dbpedia_search, wikidata_search
from .ingest import batch_lookup, filter_candidates, lookup_candidates, to_reference_payload

__all__ = [
    "ExternalCandidate",
    "dbpedia_search",
    "wikidata_search",
    "batch_lookup",
    "filter_candidates",
    "lookup_candidates",
    "to_reference_payload",
]
