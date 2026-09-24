from pathlib import Path
import importlib.util
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


def embryo_id(name: str) -> str:
    return name.removesuffix(".zarr").split("_", 1)[0]


samples = sorted(path.name.removesuffix(".zarr") for path in TRAIN.glob("*.zarr"))
train_names = [name for name in samples if embryo_id(name) == "44b6"]
test_names = [name for name in samples if embryo_id(name) == "6bba"]
assert len(train_names) == 71, len(train_names)
assert len(test_names) == 128, len(test_names)
split = [{
    "held_out_embryo": "6bba",
    "train": train_names,
    "test": test_names,
}]
splits_path = REPO / "dataset_splits.json"
splits_path.write_text(json.dumps(split, indent=2))

all_best = sorted(INPUT_ROOT.rglob("edge_predictor_best.pth"))
best_candidates = [path for path in all_best if "edge-only-training-6k" in str(path).lower()]
assert len(best_candidates) == 1, best_candidates
source_weights = best_candidates[0]
source_config = source_weights.parent / "config.json"
assert source_config.exists(), source_config
weights_dir = REPO / "weights/unet_transformer/split_0"
weights_dir.mkdir(parents=True, exist_ok=True)
weights_path = weights_dir / "edge_predictor_best.pth"
shutil.copy2(source_weights, weights_path)
shutil.copy2(source_config, weights_dir / "config.json")
print("Using checkpoint", source_weights)

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
os.environ["BIOHUB_DATA_DIR"] = str(TRAIN)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


predict_mod = load_module(
    "predict_unet_transformer",
    REPO / "scripts/predict_unet_transformer.py",
)
dataspec = load_module("dataspec_runtime", REPO / "scripts/dataspec.py")

method = "unet_transformer_fold0_full_edge500"
cfg = predict_mod.PredictConfig(
    det_threshold=0.57,
    det_tta=False,
    pool_kernel_um=5.0,
    edge_activation="softmax",
    threshold=0.5,
    use_ilp=False,
)
predict_mod.predict(
    data_dir=TRAIN,
    fold=0,
    splits_file=splits_path,
    weights_path=weights_path,
    cfg=cfg,
    method=method,
    unet_batch_size=4,
    evaluate=False,
)

output_dir = Path(dataspec.PREDICTIONS_PATH) / predict_mod.USERNAME / method / "split_0"
run = {
    "username": predict_mod.USERNAME,
    "method": method,
    "split": "split_0",
    "dir": output_dir,
    "geffs": sorted(output_dir.glob("*.geff")),
}
evaluation = predict_mod.evaluate_run(run)
summary = predict_mod.summarise(evaluation)
result = {
    key: (value.item() if hasattr(value, "item") else value)
    for key, value in summary.items()
}
manifest = {
    "fold": 0,
    "checkpoint_source": "versavice/biohub-fold0-edge-only-training-6k",
    "train_embryo": "44b6",
    "held_out_embryo": "6bba",
    "train_clips": len(train_names),
    "oof_clips": len(test_names),
    "detection_threshold": 0.57,
    "edge_threshold": 0.5,
    "detection_tta": False,
    "pool_kernel_um": 5.0,
    "use_ilp": False,
    "result": result,
}
(WORK / "fold0_full_oof_result.json").write_text(json.dumps(result, indent=2))
(WORK / "fold0_full_oof_manifest.json").write_text(json.dumps(manifest, indent=2))
print("FULL_OOF_RESULT", json.dumps(result, sort_keys=True), flush=True)
print(json.dumps(manifest, indent=2))
print("FOLD0_FULL_OOF_COMPLETE")
