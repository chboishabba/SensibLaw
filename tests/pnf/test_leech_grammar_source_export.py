"""Original SLR numeric-spaCy grammar export contract and Leech handoff.

No live PostgreSQL or TinyStories source is fabricated here: these are
bounded source-row and manifest failure/control fixtures. A physical export
requires the genuine original parser execution database and source files.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.pnf.leech_grammar_source_export import (
    SCHEMA,build_leech_grammar_observation)
from scripts.export_leech_spacy_grammar import export_manifest


def rows(source="Lily saw Max.",run="run:1",doc="story:1",
         split="train",sentence_id=17):
    raw=source.encode("utf-8")
    # Same number of Unicode codepoints and identical 4/3/3/1 lexical spans.
    token_spans=[(0,4),(5,8),(9,12),(12,13)]
    source_rows=[("source:1",sha256(raw).digest(),len(raw),
                  "utf8-canonical-source:v1")]
    coverage=[("complete",1,1,0,True,True,True)]
    partitions=[("partition:1","parser:strict:1","completed",
                 sha256(b"parser receipt").digest(),"en_core_web_sm","3.x")]
    tokens=[(101+i,start,end,201+i,301+i,401+i,102,
             sentence_id,sha256(f"token:{i}".encode()).digest(),2)
            for i,(start,end) in enumerate(token_spans)]
    return dict(run_ref=run,document_ref=doc,split=split,
                source_text=source,source_rows=source_rows,
                coverage_rows=coverage,partition_rows=partitions,
                token_rows=tokens)


class TestNumericGrammarSourceReceipt(unittest.TestCase):
    def test_real_row_contract_is_deterministic_and_not_world_authority(self):
        item=rows()
        first=build_leech_grammar_observation(**item)
        second=build_leech_grammar_observation(**item)
        self.assertEqual(first,second)
        self.assertEqual(first["schema_version"],SCHEMA)
        self.assertEqual(first["source_sha256"],
                         sha256(item["source_text"].encode()).hexdigest())
        self.assertEqual(first["slr_tokens"][0]["token_id"],101)
        self.assertEqual(first["slr_tokens"][0]["head_token_id"],102)
        self.assertTrue(first["world_resolution_deferred"])
        self.assertFalse(first["parser_observation_is_semantic_authority"])
        self.assertEqual(len(first["parser_receipt_sha256"]),64)
        self.assertEqual(first["visibility"],"full_context")

    def test_unicode_byte_sha_but_character_positions(self):
        item=rows(source="Élie saw Max.")  # É has two UTF-8 bytes
        result=build_leech_grammar_observation(**item)
        self.assertEqual(result["slr_tokens"][0]["end_char"],4)
        self.assertEqual(len(item["source_text"].encode()),len(item["source_text"])+1)
        self.assertEqual(result["source_sha256"],sha256(
            item["source_text"].encode()).hexdigest())
        item["source_text"]="Elie saw Max."
        with self.assertRaisesRegex(ValueError,"source bytes"):
            build_leech_grammar_observation(**item)

    def test_fails_closed_reserved_missing_source_or_incomplete_parser(self):
        base=rows()
        for split in ("test","reserved","F5","validation"):
            bad=dict(base,split=split)
            with self.assertRaisesRegex(ValueError,"train/development"):
                build_leech_grammar_observation(**bad)
        bad=dict(base,coverage_rows=[("open",1,0,1,True,True,True)])
        with self.assertRaisesRegex(ValueError,"coverage"):
            build_leech_grammar_observation(**bad)
        bad=dict(base,source_rows=[])
        with self.assertRaisesRegex(ValueError,"one original source"):
            build_leech_grammar_observation(**bad)
        bad=dict(base,partition_rows=[(
            "p","contract","completed",None,"en_core_web_sm","3.x")])
        with self.assertRaisesRegex(ValueError,"receipt"):
            build_leech_grammar_observation(**bad)

    def test_parser_contract_and_head_must_be_source_local(self):
        base=rows()
        changed=list(base["token_rows"])
        changed[0]=(*changed[0][:6],999,*changed[0][7:])
        with self.assertRaisesRegex(ValueError,"same original sentence"):
            build_leech_grammar_observation(**dict(base,token_rows=changed))
        changed=list(base["token_rows"])
        changed[3]=(*changed[3][:7],18,*changed[3][8:])
        with self.assertRaisesRegex(ValueError,"same original sentence"):
            build_leech_grammar_observation(**dict(base,token_rows=changed))
        changed=list(base["token_rows"])
        changed[0]=(*changed[0][:3],None,*changed[0][4:])
        with self.assertRaisesRegex(ValueError,"capability"):
            build_leech_grammar_observation(**dict(base,token_rows=changed))
        bad=dict(base,partition_rows=[
            base["partition_rows"][0],
            ("partition:2","different-parser","completed",
             sha256(b"2").digest(),"en_core_web_sm","3.x")],
            coverage_rows=[("complete",2,2,0,True,True,True)])
        with self.assertRaisesRegex(ValueError,"mixed parser"):
            build_leech_grammar_observation(**bad)

    def test_overlapping_or_duplicate_occurrences_rejected(self):
        base=rows()
        changed=list(base["token_rows"])
        row=changed[1]
        changed[1]=(row[0],3,row[2],*row[3:])
        with self.assertRaisesRegex(ValueError,"source-ordered"):
            build_leech_grammar_observation(**dict(base,token_rows=changed))
        changed=list(base["token_rows"])
        row=changed[1]
        changed[1]=(101,*row[1:])
        with self.assertRaisesRegex(ValueError,"duplicate"):
            build_leech_grammar_observation(**dict(base,token_rows=changed))

    @staticmethod
    def fake_db_export(*,database_url,run_ref,document_ref,split,source_text):
        return build_leech_grammar_observation(**rows(
            source=source_text,run=run_ref,doc=document_ref,split=split))

    def test_manifest_emits_exact_jsonl_only_for_train_development(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            paths=[root/"train.txt",root/"development.txt"]
            sources=["Lily saw Max.","Anna saw Eli."]
            manifest=[]
            for index,(path,source) in enumerate(zip(paths,sources)):
                path.write_text(source,encoding="utf-8")
                manifest.append(dict(run_ref="run:1",
                    document_ref=f"original:{index}",
                    split="train" if index==0 else "development",
                    source_path=str(path),
                    source_sha256=sha256(path.read_bytes()).hexdigest()))
            manifest_path=root/"manifest.json"
            manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
            target=root/"export.jsonl"
            with patch("scripts.export_leech_spacy_grammar.query_leech_grammar_observation",
                       side_effect=self.fake_db_export):
                receipt=export_manifest(database_url="ignored",manifest=manifest_path,
                                        output=target)
            self.assertEqual(receipt["train_documents"],1)
            self.assertEqual(receipt["development_documents"],1)
            data=[json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual({row["split"] for row in data},{"train","development"})
            self.assertFalse(any(row["parser_observation_is_semantic_authority"]
                                 for row in data))
            self.assertEqual(sha256(target.read_bytes()).hexdigest(),
                             receipt["output_sha256"])
            with self.assertRaises(FileExistsError):
                export_manifest(database_url="ignored",manifest=manifest_path,
                                output=target)

    def test_manifest_source_cross_split_duplicate_and_reserved_refused(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source=root/"story.txt"
            source.write_text("Lily saw Max.",encoding="utf-8")
            digest=sha256(source.read_bytes()).hexdigest()
            original=dict(run_ref="run:1",document_ref="original:1",
                split="train",source_path=str(source),source_sha256=digest)
            follow=dict(original,document_ref="original:2",
                        split="development")
            manifest=root/"m.json"
            manifest.write_text(json.dumps([original,follow]))
            with self.assertRaisesRegex(ValueError,"across train/development"):
                export_manifest(database_url="ignored",manifest=manifest,
                                output=root/"out.jsonl")
            follow["split"]="reserved"
            manifest.write_text(json.dumps([original,follow]))
            with self.assertRaisesRegex(ValueError,"reserved/test/F5"):
                export_manifest(database_url="ignored",manifest=manifest,
                                output=root/"out.jsonl")


if __name__=="__main__":
    unittest.main()
