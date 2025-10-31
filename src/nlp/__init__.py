"""NLP utilities for statutory rule extraction."""

from .rules import (
    RuleMatchResult,
    RuleMatcher,
    create_rule_matcher,
    get_rule_matcher,
)

__all__ = ["RuleMatcher", "RuleMatchResult", "create_rule_matcher", "get_rule_matcher"]
