# Zelph PNF Closure Benchmark

Zelph is an optional executor for monotone, revision-bound closure jobs. It is not a
semantic owner and is not a replacement for deterministic SensibLaw reduction.

The representative benchmark covers normalized candidate generation for:

```text
modal + polarity → obligation/prohibition/permission candidate
condition marker → condition candidate
exception marker → exception candidate
transition predicate → legal transition candidate
```

Run:

```text
uv run python scripts/benchmark_pnf_closure_backends.py \
  --output build/closure-backend-parity.json
```

When the `zelph` command is unavailable or fails, the output records
`engine_unavailable_or_failed`, leaves `adopt_backend` false, and exits without pretending
that parity was measured.

When the engine runs, the benchmark records:

```text
fact serialization time
Zelph engine time
result decoding time
total backend time
derived triples
derived proposals
Python proposal refs
Zelph proposal refs
Python reduction graph ref
Zelph reduction graph ref
```

A backend is eligible for further performance testing only when both proposal identities
and deterministic reduction identities match. This benchmark does not automatically alter
production configuration. End-to-end document timing must also improve before a rule family
may be switched.

The benchmark rule pack deliberately consumes normalized immutable facts rather than raw
text. Parsing, canonical coordinates, compatibility reduction, ambiguity preservation,
coverage barriers, fixed-point certification, Legal IR projection, and legal authority all
remain outside Zelph.
