#!/bin/bash
set -euo pipefail

echo "========================================================"
echo " S E N S I B L A W  ×  Z E L P H  |  D B   I N G E S T   "
echo "========================================================"
echo ""

DB_PATH="../data/corpus/ingest.sqlite"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Could not find $DB_PATH!"
    exit 1
fi

echo "[1] Pulling 'rule_atoms' from SQLite onto Zelph facts..."
python3 compile_db.py "$DB_PATH" db_facts.zlp
echo "✅ Compilation successful. Generated db_facts.zlp."
echo ""

echo "[2] Running Inference..."
echo "--- db_rules.zlp ---"
cat db_rules.zlp
echo "--------------------------"
echo ""

echo "[3] Executing Zelph..."
zelph db_facts.zlp db_rules.zlp 2>&1
