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

import tracksdata as td
from geff import GeffMetadata

from biohub_tracking.io import open_dataset
from biohub_tracking.metrics import (
    evaluate as compute_metric,
    node_recall,
    per_sample_metrics,
    summarise,
)


def find_prediction_dir(kernel_slug: str, method: str) -> Path:
    candidates = [
        path / "split_0"
        for path in INPUT_ROOT.rglob(method)
        if kernel_slug in str(path).lower() and (path / "split_0").is_dir()
    ]
    assert len(candidates) == 1, candidates
    return candidates[0]


def estimated_total(gt_path: Path) -> float:
    try:
        meta = GeffMetadata.read(gt_path)
        value = (meta.extra or {}).get("estimated_number_of_nodes")
        return float(value) if value is not None else float("nan")
    except Exception:
        return float("nan")


folds = {
    "fold0": {
        "kernel": "biohub-fold0-full-oof-edge500",
        "method": "unet_transformer_fold0_full_edge500",
        "expected_clips": 128,
        "tuned_probability": 0.50,
        "tuned_distance": 5.0,
    },
    "fold1": {
        "kernel": "biohub-fold1-full-oof-edge300",
        "method": "unet_transformer_fold1_full_edge300",
        "expected_clips": 71,
        "tuned_probability": 0.35,
        "tuned_distance": 5.0,
    },
}

prediction_paths = {}
for fold_name, cfg in folds.items():
    prediction_dir = find_prediction_dir(cfg["kernel"], cfg["method"])
    paths = sorted(prediction_dir.glob("*.geff"))
    assert len(paths) == cfg["expected_clips"], (fold_name, prediction_dir, len(paths))
    prediction_paths[fold_name] = paths
    print(f"{fold_name}: {prediction_dir} ({len(paths)} clips)", flush=True)

variants = {
    "baseline": False,
    "tuned": True,
}
results = {}

for variant_name, apply_tuning in variants.items():
    combined_rows = []
    fold_results = {}

    for fold_name, cfg in folds.items():
        fold_rows = []
        kept_edges = 0
        removed_probability = 0
        removed_distance = 0

        for index, pred_path in enumerate(prediction_paths[fold_name], start=1):
            name = pred_path.stem
            loaded = td.graph.IndexedRXGraph.from_geff(pred_path)
            graph = loaded[0] if isinstance(loaded, tuple) else loaded

            if apply_tuning:
                edge_attrs = graph.edge_attrs(
                    attr_keys=["edge_id", "edge_prob", "edge_dist"]
                )
                for edge in edge_attrs.iter_rows(named=True):
                    remove_for_probability = (
                        float(edge["edge_prob"]) < cfg["tuned_probability"]
                    )
                    remove_for_distance = (
                        float(edge["edge_dist"]) > cfg["tuned_distance"]
                    )
                    if remove_for_probability or remove_for_distance:
                        graph.remove_edge(edge_id=int(edge["edge_id"]))
                        removed_probability += int(remove_for_probability)
                        removed_distance += int(
                            remove_for_distance and not remove_for_probability
                        )
                    else:
                        kept_edges += 1
            else:
                kept_edges += graph.num_edges()

            ds = open_dataset(TRAIN / name, require_tracks=True, load_image=False)
            metric = compute_metric(graph, ds.tracks, scale=ds.scale)
            recall = (
                node_recall(graph, ds.tracks)
                if graph.num_edges() > 0 and graph.num_nodes() > 0
                else 0.0
            )
            row = per_sample_metrics(
                metric,
                estimated_total(TRAIN / f"{name}.geff"),
                recall,
            )
            fold_rows.append(row)
            combined_rows.append(row)

            if index % 16 == 0 or index == len(prediction_paths[fold_name]):
                print(
                    f"{variant_name} {fold_name}: {index}/{len(prediction_paths[fold_name])}",
                    flush=True,
                )

        summary = summarise(fold_rows)
        fold_results[fold_name] = {
            "probability": cfg["tuned_probability"] if apply_tuning else None,
            "max_distance": cfg["tuned_distance"] if apply_tuning else None,
            "kept_edges": kept_edges,
            "removed_probability": removed_probability,
            "removed_distance": removed_distance,
            **{
                key: (value.item() if hasattr(value, "item") else value)
                for key, value in summary.items()
            },
        }

    combined = summarise(combined_rows)
    results[variant_name] = {
        "folds": fold_results,
        "combined": {
            key: (value.item() if hasattr(value, "item") else value)
            for key, value in combined.items()
        },
    }
    (WORK / "edge_postprocess_full_results.json").write_text(
        json.dumps(results, indent=2)
    )
    print("FULL_POSTPROCESS_RESULT", variant_name, json.dumps(results[variant_name], sort_keys=True), flush=True)

manifest = {
    "inputs": {
        "fold0": "versavice/biohub-fold0-full-oof-edge500",
        "fold1": "versavice/biohub-fold1-full-oof-edge300",
    },
    "conditions": {
        fold_name: {
            "probability": cfg["tuned_probability"],
            "max_distance": cfg["tuned_distance"],
        }
        for fold_name, cfg in folds.items()
    },
    "results": results,
}
(WORK / "edge_postprocess_full_manifest.json").write_text(json.dumps(manifest, indent=2))
print("EDGE_POSTPROCESS_FULL_COMPLETE")
