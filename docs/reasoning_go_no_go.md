# Reasoning Go/No-Go Checklist

Default stance: **NO**. Only cross into reasoning when every “Go” condition is satisfied and no “No-Go” flag is present.

## Go only if ALL are true
- Reasoning lives in a separate package/repo (e.g., `sensiblaw-interpretation`), never mixed into core.
- Outputs are explicitly labeled **interpretive/hypothetical** and versioned separately (`interpretation.v0.*`).
- Core payloads remain read-only; removing the interpretation layer leaves all core hashes and behavior unchanged.
- Multiple contradictory outcomes are acceptable and surfaced to users.
- Assumptions are first-class in every result.
- UI/exports clearly mark interpretive content; users cannot confuse it with core facts.

## Immediate No-Go flags
- Pressure to change any core `*.v1` schema.
- Pressure to emit compliance/breach/precedence in core payloads.
- Plans to “upgrade” core payloads with reasoning outputs.
- Inability to show or remove assumptions, or to tolerate multiple outcomes.

## If Go, enforce guardrails
- Import-boundary tests: interpretation code cannot mutate or depend on core internals.
- Disclaimers required in every interpretive payload and render.
- Interpretive outputs are optional and discardable in all workflows.
