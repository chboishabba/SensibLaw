# User Stories (Work/Home, Legal/Therapeutic Boundaries)

Purpose: capture day-in-the-life narratives that pressure-test ITIR/SensibLaw
invariants without collapsing epistemic boundaries. These are **stories**, not
requirements; they must align with the doctrine: explicit status, no silent
promotion, and visible absences.

Implementation status is tracked separately in
`docs/planning/user_story_implementation_coverage_20260326.md` so this file
does not imply that every story already has product-grade code behind it.

## Persona 1 — Lawyer

Profile:
- Senior litigation lawyer.
- High interruption rate, high consequence of factual drift.
- Uses SensibLaw at work; uses ITIR/TiRCorder at home (no corpus access).

### At Work (court + chambers)
Morning case preparation:
- Reviews provisions/principles in SensibLaw.
- SB records review activity and tool envelopes (search, extract, annotate).
- ITIR ingests references only; no summaries, no semantic rewriting.
- When a known authority must be checked, retrieval stays inside repo-owned
  authority seams (`AustLII` explicit URL or deterministic neutral-citation
  resolution for known cases, `JADE` exact MNC when authorized, bounded
  `AustLII SINO` only when discovery is still required), and paragraph work
  happens locally on the fetched artifact.
- If the operator starts from free text instead of a concrete URL/citation,
  `jade-search` is a secondary best-effort selection seam; exact `jade-fetch`
  and explicit AustLII fetch remain the stable core.
- Invariant: SB never claims meaning or strength of argument.
- Forbidden: ad hoc site probing or repeated live retries outside the bounded
  source contracts.
- Failure prevented: unreproducible authority lookup, source-policy drift, and
  hidden overuse of public legal-host endpoints.

Midday drafting:
- Dictates/edits arguments.
- TiRCorder captures raw speech; SB records session structure.
- ITIR preserves divergent trajectories as hypotheses; no collapse.
- Invariant: disagreement and backtracking are preserved, not corrected.

Afternoon client meeting:
- Client instructions are recorded as **commitments (external)** with provenance.
- SB does not interpret or reconcile contradictions.
- Invariant: declared intent is recorded without inference.

End-of-day review:
- Daily brief shows timeline, unresolved threads, absences.
- No “progress” judgments or prioritization.
- Invariant: “what happened” only.

### Authority Follow from Cited Material
As a lawyer or legal operator working from a pleading, judgment extract,
benchbook paragraph, or transcript that mentions a concrete legal authority, I
want the system to follow that cited authority through repo-owned source seams,
ingest the fetched authority as a bounded source receipt, and keep the follow
chain visible so I can move from cited section to primary material without
copy-paste searching or hidden authority drift.

Typical flow:
- Operator starts from material already in the corpus that contains a concrete
  authority cue such as a neutral citation, explicit AustLII URL, or known
  JADE citation.
- The system resolves that authority through the bounded repo-owned order:
  known local/already-ingested artifact if present, direct known-authority
  fetch when citation/URL is concrete, then bounded discovery only when needed.
- The fetched authority is ingested with provenance, selected paragraph windows
  remain inspectable locally, and any unresolved follow remains explicit.

Preferences:
- One obvious path from cited authority mention to fetched source receipt.
- Bounded follow behavior with visible abstention instead of repeated silent
  retries.
- Clear distinction between a cited authority hint, a fetched authority
  artifact, and any later semantic use of that authority.

Requirements:
- Citation-like text must not silently become authority unless it passes
  through the repo-owned follow/ingest seams.
- The follow chain must preserve provenance, bounded source selection, and
  unresolved status.
- Discovery/follow behavior must remain citation-driven and source-contract
  bounded, not open-ended crawling.

Acceptance criteria:
- A concrete legal citation can be turned into a bounded authority fetch/ingest
  receipt through repo-owned seams.
- Followed authority material is queryable as an ingested source/receipt rather
  than only a transient operator fetch.
- Unresolved or non-exact matches remain explicit and do not silently promote
  into authority.
- Normal semantic/runtime lanes may consume these receipts only through an
  explicit documented path; a parser seeing cite-like text alone is not enough
  to auto-promote authority.

### Cross-Source Follow / Review Parity
As an operator moving between AU, transcript, affidavit, chat, Messenger, and
other source families, I want the next bounded action to appear in a shared
control-plane shape so I do not have to relearn a different queue grammar for
every corpus.

Typical flow:
- A source family emits a hint, receipt, or structured substrate that is not
  yet enough to close the work.
- The system turns that into a bounded conjecture and operator queue item using
  the same portable fields across lanes.
- The lane may still carry source-specific detail, but the operator can always
  read the same core questions: what is the item, what route does it suggest,
  and what is its current resolution status.

Preferences:
- Shared queue grammar across source families.
- Portable route-target / resolution vocabulary.
- Extra lane-specific detail only after the portable minimum shape is visible.

Requirements:
- Cross-source parity should live at the control-plane layer, not by forcing
  identical domain predicates or identical fetch logic.
- `route_target` and `resolution_status` remain workflow metadata, not semantic
  truth.
- Portable queue fields must remain available even when a lane adds richer
  source-specific context.

Acceptance criteria:
- At least two distinct source-family queues share one documented portable
  contract.
- UI/workbench surfaces can render those queues generically from the shared
  control-plane fields.
- Future source families can join the same contract without another lane-
  specific UI rewrite.

### At Home (evening/weekend)
- No SensibLaw corpus access.
- TiRCorder captures personal speculation.
- SB/ITIR stores hypotheses explicitly labeled as such.
- Invariant: private speculation never becomes professional commitment.

## Persona 2 — Psychologist

Profile:
- Clinical psychologist working with high-risk material.
- Extremely sensitive to narrative drift and suggestion effects.
- Uses SensibLaw for ethics/obligations at work; ITIR/TiRCorder at home.

### At Work (clinical setting)
Session:
- TiRCorder captures therapist reflections and uncertainty.
- SB records session boundaries, pauses, and interruptions.
- ITIR preserves conflicting accounts without resolution.
- Invariant: no diagnosis inference; no story compression.

After-session reflection:
- Competing hypotheses recorded as hypotheses with explicit status.
- ITIR may surface contradictions but never resolves truth.
- Invariant: uncertainty remains explicit.

Supervision/documentation:
- SensibLaw consulted for reporting/consent obligations.
- SB records which rules were consulted, when.
- Invariant: no advice generation; references only.

### At Home
- Personal reflections are recorded as hypotheses (private).
- Later review distinguishes personal reflection from clinical observation.
- Invariant: home context never leaks into professional commitments.

## Shared boundary rules (non-negotiable)
- Sequence is preserved; order matters more than interpretation.
- Epistemic status is explicit (hypothesis/intention/projection/commitment).
- Absence is visible and queryable; no silent fill-in.
- Context boundaries are enforced (home/work, private/professional).
- No automatic promotion; commitments require explicit action and receipts.

