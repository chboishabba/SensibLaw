# Judicial Decision Behavior (Descriptive) Contract

This document specifies a **descriptive-only** analytics layer for summarizing
observed decision outcomes over a corpus of judgments.

This is **not** a wrongs taxonomy. It is a taxonomy of **decision outcomes and
case features** suitable for retrospective aggregation.

## Scope
- Compute deterministic, auditable **observed outcome distributions** conditioned
  on typed case metadata and extracted predicate/features.
- Support institutional aggregation (court/jurisdiction/era/matter-type).
- Preserve the system posture: **non-authoritative, non-predictive by default**.

## Non-Goals (Hard)
- No forecasting or “probability of ruling” outputs in canonical surfaces.
- No “pro-/anti-” labels for individuals.
- No risk scoring, ranking, or recommendation (“pick judge X”).
- No hidden or passive identity resolution; all IDs must be explicit inputs.

These constraints align with `SensibLaw/docs/panopticon_refusal.md` and
`SensibLaw/docs/no_reasoning_contract.md`.

## Data Model (v0.1)

### CaseObservation
Minimum observation record required for aggregation:
- `case_id` (stable external identifier; string)
- `jurisdiction_id` (string)
- `court_id` (string)
- `court_level` (string; ex: `trial`, `intermediate_appellate`, `final_appellate`)
- `decision_date` (ISO date string; optional)
- `wrong_type_id` (string; optional)
- `predicate_keys` (list[string]; extracted/curated feature keys)
- `outcome` (enum string; see below)
- optional individual fields (guarded; see below):
  - `judge_id` (string)
  - `panel_ids` (list[string])

### OutcomeLabel
Canonical outcome labels for descriptive aggregation:
- `plaintiff`
- `defendant`
- `mixed`
- `remitted`
- `procedural`
- `unknown`

## Language Contract (UI / Reports)
This module may compute statistical summaries, but it must not be *presented* as
predictive behavior modelling.

Allowed phrasing:
- "Observed outcome distribution"
- "Posterior estimate of an underlying rate parameter (theta)"
- "Credible interval for theta"

Forbidden phrasing:
- "Probability this judge will rule for X"
- "Pro-/anti-plaintiff judge"
- "Judge risk score"

### Statistical Interpretation Guard (Mandatory)
All surfaces for this module must carry a fixed interpretation guard:
- Observed rates/posteriors are **empirical summaries of the selected corpus and
  slice definition**.
- They do **not** imply causal tendency, personal disposition, or
  counterfactual behavior under different predicate conditions.
- Comparisons across slices are meaningful only to the extent that slice filters
  and time bounds are comparable.

## Aggregation Contract

### Determinism
All aggregation outputs must be:
- order-independent w.r.t input observation ordering
- stable across Python versions supported by the repo
- emitted with a deterministic key ordering (sorted keys)

### Identity Contract
The aggregation layer does not infer identities. It consumes:
- explicit `judge_id` / `panel_ids` only when provided by a dataset

### Individual-Level Guard
Per `panopticon_refusal.md`, individual-level statistics are **disabled by
default**.

The aggregation API must require an explicit opt-in to group by:
- `judge_id`
- `panel_id`
- any other individual actor identifier

If not opted-in, the API must raise a refusal/error with an explicit reason.

### Explicit Slice Declaration (Mandatory)
Aggregation requests must declare slice intent explicitly; no silent defaults.

Each aggregation call must provide a `SliceDeclaration` object (JSON-friendly):
- `filters`: dict of filter dimensions applied (may be empty, but must exist)
- `group_by`: list of grouping keys (must match the function call `group_by`)
- `time_bounds_declared`: `{ "start": <ISO date or null>, "end": <ISO date or null> }`
- optional: `notes` (string)

The aggregation output must echo the normalized declaration under `slice`.

### Sample-Size & Time-Bounds Disclosure (Mandatory)
All outputs must include:
- `corpus.n_total` (total observations processed after normalization)
- `corpus.time_min` / `corpus.time_max` (observed min/max decision_date, if available)
- the full `slice` declaration (filters + declared time bounds + group keys)

This disclosure contract applies to **all** descriptive aggregation APIs in this
module, including:
- outcome counts (`aggregate_outcomes`)
- Beta-Binomial (`aggregate_beta_binomial`)
- Gamma-Poisson (`aggregate_gamma_poisson`)
- ridge-logistic association (`aggregate_ridge_logistic_map`)
- lognormal tail fitting (`aggregate_lognormal_tail`)

