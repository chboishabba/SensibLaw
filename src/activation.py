from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from src.obligation_identity import compute_identities
from src.obligations import LifecycleTrigger, ObligationAtom

FACT_ENVELOPE_VERSION = "fact.envelope.v1"
ACTIVATION_VERSION = "obligation.activation.v1"


@dataclass(frozen=True)
class Fact:
    """A declarative fact supplied by the user/system."""

    key: str
    value: Any
    at: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class FactEnvelope:
    """Container for facts used in activation simulation."""

    version: str
    issued_at: Optional[str]
    facts: List[Fact]


@dataclass(frozen=True)
class ActivationReason:
    trigger: str  # activation | termination
    text: str
    fact_key: str
    fact_value: Any


@dataclass(frozen=True)
class ActivationResult:
    version: str
    active: List[str]
    inactive: List[str]
    terminated: List[str]
    reasons: Mapping[str, List[ActivationReason]]


def _norm(val: Optional[str]) -> str:
    return (val or "").strip().lower()


def _fact_index(facts: Iterable[Fact]) -> Dict[str, Fact]:
    index: Dict[str, Fact] = {}
    for fact in facts:
        key = _norm(fact.key)
        if key:
            index[key] = fact
    return index


def _matches(trigger: LifecycleTrigger, fact_index: Mapping[str, Fact]) -> Optional[Fact]:
    trig = _norm(trigger.normalized or trigger.text)
    for fact_key, fact in fact_index.items():
        if not trig or not fact_key:
            continue
        if fact_key == trig or trig.startswith(fact_key) or fact_key.startswith(trig):
            return fact
    return None


def simulate_activation(
    obligations: Iterable[ObligationAtom],
    envelope: FactEnvelope,
    *,
    at: Optional[str] = None,
) -> ActivationResult:
    """Descriptive activation: only triggers that match fact keys activate/terminate."""

    fact_index = _fact_index(envelope.facts)
    identities = compute_identities(obligations)

    active: List[str] = []
    inactive: List[str] = []
    terminated: List[str] = []
    reasons: Dict[str, List[ActivationReason]] = {}

    for ob, identity in zip(obligations, identities):
        has_trigger = bool(ob.lifecycle)
        identity_hash = identity.identity_hash
        state = "inactive"

        # termination takes precedence if matching fact exists
        term_match: Tuple[LifecycleTrigger, Fact] | None = None
        for lc in ob.lifecycle:
            if lc.kind != "termination":
                continue
            fact = _matches(lc, fact_index)
            if fact:
                term_match = (lc, fact)
                break

        if term_match:
            lc, fact = term_match
            state = "terminated"
            reasons.setdefault(identity_hash, []).append(
                ActivationReason(trigger="termination", text=lc.text, fact_key=fact.key, fact_value=fact.value)
            )
        else:
            act_match: Tuple[LifecycleTrigger, Fact] | None = None
            for lc in ob.lifecycle:
                if lc.kind != "activation":
                    continue
                fact = _matches(lc, fact_index)
                if fact:
                    act_match = (lc, fact)
                    break
            if act_match:
                lc, fact = act_match
                state = "active"
                reasons.setdefault(identity_hash, []).append(
                    ActivationReason(trigger="activation", text=lc.text, fact_key=fact.key, fact_value=fact.value)
                )

        if not has_trigger:
            state = "inactive"

        if state == "active":
            active.append(identity_hash)
        elif state == "terminated":
            terminated.append(identity_hash)
        else:
            inactive.append(identity_hash)

    return ActivationResult(
        version=ACTIVATION_VERSION,
        active=active,
        inactive=inactive,
        terminated=terminated,
        reasons=reasons,
    )


def activation_to_payload(result: ActivationResult) -> dict:
    """Serialise ActivationResult to deterministic, snapshot-friendly payload."""

    def _reason_dict(reason: ActivationReason) -> dict:
        return {
            "trigger": reason.trigger,
            "text": reason.text,
            "fact_key": reason.fact_key,
            "fact_value": reason.fact_value,
        }

    return {
        "version": result.version,
        "active": sorted(result.active),
        "inactive": sorted(result.inactive),
        "terminated": sorted(result.terminated),
        "reasons": {
            identity: [_reason_dict(r) for r in sorted(reason_list, key=lambda x: (x.trigger, x.text, x.fact_key))]
            for identity, reason_list in sorted(result.reasons.items(), key=lambda kv: kv[0])
        },
    }


__all__ = [
    "FACT_ENVELOPE_VERSION",
    "ACTIVATION_VERSION",
    "Fact",
    "FactEnvelope",
    "ActivationReason",
    "ActivationResult",
    "simulate_activation",
    "activation_to_payload",
]
