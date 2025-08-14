import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.policy.opa_gateway import OPAGateway
from src.ingestion.consent_gate import ConsentError, check_consent

POLICY_PATH = ROOT / "policies" / "consent.rego"


def test_deny_without_consent():
    gateway = OPAGateway(POLICY_PATH)
    record = {
        "metadata": {"citation": "case:1"},
        "cultural_flags": ["sacred"],
    }
    assert gateway.is_allowed(record) is False
    with pytest.raises(ConsentError):
        check_consent(record)


def test_allow_with_consent():
    gateway = OPAGateway(POLICY_PATH)
    record = {
        "metadata": {"citation": "case:2"},
        "cultural_flags": ["sacred"],
        "consent": True,
        "consent_receipt": "granted",
    }
    assert gateway.is_allowed(record) is True
    # Should not raise
    check_consent(record)