## Why this matters
Both professions cannot afford silent drift. SB/ITIR exists to ensure:
- memory does not lie
- speculation does not become authority
- context does not leak across domains

## Additional roles (stress tests)

### Banker (institutional risk)
- Work: execution envelopes capture model runs, versions, declared intent, and host/toolchain.
- Home: private risk concerns remain hypotheses; no promotion into work commitments.
- Failure prevented: hindsight laundering and retroactive certainty.

### CEO (strategy under ambiguity)
- Work: pivots and unresolved threads preserved without narrative overwrite.
- Home: speculative thoughts remain hypotheses.
- Failure prevented: false inevitability and post-hoc rationalization.

### Middle manager (coordination pressure)
- Work: meetings yield commitments only when explicit; absences are recorded.
- Home: stress reflections remain private hypotheses.
- Failure prevented: responsibility inversion and gaslighting.

### Removalist (sequence + safety)
- Work: instruction changes and task sequencing preserved; no blame inference.
- Home: fatigue markers remain non-authoritative.
- Failure prevented: blame without context.

### Barista (tempo + interruptions)
- Work: rush periods and equipment issues recorded; no personal judgment.
- Failure prevented: misattribution of fault.

### Barrister (forensic reasoning)
- Work: argument chains preserved as hypotheses vs commitments.
- Home: rehearsals remain private hypotheses.
- Failure prevented: mixing rehearsal with evidence.

### Air force pilot (life-critical)
- Work: training vs live runs separated; deviations recorded without inference.
- Home: reflection never merges with operational commitments.
- Failure prevented: training/live confusion.

### Mechanic (diagnosis under uncertainty)
- Work: tests and parts replaced recorded in sequence.
- Home: tentative diagnosis remains hypothesis.
- Failure prevented: cargo-cult repairs and overconfidence.

### Public figure (Zohran Mamdani — campaign to office)
- Context envelopes on interviews/speeches/jokes: framing, audience, and medium recorded; no decontextualized excerpts by default.
- Role-separated views (personal/campaign/office) with no automatic merge; commitments only when explicit.
- ITIR surfaces context drift warnings when clips leave original audience or time window.
- Failure prevented: identity flattening, narrative laundering, and misclassification of role-bound statements.

## Organization-level narratives (admins, teams, regulators)

These extend the individual stories with **team/admin/org** perspectives. The
rules are fixed: individuals own intent, orgs own commitments, aggregates never
overwrite individual timelines, and admins cannot “clean up” history.

### Banker → Bank → Regulators
- Team view: exploratory runs vs committee-approved commitments are distinct.
- Admin view: envelopes, model versions, declared commitments, timestamps only.
- Forbidden: reclassifying exploration as approval; collapsing dissent.
- Failure prevented: retrospective laundering and scapegoating.

### CEO → Exec Team → Board
- Team view: pivots, unresolved tensions, and decision gaps are preserved.
- Board view: commitment timelines and dependency chains only.
- Forbidden: converting private speculation into official direction.
- Failure prevented: strategy myth-making and narrative overwrite.

### Crypto founder / product lead → Team → Partners
- Founder view: sees where the product is strong, where it is still
  narrative-first, and which capabilities remain hypothesis-level rather than
  infrastructure-grade commitments.
- Team view: separates market claims, technical blind spots, and roadmap
  probes; unresolved architecture questions stay unresolved.
- Partner view: shared materials describe exact strengths, gaps, and interface
  contracts; no “platform maturity” inflation.
- Forbidden: pitch-deck certainty, silent collapse of prototype behavior into
  production guarantees, or hiding stage/risk signals.
- Failure prevented: premature institutional positioning and product-category
  confusion.

### Crypto research / diligence analyst → Desk → Investment Committee
- Analyst view: chain claims, protocol narratives, and market/regulatory
  summaries remain linked to sources, timestamps, and explicit unknowns.
- Desk view: theoretical TPS, sustainable TPS, state growth, node requirements,
  validator economics, and governance concentration stay separable.
- Committee view: board-safe summaries expose exclusions, freshness windows,
  and unresolved diligence gaps.
- Forbidden: letting narrative coherence substitute for technical depth or
  presenting chain marketing claims as settled fact.
- Failure prevented: research theater, infra-blind investment memos, and
  hindsight-laundered diligence.

### Institutional investor → Investment Team → IC / clients
- Investor view: can ask whether a token appears compliant in a named
  jurisdiction and get a source-backed review queue rather than a yes/no
  oracle.
- Team view: token function, issuance structure, rights, cashflow exposure,
  derivative/security/stablecoin/payment-token hypotheses, and explicit
  unknowns remain separable.
- IC/client view: receives an industry-grade report with provenance, legal
  scope, freshness window, and a declared list of what was not determined.
- Forbidden: binary compliance labels without jurisdiction/date scope, or
  treating candidate legal characterizations as settled classification.
- Failure prevented: board/client misuse of provisional legal analysis and
  false comfort from overcompressed token summaries.

### Token classification analyst → Research / legal → Decision maker
- Analyst view: answers “what is the coin, what does it do, what rights or
  exposures attach to it, and what category hypotheses are in play.”
- Research/legal view: protocol utility, governance role, fee rights, collateral
  structure, synthetic exposure, and derivative-like behavior are mapped with
  source receipts.
- Decision-maker view: sees a bounded classification surface that distinguishes
  description, function, and legal characterization.
- Forbidden: collapsing utility description into legal status, or hiding
  contested features because the narrative summary reads better.
- Failure prevented: category confusion between product description, market
  narrative, and legal treatment.

### Compliance / policy / regtech analyst → Compliance Team → Regulator / Auditor
- Analyst view: ASIC/AUSTRAC/licensing/tax/AML references are jurisdiction- and
  date-scoped with explicit provenance.
- Team view: policy shifts, obligation deltas, and consultation windows are
  tracked as timelines rather than free-text summaries.
- Regulator/auditor view: exports show exact sources, retrieval windows, and
  what the system did not evaluate.
- Forbidden: stale guidance presented as live advice, or compliance posture
  claimed without source receipts.
- Failure prevented: executive-safe but unverifiable compliance summaries and
  regulatory overclaim.

### Regulatory applicability mapper → Policy team → Counsel / compliance
- Analyst view: can ask which guides, statutes, rulings, and tax materials are
  potentially applicable to a token/product/activity and get a bounded list
  with reasons and exclusions.
- Policy team view: Corporations Act, tax acts/rulings, AML/CTF guidance,
  licensing guidance, and agency materials stay distinct by jurisdiction,
  hierarchy, and effective date.
