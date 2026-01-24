# Obligations layer (S4.1)

Status: additive-only. Extraction + LT-REF-1..6 + CR-ID/DIFF/PROV are frozen.

This layer detects *normative force* (obligation/permission/prohibition/exclusion) from logic-tree scoped clause spans. It must not invent references, and must be stable under OCR/formatting noise.

## Data model

### ObligationAtom
An obligation is a clause-local semantic object:

- **type**: one of `{obligation, permission, prohibition, exclusion}`
- **modality**: the modal trigger (e.g., `must`, `may`, `must not`, `does not apply`, `required`)
- **clause_id**: stable identifier for the clause span (logic-tree scoped)
- **actor**: optional `ActorAtom` extracted from the clause subject; `None` if missing/implicit
- **reference_identities**: set of identity hashes derived from the clause’s RuleReferences (CR-ID)
- **conditions**: optional list of condition spans (e.g., “if …”, “unless …”, “except …”)
- **span**: `(start_idx, end_idx)` in the normalised token stream for the obligation-bearing clause
- **provenance**: diagnostic only (page numbers, source=token/link, anchor_used); never affects identity

### ActorAtom (S5.1)
- **text**: surface text of the actor phrase (clause-local)
- **normalized**: lowercased, punctuation-trimmed, whitespace-collapsed actor string for identity
- **span**: `(start_idx, end_idx)` in the token stream for the clause-local actor phrase
- **clause_id**: clause identifier matching the parent obligation
- **feature flag**: `OBLIGATIONS_ENABLE_ACTOR_BINDING` (env) or CLI `--disable-actor-binding` controls attachment; when off, `actor=None` and identities ignore actor.

### ActionAtom / ObjectAtom (S5.2)
- **action**: normalized verb head/phrase drawn from the clause (e.g., `keep`, `file`, `notify`, `enter`).
- **object**: normalized object phrase acted upon (e.g., `records`, `returns`, `the area`, `notice`).
- **spans**: clause-local `(start_idx, end_idx)` for action/object text.
- **identity**: normalized action/object feed obligation identity when action binding is enabled (flag `OBLIGATIONS_ENABLE_ACTION_BINDING` or CLI `--disable-action-binding` to turn off).

### ScopeAtom (S5.3)
- **time_scope**: explicit temporal phrases (e.g., “within 14 days”, “immediately”, “at all times”).
- **place_scope**: explicit spatial phrases (e.g., “on the premises”, “within the zone”).
- **context_scope**: situational phrases (e.g., “during operations”, “when requested”, “in an emergency”).
- Scope is attachment-only; does not change obligation existence.

## Invariants

### OBL-1 Scope & provenance (logic-tree scoped)
Every emitted ObligationAtom originates from a bounded logic-tree clause span.

Formally: let `T` be the normalised token stream, `L = build_logic_tree(T)`, and `C` the set of clause spans from nodes in `L` of type `{CLAUSE}`. Then for every obligation `o`, `∃ c ∈ C` such that `o.span ⊆ c`.

Forbidden: whole-document scanning, paragraph-level regex scraping, or cross-clause aggregation.

### OBL-2 No semantic invention (reference safety)
Obligations may only bind to references that already exist in that clause span.

Let `R(c)` be the set of RuleReferences extracted from clause `c` (after LT-REF canonicalisation). Let `ID(r)` be CR-ID identity hash for reference `r`.

Then for any obligation `o` emitted for clause `c`: `o.reference_identities ⊆ { ID(r) : r ∈ R(c) }`.

Forbidden: guessing instruments, inserting sections, expanding abbreviations not present in tokens.

### OBL-3 Monotone refinement (no splitting into *new* claims)
Post-processing is many-to-one only. If `O0…Ok` are obligation sets after normalisation/canonicalisation/condition extraction, then:
- `|O0| ≥ |O1| ≥ … ≥ |Ok|`
- each `o ∈ Oi` is a canonical form of some `o' ∈ O(i-1)`
- no step may introduce new obligations not supported by clause tokens

### OBL-4 Determinism
Identical normalised token stream + identical logic-tree build ⇒ identical emitted obligations (modulo ordering, which must be stable).

### OBL-5 Stability under OCR noise
For OCR edits that preserve the clause’s modal meaning (spacing, bracket noise, roman numerals, punctuation drift), the obligation identity must remain unchanged.

