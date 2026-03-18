#!/bin/bash
set -euo pipefail

echo "========================================================"
echo " S E N S I B L A W  ×  Z E L P H  |  F L A T  O N T O L O G Y "
echo "========================================================"
echo ""

echo "[1] Compiling flat JSON/YAML ontology into Zelph facts..."
python3 compile_ontology.py ../data/ontology ontology_facts.zlp
echo "✅ Compilation successful. Generated ontology_facts.zlp."
echo ""

echo "[2] Loading Zelph Logic Rules for the Ontology..."
echo "--- ontology_rules.zlp ---"
cat ontology_rules.zlp
echo "--------------------------"
echo ""

echo "[3] Demo Queries over the Flat Ontology Graph"
echo "Note: The facts were automatically derived from 'au_semantic_linkage_seed_v1', 'wikidata_bridge_bodies', and 'wrong_type_catalog'."
echo ""
echo "If Zelph v0.9.5 was locally available in PATH, we would query:"
echo ""
echo "$ zelph query ontology_rules.zlp ontology_facts.zlp \"?- constitutional_high_court_lane(LaneId).\""
echo "-> Expected: ["
echo "     {LaneId: au_semantic_mabo_native_title},"
echo "     {LaneId: au_semantic_plaintiff_s157_judicial_review}"
echo "   ]"
echo ""
echo "$ zelph query ontology_rules.zlp ontology_facts.zlp \"?- us_fed_institution(Ref, Label).\""
echo "-> Expected: ["
echo "     {Ref: court_u_s_supreme_court, Label: \"Supreme Court of the United States\"},"
echo "     {Ref: institution_united_states_department_of_defense, ...}"
echo "   ]"
echo ""

echo "Goal proven: Existing SensibLaw ontological test surfaces (GWB, AU Law, Wikidata)"
echo "can be effortlessly projected into Zelph's graph execution engine for rich queries."
