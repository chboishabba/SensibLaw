# Numeric reuse benchmark records

These files are compact, credential-free empirical records for pinned numeric
reuse fixtures. They preserve benchmark conditions and observations, not a
second receipt authority or a retained database.

`2026-08-16-v1.json` records the first fresh PostgreSQL run of
`data/benchmarks/numeric_reuse_v1`. Exact replay parity is established there;
leaf-level edit locality and same-domain work-per-token non-increase remain
open measurements.

`2026-08-17-v2.json` records the first leaf-closure audit. It is deliberately
`indeterminate`: the fixture has non-unique source anchors, and the audit does
not guess a changed-leaf correspondence. It is therefore evidence against a
locality claim, not evidence of a locality violation.
