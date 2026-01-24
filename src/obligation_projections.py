from __future__ import annotations

from typing import Dict, Iterable, List

from src.obligations import ObligationAtom, obligation_to_dict


def actor_view(obligations: Iterable[ObligationAtom]) -> List[Dict]:
    bucket: Dict[str, List[ObligationAtom]] = {}
    for ob in obligations:
        if ob.actor:
            text = ob.actor.text.lower().strip()
            actor = text if text else ob.actor.normalized
        else:
            actor = "unknown"
        bucket.setdefault(actor, []).append(ob)
    return [
        {
            "actor": actor,
            "obligations": [obligation_to_dict(ob) for ob in sorted(obs, key=lambda o: o.clause_id)],
        }
        for actor, obs in sorted(bucket.items(), key=lambda kv: kv[0])
    ]


def action_view(obligations: Iterable[ObligationAtom]) -> List[Dict]:
    bucket: Dict[str, List[ObligationAtom]] = {}
    for ob in obligations:
        action = ob.action.normalized if ob.action else "unknown"
        bucket.setdefault(action, []).append(ob)
    return [
        {
            "action": action,
            "obligations": [obligation_to_dict(ob) for ob in sorted(obs, key=lambda o: o.clause_id)],
        }
        for action, obs in sorted(bucket.items(), key=lambda kv: kv[0])
    ]


def clause_view(obligations: Iterable[ObligationAtom]) -> List[Dict]:
    return [
        obligation_to_dict(ob) for ob in sorted(obligations, key=lambda o: o.clause_id)
    ]


def timeline_view(obligations: Iterable[ObligationAtom]) -> List[Dict]:
    # ordered by clause_id; lifecycle data stays descriptive
    out: List[Dict] = []
    for ob in sorted(obligations, key=lambda o: o.clause_id):
        out.append(
            {
                "clause_id": ob.clause_id,
                "modality": ob.modality,
                "action": ob.action.normalized if ob.action else None,
                "lifecycle": [
                    {"kind": lc.kind, "normalized": lc.normalized, "text": lc.text}
                    for lc in sorted(ob.lifecycle, key=lambda l: (l.kind, l.normalized))
                ],
            }
        )
    return out


__all__ = ["actor_view", "action_view", "clause_view", "timeline_view"]
