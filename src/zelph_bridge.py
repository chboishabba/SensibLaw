import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

def run_zelph_inference(facts: str, rules: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        facts_file = tmpdir_path / "facts.zlp"
        rules_file = tmpdir_path / "rules.zlp"
        query_file = tmpdir_path / "query.zph"
        
        facts_file.write_text(facts)
        rules_file.write_text(rules)
        
        # Include rules and facts, then query
        query_file.write_text(f'include "{rules_file}"\ninclude "{facts_file}"\n')
        
        try:
            result = subprocess.run(
                ["zelph", str(query_file)],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error running zelph: {e.stderr}"
        except FileNotFoundError:
            return "Error: zelph command not found"

def workbench_to_zelph_facts(workbench: Mapping[str, Any]) -> str:
    facts = []
    # Convert observations to triples
    for obs in workbench.get("observations", []):
        obs_id = obs.get("observation_id", "unknown").replace(":", "_")
        subj = obs.get("subject_text") or "node_subject"
        pred = obs.get("predicate_key", "predicate")
        obj = obs.get("object_text", "node_object")
        
        # Simple triple format for Zelph
        facts.append(f'"{subj}" "{pred}" "{obj}"')
    
    return "\n".join(facts)
