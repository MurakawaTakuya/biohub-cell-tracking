"""E009: E006 + weak-leaf pruning ported from Geometric Fusion (threshold 0.3, no sweep).

Copies `prune_weak_leaf_nodes` verbatim from the Geometric Fusion fork and inserts the same call right
after short-track filtering in `filter_output_graph`, as in Geometric Fusion. Nothing else changes.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "submit-geometric-fusion" / "biohub-geometric-fusion.ipynb"
SRC = ROOT / "submit-e006-x138-gate03"
OUT = ROOT / "submit-e009-x138-gate03-leaf03"

g = "".join(json.loads(GEO.read_text())["cells"][5]["source"])
a = g.index("def prune_weak_leaf_nodes(")
b = g.index("\ndef ", a + 10)
prune_fn = g[a:b].rstrip() + "\n\n\n"

CALL_ANCHOR = """    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    print(f"  [{dataset}] after short-track filtering: {len(nodes_by_id)} nodes, {len(edges)} edges"
          f" (components_removed={stats['short_track_components_removed']})")
"""
CALL = CALL_ANCHOR + """    if LEAF_PRUNE_MIN_EDGE_PROB > 0.0:
        nodes_by_id, edges = prune_weak_leaf_nodes(nodes_by_id, edges, stats)
        print(f"  [{dataset}] after weak-leaf pruning: {len(nodes_by_id)} nodes, {len(edges)} edges"
              f" (leaf_pruned={stats.get('leaf_prune_nodes', 0)})")
"""
DEF_ANCHOR = "def filter_short_track_components(\n"
CONST = '\nLEAF_PRUNE_MIN_EDGE_PROB = float(os.environ.get("BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB", "0.0"))\n\n\n'

nb = json.loads((SRC / "notebook.ipynb").read_text())
cell = "".join(nb["cells"][5]["source"])
for anchor in (CALL_ANCHOR, DEF_ANCHOR):
    assert cell.count(anchor) == 1, anchor[:50]
assert "def prune_weak_leaf_nodes" not in cell
cell = cell.replace(CALL_ANCHOR, CALL).replace(DEF_ANCHOR, CONST + prune_fn + DEF_ANCHOR)
nb["cells"][5]["source"] = cell.splitlines(keepends=True)
c0 = "".join(nb["cells"][0]["source"]) + '\n# E009: weak-leaf pruning (Geometric Fusion) on E006.\nos.environ["BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB"] = "0.3"\n'
nb["cells"][0]["source"] = c0.splitlines(keepends=True)
OUT.mkdir(exist_ok=True)
(OUT / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
meta = json.loads((SRC / "kernel-metadata.json").read_text())
meta.update(id="versavice/biohub-e009-x138-gate03-leaf03", title="Biohub E009 x138 Gate03 Leaf03")
(OUT / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
print("wrote", OUT)
