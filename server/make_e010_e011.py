"""E010: E006 + DivNet rescue 0.7 (env change only).
E011: E006 + weak-leaf pruning 0.3 applied AFTER linefit smoothing (so surviving node coordinates stay as in E006).
Both start from the pushed E006 notebook; nothing else changes.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E006 = ROOT / "submit-e006-x138-gate03"
GEO = ROOT / "submit-geometric-fusion" / "biohub-geometric-fusion.ipynb"


def load_e006():
    nb = json.loads((E006 / "notebook.ipynb").read_text())
    meta = json.loads((E006 / "kernel-metadata.json").read_text())
    return nb, meta


def append_env(nb, header, env):
    c0 = "".join(nb["cells"][0]["source"]) + f"\n# {header}\n" + "".join(f'os.environ["{k}"] = "{v}"\n' for k, v in env.items())
    nb["cells"][0]["source"] = c0.splitlines(keepends=True)


def save(nb, meta, out, kid, title):
    out.mkdir(exist_ok=True)
    (out / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
    meta = dict(meta, id=kid, title=title)
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print("wrote", out)


# E010
nb, meta = load_e006()
assert "def divnet_rescue_parent" in "".join(nb["cells"][5]["source"])
append_env(nb, "E010: DivNet rescue 0.7 on E006.", {"BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.7"})
save(nb, meta, ROOT / "submit-e010-x138-rescue07", "versavice/biohub-e010-x138-rescue07", "Biohub E010 x138 Rescue07")

# E011
nb, meta = load_e006()
g = "".join(json.loads(GEO.read_text())["cells"][5]["source"])
a = g.index("def prune_weak_leaf_nodes(")
prune_fn = g[a:g.index("\ndef ", a + 10)].rstrip() + "\n\n\n"
cell = "".join(nb["cells"][5]["source"])
SMOOTH = "    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)\n"
DEF = "def filter_short_track_components(\n"
assert cell.count(SMOOTH) == 1 and cell.count(DEF) == 1 and "def prune_weak_leaf_nodes" not in cell
cell = cell.replace(SMOOTH, SMOOTH + """    if LEAF_PRUNE_MIN_EDGE_PROB > 0.0:
        nodes_by_id, edges = prune_weak_leaf_nodes(nodes_by_id, edges, stats)
        print(f"  [{dataset}] after weak-leaf pruning (post-smoothing): {len(nodes_by_id)} nodes, {len(edges)} edges"
              f" (leaf_pruned={stats.get('leaf_prune_nodes', 0)})")
""")
cell = cell.replace(DEF, '\nLEAF_PRUNE_MIN_EDGE_PROB = float(os.environ.get("BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB", "0.0"))\n\n\n' + prune_fn + DEF)
nb["cells"][5]["source"] = cell.splitlines(keepends=True)
append_env(nb, "E011: weak-leaf pruning 0.3 after smoothing, on E006.", {"BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB": "0.3"})
save(nb, meta, ROOT / "submit-e011-x138-leafpost03", "versavice/biohub-e011-x138-leafpost03", "Biohub E011 x138 LeafPost03")

# E014: gate off (min_prob 0.0, every parent accepted) + rescue 0.7, on E006 = B005 + rescue 0.7 only.
# BIOHUB_DIVNET_GATE must stay "1" because divnet_rescue_parent is disabled when the gate flag is off.
nb, meta = load_e006()
append_env(nb, "E014: DivNet gate off (min_prob 0.0) + rescue 0.7, on E006.",
           {"BIOHUB_DIVNET_MIN_PROB": "0.0", "BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.7"})
save(nb, meta, ROOT / "submit-e014-x138-rescue07-nogate", "versavice/biohub-e014-x138-rescue07-nogate", "Biohub E014 x138 Rescue07 NoGate")
