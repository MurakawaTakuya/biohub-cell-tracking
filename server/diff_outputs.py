"""Compare submission.csv outputs: nodes, edges, and division events (parent + 2 daughters), by coordinates.

Node ids can differ between runs, so everything is keyed by (dataset, t, z, y, x).
Usage: python3 server/diff_outputs.py NAME=path.csv NAME=path.csv ...  (first one is the reference)
"""
import sys
from collections import Counter

import pandas as pd


def load(path):
    d = pd.read_csv(path)
    n = d[d.row_type == "node"]
    pos = {(r.dataset, r.node_id): (r.dataset, r.t, r.z, r.y, r.x) for r in n.itertuples()}
    e = d[d.row_type == "edge"]
    edges = {(pos[(r.dataset, r.source_id)], pos[(r.dataset, r.target_id)]) for r in e.itertuples()}
    kids = {}
    for s, t in edges:
        kids.setdefault(s, []).append(t)
    divs = {s: frozenset(v) for s, v in kids.items() if len(v) == 2}
    return set(pos.values()), edges, divs


runs = [a.split("=", 1) for a in sys.argv[1:]]
data = {name: load(path) for name, path in runs}
ref_name = runs[0][0]
rn, re_, rd = data[ref_name]
print(f"{ref_name}: nodes={len(rn)} edges={len(re_)} divisions={len(rd)}")
for name, _ in runs[1:]:
    n, e, d = data[name]
    common = {p for p in d if p in rd and d[p] == rd[p]}
    same_parent_diff_kids = {p for p in d if p in rd and d[p] != rd[p]}
    print(f"\n{name} vs {ref_name}: nodes={len(n)} (+{len(n - rn)} / -{len(rn - n)}), "
          f"edges={len(e)} (+{len(e - re_)} / -{len(re_ - e)}), divisions={len(d)}")
    print(f"  divisions: common={len(common)} removed={len(set(rd) - set(d))} "
          f"new={len(set(d) - set(rd))} same_parent_other_daughters={len(same_parent_diff_kids)}")
    print("  removed divisions per dataset:", dict(Counter(p[0] for p in set(rd) - set(d))))
    print("  new divisions per dataset:", dict(Counter(p[0] for p in set(d) - set(rd))))
    print("  ref divisions per dataset:", dict(Counter(p[0] for p in rd)))
