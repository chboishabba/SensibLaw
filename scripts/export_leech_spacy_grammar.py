#!/usr/bin/env python3
"""Export original, CLOSED numeric spaCy observations for Leech grammar probes.

Example:
    python -m scripts.export_leech_spacy_grammar \
      --database-url "$DATABASE_URL" \
      --manifest /tmp/x369_original_source_manifest.json \
      --output /tmp/x369_slr_original_train_dev.jsonl

Manifest (list of records):
  {"run_ref":"...", "document_ref":"...", "split":"train"|"development",
   "source_path":"/path/to/original/utf8.txt",
   "source_sha256":"64 hex chars"}

Requires original source on disk and a complete SLR PostgreSQL parser run.
Never runs spaCy; never exports reserved/F5 rows; never promotes PNF to truth.
The output is a source-containing JSONL file: handle as original corpus data.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from src.pnf.leech_grammar_source_export import query_leech_grammar_observation


def export_manifest(*, database_url:str, manifest:Path, output:Path) -> dict:
    if output.exists() or output.with_suffix(output.suffix+".tmp").exists():
        raise FileExistsError("source output or temporary export already exists")
    entries=json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(entries,list) or not entries:
        raise ValueError("nonempty source manifest list required")
    validated=[]
    ids=set()
    hashes={}
    for item in entries:
        if not isinstance(item,dict):
            raise ValueError("manifest entry must be an original source object")
        split=item.get("split")
        if split not in ("train","development"):
            raise ValueError("reserved/test/F5 source not exportable")
        ref=item.get("document_ref")
        run=item.get("run_ref")
        src=item.get("source_path")
        expected_sha=item.get("source_sha256")
        if (not isinstance(ref,str) or not ref or
            not isinstance(run,str) or not run or
            not isinstance(src,str) or not src or
            not isinstance(expected_sha,str) or len(expected_sha)!=64 or
            any(c not in "0123456789abcdef" for c in expected_sha)):
            raise ValueError("original run/document/path/SHA256 receipt required")
        if ref in ids:
            raise ValueError("duplicate original document across manifest")
        ids.add(ref)
        raw=Path(src).read_bytes()
        try: text=raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("source text is not UTF-8") from e
        actual_sha=hashlib.sha256(raw).hexdigest()
        if actual_sha!=expected_sha:
            raise ValueError("original source file digest mismatch")
        if actual_sha in hashes and hashes[actual_sha]!=split:
            raise ValueError("duplicate source bytes across train/development")
        hashes[actual_sha]=split
        validated.append((run,ref,split,text,actual_sha))
    # Finish global source/split/F5 validation BEFORE the first DB access.
    # A late forbidden F5 row must not trigger earlier parser reads.
    if {split for _,_,split,_,_ in validated}!={"train","development"}:
        raise ValueError("train and development original documents required")
    documents=[]
    for run,ref,split,text,actual_sha in validated:
        exported=query_leech_grammar_observation(
            database_url=database_url,run_ref=run,document_ref=ref,
            split=split,source_text=text)
        if exported["source_sha256"]!=actual_sha:
            raise AssertionError("database source digest diverged after export")
        documents.append(exported)
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(output.suffix+".tmp")
    try:
        with tmp.open("x",encoding="utf-8") as fp:
            for row in documents:
                fp.write(json.dumps(row,ensure_ascii=False,sort_keys=True,
                                    separators=(",",":"))+"\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp,output)
    finally:
        if tmp.exists():tmp.unlink()
    return dict(schema="slr.numeric_spacy.leech_grammar.export_manifest.v1",
                output=str(output),output_sha256=hashlib.sha256(
                    output.read_bytes()).hexdigest(),
                train_documents=sum(x["split"]=="train" for x in documents),
                development_documents=sum(
                    x["split"]=="development" for x in documents),
                reserved_F5_documents_exported=0,
                world_truth_or_semantic_admission_promoted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database-url",default=os.environ.get("DATABASE_URL"),
        help="database URL; defaults to DATABASE_URL environment (not argv)")
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if not args.database_url:
        p.error("DATABASE_URL env or explicit --database-url required")
    print(json.dumps(export_manifest(
        database_url=args.database_url,manifest=args.manifest,
        output=args.output),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
