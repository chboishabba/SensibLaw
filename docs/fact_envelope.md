# FactEnvelope and Activation (Sprint 7 Track A)

Purpose: describe the payloads and guardrails for descriptive, fact-driven activation without compliance reasoning.

## FactEnvelope (`fact.envelope.v1`)

```jsonc
{
  "version": "fact.envelope.v1",
  "issued_at": "2026-01-29T00:00:00Z",
  "facts": [
    {
      "key": "upon commencement",
      "value": true,
      "at": "2026-01-29T00:00:00Z",
      "source": "user"
    }
  ]
}
```

Rules:
- Facts are declarative; no defaults. Missing fact = unknown.
- Keys are free text; activation only occurs when a key matches explicit lifecycle trigger text.
- Time is optional and explicit; no “now” inference.

## ActivationResult (`obligation.activation.v1`)

```jsonc
{
  "version": "obligation.activation.v1",
  "active": ["<identity_hash>"],
  "inactive": ["<identity_hash>"],
  "terminated": ["<identity_hash>"],
  "reasons": {
    "<identity_hash>": [
      {
        "trigger": "activation|termination",
        "text": "upon commencement",
        "fact_key": "upon commencement",
        "fact_value": true
      }
    ]
  }
}
```

Rules:
- Identity hashes are unchanged (computed from obligations).
- No compliance labels (“compliant”, “violation”, etc.).
- No inferred facts; only exact fact-key matches to lifecycle trigger text activate or terminate.
- If no trigger text exists, obligations remain inactive regardless of facts.

## Guardrails
- ❌ No compliance judgment.
- ❌ No inferred edges or default truths.
- ✅ Activation/termination are additive metadata; obligation identity and payloads remain untouched.
- ✅ Deterministic ordering of lists for snapshotting.

## Test expectations (red flags)
- Missing fact ⇒ inactive.
- No trigger text ⇒ inactive even with facts.
- Activation never mutates identity.
- Compliance language absent from results.
- Termination only when a termination trigger text matches a provided fact.