- Counsel/compliance view: receives an applicability map that shows why a
  source may matter, how strongly it applies, and where the boundaries are.
- Forbidden: flattening all legal materials into one “regulatory guide” layer,
  or implying statutory applicability without jurisdiction/scope checks.
- Failure prevented: missed obligations, overbroad legal mapping, and unusable
  statute-guide bundles.

### Exchange / wallet risk operator → Risk Team → Exec / Regulator
- Operator view: candidate harm patterns, money-flow anomalies, fraud/manip,
  predatory lending, and unusual relationship-level behaviors are visible as
  review queues with provenance.
- Team view: product/cohort/time-window patterns can be compared without
  collapsing hypotheses into accusations.
- Exec/regulator view: risk concentration, affected cohorts, and obligation
  triggers are explainable and exportable.
- Forbidden: black-box risk scoring, silent escalation from candidate pattern
  to allegation, or raw anomaly counts without loss/coverage markers.
- Failure prevented: opaque abuse detection, false certainty, and unusable
  regulator-facing risk reports.

### Market stress / bad-day reviewer → Risk desk → Exec / clients
- Reviewer view: “bad day” indicators stay decomposed into market moves,
  liquidity stress, liquidations, outages, stablecoin dislocations, regulatory
  events, and correlation shifts.
- Desk view: correlations are time-windowed, source-scoped, and explicitly
  labeled as observed co-movement rather than causal proof.
- Exec/client view: receives stress reports that explain what moved together,
  what diverged, and what data was missing.
- Forbidden: causal storytelling from correlation alone, or hiding the time
  window / benchmark choice behind a single stress score.
- Failure prevented: panic dashboards, fake macro coherence, and post-hoc
  market mythology.

### Executive / client report consumer → Coverage team → board / client
- Consumer view: needs a report that is polished enough to share upward or
  outward without losing provenance, caveats, and exclusions.
- Coverage team view: can render board/client-safe reports from the same
  underlying evidence graph without inventing unsupported certainty.
- Board/client view: sees concise findings, source basis, confidence boundaries,
  and explicit next-review items in one package.
- Forbidden: cleaning the report by deleting ambiguities, review-required
  items, or loss markers to make it look more “industry grade.”
- Failure prevented: elegant but unsafe briefing packs and governance failure
  from presentation-layer overclaim.

### Real-time alert reviewer → Operations Desk → Audit
- Desk view: hacks, liquidations, chain outages, regulatory announcements, and
  unusual transactions appear as candidate alerts with latency, coverage, and
  confidence/loss envelopes.
- Ops view: alert sources, missing feeds, and duplicate/related signals are
  explicit; “not monitored” is visible.
- Audit view: every alert decision is traceable to source events and declared
  exclusions.
- Forbidden: “real-time” claims without feed/latency provenance, or summary
  text that hides missing coverage.
- Failure prevented: pseudo-alerting, alert fatigue, and post-incident
  unverifiability.

### Institutional buyer / integration lead → Procurement → Board / Regulator
- Buyer view: evaluates API/stream surfaces, export stability, receipts, and
  integration boundaries rather than UI demos alone.
- Procurement view: checks traceability, explainability, role-based exports,
  and non-UI operating surfaces.
- Board/regulator view: receives summaries that are safe to hand over because
  omissions, provenance, and confidence boundaries remain visible.
- Forbidden: UI-only black boxes, unversioned outputs, or hand-wavy “AI
  insights” with no replay path.
- Failure prevented: failed pilots, procurement rejection, and governance
  failure at deployment time.

### Partner platform (Mirror-like) → Joint product team → Shared customers
- Partner view: consumes SensibLaw/TiRC as a human-risk / obligations /
  explainability layer, not as a competing narrative assistant.
- Joint product view: shared surfaces are stream/API/export contracts with
  explicit responsibilities for narrative, evidence, and obligation handling.
- Customer view: combined outputs explain both system events and their effects
  on people, obligations, and regulated workflows.
- Forbidden: category overlap hidden behind co-marketing, or silent merging of
  narrative outputs with provenance-bearing facts.
- Failure prevented: partnership incoherence and unsafe product bundling.

### Sales / BD lead → Prospects → Internal governance
- Sales view: can describe the product in a way that is compelling without
  implying autonomous legal judgment, universal coverage, or instant
  compliance clearance.
- Prospect view: sees bounded claims about review queues, provenance, exports,
  and role-safe reporting rather than hand-wavy "AI intelligence."
- Internal governance view: approved claims, exclusions, and red-line language
  are versioned so demos do not outrun the actual system.
- Forbidden: selling provisional classifiers as determinations, or pitching
  roadmap hypotheses as current product guarantees.
- Failure prevented: oversold pilots, contractual mismatch, and avoidable trust
  collapse after procurement.

### Customer success / implementation lead → Customer ops → Renewal owner
- Implementation view: onboarding tracks schema mappings, feed coverage,
  freshness windows, replay paths, and declared exclusions from day one.
- Customer ops view: can see where a deployment is source-thin, queue-heavy,
  or failing because of input quality rather than model "intelligence."
- Renewal owner view: customer health is explained through operating surfaces
  and unresolved review pressure, not vanity usage metrics.
- Forbidden: onboarding by narrative alone, or hiding missing feeds and
  brittle mappings until renewal time.
- Failure prevented: failed implementations, false blame on users, and silent
  drift between promised and actual operating scope.

### Data / integration engineer → Platform team → Audit / procurement
- Engineer view: needs stable contracts for feeds, receipts, retries,
  idempotency, export schemas, and audit trails.
- Platform view: can trace how a source event became a review row, provisional
  queue item, export, or client-visible report.
- Audit/procurement view: receives replayable evidence that outputs are
  versioned, attributable, and reproducible within the stated coverage window.
- Forbidden: mutable outputs with no replay path, or hidden dependence on one
-off prompts and manual operator memory.
- Failure prevented: integration fragility, unverifiable exports, and
  procurement failure on technical assurance grounds.

### External counsel → Client team → Board / regulator
- Counsel view: receives applicability maps, token classification surfaces, and
  evidence bundles as bounded analytical inputs rather than machine-issued
  legal conclusions.
- Client team view: can separate legal questions, factual questions, and
  unresolved evidence gaps before escalating advice requests.
- Board/regulator view: downstream legal memos or submissions can cite the
  underlying source base and declared exclusions without laundering uncertainty.
- Forbidden: presenting candidate statutory applicability or derivative-like
  behavior as settled legal advice, or deleting unresolved items to make a memo
  look cleaner.
- Failure prevented: unauthorized-practice drift, bad legal reliance, and
  governance failure from overcompressed counsel packs.

### Regulator / auditor → Supervision team → Enforcement / public record
- Regulator view: reviews exact source basis, retrieval windows, scope
  exclusions, and why a matter was surfaced for review without inheriting a
  vendor's hidden scoring logic.
