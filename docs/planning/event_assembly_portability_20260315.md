# Event Assembly Portability

Date: 2026-03-15
Status: planned / contract guidance

## Core Principle

Use a two-stage deterministic pipeline:

`text -> language-aware normalization -> predicate observations -> event assembly`

The event assembler must remain:

- language-neutral
- jurisdiction-neutral
- deterministic

Language and jurisdiction should change dictionaries, mappings, and priorities,
not the event-assembly logic itself.

## Assembly Input Boundary

The assembler must consume only normalized observation predicates and typed
objects, never raw surface text rules such as:

- `"if negligence then ..."`
- `"if performed surgery" in English only`

Instead it should operate on normalized observation keys like:

- `actor`
- `performed_action`
- `acted_on`
- `event_date`

## Variation Layers

Separate the stack into three layers:

### 1. Language packs

- lemmas
- cue phrases
- dependency patterns
- role labels
- date expressions

### 2. Concept mappings

- surface form -> concept
- legal source aliases
- role aliases
- action aliases

These may vary by:

- `language_code`
- `jurisdiction_code`

### 3. Assembly rules

- deterministic
- portable
- based on normalized observation families rather than language-specific text

## Jurisdiction Boundary

Jurisdiction may affect:

- role normalization
- court/procedure vocab
- source-type handling
- downstream doctrine mapping

Jurisdiction should not change basic event assembly structure.

So the same normalized observation bundle should assemble the same base event,
even if downstream legal interpretation differs.

## Parser Preference

Portable deterministic extraction should rely on stable syntactic or structural
shapes, not regex soup or open-ended bag-of-words heuristics.

Preferred sources of normalized observations:

- subject-verb-object structures
- passive-agent structures
- prepositional targets
- temporal adjuncts
- negation
- modality

## Immediate Implication For Fact Intake

The fact-intake observation and event layers should:

- validate normalized predicate vocab centrally
- keep dictionaries/mappings outside the event assembler
- keep the assembler free of language- or jurisdiction-specific keyword logic
