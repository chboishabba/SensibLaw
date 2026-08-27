# Native delta execution timing

The reusable delta-fed execution shape is:

```text
DeltaSource
-> ProjectionAtoms
-> AffectedKeys
-> LocalReducer
-> AuthorityPublication
```

`src/runtime/delta_execution_timing.py` supplies opt-in monotonic nanosecond
measurements for those stages.  It is execution observability only.

Timing never participates in semantic identity, authority digests, admissibility,
parity, candidate membership, or publication identity.  Enabling timing must not
change a reducer's semantic inputs or outputs.

Enable the fine-grained ledger with:

```text
SENSIBLAW_NATIVE_DELTA_TIMING=1
```

The default is disabled so detailed observability does not become an ordinary
production tax.  Existing coarse parser/post-parser occupancy measurements in
`streaming_spacy_execution.py` remain the acceptance clock.  Fine-grained delta
timing explains the post-parser occupancy; it does not replace or reconstruct it.

The relationship is therefore:

```text
accepted_metric_ledger
  owns parser/post-parser monotonic occupancy and the acceptance ratio

DeltaExecutionTimingLedger
  attributes measured post-parser work to reusable delta/reducer owners
```

Each observation may carry:

- stage;
- owner reference;
- affected fibre reference;
- elapsed monotonic nanoseconds;
- input semantic work units;
- output semantic work units.

Stage totals identify which reusable execution layer is expensive.  Owner totals
identify which domain reducer owns that cost.  Fibre references permit workload
normalisation and skew analysis without promoting timing into semantic authority.

For the immediate production milestone, measurements should support the direct
budget:

```text
T_source_to_authority <= 1.5 * T_spaCy
```

while preserving the stronger repository target:

```text
T_post_parser <= 0.10 * T_spaCy
```

Both sides of parser-relative claims must remain directly measured.  Fine-grained
stage totals must never be used to synthesize a missing parser or post-parser
occupancy by subtraction.

The intended optimisation loop is:

```text
measure coarse parser/post-parser occupancy
-> attribute post-parser occupancy to delta stages/owners
-> rank by absolute wall exposure
-> remove unnecessary work first
-> make remaining work delta-local
-> only then vectorise/parallelise measured kernels
-> rerun semantic parity and performance gates separately
```
