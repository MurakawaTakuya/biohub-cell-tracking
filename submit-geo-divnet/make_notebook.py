"""Build the Geometric Fusion + DivNet gate notebook from the plain fork."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
# Usage: make_notebook.py [SRC.ipynb DST.ipynb]  (default: Geometric Fusion fork -> geo-divnet.ipynb)
SRC = Path(sys.argv[1]) if len(sys.argv) > 2 else HERE.parent / "submit-geometric-fusion" / "biohub-geometric-fusion.ipynb"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "geo-divnet.ipynb"

DIVNET_CODE = r'''
# ---------------------------------------------------------------- DivNet parent gate
# giorgosi/biohub-divnet-v2 best_overall.pt: per-node division classifier.
# Input (1, 5, 16, 32, 32): frames t-1..t+2 pooled 4x in xy, p50/p99.5 normalised
# per frame, cropped at the parent, plus a Gaussian marker at the parent.
# Verified on train GT (server): AUC 0.832, channel order matters (marker-first 0.611).
DIVNET_GATE_ENABLE = os.environ.get("BIOHUB_DIVNET_GATE", "1") != "0"
DIVNET_MIN_PROB = float(os.environ.get("BIOHUB_DIVNET_MIN_PROB", "0.5"))
# Ranking bonus in um subtracted from the safe-division proposal score (0 = gate only).
DIVNET_RANK_WEIGHT_UM = float(os.environ.get("BIOHUB_DIVNET_RANK_WEIGHT_UM", "0.0"))
# Rescue: keep a candidate the DeepCenter veto rejected when the parent's DivNet prob is at least this (0 = off).
DIVNET_RESCUE_MIN_PROB = float(os.environ.get("BIOHUB_DIVNET_RESCUE_MIN_PROB", "0.0"))
_DIVNET = {"model": None, "frames": {}, "scores": {}, "stats": {"checked": 0, "rejected": 0, "accepted": 0, "rescue_checked": 0, "rescued": 0}}


def _divnet_load():
    if _DIVNET["model"] is not None:
        return _DIVNET["model"]
    import torch as _t
    import torch.nn as _nn
    paths = sorted(Path("/kaggle/input").rglob("best_overall.pt"))
    paths = [p for p in paths if "divnet" in str(p).lower()]
    if len(paths) < 1:
        raise RuntimeError("DIVNET weights not mounted (attach giorgosi/biohub-divnet-v2)")

    class _Block(_nn.Module):
        def __init__(self, a, b):
            super().__init__()
            g = min(8, b)
            self.block = _nn.Sequential(
                _nn.Conv3d(a, b, 3, padding=1, bias=False), _nn.GroupNorm(g, b), _nn.SiLU(inplace=True),
                _nn.Conv3d(b, b, 3, padding=1, bias=False), _nn.GroupNorm(g, b), _nn.SiLU(inplace=True))

        def forward(self, x):
            return self.block(x)

    class _DivNet(_nn.Module):
        def __init__(self, cin=5, c=16):
            super().__init__()
            self.enc1 = _Block(cin, c); self.enc2 = _Block(c, 2 * c); self.enc3 = _Block(2 * c, 4 * c)
            self.bottleneck = _Block(4 * c, 8 * c)
            self.up3 = _nn.ConvTranspose3d(8 * c, 4 * c, 2, 2); self.dec3 = _Block(8 * c, 4 * c)
            self.up2 = _nn.ConvTranspose3d(4 * c, 2 * c, 2, 2); self.dec2 = _Block(4 * c, 2 * c)
            self.up1 = _nn.ConvTranspose3d(2 * c, c, 2, 2); self.dec1 = _Block(2 * c, c)
            self.pool = _nn.MaxPool3d(2, 2)
            self.head = _nn.Linear(c, 1)

        def forward(self, x):
            e1 = self.enc1(x); e2 = self.enc2(self.pool(e1)); e3 = self.enc3(self.pool(e2))
            b = self.bottleneck(self.pool(e3))
            d3 = self.dec3(_t.cat([self.up3(b), e3], 1))
            d2 = self.dec2(_t.cat([self.up2(d3), e2], 1))
            d1 = self.dec1(_t.cat([self.up1(d2), e1], 1))
            return self.head(d1.mean(dim=(2, 3, 4))).squeeze(1)

    ck = _t.load(paths[0], map_location="cpu", weights_only=False)
    model = _DivNet(int(ck["config"]["input"]["channels"]), int(ck["config"]["model"]["base_channels"]))
    model.load_state_dict(ck["model_state"], strict=True)
    dev = _t.device("cuda" if _t.cuda.is_available() else "cpu")
    model.to(dev).eval()
    cfg = ck["config"]["input"]
    grids = np.meshgrid(*[np.arange(s) - s // 2 for s in (cfg["crop_z"], cfg["crop_yx"], cfg["crop_yx"])], indexing="ij")
    marker = np.exp(-sum(g ** 2 / (2 * s ** 2) for g, s in zip(grids, cfg["marker_sigma"]))).astype(np.float32)
    _DIVNET["model"] = (model, dev, cfg, marker)
    print("DIVNET_GATE_LOADED", paths[0], "min_prob=", DIVNET_MIN_PROB, "rank_weight_um=", DIVNET_RANK_WEIGHT_UM, "rescue_min_prob=", DIVNET_RESCUE_MIN_PROB, flush=True)
    return _DIVNET["model"]


def _divnet_frame(dataset, t, frame_cache):
    key = (dataset, int(t))
    got = _DIVNET["frames"].get(key)
    if got is None:
        vol = read_test_frame(dataset, int(t), frame_cache)
        pooled = _dc_pool_frame_xy(vol, 4)
        lo, hi = np.percentile(pooled, [50.0, 99.5])
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            got = np.zeros_like(pooled, dtype=np.float32)
        else:
            got = np.clip((pooled - lo) / (hi - lo), -0.5, 6.0).astype(np.float32)
        if len(_DIVNET["frames"]) > 24:
            _DIVNET["frames"].pop(next(iter(_DIVNET["frames"])))
        _DIVNET["frames"][key] = got
    return got


def _divnet_crop(vol, center, size):
    out = np.zeros(size, dtype=np.float32)
    src, dst = [], []
    for c, s, n in zip(center, size, vol.shape):
        a = int(round(c)) - s // 2
        s0, s1 = max(a, 0), min(a + s, n)
        src.append(slice(s0, s1)); dst.append(slice(s0 - a, s1 - a))
    out[tuple(dst)] = vol[tuple(src)]
    return out


def divnet_parent_prob(dataset, t, source_id, source, frame_cache):
    key = (dataset, int(t), int(source_id))
    if key in _DIVNET["scores"]:
        return _DIVNET["scores"][key]
    import torch as _t
    model, dev, cfg, marker = _divnet_load()
    n_frames = int(json.loads((TEST_DIR / f"{dataset}.zarr" / "0" / "zarr.json").read_text())["shape"][0])
    size = (cfg["crop_z"], cfg["crop_yx"], cfg["crop_yx"])
    center = (float(source["z"]), float(source["y"]) / 4.0, float(source["x"]) / 4.0)
    chans = [_divnet_crop(_divnet_frame(dataset, min(max(int(t) + lag, 0), n_frames - 1), frame_cache), center, size)
             for lag in cfg["image_lags"]]
    x = np.stack(chans + [marker])[None]
    with _t.no_grad():
        prob = float(_t.sigmoid(model(_t.from_numpy(x).to(dev))).item())
    _DIVNET["scores"][key] = prob
    return prob


def divnet_accept_parent(dataset, t, source_id, source, frame_cache):
    if not DIVNET_GATE_ENABLE or dataset is None:
        return True
    prob = divnet_parent_prob(dataset, t, source_id, source, frame_cache)
    _DIVNET["stats"]["checked"] += 1
    if prob < DIVNET_MIN_PROB:
        _DIVNET["stats"]["rejected"] += 1
        return False
    _DIVNET["stats"]["accepted"] += 1
    return True


def divnet_rescue_parent(dataset, t, source_id, source, frame_cache):
    if not DIVNET_GATE_ENABLE or dataset is None or DIVNET_RESCUE_MIN_PROB <= 0.0:
        return False
    _DIVNET["stats"]["rescue_checked"] += 1
    if divnet_parent_prob(dataset, t, source_id, source, frame_cache) >= DIVNET_RESCUE_MIN_PROB:
        _DIVNET["stats"]["rescued"] += 1
        return True
    return False


def divnet_rank_bonus(dataset, t, source_id, source, frame_cache):
    if not DIVNET_GATE_ENABLE or dataset is None or DIVNET_RANK_WEIGHT_UM <= 0.0:
        return 0.0
    return DIVNET_RANK_WEIGHT_UM * divnet_parent_prob(dataset, t, source_id, source, frame_cache)


'''

GATE_ANCHOR = '''                    "safe_div",
                    DEEPCENTER_SAFE_DIV_THRESHOLD,
                ):
                    continue
'''
GATE_CODE = '''                    "safe_div",
                    DEEPCENTER_SAFE_DIV_THRESHOLD,
                ):
                    if not divnet_rescue_parent(dataset, t, source_id, source, frame_cache):
                        continue
                if not divnet_accept_parent(dataset, t, source_id, source, frame_cache):
                    continue
'''
SCORE_ANCHOR = "                score = parent_dist + 0.15 * sister_dist\n"
SCORE_CODE = ("                score = parent_dist + 0.15 * sister_dist"
              " - divnet_rank_bonus(dataset, t, source_id, source, frame_cache)\n")
STATS_ANCHOR = "    _geo_cands = stats['safe_division_geometric_candidates']\n"
STATS_CODE = ('    print(f"  [{dataset}] DIVNET gate cumulative: {_DIVNET[\'stats\']}", flush=True)\n'
              + STATS_ANCHOR)
DEF_ANCHOR = "def add_safe_divisions_postlink(\n"

nb = json.loads(SRC.read_text())
hits = 0
for cell in nb["cells"]:
    src = "".join(cell["source"])
    if DEF_ANCHOR not in src:
        continue
    for anchor, new in [(GATE_ANCHOR, GATE_CODE), (SCORE_ANCHOR, SCORE_CODE), (STATS_ANCHOR, STATS_CODE), (DEF_ANCHOR, DIVNET_CODE + DEF_ANCHOR)]:
        if src.count(anchor) != 1:
            sys.exit(f"anchor count {src.count(anchor)} for {anchor[:40]!r}")
        src = src.replace(anchor, new)
    cell["source"] = src.splitlines(keepends=True)
    hits += 1
assert hits == 1, hits
if len(sys.argv) <= 2:  # keep the original geo-divnet notebook byte-identical
    nb["cells"][0]["source"] = ("".join(nb["cells"][0]["source"]).replace(
        "BIOHUB_SCORE_AXIS = 'v4:", "BIOHUB_SCORE_AXIS = 'v4+divnet-gate0.5:", 1)).splitlines(keepends=True)
DST.write_text(json.dumps(nb, indent=1))
print("wrote", DST)
