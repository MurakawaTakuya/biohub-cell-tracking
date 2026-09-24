from pathlib import Path
import importlib.util
import math
import os
import shutil
import subprocess
import sys

COMP = Path("/kaggle/input/competitions/biohub-cell-tracking-during-development")
TRAIN = COMP / "train"
SUPPORT_CANDIDATES = [
    Path("/kaggle/input/biohub-tracking-support-pack-50ep-v1"),
    Path("/kaggle/input/datasets/pilkwang/biohub-tracking-support-pack-50ep-v1"),
]
SUPPORT = next((path for path in SUPPORT_CANDIDATES if path.exists()), SUPPORT_CANDIDATES[0])
INPUT_ROOT = Path("/kaggle/input")
WORK = Path("/kaggle/working")
REPO = WORK / "tracking_repo"

assert TRAIN.exists(), TRAIN
assert SUPPORT.exists(), SUPPORT
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(SUPPORT / "repo", REPO)

packages = [
    "tracksdata", "zarr", "pyscipopt", "geff", "geff-spec", "ilpy",
    "polars-runtime-32", "polars", "blosc2", "dask", "imagecodecs",
    "pyarrow", "rustworkx", "sqlalchemy", "donfig", "numcodecs",
]
subprocess.run(
    [
        sys.executable, "-m", "pip", "install", "--quiet", "--no-index",
        "--find-links", str(SUPPORT / "wheels"), "--force-reinstall", *packages,
    ],
    check=True,
)

import numpy as np

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


train_mod = load_module("train_unet_transformer", REPO / "scripts/train_unet_transformer.py")
pred_mod = load_module("predict_unet_transformer", REPO / "scripts/predict_unet_transformer.py")

all_checkpoints = sorted(INPUT_ROOT.rglob("edge_predictor_best.pth"))
checkpoint_candidates = [p for p in all_checkpoints if "fold0" in str(p).lower()]
assert len(checkpoint_candidates) == 1, checkpoint_candidates
weights_path = checkpoint_candidates[0]

import torch
import zarr

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model, window_size, downsample = pred_mod.load_model(weights_path, device)
model.eval()

sample = "6bba_05b6850b"
sample_path = TRAIN / sample
video_meta, windows = train_mod.load_dataset_windows(
    sample_path,
    window_size=window_size,
    downsample=downsample,
)
assert windows
window = windows[0]
train_dataset = train_mod.FrameWindowDataset([(video_meta, [window])])
item = train_dataset[0]
imgs_train = item["imgs"].float()

ds = pred_mod.open_dataset(
    sample_path,
    normalize=False,
    load_image=False,
    downsample=downsample,
)
zarr_arr = zarr.open_group(str(ds.zarr_path), mode="r")["0"]
target_shape = list(ds.image_shape[1:])
t_start = int(item["t_start"])
imgs_pred = torch.stack(
    [
        pred_mod._load_frame(zarr_arr, t, target_shape, downsample)
        for t in range(t_start, t_start + window_size)
    ]
)
q_low = float(ds.quantiles["0.001"])
q_high = float(ds.quantiles["0.999"])
imgs_pred = ((imgs_pred - q_low) / (q_high - q_low + 1e-6)).clamp(0.0)

print("sample", sample, "t_start", t_start)
print("window_size", window_size, "downsample", downsample)
print("train_image_shape", tuple(imgs_train.shape), "pred_image_shape", tuple(imgs_pred.shape))
print("image_max_abs_diff", float((imgs_train - imgs_pred).abs().max()))
print("image_mean_abs_diff", float((imgs_train - imgs_pred).abs().mean()))
print("train_range", float(imgs_train.min()), float(imgs_train.max()))
print("pred_range", float(imgs_pred.min()), float(imgs_pred.max()))

with torch.no_grad():
    _, train_logits = model.encode(imgs_train.unsqueeze(0).to(device))
    pred_unet_out, pred_logits = model.encode(imgs_pred.unsqueeze(0).to(device))

image_shape = tuple(int(x) for x in item["image_shape"].tolist())
voxel_size = tuple(float(x) for x in item["voxel_size"].tolist())
coords_gt = item["coords"].unsqueeze(0).to(device)
masks_gt = item["masks"].unsqueeze(0).to(device)
pool_kernel = pred_mod.pool_kernel_from_um(5.0, voxel_size)
prob_threshold = 1.0 / (1.0 + math.exp(-0.3))
frame_detection_data = []