- Supervision view: can compare reporting posture across entities and time
  windows while keeping statutory hierarchy, jurisdiction, and evidence quality
  explicit.
- Enforcement/public-record view: exported materials preserve chain-of-source,
  abstentions, and loss markers so they can be challenged and defended.
- Forbidden: black-box risk rankings, opaque "confidence" labels detached from
  source quality, or reports that suppress missing coverage.
- Failure prevented: regulator distrust, unusable audit packs, and contested
  oversight actions built on irreproducible vendor claims.

### Middle Manager → Department → HR/Ops
- Team view: unresolved blockers and handoff failures are explicit.
- Admin view: workload density, interruption patterns, system bottlenecks.
- Forbidden: private reflections; blame narratives without commitments.
- Failure prevented: gaslighting and unfair performance review dynamics.

### Removalist → Crew → Logistics Admin
- Team view: instruction changes and constraints remain visible.
- Admin view: route changes, staffing gaps, equipment issues only.
- Forbidden: rewriting instructions after the fact.
- Failure prevented: worker scapegoating and unsafe speed pressure.

### Barista → Store → Chain HQ
- Team view: rush periods, staffing mismatches, equipment failures.
- HQ view: throughput vs staffing; absence of slack.
- Forbidden: individual “mistakes” as primary narrative.
- Failure prevented: blame-based management and churn.

### Barrister → Chambers → Courts
- Team view: research timelines and evidentiary references.
- Oversight view: due diligence and ethical boundary evidence.
- Forbidden: speculative rehearsal treated as evidence.
- Failure prevented: conflating speculation with fact.

### Air Force Pilot → Squadron → Command
- Team view: training vs live runs, deviations, environmental context.
- Command view: pattern-level deviations and training gaps.
- Forbidden: rewriting procedures post-incident.
- Failure prevented: cover-ups and chilled reporting.

### Mechanic → Shop → Fleet/Manufacturer
- Team view: test sequences and part swaps.
- Fleet view: failure clusters and diagnostic ambiguity.
- Forbidden: personal guesswork framed as certainty.
- Failure prevented: cargo-cult fixes and warranty disputes.

## Public sector (police/EMS/health/government)

### Police / EMS / Health (front-line emergency)
- Individual view: execution envelopes capture timing, procedure references, and explicit absences.
- Team view: handoff gaps, timing overlaps, tool availability failures.
- Oversight view: sequence reconstruction and systemic stressors only.
- Forbidden: intent inference, “who hesitated,” or emotional-state capture.
- Failure prevented: post-hoc reconstruction, absence treated as success.

### Government (administration/regulators/elected officials)
- Civil service view: policy issuance/amendments/exceptions recorded with timelines.
- Regulator view: immutable sequences, declared commitments, and explicit absences.
- Elected officials: commitments only; no strategy or persuasion capture.
- Forbidden: post-hoc sanitization, semantic relabeling, or centralized truth fusion.
- Failure prevented: policy drift myth-making and vendor-dependency collapse.

### Public servant / internal whistleblower → integrity body / counsel / oversight
- Public-servant view: can document suspected malfeasance, maladministration,
  procurement irregularity, retaliation, or unsafe practice at work while
  keeping direct observations, hearsay, documents, and private hypotheses
  clearly separate.
- Integrity/counsel view: receives a bounded chronology with sources,
  attachments, absences, and explicit uncertainty markers rather than an
  emotionally compressed accusation bundle.
- Oversight view: can inspect sequence, policy/process references, and
  corroborating gaps without inheriting a hidden credibility score.
- Forbidden: converting workplace suspicion into machine-certified wrongdoing,
  or forcing the record into employer-safe language before protected disclosure
  decisions are made.
- Failure prevented: whistleblower self-exposure, integrity-report collapse,
  and retaliation aided by incoherent or overcompressed records.

### NGO / campaign coordinator → Coalition → Public / funders / counsel
- Coordinator view: campaign events, public statements, incidents, harms,
  obligations, and partner commitments stay on one timeline with explicit
  absences and provenance.
- Coalition view: allied orgs can exchange bounded artifacts and verified
  counts without forcing a merged database or one canonical narrative.
- Public/funder/counsel view: exports declare uncertainty, exclusions, and
  evidentiary limits up front.
- Forbidden: dashboard-driven pressure to overstate certainty, or collapsing
  advocacy narrative into unsupported factual claims.
- Failure prevented: credibility loss, coalition drift, and legally unsafe
  reporting.

### Disability / advocacy org → Members / carers / funders / regulators
- Advocate view: can track access failures, service denials, harm episodes,
  accommodation requests, and institution responses without flattening lived
  experience into one admin category.
- Member/carer view: can contribute bounded records and supporting context
  while keeping sensitive personal material role-scoped and selectively
  shareable.
- Funder/regulator view: receives counts, patterns, timelines, and exclusions
  that stay attached to provenance and do not erase minority or hard-to-fit
  cases.
- Forbidden: forcing disability experience into tidy service metrics only, or
  trading away user safety/privacy for dashboard readability.
- Failure prevented: advocacy evidence loss, inaccessible reporting, and
  service-system pressure to understate complex harms.

### Community legal / casework / service org → Team → Oversight
- Caseworker view: money, conversations, harms, and obligations remain
  first-class and time-aligned; fragmented recall and conflicting accounts can
  coexist.
- Team view: recurring patterns across clients or episodes can be noticed
  without deleting context or person-level nuance.
- Oversight view: service load, obligation pressure, and systemic gaps are
  visible without exposing unnecessary personal detail.
- Forbidden: forced coherence, premature case scoring, or decontextualized
  pattern claims.
- Failure prevented: losing relational/economic abuse signals and flattening
  vulnerable users into admin-friendly summaries.

### Wikidata editor / ontology reviewer
- Review view: sees bounded candidate issues with exact provenance, explicit
  statuses, and visible absences; no auto-fix and no forced semantic collapse.
- Tooling view: contradiction, missing-claim, and unsupported-claim surfaces
  remain review queues, not autonomous edits.
- Export view: every suggestion stays linked to its source article span,
  revision window, or pinned diagnostic artifact.
- Forbidden: silent promotion from candidate issue to accepted truth; hiding
  abstentions or missing evidence to make the report look cleaner.
- Failure prevented: opaque bot behavior, unverifiable cleanup claims, and
  reviewer overload caused by context-free flags.

### Shared danger zone (explicit guardrails)
- No real-time authority or recommendations.
- Absence-as-signal is mandatory.
- Epistemic separation enforced (hypothesis ≠ commitment).

## Trauma-affected primary user (anonymised)

