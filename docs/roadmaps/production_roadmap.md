# SensibLaw: Roadmap to Production

## Phase 0 (NOW): Research Instrument Hardening (in progress)

**Purpose**
Turn SensibLaw into a trustworthy research tool, not a speculative demo.

### Deliverables
- Citation-driven ingestion (PDF -> cites -> follow -> ingest)
- AustLII SINO adapter with compliance notes
- Offline-first test suite + opt-in live canaries
- Playwright E2E covering **Documents ingest**
- Research-health CLI (JSON)
- Documents citations panel + unresolved workflow (nearly done)

### Exit criteria
- Every ingest produces normalized citations, resolved/unresolved status, and bounded follow provenance
- You can answer quantitatively: "How complete is this corpus?"

### Non-goals
- No semantic “legal reasoning”
- No recommendations beyond citation traversal
- No user auth / permissions
- No scale claims

---

## Phase 1: Structural Correctness & Corpus Trust (CRITICAL)

**Purpose**
Ensure the system never lies about structure even if content is messy.

### Key work
1) Citation / Text separation invariant
   - Citations never appear in clause text
   - “Following paragraph cited by” -> metadata only
   - Enforced by unit tests and a Playwright UI assertion
2) Canonical PDF fixture set (CLR-era dense cites, AustLII HTML->PDF hybrids, JADE headnotes/footnotes, broken scans)
3) Resolver precedence rules (JADE > AustLII > PDF-internal), frozen in `sources_contract.md`, tested via normalization fixtures
4) Unresolved citations as first-class output (always emitted, never dropped; visible in UI + CLI)

### Exit criteria
- You trust the shape of the data even when content is ugly
- You can diff two ingests and understand why they differ

### Non-goals
- No embeddings
- No inference
- No “this case applies” claims

---

## Phase 2: Deterministic Knowledge Graph (Read-Only)

**Purpose**
Make the graph true, not smart.

### What the graph is (and is not)
- Nodes = documents, provisions, citations
- Edges = cites, followed_from, derived_from
- No semantic edges
- No weights pretending to be meaning

### Deliverables
- Graph built only from ingestion artifacts
- Provenance tooltips everywhere
- CLI export: graph -> JSON / DOT
- Playwright test: graph view renders; edge counts match citation counts

### Exit criteria
- You can explain every edge
- No edge exists without a document source

### Non-goals
- No embeddings
- No ML
- No ranking

---

## Phase 3: Corpus Health, Drift & Guardrails

**Purpose**
Stop silent degradation as the corpus grows.

### Deliverables
1) Research-health CLI (locked schema): documents, citations_total, unresolved_percent, max_depth, db_growth_per_doc, compression_ratio
2) Growth guards: hard limits on citation fan-out, recursion depth, DB delta per doc; fail loudly
3) Reproducibility: same PDFs + adapters => same graph and unresolved list

### Exit criteria
- You can run ingest in 6 months and detect drift
- You can prove nothing exploded quietly

### Non-goals
- No predictive scoring
- No legal advice

---

## Phase 4: Controlled Semantics (Optional, Gated)

**Purpose**
Introduce meaning without destroying trust; this is optional.

### Preconditions
- Corpus health metrics stable
- Citation graph trusted
- Clear separation between facts, citations, interpretations

### Possible additions
- Fact tags (explicit, user-provided)
- Rule templates (transparent, declarative)
- Case structure comparison (no outcomes)

Everything must be opt-in, provenance-linked, and reversible.

### Exit criteria
- Users can say why the system suggested something
- Nothing is “learned” without being inspectable

---

## Phase 5: Productionisation (Ops, not features)

**Purpose**
Make it boring and dependable.

### Deliverables
- Headless ingestion CLI
- Deterministic DB migrations
- Backup / restore
- Logging of every external fetch and follow decision
- Configurable rate limits per source

### Compliance posture
- Citation-driven only
- No crawling
- Explicit source contracts
- Live access opt-in only

### Exit criteria
- You’d be comfortable handing this to a court researcher, a law reform body, or an academic lab

---

## What “Prod” Means Here (Important)

Production ≠ scale ≠ SaaS ≠ AI judge.
Production means: “This system can be relied upon not to mislead.”

If later you want embeddings, search, recommendations, or LLM interfaces, they sit on top of this foundation, not inside it.

---

## The North Star

A legally conservative, structurally honest research substrate on which others can safely experiment.

If you want, next I can mark where JADE ingestion fits into Phase 1, define a “minimum credible prod” checklist, or sketch the first “no-regrets” semantic layer.
