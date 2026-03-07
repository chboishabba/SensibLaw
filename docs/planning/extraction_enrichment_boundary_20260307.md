# Extraction vs Enrichment Boundary (Deterministic)

Date: 2026-03-07
Status: active boundary note

## Purpose
Freeze one explicit contract for what is authoritative in local extraction
versus what is downstream enrichment/diagnostic support from Wikidata.

## Boundary contract
- Canonical text/token/lexeme identity is local and deterministic.
- Parser/dependency outputs (including spaCy) are local deterministic evidence
  that may support role/relation candidate extraction.
- Wikidata is downstream only:
  - reviewed identity linking (`actor_external_refs`, `concept_external_refs`)
  - bounded diagnostics over statement bundles (projection/drift/reporting)
- Wikidata must never define canonical token identity or rewrite canonical
  ontology rows by itself.

## Allowed deterministic flow
1. Canonical text and lexeme stream are produced locally.
2. Deterministic parser evidence yields role/relation candidates with receipts.
3. Candidate entities/relations may be checked/enriched using reviewed bridge
   mappings and bounded Wikidata diagnostics.
4. Canonical promotion decisions remain local-policy decisions with explicit
   receipts and abstention behavior.

## Non-goals
- No open-world entity resolution inside canonical lexer/token identity.
- No importing external class structure as authoritative legal ontology.
- No conflation of identity-link curation with ontology-diagnostic findings.

## Canonical references
- `docs/tokenizer_contract.md`
- `docs/external_ontologies.md`
- `docs/itir_vs_sl.md`
- `docs/wikidata_working_group_status.md`