> Persona note (non-user-facing): primary user lives with long-term psychological
> injury; memory can be non-linear and fragmented; forced coherence or loss of
> context is itself harmful. The system must privilege safety and agency over
> completeness or speed.

### ITIR
- Record without explaining: user can log an event fragment with no motive,
  interpretation, or emotional label; "unknown / not ready" is terminal.
- Preserve context with gaps: approximate dates, relative ordering, and
  confidence flags are accepted; no auto-fill or timeline coercion.
- Safe review: progressive disclosure by default; no surprise expansion; no
  auto-surfaced "related" events.
- Coexisting truths: conflicting accounts can persist without reconciliation or
  canonical preference.

### SB
- Patterns without conclusions: optional overlays for repetition/proximity;
  never diagnoses, moral claims, or causal assertions.
- Anti case-study: no automatic summaries or "insights"; any synthesis requires
  explicit action and declares omissions.

### Cross-suite (Right to Context)
- Prevent decontextualized sharing: exports include context envelopes by
  default; removing context triggers warnings and immutable logs.
- Right to not know: "unknown" is a valid end state; no reminders to "complete"
  stories; no progress metrics tied to completeness; no nudging toward
  interpretation.

### Explicit non-goals
- No diagnosis, intent inference, timeline enforcement, credibility ranking, or
  clarity-over-safety optimization.
- No preference for institutional readability over user agency.
- Cross-agency fusion is opt-in, delayed, and non-reversible by default.

## Modern org stack (dev → team → CEO → finance)

### Individual developer (home + work)
- Captures execution envelopes (builds/tests/scripts) + prompt hashes.
- Hypothesis vs commitment is explicit (experiments vs merges/deploys).
- Absence-as-signal: missing tests, unavailable CI, missing logs.
- Value: externalized working memory without judgment.

### Dev team (shared truth, not shared control)
- Aggregates patterns (failure motifs, systemic absences) without naming names.
- No ranking, no effort inference, no private exploration exposed.
- Value: coordinated reality without blame inflation.

### CEO (strategic, non-operational)
- Sees commitment timelines, decision latency, bottleneck signals.
- Does not see prompts, hypotheses, or individual tool usage.
- Value: strategy radar, not surveillance.

### Finance (commitments only)
- Prices commitments and reversals, not exploration time.
- No individual productivity scoring; no hypothesis-level costs.
- Value: cost attribution without killing uncertainty.

### Cross-cut: Hypothesis vs commitment
- Explicit transitions; no silent promotion.
- Prevents retro narratives and KPI theater.

### Cross-cut: Absence-as-signal
- Missing tests/metrics/CI are recorded and queryable.
- Prevents false confidence and post-hoc patching.

## Air-gapped / battlefield / Palantir interoperability

### Prime constraint
- SB/ITIR is never the commander or planner; it is the memory substrate.

### State vs non-state coordination
- State-style systems centralize truth and action; SB must not inherit their authority.
- Federated systems share signals, not commands; SB aligns naturally with this.

### Execution envelope normalization
- All operational artifacts reduce to envelopes (time window, modality, host/toolchain, hashes).
- No plans/predictions/commands are stored as commitments.

### Operational planning (danger zone)
- Plans are ingested as **hypotheses**, never commitments.
- SB records when plans existed and when execution diverged.

### Drones / cams / telemetry (local-first)
- Devices write locally; export hashes + metadata only.
- Raw artifacts remain local; SB records absence signals (dropouts, obstruction).

### Absence-as-signal (critical)
- Missing telemetry is explicit and queryable; no silent “all clear.”

### Interop with Palantir-like systems
- External outputs are ingested as non-authoritative annotations only.
- SB never promotes these to commitments or action boundaries.

### Local sovereignty
- Append-only, schema-validated, air-gapped by default.
- Cross-node exchange is facts-only; interpretations are refused.

## Activist coordination (Greenpeace-style)

### Organizer reality
- Long timelines, legal risk, uneven training, rotating roles.
- SB used for memory/accountability, not live command.

### Before action (planning)
- Declared intent + constraints recorded; tactics excluded.
- Legal context snapshots recorded.
- Absence markers explicitly note what is not recorded.

### During action (live)
- No real-time synthesis or classification.
- Raw artifacts captured locally; SB stays quiet.

### After action (reconstruction)
- Observer logs, arrest times, media/police statements ingested as artifacts.
- Competing accounts preserved side-by-side; absences visible.

### Coordination with lawyers/observers/media
- Scoped access by role (legal observers, media, allied orgs).
- Artifacts are content-addressed; loss profiles explicit.
- No global dashboard or merged database.

### Red lines
- No participant ranking, risk scoring, or predictive escalation.
- No “suspicious behavior” flags.

## Trauma + authoritarian pressure (resilience without coercion)

### Core risks
- Temporal disorientation, memory erosion, forced narratives, administrative exhaustion.
- Internal mistrust and burnout masked as personal failure.

### What SB/ITIR must not do
- Centralize truth or collapse uncertainty into scores.
- Infer intent, predict behavior, or rank risk.
- Merge identities across domains or automate suspicion.

### What SB/ITIR provides
- Epistemic stabilization: preserves ambiguity and fragmented recall.
- Absence-as-signal: silence is valid and explicit.
- Hypothesis vs commitment separation protects against self-incrimination.
- Layered time: retroactive annotation and parallel timelines allowed.

### Individual → group → movement scale
- Individuals: external memory prosthesis without judgment.
- Groups: shared memory without forced consensus.
- Movements: federated memory with local sovereignty and auditable exchange.

### Hostile state context
- Local-first, air-gapped, append-only by default.
- Non-operational posture; documentation without command logic.

## Access scopes + legal reconstruction (activist/observer/lawyer/media)

### Access scope invariants
- Read-only for all roles; no mutation of primary records.
- Absence and redaction are visible and distinct.
- Provenance is mandatory; exclusions declared.
- No inference surfaces (no scoring, intent detection, prediction).

### Observer scope
- Can access: time-bounded activity events, counts, provenance, absences.
- Cannot access: identities beyond role-safe pseudonyms, hypotheses, intent labels.
- UI: “observational only” banner + exclusion watermark.

### Lawyer scope
- Can access: full events with identifiers (where lawful), chain-of-custody, redaction history.
- Explicit split: admissible facts vs hypotheses (non-evidentiary).
- Export: court-safe bundle only.

### Media scope
- Can access: anonymized timelines, verified counts, uncertainty markers.
- Cannot access: raw identities, privileged material, internal hypotheses.
- UI: “not a complete record” banner + disputed/absent markers.

### Post-action reconstruction (defensive)
- Freeze window → align events → separate fact/hypothesis/absence → export.
- Drift analysis uses counts only; no motive inference.

### Infiltration stress-test (defensive)
- No trust amplification; inputs remain hypotheses until corroborated.
- Provenance and capture distance always visible.
- No operational surfaces or “next steps.”

