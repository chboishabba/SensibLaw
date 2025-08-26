import logging
from pathlib import Path
from typing import Any, Dict

from src.policy.engine import CulturalFlags, PolicyEngine

logger = logging.getLogger(__name__)

SUMMARY_NOTE = "Summary: content withheld due to cultural policy."

DEFAULT_POLICY = {
    "if": "SACRED_DATA",
    "then": "require",
    "else": "allow",
}

_engine = PolicyEngine(DEFAULT_POLICY)

from src.policy.opa_gateway import OPAGateway

logger = logging.getLogger(__name__)

# Compile the consent policy at import time
_POLICY_PATH = Path(__file__).resolve().parents[2] / "policies" / "consent.rego"
OPA_GATEWAY = OPAGateway(_POLICY_PATH)


class ConsentError(Exception):
    """Raised when cultural policy checks fail."""


def check_consent(record: Dict[str, Any]) -> None:
    """Evaluate cultural flags and consent before persisting a record."""

    flags = []
    for name in record.get("cultural_flags", []):
        try:
            flags.append(CulturalFlags[name.upper()])
        except KeyError:
            continue
    action = _engine.evaluate(flags)

    storage_consent = record.get("storage_consent", record.get("consent", False))
    inference_consent = record.get("inference_consent", record.get("consent", False))
    record["consent"] = storage_consent and inference_consent
    citation = record.get("metadata", {}).get("citation")

    if record.get("consent_required") and not (storage_consent and inference_consent):
        logger.warning(
            "Blocked record %s due to missing consent", citation
        )
        raise ConsentError("Consent required for records with cultural flags")

    if action == "deny":
        logger.warning("Blocked record %s by policy", citation)
        raise ConsentError("Consent required for records with cultural flags")

    if action == "require" and not (storage_consent and inference_consent):
        record["body"] = SUMMARY_NOTE
        logger.warning(
            "Missing consent for record %s; storing summary only", citation
        )
        return

    if action == "transform":
        record["body"] = SUMMARY_NOTE
        logger.info("Transformed record %s per policy", citation)
        return
    if not OPA_GATEWAY.is_allowed(record):
        logger.warning(
            "Blocked record %s due to missing consent",
            record.get("metadata", {}).get("citation"),
        )
        raise ConsentError("Consent required for records with cultural flags")

    if storage_consent and inference_consent:
        receipt = record.get("consent_receipt")
        if receipt:
            logger.info(
                "Consent receipt for record %s: %s",
                citation,
                receipt,
            )
        else:
            logger.info(
                "Consent receipt for record %s: consent granted",
                citation,
            )
