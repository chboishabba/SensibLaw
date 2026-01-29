# Why SensibLaw Does Not Reason

This system is deliberately non-reasoning. That choice is architectural, ethical, and practical.

## What “reasoning” means here

For SensibLaw, reasoning includes:
- Drawing conclusions not explicitly stated in source text
- Resolving conflicts, precedence, or hierarchy
- Determining compliance, breach, or legality
- Inferring intent, purpose, or effect
- Ranking or weighting obligations or authorities

None of these are performed in this system.

## Why this boundary exists

1. Legal meaning is adversarial. Legal conclusions are contested positions; encoding them as facts collapses debate into assertion.
2. Reasoning destroys reproducibility. Two lawyers can reasonably disagree; a deterministic system must not silently choose between them.
3. Trust precedes power. A system that explains what is there earns trust. A system that explains what it means must earn authority. SensibLaw chooses trust.

## What SensibLaw does instead

- Extracts textually grounded obligations
- Preserves identity and provenance
- Surfaces explicit relationships only
- Enables human review and annotation
- Freezes semantics behind versioned schemas

This makes it a microscope, not a judge.

## How reasoning may exist (elsewhere)

Reasoning is allowed only if:
- It lives in a separate, versioned subsystem
- Outputs are explicitly labeled as speculative
- Humans are always in the loop
- Core payloads remain unchanged
- Removal of reasoning leaves identical hashes

If these conditions are not met, reasoning must not be added.

## Summary

SensibLaw does not reason because:

> Correctness without authority is better than authority without correctness.

If reasoning is required, build it on top, not inside.
