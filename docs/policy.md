# Policy Engine

The policy engine evaluates content flagged with ``CulturalFlags`` against JSON
policies. Each policy contains a list of rules mapping a flag to an action. The
supported actions are:

- ``allow`` – content passes through unchanged.
- ``deny`` – content is rejected.
- ``transform`` – content should be transformed by an inference layer.
- ``log`` – content is recorded by a storage layer for auditing.

## Example: SacredDataGuard

```json
{
  "name": "SacredDataGuard",
  "rules": [
    {"flag": "SACRED_DATA", "action": "deny"},
    {"flag": "PERSONALLY_IDENTIFIABLE_INFORMATION", "action": "log"}
  ],
  "default": "allow"
}
```

```python
from src.policy.engine import CulturalFlags, PolicyEngine

policy_json = """
{
  "name": "SacredDataGuard",
  "rules": [
    {"flag": "SACRED_DATA", "action": "deny"},
    {"flag": "PERSONALLY_IDENTIFIABLE_INFORMATION", "action": "log"}
  ],
  "default": "allow"
}
"""

logs = []

def storage_hook(flag, action):
    logs.append((flag, action))

engine = PolicyEngine.from_json(policy_json, storage_hook=storage_hook)
result = engine.evaluate({CulturalFlags.SACRED_DATA})
assert result == "deny"
assert logs == [(CulturalFlags.SACRED_DATA, "deny")]
```
