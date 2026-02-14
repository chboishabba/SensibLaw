# Feature Schema: US Executive Foreign Policy (Iraq) v1

This document defines a **typed, auditable predicate feature schema** for
foreign-policy “Iraq decision tree” action episodes (US federal executive).

It is a **schema** only: it does not contain extraction rules, linkage logic,
or interpretations. Features are intended to be populated from sources with
evidence spans and provenance.

## Schema Identity
- `schema_name`: `us_exec_foreign_policy_iraq`
- `schema_version`: `1`

## Feature Keys (v1)

### A) Legal Authority Claims
- `legal.auth.congressional_authorization_claimed` (bool)
- `legal.auth.aumf_2002_invoked` (bool)
- `legal.auth.unsc_resolution_invoked` (bool)
- `legal.auth.inherent_article_ii_claimed` (bool)
- `legal.auth.collective_self_defense_invoked` (bool)
- `legal.auth.preemptive_self_defense_invoked` (bool)
- `legal.auth.domestic_statute_cited` (set[string])

### B) Emergency Framing / Threat Characterization
- `ctx.emergency.post_911` (bool)
- `ctx.threat.wmd_claimed` (bool)
- `ctx.threat.imminent` (bool)
- `ctx.threat.link_to_terror` (bool)
- `ctx.threat.humanitarian` (bool)
- `ctx.threat.regime_change_explicit` (bool)

### C) Anticipated Duration / Scope Framing
- `ctx.duration.short_term_claimed` (bool)
- `ctx.duration.open_ended` (bool)
- `ctx.scope.limited_strike` (bool)
- `ctx.scope.full_scale_invasion` (bool)
- `ctx.scope.occupation_expected` (bool)
- `ctx.scope.reconstruction_planned` (bool)

### D) Coalition / Multilateral Context
- `ctx.coalition.multinational` (bool)
- `ctx.coalition.un_backed` (bool)
- `ctx.coalition.bilateral_only` (bool)

### E) Constraint Context (descriptive tags; not excuses)
- `ctx.constraint.congressional_pressure` (bool)
- `ctx.constraint.intelligence_consensus_claimed` (bool)
- `ctx.constraint.security_council_deadlock` (bool)
- `ctx.constraint.domestic_political_pressure` (bool)

### F) Operational Escalation Indicators
- `op.escalation.troop_increase` (bool)
- `op.escalation.long_term_basing` (bool)
- `op.deescalation.troop_withdrawal` (bool)
- `op.governance.administrative_authority_established` (bool)

### G) Commitment Interaction Features (link-level helpers)
- `commitment.conditional_trigger_met` (bool)
- `commitment.temporally_active` (bool)
- `commitment.superseded` (bool)

### H) Outcome-Level Features
- `outcome.force_authorized` (bool)
- `outcome.force_commenced` (bool)
- `outcome.occupation_established` (bool)
- `outcome.escalation` (bool)
- `outcome.deescalation` (bool)

## Notes
- Features are **typed** and must be stored with evidence spans at ingestion
  time (outside this schema doc).
- Keys are intentionally namespaced to keep collisions unlikely across future
  foreign-policy slices.

