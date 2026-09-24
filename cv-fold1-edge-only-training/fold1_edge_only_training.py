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

# Reuse the already verified ranking metrics and detector-freezing implementation.
base_histories = [
    path for path in INPUT_ROOT.rglob("training_history.json")
    if "edge-only-training-6k" in str(path).lower()
]
assert len(base_histories) == 1, base_histories
base_repo = base_histories[0].parents[3]
assert (base_repo / "scripts/train_unet_transformer.py").exists(), base_repo
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(base_repo, REPO)

# Replace Fold 0 weights with the existing detector trained on all 6bba clips.
fold1_weights = [
    path for path in INPUT_ROOT.rglob("edge_predictor_best.pth")
    if "biohub-cv-temporal-fold-weights-v1" in str(path).lower()
    and "fold1" in path.parts
]
assert len(fold1_weights) == 1, fold1_weights
resume_path = fold1_weights[0]
source_config = resume_path.parent / "config.json"
assert source_config.exists(), source_config
weights_dir = REPO / "weights/unet_transformer/split_0"
weights_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(resume_path, weights_dir / "edge_predictor_best.pth")
shutil.copy2(source_config, weights_dir / "config.json")
print("Base training code", base_repo)
print("Fold 1 detector checkpoint", resume_path)


def embryo_id(name: str) -> str:
    return name.removesuffix(".zarr").split("_", 1)[0]


samples = sorted(path.name.removesuffix(".zarr") for path in TRAIN.glob("*.zarr"))
train_names = [name for name in samples if embryo_id(name) == "6bba"]
held_out_names = [name for name in samples if embryo_id(name) == "44b6"]
assert len(train_names) == 128, len(train_names)
assert len(held_out_names) == 71, len(held_out_names)
pilot_size = 8
pilot_indices = [round(i * (len(held_out_names) - 1) / (pilot_size - 1)) for i in range(pilot_size)]
pilot_test = [held_out_names[index] for index in pilot_indices]
split = [{
    "held_out_embryo": "44b6",
    "train": train_names,
    "test": pilot_test,
}]
(REPO / "dataset_splits.json").write_text(json.dumps(split, indent=2))
print({"train_clips": len(train_names), "pilot_test_clips": len(pilot_test)})
print("pilot_test", pilot_test)

train_cmd = [
    sys.executable, "scripts/train_unet_transformer.py",
    "--data-dir", str(TRAIN), "--splits", "dataset_splits.json", "--split", "0",
    "--epochs", "20", "--max-iters", "200", "--batch-size", "4", "--num-workers", "4",
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
    "fold": 1,
    "stage": "edge_only",
    "train_embryo": "6bba",
    "held_out_embryo": "44b6",
    "detector_source": "versavice/biohub-cv-temporal-fold-weights-v1/fold1",
    "training_code_source": "versavice/biohub-fold0-edge-only-training-6k",
    "additional_epochs": 20,
    "max_iters_per_epoch": 200,
    "total_additional_iterations": 4000,
    "batch_size": 4,
    "detector_frozen": True,
    "validation_clips": pilot_test,
    "best_weights": str(output_dir / "edge_predictor_best.pth"),
    "last_weights": str(output_dir / "edge_predictor_last.pth"),
    "history": str(output_dir / "training_history.json"),
}
(WORK / "fold1_edge_only_training_manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
print("FOLD1_EDGE_ONLY_TRAINING_COMPLETE")