## Judicial context (judges, staff, bailiffs, family)

### Core principle
- SB provides memory hygiene and scope control, never judgment support.

### Judge (professional use)
- Case-local memory discipline: hearings, exhibits (hashes), rulings, procedural events.
- Hypotheses are private, non-exportable, time-scoped; commitments are rulings only.
- Absence-as-signal prevents filling gaps from memory.

### Judicial staff (clerks/associates)
- Log procedural facts, filings, deadlines, explicit absences.
- Forbidden: summaries, narrative framing, strength ranking.

### Bailiffs / court officers
- Log objective events (removals, delays, security incidents) with timestamps.
- Forbidden: intent attribution or behavioral labels.

### Family members (extremely constrained)
- Non-case access only: workload patterns, schedule load.
- Forbidden: case details, parties, outcomes, topics.

### Absolute red lines
- No outcome suggestions or “similar case” surfacing.
- No predictive appeal success or public reaction modeling.
- No judge consistency scoring or argument ranking.


## Context fields (weather / market / astronomy / astrology)

Principle: external fields of force, not facts about the user. Align by time/place only; never drive inference, advice, alerts, or prioritisation.

- Weather: optional band of observed readings; no behavioural claims (e.g., "heat caused...").
- Market: index/volatility strips only; no portfolio inference, profit framing, or nudges; label "public market context (non-personal)".
- Astronomy: sunrise/sunset/moon glyphs; optional shading; never prescriptive.
- Astrology: symbolic overlay, opt-in, visual-only, labeled "symbolic / non-causal"; never auto-attached to events.
- Exports/summaries must declare whether context fields are included/excluded; removing context logs a loss entry.

## Explicit non-goals (context & interpretation)
- No causal language ("caused, influenced, impacted") in context panels.
- No risk/advice/diagnosis derived from context fields.
- No automatic linkage of symbolic overlays to events.


## Plural temporal/knowledge users (farmer, symbolic cycles)

### Farmer
- Uses seasons/phenology, distrusts "insights"; enables LES overlays for slow variables (rainfall memory, frost windows, heat load) and optional regional Indigenous seasonal calendars.
- SB entries: situated actions (“delayed planting”, “moved stock”) stamped with LES snapshot; no system explanation.
- ITIR: browse by season; replay environment alongside actions without advice.

### Symbolic/astrology-oriented user
- Enables astronomical state and optional symbolic calendar (opt-in, labeled non-causal).
- SB holds self-authored meaning only (“felt unsettled”, “waited”); system never links symbols to behaviour.
- ITIR: overlays symbolic cycles parallel to events; togglable; no fusion.

### Same person is both
- LES hosts multiple models side-by-side (meteorological, agro-ecological, Indigenous seasonal, symbolic) without merging or prioritising.
- SB logs actions/notes without forced justification; ambiguity allowed.
- ITIR replays time with multiple models visible; user notices patterns, system asserts none.

### Anti-collapse rules
- No causal/normative claims tying context to behaviour (e.g., “because Mercury retrograde”, “productivity dropped due to drought”).
- No merging of Indigenous calendars into Gregorian; no translation of symbolic systems into advice.
- Explicit model provenance and type (environmental vs symbolic) in overlays.

## Partial-stack client map

Principle: different clients may need only one layer of the stack. Packaging,
claims, and evaluation criteria should follow the layer actually being used,
not the full suite story.

### Capture-only clients (TiRCorder / append-only logging)
- Typical users: journalists, inspectors, ombuds teams, field researchers,
  workplace investigators, legal observers, interview-based audit teams.
- They buy: trustworthy capture, timestamps, receipts, append-only history,
  role-safe export.
- They do not need: legal reasoning, synthesis, or full review geometry.
- Failure prevented: treating a capture tool as an analysis engine and then
  overclaiming what the recorded material means.

### Timeline / reconstruction clients (ITIR)
- Typical users: insurance claims teams, HR investigators, safety teams,
  patient-safety review, incident response, warranty/dispute teams.
- They buy: sequence reconstruction, explicit absences, provenance, parallel
  hypotheses, and replayable timelines.
- They do not need: domain-law overlays or broad narrative intelligence.
- Failure prevented: premature coherence, missing-gap blindness, and unusable
  post-incident reconstructions.

### Obligations / reference clients (SensibLaw core)
- Typical users: in-house compliance, policy teams, trustees, external counsel
  support, procurement-risk teams, governance offices.
- They buy: source-backed legal/regulatory mapping, applicability surfaces,
  statute/guide separation, freshness windows, and bounded exports.
- They do not need: personal memory tooling or activist-grade local-first
  capture.
- Failure prevented: stale advice posture, flattened legal hierarchies, and
  unverifiable compliance summaries.

### Review-queue / triage clients
- Typical users: diligence desks, research teams, fact-checking groups,
  knowledge-graph maintainers, NGO documentation teams, integrity teams.
- They buy: bounded candidate issues, explicit statuses, queueing, clustering,
  and visible abstentions.
- They do not need: autonomous decisioning or polished narrative copilots.
- Failure prevented: silent promotion, reviewer overload, and context-free flag
  spam.

### Semantic-governance / promotion-integrity clients
- Typical users: maintainers, ontology/review pipeline owners, CI/release
  stewards, partner teams consuming truth-bearing semantic fields.
- They buy: explicit candidate schemas, central promotion gates,
  truth-bearing/non-truth-bearing boundaries, and auditability over which code
  paths may promote canonical semantic truth.
- They do not need: lane-local shortcuts that silently assign semantic truth
  from extraction code or surface heuristics.
- Failure prevented: ontology drift, lexical-to-semantic creep, and downstream
  systems treating review hints or operational state as canonical truth.

### Mission accounting / planning crossover clients
- Typical users: SB/ITIR operators using mission-lens artifacts to compare
  actual activity against intended planning nodes and deadlines.
- They buy: reviewed actual-to-mission mapping, operational overlays, and
  bounded planning/accounting surfaces that stay replayable and reviewable.
- They do not need: premature promotion of observer overlays into canonical
  semantic truth before a separate reducer/promotion model exists.
- Failure prevented: workflow/accounting state being misread as factual or
  legal truth, and mission drift being overclaimed from lexical or weakly
  grounded mappings alone.

### Reporting / export clients
- Typical users: investor-relations/legal ops, audit committees, watchdogs,
  grant-reporting teams, board reporting teams, regulator-facing admins.
- They buy: board-safe and regulator-safe outputs with provenance, exclusions,
  and reproducible evidence bundles.
- They do not need: the full authoring or exploratory workflow used upstream.
- Failure prevented: elegant reports that cannot survive challenge or audit.

