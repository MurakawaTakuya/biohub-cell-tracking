from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys


FOLD_NAME = "fold0"

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


folds = {
    "fold0": {
        "train_embryo": "44b6",
        "held_out_embryo": "6bba",
        "expected_train": 71,
        "expected_test": 128,
        "checkpoint_match": "edge-only-training-6k",
        "checkpoint_source": "versavice/biohub-fold0-edge-only-training-6k",
        "greedy_full_score": 0.550431658661895,
        "ilp_det057_full_score": 0.5976826820477505,
    },
    "fold1": {
        "train_embryo": "6bba",
        "held_out_embryo": "44b6",
        "expected_train": 128,
        "expected_test": 71,
        "checkpoint_match": "fold1-edge-only-training-4k",
        "checkpoint_source": "versavice/biohub-fold1-edge-only-training-4k",
        "greedy_full_score": 0.6673449285076791,
        "ilp_det057_full_score": 0.7114563135066861,
    },
}
cfg_fold = folds[FOLD_NAME]

samples = sorted(path.name.removesuffix(".zarr") for path in TRAIN.glob("*.zarr"))
train_names = [name for name in samples if embryo_id(name) == cfg_fold["train_embryo"]]
test_names = [name for name in samples if embryo_id(name) == cfg_fold["held_out_embryo"]]
assert len(train_names) == cfg_fold["expected_train"], len(train_names)
assert len(test_names) == cfg_fold["expected_test"], len(test_names)

split = [{
    "held_out_embryo": cfg_fold["held_out_embryo"],
    "train": train_names,
    "test": test_names,
}]
splits_path = WORK / f"{FOLD_NAME}_full_ilp_splits.json"
splits_path.write_text(json.dumps(split, indent=2))

all_best = sorted(INPUT_ROOT.rglob("edge_predictor_best.pth"))
candidates = [
    path for path in all_best
    if cfg_fold["checkpoint_match"] in str(path).lower()
]
assert len(candidates) == 1, candidates
weights_path = candidates[0]
assert (weights_path.parent / "config.json").exists(), weights_path.parent
print(f"{FOLD_NAME}: checkpoint={weights_path}", flush=True)

predict_path = REPO / "scripts/predict_unet_transformer.py"
predict_source = predict_path.read_text()
candidate_hook_needle = """        graph = build_graph(coords, edges)
        if cfg.use_ilp and graph.num_edges() > 0:
"""
candidate_hook_replacement = """        graph = build_graph(coords, edges)
        candidate_output_dir = (
            output_dir.parent.parent / f"{method}_candidates" / f"split_{fold}"
        )
        candidate_output_dir.mkdir(parents=True, exist_ok=True)
        save_graph(graph, candidate_output_dir / f"{name}.geff")
        if cfg.use_ilp and graph.num_edges() > 0:
"""
assert candidate_hook_needle in predict_source
predict_path.write_text(
    predict_source.replace(
        candidate_hook_needle,
        candidate_hook_replacement,
        1,
    )
)

predict_mod = load_module(
    "predict_unet_transformer",
    predict_path,
)
dataspec = load_module("dataspec_runtime", REPO / "scripts/dataspec.py")

method = f"unet_transformer_{FOLD_NAME}_full_ilp_det990_edge100"
cfg = predict_mod.PredictConfig(
    det_threshold=0.99,
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
assert len(run["geffs"]) == len(test_names), len(run["geffs"])
evaluation = predict_mod.evaluate_run(run)
summary = predict_mod.summarise(evaluation)
result = {
    key: (value.item() if hasattr(value, "item") else value)
    for key, value in summary.items()
}
result["delta_vs_greedy_postprocessed"] = result["score"] - cfg_fold["greedy_full_score"]
result["delta_vs_ilp_det057"] = result["score"] - cfg_fold["ilp_det057_full_score"]

manifest = {
    "fold": FOLD_NAME,
    "checkpoint_source": cfg_fold["checkpoint_source"],
    "train_embryo": cfg_fold["train_embryo"],
    "held_out_embryo": cfg_fold["held_out_embryo"],
    "train_clips": len(train_names),
    "oof_clips": len(test_names),
    "detection_threshold": 0.99,
    "candidate_edge_threshold": 0.1,
    "candidate_graph_method": f"{method}_candidates",
    "candidate_graphs_saved": True,
    "use_ilp": True,
    "ilp_edge_weight": -1.0,
    "ilp_appearance_weight": 0.1,
    "ilp_disappearance_weight": 0.1,
    "ilp_division_weight": 1.0,
    "greedy_postprocessed_full_score": cfg_fold["greedy_full_score"],
    "ilp_det057_full_score": cfg_fold["ilp_det057_full_score"],
    "result": result,
}
(WORK / f"{FOLD_NAME}_full_ilp_result.json").write_text(json.dumps(result, indent=2))
(WORK / f"{FOLD_NAME}_full_ilp_manifest.json").write_text(json.dumps(manifest, indent=2))
print("FULL_ILP_RESULT", json.dumps(result, sort_keys=True), flush=True)
print(json.dumps(manifest, indent=2), flush=True)
print(f"{FOLD_NAME.upper()}_FULL_ILP_COMPLETE")
