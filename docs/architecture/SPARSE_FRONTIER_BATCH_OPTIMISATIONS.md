# Sparse Frontier Batch Optimisations

## Migration 068

`068_complete_frontier_reduction_and_batch_indexes.sql` completes two runtime
edges after the sparse-frontier implementation in migrations 062–067.

## Complete structural reduction

The explicit compatibility reduction previously enumerated the principal
paragraph/adaptive/document kinds. The closure trigger already reduced newly
closed non-sentence regions, but an upgraded database could contain older
closed structural interfaces of another kind.

The document-level repair pass now includes every closed region except:

- kind 1: sentence/local leaf interfaces; and
- kind 9: parentless adjacent-reconciliation evidence fibres.

Reduction remains bottom-up by region kind, then region span, authored sequence
and interface identity. This prevents an older unreduced structural interface
from leaking copied interiors into the document root.

## Statement-level object-kind indexing

Migration 047 installed `semantic_pnf_object_export_kind_index` as a row
trigger. Each exported object performed an object-table lookup and an
individual lookup insert.

Migration 068 replaces it with:

```text
semantic_pnf_object_export_kind_index_batch
```

The new trigger uses `REFERENCING NEW TABLE AS inserted_export` and performs one
set-oriented `INSERT ... SELECT ... ON CONFLICT DO NOTHING` per export
statement.

This optimisation applies at sentence-local closure as well as sparse parent
closure. It does not alter export admission or semantic authority; it only
changes the physical indexing path.

## Validation

The focused sparse-frontier workflow now checks:

- all non-leaf/non-reconciliation kinds are included;
- the superseded row trigger is absent;
- the batch function and statement trigger are installed; and
- no JSON/JSONB authority is introduced.

Apply migrations through 068 before a fresh controlled benchmark.
