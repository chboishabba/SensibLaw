import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

SENSITIVE_FLAGS = {"sacred", "restricted", "no_store", "no_share"}


class ConsentError(Exception):
    """Raised when cultural policy checks fail."""


def check_consent(record: Dict[str, Any]) -> None:
    """Evaluate cultural flags and consent before persisting a record.

    If the record contains any cultural flags deemed sensitive, consent must be
    explicitly granted via the ``consent`` field. A consent receipt is logged
    on success, otherwise a :class:`ConsentError` is raised to block persistence
    or transmission.
    """

    flags = set(record.get("cultural_flags", []))
    if flags & SENSITIVE_FLAGS:
        if not record.get("consent"):
            logger.warning(
                "Blocked record %s due to missing consent", record.get("metadata", {}).get("citation")
            )
            raise ConsentError("Consent required for records with cultural flags")
        logger.info(
            "Consent receipt for record %s: %s",
            record.get("metadata", {}).get("citation"),
            record.get("consent_receipt", "consent granted"),
        )
