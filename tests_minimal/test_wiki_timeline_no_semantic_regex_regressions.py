import re
import unittest
from pathlib import Path


class TestWikiTimelineNoSemanticRegexRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script_path = Path(__file__).resolve().parents[1] / "scripts" / "wiki_timeline_aoo_extract.py"
        cls.src = cls.script_path.read_text(encoding="utf-8")

    def test_reported_subject_regex_injector_not_present(self) -> None:
        self.assertNotIn("REPORTED_SUBJECT_RE", self.src)
        self.assertNotIn("reported_subject_re", self.src.lower())

    def test_reported_cautioned_sentence_family_regex_branch_not_present(self) -> None:
        self.assertIsNone(re.search(r're\.search\(r"[^"\n]*\\breported\\b[^"\n]*",\s*parse_text', self.src))
        self.assertIsNone(re.search(r're\.search\(r"[^"\n]*\\bcautioned\\b[^"\n]*",\s*parse_text', self.src))

    def test_dependency_chain_path_is_present(self) -> None:
        self.assertIn("DEFAULT_COMMUNICATION_CHAIN_CONFIG", self.src)
        self.assertIn("_extract_communication_chain_steps", self.src)
        self.assertIn("_profile_communication_chain_config", self.src)

    def test_requester_and_by_agent_are_dependency_first_with_fallbacks(self) -> None:
        self.assertIn("_extract_requester_from_doc", self.src)
        self.assertIn("_extract_passive_agents_from_doc", self.src)
        self.assertIn("fallback_requester_regex", self.src)
        self.assertIn("fallback_by_agent_regex", self.src)

    def test_leading_determiner_normalization_is_not_regex_based(self) -> None:
        m = re.search(
            r"def _strip_leading_determiner\(text: str\) -> str:\n(?P<body>(?:    .*\n){1,20})",
            self.src,
        )
        self.assertIsNotNone(m)
        body = m.group("body")  # type: ignore[union-attr]
        self.assertNotIn("re.", body)


if __name__ == "__main__":
    unittest.main()
