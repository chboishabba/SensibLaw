import pytest
from src.zelph_bridge import (
    _fact_node_id,
    _quote_zelph_text,
    workbench_to_zelph_facts,
    _native_rule_triples,
    enrich_workbench_with_zelph,
)

def test_fact_node_id():
    assert _fact_node_id("f1") == "fact_f1"
    assert _fact_node_id("doc:123-abc") == "fact_doc_123_abc"
    assert _fact_node_id(None) == "fact_unknown"

def test_quote_zelph_text():
    assert _quote_zelph_text("hello") == '"hello"'
    assert _quote_zelph_text('he"llo') == '"he\\"llo"'
    assert _quote_zelph_text(123) == '"123"'

def test_workbench_to_zelph_facts_basic():
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"],
                "signal_classes": ["volatility_signal"],
                "statement_texts": ["Revision by Alice: Fixed typo"]
            }
        ],
        "observations": []
    }
    
    facts_str = workbench_to_zelph_facts(workbench)
    assert '"fact_f1" "fact_id" "f1".' in facts_str
    assert '"fact_f1" "source_type" "wiki_article".' in facts_str
    assert '"fact_f1" "signal_class" "volatility_signal".' in facts_str
    # Check lexical projection (wiki_revision pack should be active)
    assert '"fact_f1" "lexical pack" "wiki_revision".' in facts_str

def test_native_rule_triples_wiki():
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"],
                "source_signal_classes": []
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    # wiki_article source_type should infer public_summary and wiki_article source_signal_classes
    assert {"subject": "fact_f1", "predicate": "source_signal_class", "object": "public_summary"} in triples
    assert {"subject": "fact_f1", "predicate": "source_signal_class", "object": "wiki_article"} in triples

def test_native_rule_triples_authority_risk():
    workbench = {
        "facts": [
            {
                "fact_id": "f2",
                "source_signal_classes": ["public_summary", "wiki_article"],
                # No strong legal source
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    assert {"subject": "fact_f2", "predicate": "signal_class", "object": "authority_transfer_risk"} in triples

def test_native_rule_triples_public_knowledge():
    workbench = {
        "facts": [
            {
                "fact_id": "f3",
                "source_signal_classes": ["public_summary", "strong_legal_source"],
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    assert {"subject": "fact_f3", "predicate": "signal_class", "object": "public_knowledge_not_authority"} in triples

def test_enrich_workbench_with_zelph_portable():
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"],
                "signal_classes": [],
                "source_signal_classes": []
            }
        ]
    }
    # enrich without rules (portable only)
    enriched = enrich_workbench_with_zelph(workbench)
    
    fact = enriched["facts"][0]
    assert "public_summary" in fact["source_signal_classes"]
    assert "wiki_article" in fact["source_signal_classes"]
    assert fact["inferred_source_signal_classes"] == ["public_summary", "wiki_article"]
    assert enriched["zelph"]["rule_status"] == "portable_only"
    assert enriched["zelph"]["inferred_fact_count"] == 1

def test_native_rule_triples_wiki_uncertainty():
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"],
                "statement_texts": ["Revision by Alice: Maybe fixed typo?"]
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    # wiki_article + "maybe" should now infer uncertainty_preserved (via lexical_signal_classes)
    assert {"subject": "fact_f1", "predicate": "signal_class", "object": "uncertainty_preserved"} in triples
    # And still the source classes
    assert {"subject": "fact_f1", "predicate": "source_signal_class", "object": "public_summary"} in triples

def test_native_rule_triples_reversion_and_reason():
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"],
                "statement_texts": ["Revision by Alice: Reverted vandalism because of wrong info"]
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    
    # "Reverted" and "vandalism" in wiki revision comment -> reversion_edit, volatility_signal
    # reversion_edit -> is_reversion "True" (New portable rule)
    assert {"subject": "fact_f1", "predicate": "signal_class", "object": "reversion_edit"} in triples
    assert {"subject": "fact_f1", "predicate": "signal_class", "object": "volatility_signal"} in triples
    assert {"subject": "fact_f1", "predicate": "is_reversion", "object": "True"} in triples
    
    # "because" -> has_context_reason "True" (New portable rule)
    assert {"subject": "fact_f1", "predicate": "has_context_reason", "object": "True"} in triples

def test_native_rule_triples_union_fix():
    # Test that authority_transfer_risk is triggered even if 'public_summary' 
    # only comes from lexical analysis (which is common for wiki items).
    workbench = {
        "facts": [
            {
                "fact_id": "f1",
                "source_types": ["wiki_article"], # This implies public_summary lexically
                "statement_texts": ["Revision by Alice: Fixed typo"]
            }
        ]
    }
    triples = _native_rule_triples(workbench)
    
    # Before the fix, authority_transfer_risk wouldn't trigger because 'public_summary' 
    # was in lexical_source_signal_classes, not source_signal_classes.
    assert {"subject": "fact_f1", "predicate": "source_signal_class", "object": "public_summary"} in triples
    assert {"subject": "fact_f1", "predicate": "signal_class", "object": "authority_transfer_risk"} in triples
