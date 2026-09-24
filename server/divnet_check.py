"""Check that the public DivNet checkpoint reproduces its reported AUC on train GT.

Positives: GT nodes with out-degree 2 (divisions). Negatives: GT nodes with
out-degree 1, sampled per movie. The checkpoint (best_overall.pt, a single fold)
saw about 3/4 of the movies, so the AUC here is mostly in-sample. It only checks
preprocessing: AUC near 0.5 means the input recipe is wrong.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import zarr
from sklearn.metrics import roc_auc_score


class ConvBlock3d(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        g = min(8, cout)
        self.block = nn.Sequential(
            nn.Conv3d(cin, cout, 3, padding=1, bias=False), nn.GroupNorm(g, cout), nn.SiLU(inplace=True),
            nn.Conv3d(cout, cout, 3, padding=1, bias=False), nn.GroupNorm(g, cout), nn.SiLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class DivNet(nn.Module):
    """DeepCenterUNet3D(5, 16) body; head = global average pool of dec1 + Linear(16, 1)."""

    def __init__(self, cin=5, c=16):
        super().__init__()
        self.enc1 = ConvBlock3d(cin, c); self.enc2 = ConvBlock3d(c, 2 * c); self.enc3 = ConvBlock3d(2 * c, 4 * c)
        self.bottleneck = ConvBlock3d(4 * c, 8 * c)
        self.up3 = nn.ConvTranspose3d(8 * c, 4 * c, 2, 2); self.dec3 = ConvBlock3d(8 * c, 4 * c)
        self.up2 = nn.ConvTranspose3d(4 * c, 2 * c, 2, 2); self.dec2 = ConvBlock3d(4 * c, 2 * c)
        self.up1 = nn.ConvTranspose3d(2 * c, c, 2, 2); self.dec1 = ConvBlock3d(2 * c, c)
        self.pool = nn.MaxPool3d(2, 2)
        self.head = nn.Linear(c, 1)

    def forward(self, x):
        e1 = self.enc1(x); e2 = self.enc2(self.pool(e1)); e3 = self.enc3(self.pool(e2))
        b = self.bottleneck(self.pool(e3))
        d3 = self.dec3(torch.cat([self.up3(b), e3], 1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], 1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], 1))
        return self.head(d1.mean(dim=(2, 3, 4))).squeeze(1)


def block_mean_xy(v, f):
    z, y, x = v.shape
    y2, x2 = y // f * f, x // f * f
    return v[:, :y2, :x2].astype(np.float32).reshape(z, y2 // f, f, x2 // f, f).mean(axis=(2, 4))


def normalize(v, lo_pct=50.0, hi_pct=99.5, clip=(-0.5, 6.0)):
    lo, hi = np.percentile(v, [lo_pct, hi_pct])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(v, dtype=np.float32)
    return np.clip((v - lo) / (hi - lo), *clip).astype(np.float32)


def crop(vol, center, size):
    out = np.zeros(size, dtype=np.float32)
    src, dst = [], []
    for c, s, n in zip(center, size, vol.shape):
        a = int(round(c)) - s // 2
        s0, s1 = max(a, 0), min(a + s, n)
        src.append(slice(s0, s1)); dst.append(slice(s0 - a, s1 - a))
    out[tuple(dst)] = vol[tuple(src)]
    return out


def gaussian_marker(size, sigma):
    grids = np.meshgrid(*[np.arange(s) - s // 2 for s in size], indexing="ij")
    return np.exp(-sum(g ** 2 / (2 * sg ** 2) for g, sg in zip(grids, sigma))).astype(np.float32)


def load_geff(path):
    g = zarr.open_group(str(path), mode="r")
    ids = np.asarray(g["nodes/ids"])
    props = {k: np.asarray(g[f"nodes/props/{k}/values"]) for k in "tzyx"}
    edges = np.asarray(g["edges/ids"])
    return ids, props, edges


def samples_for_movie(geff, rng, neg_per_movie):
    ids, p, edges = load_geff(geff)
    outdeg = {}
    for s in edges[:, 0]:
        outdeg[int(s)] = outdeg.get(int(s), 0) + 1
    rows = [(int(i), int(p["t"][k]), float(p["z"][k]), float(p["y"][k]), float(p["x"][k]), outdeg.get(int(i), 0))
            for k, i in enumerate(ids)]
    pos = [r for r in rows if r[5] == 2]
    # Negatives only from division frames plus 3 random frames, to limit frame reads.
    all_t = sorted({r[1] for r in rows})
    frames = {r[1] for r in pos} | set(rng.choice(all_t, min(3, len(all_t)), replace=False).tolist())
    neg = [r for r in rows if r[5] == 1 and r[1] in frames]
    if len(neg) > neg_per_movie:
        neg = [neg[i] for i in rng.choice(len(neg), neg_per_movie, replace=False)]
    return [(r, 1) for r in pos] + [(r, 0) for r in neg]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/train")
    ap.add_argument("--ckpt", default="inputs/divnet_local/best_overall.pt")
    ap.add_argument("--out", default="runs/divnet_check")
    ap.add_argument("--neg-per-movie", type=int, default=20)
    ap.add_argument("--max-movies", type=int, default=0)
    ap.add_argument("--variant", default="base", choices=["base", "marker_first", "no_pad_clamp"])
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    cfg = ck["config"]["input"]
    model = DivNet(cfg["channels"], ck["config"]["model"]["base_channels"])
    model.load_state_dict(ck["model_state"], strict=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(dev).eval()

    size = (cfg["crop_z"], cfg["crop_yx"], cfg["crop_yx"])
    marker = gaussian_marker(size, cfg["marker_sigma"])
    lags, f = cfg["image_lags"], cfg["pool_xy"]
    rng = np.random.default_rng(0)

    movies = sorted(Path(args.data).glob("*.zarr"))
    if args.max_movies:
        movies = movies[: args.max_movies]
    scores, labels, meta = [], [], []
    for mi, zp in enumerate(movies):
        geff = zp.with_suffix(".geff")
        if not geff.exists():
            continue
        arr = zarr.open(str(zp / "0"), mode="r")
        T = arr.shape[0]
        cache = {}

        def frame(t):
            t = min(max(t, 0), T - 1)
            if t not in cache:
                cache[t] = normalize(block_mean_xy(np.asarray(arr[t]), f))
            return cache[t]

        batch, blabels = [], []
        for (nid, t, z, y, x, _), lab in samples_for_movie(geff, rng, args.neg_per_movie):
            center = (z, y / f, x / f)
            chans = [crop(frame(t + l), center, size) for l in lags]
            x_in = [marker] + chans if args.variant == "marker_first" else chans + [marker]
            batch.append(np.stack(x_in)); blabels.append(lab); meta.append((zp.stem, nid, t, lab))
        if not batch:
            continue
        with torch.no_grad():
            logits = model(torch.from_numpy(np.stack(batch)).to(dev)).float().cpu().numpy()
        scores.extend(logits.tolist()); labels.extend(blabels)
        if mi % 20 == 0:
            print(f"[{mi}/{len(movies)}] samples={len(labels)} pos={sum(labels)}", flush=True)

    labels_a, scores_a = np.asarray(labels), np.asarray(scores)
    auc = roc_auc_score(labels_a, scores_a) if 0 < labels_a.sum() < len(labels_a) else float("nan")
    summary = {"variant": args.variant, "n": int(len(labels_a)), "pos": int(labels_a.sum()), "auc": float(auc),
               "ckpt_best_score": float(ck["best_score"])}
    print(json.dumps(summary), flush=True)
    (out / f"summary_{args.variant}.json").write_text(json.dumps(summary, indent=1))
    np.savez(out / f"scores_{args.variant}.npz", scores=scores_a, labels=labels_a,
             meta=np.asarray(meta, dtype=object))


if __name__ == "__main__":
    main()
