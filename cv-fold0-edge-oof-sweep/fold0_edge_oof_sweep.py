from pathlib import Path
import gc
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
held_out_samples = [name for name in samples if embryo_id(name) == "6bba"]
pilot_size = 8
pilot_indices = [round(i * (len(held_out_samples) - 1) / (pilot_size - 1)) for i in range(pilot_size)]
pilot_test = [held_out_samples[i] for i in pilot_indices]
split = [{
    "held_out_embryo": "6bba",
    "train": [name for name in samples if embryo_id(name) == "44b6"],
    "test": pilot_test,
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

# Training used raw detection logits > 0.3, approximately sigmoid > 0.574.
# Sweep the newly calibrated edge probabilities while keeping detection fixed.
edge_thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
results = []
for threshold in edge_thresholds:
    method = f"unet_transformer_edge{round(threshold * 1000):03d}"
    print(f"\n=== {method} threshold={threshold:.3f} ===", flush=True)
    cfg = predict_mod.PredictConfig(
        det_threshold=0.57,
        det_tta=False,
        pool_kernel_um=5.0,
        edge_activation="softmax",
        threshold=threshold,
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
    record = {
        "edge_threshold": threshold,
        "method": method,
        **{
            key: (value.item() if hasattr(value, "item") else value)
            for key, value in summary.items()
        },
    }
    results.append(record)
    (WORK / "fold0_edge_oof_results.json").write_text(json.dumps(results, indent=2))
    print("OOF_RESULT", json.dumps(record, sort_keys=True), flush=True)

    gc.collect()
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

manifest = {
    "fold": 0,
    "checkpoint_source": "versavice/biohub-fold0-edge-only-training-6k",
    "held_out_embryo": "6bba",
    "validation_clips": pilot_test,
    "detection_threshold": 0.57,
    "detection_tta": False,
    "pool_kernel_um": 5.0,
    "use_ilp": False,
    "edge_thresholds": edge_thresholds,
    "results": results,
}
(WORK / "fold0_edge_oof_manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
print("EDGE_OOF_SWEEP_COMPLETE")
