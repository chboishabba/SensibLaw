import json
import sys
import os
from pathlib import Path

# Add SensibLaw to path
SL_ROOT = Path(__file__).parent.parent
sys.path.append(str(SL_ROOT / "src"))

try:
    from sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans
except ImportError:
    # Handle direct-path variant if needed
    sys.path.append(str(SL_ROOT))
    from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans

def quote(s):
    return '"' + str(s).replace('"', '\\"') + '"'

def safe_node(s):
    # For Zelph atoms, let's use a simpler unique ID to avoid collisions
    # on things like '.' and '/' which both became '_'
    # We'll use lex_ + hex representation of the string.
    hex_id = s.encode('utf-8').hex()
    return f"lex_{hex_id}"

def build_cons_list(tokens):
    if not tokens:
        return "nil"
    # tokens is a list of node names
    # Zelph list syntax: <node1 node2 node3>
    return "<" + " ".join(tokens) + ">"

def process_revision(rev):
    facts = []
    comment = rev.get("comment", "")
    revid = rev.get("revid")
    author = rev.get("user", "unknown")
    
    rev_node = f"rev_{revid}"
    facts.append(f'{rev_node} "is a" "wikipedia revision"')
    facts.append(f'{rev_node} "by user" {quote(author)}')
    
    # Lex the comment
    spans = tokenize_canonical_with_spans(comment)
    lexeme_nodes = []
    for text, start, end in spans:
        node = safe_node(text)
        lexeme_nodes.append(node)
        # Define the lexeme node itself
        facts.append(f'{node} "has text" {quote(text)}')
        facts.append(f'{node} "kind" "lexeme"')
        
    # Link the revision to its comment-phrase
    phrase = build_cons_list(lexeme_nodes)
    facts.append(f'{rev_node} "has comment" {phrase}')
    
    return facts

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 lex_to_zelph.py <wiki_json> <output.zlp>")
        sys.exit(1)
        
    wiki_path = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    with open(wiki_path, "r") as f:
        data = json.load(f)
        
    all_facts = [
        "# AUTOMATED LEXICAL GRAPH FROM WIKIPEDIA TEST SURFACE",
        f'# Article: {data.get("title")}',
        "",
    ]
    
    # Link article to Wikidata (let's pretend we have the mapping or pick a known one)
    article_title = data.get("title")
    all_facts.append(f'{quote(article_title)} "is a" "wikipedia article"')
    
    for rev in data.get("rows", []):
        all_facts.extend(process_revision(rev))
        all_facts.append("")
        
    with open(output_file, "w") as f:
        f.write("\n".join(all_facts))
        
    print(f"Successfully lexed {len(data.get('rows', []))} revisions into {output_file}")

if __name__ == "__main__":
    main()
