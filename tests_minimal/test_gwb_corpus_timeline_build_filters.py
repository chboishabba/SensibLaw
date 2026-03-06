import os
import runpy
import unittest


class TestGwbCorpusTimelineBuildFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cls.mod = runpy.run_path(os.path.join(repo_root, "SensibLaw", "scripts", "gwb_corpus_timeline_build.py"))

    def test_collapse_ws_no_regex(self):
        collapse = self.mod["_collapse_ws"]
        self.assertEqual(collapse(" a\tb\nc  "), "a b c")
        self.assertEqual(collapse(""), "")

    def test_is_tocish_contents_with_many_numbers(self):
        is_tocish = self.mod["_is_tocish"]
        s = "CONTENTS INTRODUCTION 1 Quitting 2 Running 3 Personnel 4 Stem Cells 5 Day of Fire 6"
        self.assertTrue(is_tocish(s))

    def test_is_tocish_plain_sentence(self):
        is_tocish = self.mod["_is_tocish"]
        s = "On the recommendation of Karl Rove, I met with more than a dozen historians."
        self.assertFalse(is_tocish(s))

    def test_is_tocish_empty(self):
        is_tocish = self.mod["_is_tocish"]
        self.assertTrue(is_tocish("   "))


if __name__ == "__main__":
    unittest.main()

