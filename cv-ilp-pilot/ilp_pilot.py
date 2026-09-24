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

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
os.environ["BIOHUB_DATA_DIR"] = str(TRAIN)


def embryo_id(name: str) -> str:
    return name.removesuffix(".zarr").split("_", 1)[0]


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

samples = sorted(path.name.removesuffix(".zarr") for path in TRAIN.glob("*.zarr"))
all_best = sorted(INPUT_ROOT.rglob("edge_predictor_best.pth"))
folds = {
    "fold0": {
        "train_embryo": "44b6",
        "held_out_embryo": "6bba",
        "checkpoint_match": "edge-only-training-6k",
        "greedy_pilot_score": 0.5877072379268757,
    },
    "fold1": {
        "train_embryo": "6bba",
        "held_out_embryo": "44b6",
        "checkpoint_match": "fold1-edge-only-training-4k",
        "greedy_pilot_score": 0.6454113503280271,
    },
}

det_thresholds = [0.93, 0.96, 0.98, 0.99]
results = {}
for fold_name, fold_cfg in folds.items():
    held_out = [
        name for name in samples
        if embryo_id(name) == fold_cfg["held_out_embryo"]
    ]
    pilot_size = 8
    indices = [
        round(i * (len(held_out) - 1) / (pilot_size - 1))
        for i in range(pilot_size)
    ]
    pilot_test = [held_out[index] for index in indices]
    split = [{
        "held_out_embryo": fold_cfg["held_out_embryo"],
        "train": [
            name for name in samples
            if embryo_id(name) == fold_cfg["train_embryo"]
        ],
        "test": pilot_test,
    }]
    splits_path = WORK / f"{fold_name}_pilot_splits.json"
    splits_path.write_text(json.dumps(split, indent=2))

    candidates = [
        path for path in all_best
        if fold_cfg["checkpoint_match"] in str(path).lower()
    ]
    assert len(candidates) == 1, (fold_name, candidates)
    weights_path = candidates[0]
    assert (weights_path.parent / "config.json").exists(), weights_path.parent
    print(f"{fold_name}: checkpoint={weights_path}", flush=True)

    results[fold_name] = []
    for det_threshold in det_thresholds:
        det_tag = round(det_threshold * 1000)
        method = f"unet_transformer_{fold_name}_ilp_det{det_tag:03d}_edge100"
        cfg = predict_mod.PredictConfig(
            det_threshold=det_threshold,
            det_tta=False,
            pool_kernel_um=5.0,
            edge_activation="softmax",
            threshold=0.1,
            use_ilp=True,
            ilp_edge_weight=-1.0,
            ilp_appearance_weight=0.1,
            ilp_disappearance_weight=0.1,
            ilp_division_weight=1.0,
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

        output_dir = (
            Path(dataspec.PREDICTIONS_PATH)
            / predict_mod.USERNAME
            / method
            / "split_0"
        )
        run = {
            "username": predict_mod.USERNAME,
            "method": method,
            "split": "split_0",
            "dir": output_dir,
            "geffs": sorted(output_dir.glob("*.geff")),
        }
        assert len(run["geffs"]) == pilot_size, run["geffs"]
        evaluation = predict_mod.evaluate_run(run)
        summary = predict_mod.summarise(evaluation)
        record = {
            "fold": fold_name,
            "validation_clips": pilot_test,
            "detection_threshold": det_threshold,
            "candidate_edge_threshold": 0.1,
            "use_ilp": True,
            "ilp_edge_weight": -1.0,
            "ilp_appearance_weight": 0.1,
            "ilp_disappearance_weight": 0.1,
            "ilp_division_weight": 1.0,
            **{
                key: (value.item() if hasattr(value, "item") else value)
                for key, value in summary.items()
            },
        }
        results[fold_name].append(record)
        (WORK / "ilp_det_sweep_results.json").write_text(
            json.dumps(results, indent=2)
        )
        print("ILP_DET_SWEEP_RESULT", json.dumps(record, sort_keys=True), flush=True)

        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

manifest = {
    "checkpoint_sources": {
        "fold0": "versavice/biohub-fold0-edge-only-training-6k",
        "fold1": "versavice/biohub-fold1-edge-only-training-4k",
    },
    "detection_thresholds": det_thresholds,
    "results": results,
}
(WORK / "ilp_det_sweep_manifest.json").write_text(json.dumps(manifest, indent=2))
print("ILP_DET_SWEEP_COMPLETE")