This means:
- work-string normalisation used by CR-ID governs reference binding stability
- modality detection must operate on token sequences, not exact original substring matches

### OBL-6 Cross-clause non-interference
Obligations must not “leak” anchors or conditions across clause boundaries.

If two clauses `c1` and `c2` are distinct in the logic tree:
- an obligation emitted for `c1` must not include references, conditions, or modality tokens from `c2`.

### OBL-7 Link precedence compatibility
If a clause contains link-derived references and token-derived references, reference binding must respect LT-REF link precedence:
- obligation binding uses the post-canonicalised reference set for the clause (preferred_sources ranking already applied)
- obligations never override link-derived anchors

### ACT (Actor) invariants — S5.1
- **ACT-1 Clause-local**: actor extraction is confined to the obligation’s clause span.
- **ACT-2 No inference**: no cross-clause deduction or ontology lookup; actors come only from text spans.
- **ACT-3 Identity is text-derived**: actor identity uses normalized clause text (lowercase, punctuation-trimmed, whitespace-collapsed) and is stable under OCR/spacing noise.
- **ACT-4 Obligation existence**: missing/implicit actor does not suppress obligation emission; actor becomes `None/unknown`.
- **Feature flag**: `OBLIGATIONS_ENABLE_ACTOR_BINDING` (env var) or CLI `--disable-actor-binding` toggles actor attachment; when off, obligations emit with `actor=None` and identities ignore actor text.

### ACTN (Action/Object) invariants — S5.2
- **ACTN-1 Clause-local, text-derived**: action/object come only from the obligation’s clause tokens; no ontology/synonym expansion.
- **ACTN-2 Span traceability**: action/object spans are preserved; normalized forms are derived from spans (lowercase, punctuation-trimmed, whitespace-collapsed).
- **ACTN-3 Stability**: OCR/spacing noise that preserves meaning does not change normalized action/object.
- **ACTN-4 Identity binding**: when action binding is enabled, obligation identity includes normalized action/object; when disabled, identity ignores them.
- **ACTN-5 Non-invention**: absence of an object is permitted (`object=None`) and does not suppress obligation emission.

### SCP (Scope) invariants — S5.3
- **SCP-1 Explicit-only**: scopes are captured only from explicit temporal/spatial/context phrases; no invented limits.
- **SCP-2 Non-destructive**: removing scope metadata does not delete obligations.
- **SCP-3 Identity isolation**: scope affects activation semantics but not obligation identity hashes.

### LIFE (Lifecycle) invariants — S5.4
- **LIFE-1 Descriptive**: activation/termination capture explicit language only; no compliance judgement.
- **LIFE-2 Explicit triggers**: lifecycle attaches only when explicit activation/termination phrases exist.
- **LIFE-3 Identity stability**: lifecycle metadata enriches obligations without altering identity hashes.

### ID / Graph invariants (R5–R6)
- Identity depends on: modality, actor (if enabled), normalized action/object (if enabled), condition/exception types, reference identities, clause index; never on numbering/formatting noise.
- Clause isolation: no actor/action/condition carry-forward across clauses unless an explicit edge layer is added.
- Graph projection: obligation nodes + typed edges must be deterministic; edges only from explicit text triggers.

## Safety theorem (soundness)
For any document `D`, the obligations pipeline yields a set `O` that is:
1) clause-sound: every obligation is supported by clause tokens;
2) non-inventive: binds only to CR-ID from existing clause references;
3) deterministic: same input ⇒ same output;
4) stable: OCR-only edits do not create spurious diffs;
5) non-interfering: no cross-clause leakage.

## Modal trigger lexicon (initial)
This is intentionally small and token-based. It may expand later but must remain test-driven.

- obligation: `must`, `shall`, `required`, `is to`, `is required to`
- permission: `may`
- prohibition: `must not`, `shall not`, `may not`
- exclusion: `does not apply`, `do not apply`, `not apply`, `except that`, `does not affect`

All triggers are matched in normalised tokens within clause spans (no global regex).

## Notes
- We treat obligations as additive overlays. They do not alter references, dedup, or canonicalisation.
- Any expansion to holdings/case law is out of scope for S4.1.