### Provenance / receipts infrastructure clients
- Typical users: AI vendors, workflow platforms, research tools,
  case-management systems, partner products like Mirror, internal platform
  teams.
- They buy: receipts, replay paths, export contracts, coverage markers, and
  attribution scaffolding.
- They do not need: SensibLaw as a front-end destination product.
- Failure prevented: opaque partner integrations, hand-wavy AI bundling, and
  missing replayability.

### Air-gapped / local-first memory clients
- Typical users: courts, chambers, sensitive clinics, defense-adjacent teams,
  activist legal support groups, high-sensitivity corporate investigations.
- They buy: local sovereignty, append-only history, role-scoped exports, and
  no forced cloud dependence.
- They do not need: centralized dashboards or cross-tenant optimization.
- Failure prevented: governance rejection, unsafe deployment, and trust
  collapse in high-sensitivity environments.

### New client families still worth explicit stories if we pursue them
- Insurance / claims adjudication.
- HR / workplace investigations.
- Journalism / watchdog / OSINT research.
- Safety / quality / incident-review systems.
- Healthcare administration / patient-safety review.
- Internal audit / inspectorate / ombuds operations.

## Personal/private client map

Principle: personal/private users are valid first-class users of individual
stack layers, but the product promise is different from institutional use.
Private use emphasizes memory hygiene, context boundaries, local sovereignty,
and safe export, not authoritative classification or professional-style
compliance outputs.

### Personal capture users
- Typical users: diarists, trauma-affected users, carers, family recordkeepers,
  independent journalists, solo advocates, people tracking conversations or
  incidents for later recall.
- They use: TiRCorder-style capture, timestamps, append-only notes, and local
  receipts.
- They do not need: professional review queues or board-safe report packs by
  default.
- Failure prevented: memory drift, overwritten recollection, and accidental
  conversion of private notes into formal claims.

### Personal timeline / reconstruction users
- Typical users: people reconstructing disputes, care episodes, household
  incidents, landlord/employment conflicts, relationship or financial harm
  patterns, or complicated family timelines.
- They use: ITIR-style timelines, explicit absences, coexisting hypotheses,
  and role-scoped exports.
- They do not need: forced coherence, auto-summaries, or institutional
-looking case scoring.
- Failure prevented: collapsing fragmented recall into a single imposed story
  and losing the ability to distinguish fact, hypothesis, and gap.

### Personal obligations / reference users
- Typical users: people trying to understand what rules, rights, reporting
  obligations, or agency guides might matter to their situation before
  speaking to a lawyer, doctor, regulator, union, or advocate.
- They use: bounded source-backed applicability maps, rule/reference search,
  and explicit "not legal advice" scope.
- They do not need: machine-issued determinations about what they must do.
- Failure prevented: private users mistaking reference support for personal
  advice, or being pushed into false certainty before getting expert help.

### Personal reporting / export users
- Typical users: someone preparing a bundle for a lawyer, doctor, union,
  advocate, insurer, family member, or journalist.
- They use: selective exports with context envelopes, exclusions, and visible
  redactions.
- They do not need: polished corporate presentation layers.
- Failure prevented: decontextualized sharing, accidental overexposure, and
  private material losing its boundaries once exported.

### Personal provenance / receipts users
- Typical users: people who need to show when something was recorded, what
  changed later, what was omitted, or which version of a note/export was sent.
- They use: content-addressed artifacts, append-only history, and replayable
  export receipts.
- They do not need: multi-tenant platform abstractions.
- Failure prevented: "you changed your story" disputes and unverifiable
  personal recordkeeping.

### Personal local-first / high-sensitivity users
- Typical users: survivors, whistleblowers, targets of harassment, families in
  conflict, vulnerable users dealing with institutions, and anyone who cannot
  safely centralize their records in a normal SaaS app.
- They use: local-first storage, explicit absence markers, delayed/partial
  sharing, and role-scoped disclosure.
- They do not need: cloud-default collaboration or engagement loops.
- Failure prevented: unsafe exposure, coercive sharing, and institutional
  readability taking precedence over user safety.

### Private-to-professional boundary users
- Typical users: professionals whose home and work memory surfaces must remain
  separate, and private individuals who may later need to hand selected
  records to formal institutions.
- They use: explicit boundary markers between private hypotheses,
  professional commitments, and externalized exports.
- They do not need: silent sync between home and work contexts.
- Failure prevented: context leakage, accidental self-incrimination, and
  private speculation becoming official record by drift.

### Private-user red lines
- No forced progress metrics tied to completeness.
- No default sharing or ambient cloud sync.
- No authority language that upgrades personal notes into fact.
- No pressure to make private records look institutionally tidy before the user
  is ready.

## Private ↔ institutional crossover stories

Principle: crossover is where the stack is most likely to do harm if boundaries
are unclear. These stories are about selective handoff, scoped translation, and
explicit status preservation, not turning private memory into institutional
truth by default.

### Private individual → lawyer / advocate
- Individual view: can prepare a bounded export of notes, dates, gaps, and
  artifacts for a lawyer or advocate without first forcing the story into
  perfect coherence.
- Legal helper view: receives a chronology with provenance, explicit absences,
  and a visible split between direct record, recollection, and hypothesis.
- Forbidden: upgrading private notes into evidence labels automatically, or
  smoothing contradictions to make the brief look cleaner.
- Failure prevented: self-erasure under pressure, evidentiary contamination,
  and premature fixing of one story before legal review.

### Private individual → doctor / psychologist / care team
- Individual view: can share selected episodes, symptoms, dates, triggers, and
  uncertainties without exposing unrelated private context.
- Care-team view: sees a bounded record of what was experienced, when, and how
  certain the account is, without the system implying diagnosis or causation.
- Forbidden: turning self-recorded patterns into diagnostic claims, or forcing
  private reflection into clinical language before the user is ready.
- Failure prevented: suggestion effects, narrative coercion, and leakage from
  personal journaling into institutional clinical records.

### Private individual → journalist / watchdog / observer
- Individual view: can disclose a subset of incidents or materials with
  context envelopes, redactions, and explicit permission boundaries.
- Journalist/watchdog view: can distinguish firsthand material, supporting
  artifact, missing corroboration, and non-shareable context.
- Forbidden: exporting decontextualized excerpts that look cleaner but sever
  provenance and scope.
- Failure prevented: misquotation, overexposure, and public claims outrunning
  what the private record actually supports.

### Private individual → regulator / ombuds / complaint body
- Individual view: can assemble a complaint or chronology pack that shows what
  happened, what is missing, and which rules may be relevant without pretending
  the matter is already adjudicated.
- Regulator/ombuds view: receives source-backed timelines, attachments,
  exclusions, and a bounded applicability map rather than a rhetorical essay.
- Forbidden: replacing the complainant's uncertainty with machine certainty, or
  implying that agency guidance has been individualized into advice.
