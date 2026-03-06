import importlib
import os
import sys


def _reload_with_env(env_value: str | None):
    """Reload lexeme_index with a specific env value."""
    module_name = "src.text.lexeme_index"
    if module_name in sys.modules:
        del sys.modules[module_name]
    if env_value is None:
        os.environ.pop("ITIR_LEXEME_TOKENIZER_MODE", None)
    else:
        os.environ["ITIR_LEXEME_TOKENIZER_MODE"] = env_value
    return importlib.import_module(module_name)


def test_default_mode_is_deterministic():
    mod = _reload_with_env(None)
    profile = mod.get_tokenizer_profile()
    assert profile["canonical_mode"] == "deterministic_legal"
    assert profile["canonical_tokenizer_id"] == mod.LEXEME_TOKENIZER_ID


def test_legacy_env_switches_to_regex():
    mod = _reload_with_env("legacy_regex")
    profile = mod.get_tokenizer_profile()
    assert profile["canonical_mode"] == "legacy_regex"
    assert profile["canonical_tokenizer_id"] == "regex_legacy_v1"

