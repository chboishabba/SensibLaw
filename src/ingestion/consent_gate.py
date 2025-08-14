import logging
from pathlib import Path
from typing import Any, Dict

from src.policy.opa_gateway import OPAGateway

logger = logging.getLogger(__name__)

# Compile the consent policy at import time
_POLICY_PATH = Path(__file__).resolve().parents[2] / "policies" / "consent.rego"
OPA_GATEWAY = OPAGateway(_POLICY_PATH)


class ConsentError(Exception):
    """Raised when cultural policy checks fail."""


def check_consent(record: Dict[str, Any]) -> None:
    """Evaluate cultural policies and consent before persisting a record.

    The record is evaluated against the compiled Rego policies via
    :class:`OPAGateway`.  If the policy decision is ``deny`` a
    :class:`ConsentError` is raised to block persistence or transmission.
    When consent is present, a receipt is logged.
    """

    if not OPA_GATEWAY.is_allowed(record):
        logger.warning(
            "Blocked record %s due to missing consent",
            record.get("metadata", {}).get("citation"),
        )
        raise ConsentError("Consent required for records with cultural flags")

    if record.get("consent"):
        logger.info(
            "Consent receipt for record %s: %s",
            record.get("metadata", {}).get("citation"),
            record.get("consent_receipt", "consent granted"),
        )
