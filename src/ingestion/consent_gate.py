import logging
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

    if storage_consent and inference_consent:
        logger.info(
            "Consent receipt for record %s: %s",
            citation,
            record.get("consent_receipt", "consent granted"),
        )