- Failure prevented: complaint collapse, overclaim, and unusable packs that mix
  allegation, inference, and rule text without boundaries.

### Private individual → community org / disability advocate / support service
- Individual view: can share a selected chronology of harms, access barriers,
  conversations, documents, and unresolved gaps with a community or disability
  advocate without yielding the whole private archive.
- Advocate/service view: receives a bounded, person-safe record that preserves
  chronology and uncertainty while still being useful for support, escalation,
  or pattern detection across cases.
- Forbidden: requiring the person to translate lived experience into funder or
  agency language before support can begin, or widening sharing scopes by
  default because the organization is trusted.
- Failure prevented: support fatigue, coercive intake, and loss of nuance when
  personal records enter service workflows.

### Private individual → public servant / integrity process
- Individual view: if they are also a worker inside an institution, they can
  separate private reflections, work-adjacent observations, and disclosure-safe
  materials before approaching an integrity line, union, counsel, or watchdog.
- Integrity-process view: receives a chronology that distinguishes direct
  observation, internal document, secondhand report, and personal inference.
- Forbidden: silent collapse of private journaling into formal workplace
  allegations, or institution-friendly rewriting before the individual has
  chosen a disclosure path.
- Failure prevented: self-incrimination, retaliation exposure, and disclosure
  packs that blur observation and interpretation.

### Community org / advocate → lawyer / regulator / media
- Community-org view: can translate supported client/member material into
  outward-facing bundles for lawyers, regulators, journalists, or funders
  without erasing uncertainty, exclusions, or scope limits.
- Downstream-recipient view: sees whether a claim is firsthand, aggregated,
  pattern-level, or still under review.
- Forbidden: laundering advocacy synthesis into fact without preserving the
  underlying provenance and abstentions.
- Failure prevented: movement credibility collapse, unsafe public allegations,
  and institutional rejection of otherwise valuable community evidence.

### Private day → escalation journey (chat logs to help-seeking)
- Individual view: starts with personal chat logs, notes, schedules, and daily
  fragments; can tag hypotheses vs facts vs gaps without forcing coherence.
- Escalation view: can promote selected slices into exports for lawyer/doctor/
  advocate/regulator while keeping private material and unready content out of
  scope.
- Forbidden: automatic “progress” or completion scoring that pressures the user
  to sanitize or fill gaps before they choose to escalate.
- Failure prevented: overexposure, coerced coherence, and loss of control when
  moving from personal memory to formal help.

### Data labeling / annotation team → QA lead → downstream consumers
- Annotator view: handles review queues with explicit provenance, abstain/uncertain
  options, and no silent promotion from candidate to accepted labels.
- QA lead view: sees inter-rater disagreement, gap counts, and missing-evidence
  markers, not aggregate scores that hide conflict.
- Downstream consumer view: receives label exports with receipts, versioning,
  and abstentions intact.
- Forbidden: forced labels when evidence is insufficient, or collapsing
  annotator conflict into majority vote without provenance.
- Failure prevented: mislabeled training/eval data and hidden uncertainty in
  downstream models.

### Education / research user → supervisor → publication
- Researcher/student view: captures experiments, sources, and notes with
  hypothesis vs result status, timestamps, and explicit absences.
- Supervisor view: sees reproducible envelopes, missing-data warnings, and
  provenance for claims.
- Publication view: exports include receipts and exclusions instead of
  over-polished summaries.
- Forbidden: turning exploratory notes into asserted findings or stripping
  uncertainty for write-ups.
- Failure prevented: irreproducible results, accidental plagiarism, and
  misplaced confidence from compressed lab notes.

### Platform integrator (SDK/API) → their customers → auditors
- Integrator view: consumes only the provenance/receipt layer (exports, hashes,
  replay paths) via SDK/API without adopting the full product surfaces.
- Their customer view: can audit what was ingested and what changed, using
  deterministic receipts rather than vendor promises.
- Auditor view: receives versioned outputs with chain-of-source and loss
  markers even though analysis ran in the integrator’s stack.
- Forbidden: dropping receipts when embedding the stack or relabeling
  provisional outputs as final.
- Failure prevented: opaque integrations, audit failure, and blame shifting
  when embedded logic is questioned.

### Field safety / inspection (offline-first) → Org safety → Regulator/insurer
- Inspector view: records photos, checklists, and observations offline with
  timestamps and later sync; absences and failed captures remain explicit.
- Org safety view: sees hazards, follow-ups, and unresolved items with source
  receipts, not just a pass/fail rollup.
- Regulator/insurer view: receives exports that show what was inspected,
  what was not, and when sync occurred.
- Forbidden: retroactive filling of missing captures, or treating offline gaps
  as successful checks.
- Failure prevented: audit failure, unsafe sign-offs, and liability from
  hidden inspection gaps.

### Private individual → insurer / claims / dispute handler
- Individual view: can show sequence, loss markers, communications, and
  documentary receipts without silently discarding ambiguity or missing data.
- Claims/dispute view: receives a replayable account of events, documents,
  timestamps, and absences rather than a polished narrative alone.
- Forbidden: retrofitting events to match a claim form or hiding uncertainty to
  make the timeline look simpler.
- Failure prevented: denial-supporting inconsistencies, hindsight editing, and
  disputes about when records were created.

### Private individual → employer / HR / union
- Individual view: can document incidents, instructions, retaliation patterns,
  rostering issues, or unsafe conditions while keeping private reflections
  separate from workplace-shareable material.
- HR/union view: receives bounded facts, dates, messages, and explicit gaps
  rather than an all-access dump of the person's private archive.
- Forbidden: silent bleed from private journaling into employer-facing records,
  or forcing worker recollection into admin-friendly categories too early.
- Failure prevented: retaliation risk, context leakage, and premature shaping
  of the record around institutional forms.

### Private individual → family / carers / trusted circle
- Individual view: can share selected updates, practical needs, or time-bounded
  incident summaries with trusted people without opening the whole archive.
- Trusted-circle view: sees what the user chose to share, what remains
  withheld, and what support is being requested.
- Forbidden: ambient access to the full record or social pressure to widen the
  sharing boundary because the data exists.
- Failure prevented: coercive transparency, relational overreach, and loss of
  user control over sensitive material.

### Private creator / small operator → institutional counterparty
- Individual view: a founder, sole trader, or independent publisher can use
  the same bounded-reference and reporting surfaces when dealing with banks,
  platforms, counterparties, or procurement teams.
- Counterparty view: receives an export that is professional enough to review
  while still declaring uncertainty, exclusions, and unverified areas.
- Forbidden: forcing the private/small operator into enterprise theater before
  the underlying evidence actually supports it.
- Failure prevented: overpromising under pressure and mismatches between small
  operator reality and institutional intake expectations.
