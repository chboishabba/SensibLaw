# Examples

## Distinguish GLJ Demo

This demo runs a small pipeline consisting of concept matching, checklist
evaluation and proof‑tree generation against a sample story. The fixture
includes a simplified silhouette of the GLJ case and a short story.

### Running the demo

From the repository root execute:

```bash
python examples/distinguish_glj/demo.py
```

The script creates `results.json` containing concept matching and checklist
outputs and `proof_tree.dot` representing the proof tree. To render the proof
 tree you can use Graphviz:

```bash
dot -Tpng examples/distinguish_glj/proof_tree.dot -o proof_tree.png
```
