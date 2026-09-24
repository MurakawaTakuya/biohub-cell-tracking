from pathlib import Path
import json
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

history_candidates = [
    path for path in INPUT_ROOT.rglob("training_history.json")
    if "edge-training-20ep" in str(path).lower()
]
assert len(history_candidates) == 1, history_candidates
source_repo = history_candidates[0].parents[3]
assert (source_repo / "scripts/train_unet_transformer.py").exists(), source_repo
resume_path = source_repo / "weights/unet_transformer/split_0/edge_predictor_best.pth"
assert resume_path.exists(), resume_path

if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(source_repo, REPO)
print("Copied trained repository from", source_repo)
print("Resuming from", resume_path)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    assert count == 1, f"{label}: expected exactly one match, found {count}"
    return source.replace(old, new, 1)


train_path = REPO / "scripts/train_unet_transformer.py"
source = train_path.read_text()
source = replace_once(
    source,
    '''    model.train()
    total_edge_loss = 0.0
''',
    '''    model.train()
    detector_frozen = not any(p.requires_grad for p in model.unet.parameters())
    if detector_frozen:
        model.unet.eval()
        model.detect_head.eval()
    total_edge_loss = 0.0
''',
    "frozen detector mode",
)
source = replace_once(
    source,
    '''        # --- 1. Encode: UNet features + detection logits --------------------
        unet_out, det_logits = model.encode(imgs)
        # unet_out: (B, W, C, *spatial),  det_logits: list of W × (B, 1, *spatial)

        # --- 2. Detection loss over all W frames ---------------------------
        det_losses = [
            compute_detection_loss(
                det_logits[i], coords[:, i], masks[:, i],
                det_neg_weight,
            )
            for i in range(W)
        ]
        det_loss = sum(det_losses) / W
''',
    '''        # --- 1. Encode: UNet features + detection logits --------------------
        if detector_frozen:
            with torch.no_grad():
                unet_out, det_logits = model.encode(imgs)
        else:
            unet_out, det_logits = model.encode(imgs)
        # unet_out: (B, W, C, *spatial),  det_logits: list of W × (B, 1, *spatial)

        # --- 2. Detection loss over all W frames ---------------------------
        if detector_frozen:
            det_loss = torch.zeros((), device=device)
        else:
            det_losses = [
                compute_detection_loss(
                    det_logits[i], coords[:, i], masks[:, i],
                    det_neg_weight,
                )
                for i in range(W)
            ]
            det_loss = sum(det_losses) / W
''',
    "no-grad detector forward",
)
source = replace_once(
    source,
    '''    if resume_weights is not None:
        state = torch.load(resume_weights, map_location=device, weights_only=True)
        model.load_state_dict(state, strict=True)
        print(f"Resumed full model from {resume_weights}", flush=True)

    # Simple multi-GPU: split the heavy UNet pass across all visible GPUs.
''',
    '''    if resume_weights is not None:
        state = torch.load(resume_weights, map_location=device, weights_only=True)
        model.load_state_dict(state, strict=True)
        print(f"Resumed full model from {resume_weights}", flush=True)

    for parameter in model.unet.parameters():
        parameter.requires_grad_(False)
    for parameter in model.detect_head.parameters():
        parameter.requires_grad_(False)
    print("Frozen UNet and detection head; training edge transformer only", flush=True)

    # Simple multi-GPU: split the heavy UNet pass across all visible GPUs.
''',
    "freeze detector parameters",
)
source = replace_once(
    source,
    '''    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
''',
    '''    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=lr,
    )
''',
    "trainable optimizer parameters",
)
train_path.write_text(source)
subprocess.run([sys.executable, "-m", "py_compile", str(train_path)], check=True)
print("Patched edge-only training mode")

# The copied split is the same evenly spaced eight-clip 6bba validation set.
split = json.loads((REPO / "dataset_splits.json").read_text())
assert len(split) == 1 and len(split[0]["test"]) == 8, split

train_cmd = [
    sys.executable, "scripts/train_unet_transformer.py",
    "--data-dir", str(TRAIN), "--splits", "dataset_splits.json", "--split", "0",
    "--epochs", "30", "--max-iters", "200", "--batch-size", "4", "--num-workers", "4",
    "--resume-weights", str(resume_path), "--single-gpu", "--det-loss-weight", "0",
]
env = {
    **os.environ,
    "PYTHONPATH": "src",
    "PYTORCH_ALLOC_CONF": "expandable_segments:True",
}
subprocess.run(train_cmd, cwd=REPO, env=env, check=True)

output_dir = REPO / "weights/unet_transformer/split_0"
manifest = {
    "fold": 0,
    "stage": "edge_only",
    "train_embryo": "44b6",
    "held_out_embryo": "6bba",
    "resume_source": "versavice/biohub-fold0-edge-training-20ep",
    "additional_epochs": 30,
    "max_iters_per_epoch": 200,
    "total_additional_iterations": 6000,
    "batch_size": 4,
    "detector_frozen": True,
    "validation_clips": split[0]["test"],
    "best_weights": str(output_dir / "edge_predictor_best.pth"),
    "last_weights": str(output_dir / "edge_predictor_last.pth"),
    "history": str(output_dir / "training_history.json"),
}
(WORK / "fold0_edge_only_training_manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
print("EDGE_ONLY_TRAINING_COMPLETE")
