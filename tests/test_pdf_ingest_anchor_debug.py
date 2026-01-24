from src import logic_tree
from src.pipeline import normalise
from src import pdf_ingest


def test_clause_anchor_dump_contains_wspa(native_title_nsw_doc, capsys):
    norm = normalise(native_title_nsw_doc.body)
    tokens = list(norm.tokens)
    tree = logic_tree.build(tokens, source_id="nsw-debug")
    spans = pdf_ingest._iter_clause_spans(tree, len(tokens))

    clause_works = []
    for span in spans:
        clause_refs = pdf_ingest._extract_clause_statutory_references(
            tokens, span, str(norm)
        )
        canonical = pdf_ingest._canonicalize_references(
            clause_refs, anchor_core_merge=True
        )
        works = {ref.work for ref in canonical if ref.work}
        clause_works.append(works)
        print(f"CLAUSE {len(clause_works)}")
        for work in sorted(works):
            print("  ", work)

    captured = capsys.readouterr()
    flattened = set().union(*clause_works)
    assert flattened, "Expected at least one extracted anchor"
    assert "western sydney parklands act 2006" in flattened
    assert "western sydney parklands act 2006" in captured.out