for frame_idx in range(window_size):
    logit_diff = (train_logits[frame_idx] - pred_logits[frame_idx]).abs()
    detected, detected_pos, detected_mask, matches = train_mod.detect_and_match(
        pred_logits[frame_idx],
        coords_gt[:, frame_idx],
        masks_gt[:, frame_idx],
        image_shape,
        det_threshold=0.3,
        pool_kernel_um=5.0,
        max_match_distance=5.0,
        voxel_size=voxel_size,
        frame_index=frame_idx,
        window_size=window_size,
    )
    standalone = pred_mod._detect_cells_pooled(
        pred_logits[frame_idx][0],
        t_start + frame_idx,
        det_threshold=prob_threshold,
        pool_kernel=pool_kernel,
    )

    n_detected = int(detected_mask[0].sum().item())
    n_standalone = len(standalone)
    n_gt = int(masks_gt[0, frame_idx].sum().item())
    n_matched = int((matches[0] >= 0).sum().item())
    detected_np = detected[0, :n_detected].cpu().numpy()
    standalone_np = standalone[:, 1:].astype(np.float32)
    same_coords = (
        detected_np.shape == standalone_np.shape
        and np.array_equal(detected_np, standalone_np)
    )
    detected_features = model._index_features(
        pred_unet_out[:, frame_idx], detected, detected_mask,
    )
    frame_detection_data.append(
        (detected, detected_pos, detected_mask, matches, detected_features)
    )

    gt_np = coords_gt[0, frame_idx, :n_gt].cpu().numpy()
    scale = np.asarray(voxel_size, dtype=np.float32)
    if n_standalone and n_gt:
        dists = np.linalg.norm(
            (standalone_np[:, None, :] - gt_np[None, :, :]) * scale[None, None, :],
            axis=2,
        )
        nearest = dists.min(axis=0)
        nearest_quantiles = np.quantile(nearest, [0.0, 0.5, 0.9, 1.0]).tolist()
        manual_recall_5um = float((nearest <= 5.0).mean())
    else:
        nearest_quantiles = []
        manual_recall_5um = 0.0

    print(
        "frame", t_start + frame_idx,
        "logit_max_abs_diff", float(logit_diff.max()),
        "logit_range", (float(pred_logits[frame_idx].min()), float(pred_logits[frame_idx].max())),
        "n_gt", n_gt,
        "n_train_detect", n_detected,
        "n_standalone_detect", n_standalone,
        "same_coords", same_coords,
        "training_matches", n_matched,
        "manual_recall_5um", manual_recall_5um,
        "gt_nearest_distance_quantiles", nearest_quantiles,
        flush=True,
    )

edge_target = item["targets"].unsqueeze(0).to(device)
downsample_scale = item["downsample"].to(device)
src = frame_detection_data[0]
tgt = frame_detection_data[1]
n_src = int(src[2][0].sum().item())
n_tgt = int(tgt[2][0].sum().item())
pair_target = train_mod.build_matched_edge_targets(
    src[3], tgt[3], edge_target[:, 0], src[0].shape[1], tgt[0].shape[1],
)
with torch.no_grad():
    pair_logits = model.predict_edges(
        src[4], tgt[4],
        src[0] * downsample_scale, tgt[0] * downsample_scale,
        src[1], tgt[1], src[2], tgt[2],
    )
pair_probs = torch.softmax(pair_logits[0, :n_src, :n_tgt], dim=0)
pair_target = pair_target[0, :n_src, :n_tgt]
positive_probs = pair_probs[pair_target > 0.5]
negative_probs = pair_probs[pair_target < 0.5]
print(
    "edge_probability_summary",
    "n_src", n_src,
    "n_tgt", n_tgt,
    "n_positive", int(positive_probs.numel()),
    "positive_probs", positive_probs.detach().cpu().tolist(),
    "positive_min", float(positive_probs.min()) if positive_probs.numel() else None,
    "positive_max", float(positive_probs.max()) if positive_probs.numel() else None,
    "negative_q99", float(torch.quantile(negative_probs, 0.99)),
    "negative_max", float(negative_probs.max()),
    flush=True,
)
for edge_threshold in [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005]:
    selected = pair_probs > edge_threshold
    true_positive = int((selected & (pair_target > 0.5)).sum().item())
    print(
        "edge_threshold",
        edge_threshold,
        "selected", int(selected.sum().item()),
        "true_positive", true_positive,
        "positive_total", int(positive_probs.numel()),
        flush=True,
    )

print("PARITY_DIAGNOSTIC_COMPLETE", flush=True)