## Outputs (Read-Only)
Outputs are descriptive summaries only:
- counts per outcome
- observed rates per outcome (derived from counts)

No predictive interpretation is emitted.

## Bayesian Estimation (Descriptive)
Bayesian models may be used **only** as descriptive estimation of an underlying
rate parameter (theta) conditional on a slice.

### v0.1 Canonical Model: Beta-Binomial
For a binary target (e.g. `outcome == plaintiff`), let:
- `y` = number of target outcomes in the slice
- `n` = number of cases in the slice
- `theta` = underlying rate parameter for the slice

Model:
- `y ~ Binomial(n, theta)`
- `theta ~ Beta(alpha0, beta0)`
- `theta | data ~ Beta(alpha0 + y, beta0 + (n - y))`

### Empirical-Bayes Prior (Shrinkage)
When enabled, `alpha0,beta0` are derived deterministically from a baseline pool:
- baseline mean `mu` (observed rate in baseline pool)
- prior strength `kappa` (equivalent sample size; configured)
- `alpha0 = mu * kappa`
- `beta0 = (1 - mu) * kappa`

This produces shrinkage toward the baseline pool for small-`n` slices without
claiming prediction.

### Credible Intervals
If credible intervals are emitted, they must be computed deterministically (no
random sampling) and documented with the exact quantiles used (e.g. 10%/90%).

## Rare Event Counts (Optional; Descriptive)
For rare count events (e.g. "exemplary damages awarded"), the descriptive layer
may use Poisson-family count models.

### v0.1 Count Model: Gamma-Poisson (Conjugate)
Let:
- `y` = number of rare events observed in the slice
- `E` = exposure (default: number of cases in slice)
- `lambda` = underlying event rate per exposure unit

Model:
- `y ~ Poisson(lambda * E)`
- `lambda ~ Gamma(alpha0, beta0)` (shape/rate parameterization)
- `lambda | data ~ Gamma(alpha0 + y, beta0 + E)`

As with Beta-Binomial, the prior may be empirical-Bayes with a baseline pool:
- baseline rate `mu = y_base / E_base`
- strength `kappa`
- `alpha0 = mu * kappa`
- `beta0 = kappa`

If credible intervals are emitted, they must be computed deterministically by
inverting the Gamma CDF (no random sampling).

## Rare Binary Outcomes (Optional; Descriptive Association)
Rare binary outcomes can be modeled with logistic-family association models, but
canonical surfaces must not emit per-person predictions or “probability of ruling”.

### v0.1 Association Model: Ridge-Logistic MAP (Deterministic)
This provides a deterministic MAP estimate for coefficients under a Gaussian
prior (L2 penalty). It is used to summarize association structure, not to score
individuals.

Outputs are limited to:
- coefficient estimates (MAP)
- deterministic uncertainty proxy (inverse Hessian / standard errors), optional

No prediction API is part of the canonical contract.

## Damages / Heavy Tails (Optional; Descriptive)
Continuous outcomes (e.g. damages) often exhibit heavy tails. v0.1 supports
descriptive log-scale fitting (e.g. lognormal parameter estimation). Full EVT
POT/GPD fitting is out of scope unless introduced with a new contract version.

### v0.1 Tail Helper: Lognormal Fit (Deterministic)
If a lognormal tail fit is computed, it must:
- require an explicit `SliceDeclaration` (no silent defaults)
- include `corpus` disclosure fields (`n_total`, `time_min`, `time_max`)
- emit parameters and derived tail summaries only (no per-person predictions)

## Storage Schema (Optional)
If persisted storage is needed, use typed `case_feature` rows with evidence span
offsets to preserve auditability.

Any storage schema must:
- be versioned (feature schema ID/version)
- preserve evidence spans (`start/end` offsets + source reference)
- treat derived stats tables as rebuildable caches

## Integration Boundaries
- This module is not part of canonical obligation / wrongdoing reasoning.
- It must not modify or influence AAO extraction outputs.
- Any UI display must be clearly labeled “observed distributions (descriptive)”.

## Source Trace
- Chat context: `698f16cb-5408-83a0-8228-303eea59b417` (rare-event modeling note: 3A/3B/3C)
