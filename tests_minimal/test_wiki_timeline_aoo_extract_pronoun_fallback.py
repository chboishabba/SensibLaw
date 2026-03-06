import json
import os
import subprocess
import sys
import tempfile
import unittest


class TestWikiTimelineAooExtractPronounFallback(unittest.TestCase):
    def _run_extract(self, timeline_events):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        script = os.path.join(repo_root, "SensibLaw", "scripts", "wiki_timeline_aoo_extract.py")

        with tempfile.TemporaryDirectory() as td:
            tl_path = os.path.join(td, "tl.json")
            cand_path = os.path.join(td, "candidates.json")
            out_path = os.path.join(td, "out.json")

            payload = {
                "generated_at": "2026-02-14T00:00:00Z",
                "snapshot": {"source_id": "source:test", "title": "test", "path": "SensibLaw/demo/ingest/gwb/TEST"},
                "events": timeline_events,
            }
            with open(tl_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            with open(cand_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

            cmd = [
                sys.executable,
                script,
                "--timeline",
                tl_path,
                "--candidates",
                cand_path,
                "--out",
                out_path,
                "--no-spacy",
                "--no-db",
                "--max-events",
                "50",
            ]
            # Keep test output clean; surface full extractor output only on failure.
            proc = subprocess.run(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if proc.returncode != 0:
                raise RuntimeError(f"extractor failed ({proc.returncode}):\n{proc.stdout}")

            with open(out_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def test_first_person_injects_root_actor_subject(self):
        out = self._run_extract(
            [
                {
                    "event_id": "ev:0001",
                    "section": "Corpus doc: Decision Points",
                    "title": "Decision Points",
                    "path": "SensibLaw/demo/ingest/gwb/DecisionPoints.epub",
                    "root_actor": "George W. Bush",
                    "root_surname": "Bush",
                    "anchor": {"year": 2026, "month": 2, "day": 14, "precision": "day", "text": "2026-02-14", "kind": "ingest"},
                    "text": "In the final year of my presidency, I began to think seriously about writing my memoirs.",
                    "links": [],
                }
            ]
        )
        ev = next(e for e in out["events"] if e.get("event_id") == "ev:0001")
        actors = ev.get("actors") or []
        self.assertTrue(any(a.get("resolved") == "George W. Bush" and a.get("role") == "subject" for a in actors))
        self.assertTrue(any(a.get("resolved") == "George W. Bush" and a.get("source") == "surface_pronoun" for a in actors))

    def test_no_first_person_does_not_inject_root_actor_subject(self):
        out = self._run_extract(
            [
                {
                    "event_id": "ev:0002",
                    "section": "Corpus doc: Decision Points",
                    "title": "Decision Points",
                    "path": "SensibLaw/demo/ingest/gwb/DecisionPoints.epub",
                    "root_actor": "George W. Bush",
                    "root_surname": "Bush",
                    "anchor": {"year": 2026, "month": 2, "day": 14, "precision": "day", "text": "2026-02-14", "kind": "ingest"},
                    "text": "The historians suggested that the president should write memoirs.",
                    "links": [],
                }
            ]
        )
        ev = next(e for e in out["events"] if e.get("event_id") == "ev:0002")
        actors = ev.get("actors") or []
        self.assertFalse(any(a.get("source") == "surface_pronoun" for a in actors))


if __name__ == "__main__":
    unittest.main()
