"""Check predicted divisions against GT on the visible test videos (they are copies of train videos).

GT divisions = GT nodes with out-degree 2. A predicted division (parent with 2 children) counts as a hit
if a GT division parent is within R um in the same frame. Annotations are sparse, so a predicted division
with no GT match is "unlabeled", not necessarily wrong. In-sample for the public detectors: diagnostic only.
Usage: python gt_division_check.py GEFF_DIR NAME=submission.csv ...
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import zarr

SP = np.array([1.625, 0.40625, 0.40625])
R = 5.0


def gt_divs(geff):
    g = zarr.open_group(str(geff), mode="r")
    ids = np.asarray(g["nodes/ids"])
    p = {k: np.asarray(g[f"nodes/props/{k}/values"]) for k in "tzyx"}
    e = np.asarray(g["edges/ids"])
    src, cnt = np.unique(e[:, 0], return_counts=True)
    idx = {int(i): k for k, i in enumerate(ids)}
    out = []
    for s in src[cnt == 2]:
        k = idx[int(s)]
        out.append((int(p["t"][k]), np.array([p["z"][k], p["y"][k], p["x"][k]], float)))
    return out


def pred_divs(df, ds):
    d = df[df.dataset == ds]
    n = d[d.row_type == "node"].set_index("node_id")
    e = d[d.row_type == "edge"]
    src = e.groupby("source_id").size()
    out = []
    for s in src[src == 2].index:
        r = n.loc[s]
        out.append((int(r.t), np.array([r.z, r.y, r.x], float)))
    return out


geff_dir = Path(sys.argv[1])
runs = [a.split("=", 1) for a in sys.argv[2:]]
stems = sorted(p.stem for p in geff_dir.glob("*.geff"))
gts = {s: gt_divs(geff_dir / f"{s}.geff") for s in stems}
print("GT divisions per video:", {s: len(v) for s, v in gts.items()}, "total", sum(len(v) for v in gts.values()))
for name, path in runs:
    df = pd.read_csv(path)
    hit = pred = gt_found = 0
    for s in stems:
        P = pred_divs(df, s)
        G = gts[s]
        pred += len(P)
        used = set()
        for t, x in P:
            best = None
            for j, (tg, xg) in enumerate(G):
                if tg == t and j not in used and np.linalg.norm((x - xg) * SP) <= R:
                    best = j
                    break
            if best is not None:
                used.add(best)
                hit += 1
        gt_found += len(used)
    total_gt = sum(len(v) for v in gts.values())
    print(f"{name:6s} pred_div={pred:4d}  matched_GT={hit:3d}  unlabeled={pred - hit:4d}  GT_recall={gt_found}/{total_gt}")
