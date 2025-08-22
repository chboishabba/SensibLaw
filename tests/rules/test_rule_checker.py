from src.rules.checker import check_event


def test_rule_breach_detected():
    event = {"type": "unauthorised_access"}
    result = check_event(event)
    assert result["breach"] is True
    assert "unauthorised_access" in result["rules_broken"]
    assert result["details"]


def test_no_rule_breach():
    event = {"type": "something_else"}
    result = check_event(event)
    assert result == {"breach": False, "rules_broken": [], "details": []}
