# Nat peer-cohort Zelph wiring seam

Date: 2026-09-08

The runtime peer-cohort producer remains deliberately narrow:

```text
DomainInvariantSnapshot
+ bounded external graph observation
+ declared coverage policy / graph revision
+ candidate feature contributions
-> peer_cohort residual
```

Safety rules:

- incomplete, uninspected, or invalid coverage -> `unresolved`
- no independently reviewed trusted members -> `unresolved`
- admitted empirical peer values may produce `exact`, `partial`, or `contradictory`
- `exact` is diagnostic only and does not establish migration safety, `P5991 = P14143`, promotion, or edit authority
- absence in a partial Zelph view is not global Wikidata absence

Formal references:

- DASHI `ExternalContextSafetyBoundary.agda`
- DASHI `GovernedResidualOntologyLearning.agda`
- DASHI PR #822 `ZelphBoundedGraphCoverageExact.agda`
- DASHI PR #822 `SensibLawNatZelphPeerCohortExact.agda`
- DASHI PR #822 `AristotleRankQualifierPropertyEngineBoundary.agda`

Aristotle source-level distinction retained:

- rank-truthy item statement
- qualifier/scope-valid claim
- executable PKB derivability

are separate bounded receipts. None is source truth or migration authority.
