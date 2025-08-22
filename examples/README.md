# Examples

## Distinguish GLJ Demo

This demo compares a short story to a simplified silhouette of the GLJ case
using the `compare_story_to_case` helper.

### Running the demo

From the repository root execute:

```bash
python examples/distinguish_glj/demo.py
```

The script loads `glj_silhouette.json` and `story.json`, compares them and
prints overlaps and differences with paragraph citations.

### Visualising results

The textual output can be further processed or visualised. For example, proof
structures can be exported to Graphviz DOT format and rendered:

```bash
dot -Tpng examples/distinguish_glj/proof_tree.dot -o proof_tree.png
```
