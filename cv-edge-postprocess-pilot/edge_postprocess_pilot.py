from pathlib import Path
import importlib.util
import json
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

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
os.environ["BIOHUB_DATA_DIR"] = str(TRAIN)

import numpy as np
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
        "kernel": "biohub-fold0-edge-oof-sweep",
        "method": "unet_transformer_edge100",
        "probabilities": [0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
    },
    "fold1": {
        "kernel": "biohub-fold1-edge-oof-sweep",
        "method": "unet_transformer_fold1_edge100",
        "probabilities": [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45],
    },
}
distance_gates = [None, 5.0, 10.0, 20.0, 40.0]
all_results = {}

for fold_name, cfg in folds.items():
    prediction_dir = find_prediction_dir(cfg["kernel"], cfg["method"])
    pred_paths = sorted(prediction_dir.glob("*.geff"))
    assert len(pred_paths) == 8, (fold_name, prediction_dir, len(pred_paths))
    print(f"{fold_name}: {prediction_dir}", flush=True)

    distance_samples = []
    for pred_path in pred_paths:
        loaded = td.graph.IndexedRXGraph.from_geff(pred_path)
        graph = loaded[0] if isinstance(loaded, tuple) else loaded
        attrs = graph.edge_attrs(attr_keys=["edge_dist"])
        if len(attrs):
            distance_samples.extend(attrs["edge_dist"].to_list())
    distance_quantiles = (
        np.quantile(np.asarray(distance_samples), [0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]).tolist()
        if distance_samples else []
    )
    print(f"{fold_name} edge_dist quantiles: {distance_quantiles}", flush=True)

    fold_results = []
    for probability in cfg["probabilities"]:
        for max_distance in distance_gates:
            rows = []
            kept_edges = 0
            removed_probability = 0
            removed_distance = 0

            for pred_path in pred_paths:
                name = pred_path.stem
                loaded = td.graph.IndexedRXGraph.from_geff(pred_path)
                graph = loaded[0] if isinstance(loaded, tuple) else loaded
                edge_attrs = graph.edge_attrs(
                    attr_keys=["edge_id", "edge_prob", "edge_dist"]
                )
                for edge in edge_attrs.iter_rows(named=True):
                    edge_id = edge["edge_id"]
                    edge_prob = edge["edge_prob"]
                    edge_dist = edge["edge_dist"]
                    remove_for_probability = float(edge_prob) < probability
                    remove_for_distance = (
                        max_distance is not None and float(edge_dist) > max_distance
                    )
                    if remove_for_probability or remove_for_distance:
                        graph.remove_edge(edge_id=int(edge_id))
                        removed_probability += int(remove_for_probability)
                        removed_distance += int(remove_for_distance and not remove_for_probability)
                    else:
                        kept_edges += 1

                ds = open_dataset(
                    TRAIN / name,
                    require_tracks=True,
                    load_image=False,
                )
                metric = compute_metric(graph, ds.tracks, scale=ds.scale)
                recall = (
                    node_recall(graph, ds.tracks)
                    if graph.num_edges() > 0 and graph.num_nodes() > 0
                    else 0.0
                )
                rows.append(per_sample_metrics(
                    metric,
                    estimated_total(TRAIN / f"{name}.geff"),
                    recall,
                ))

            summary = summarise(rows)
            record = {
                "fold": fold_name,
                "edge_probability": probability,
                "max_edge_distance": max_distance,
                "kept_edges": kept_edges,
                "removed_probability": removed_probability,
                "removed_distance": removed_distance,
                **{
                    key: (value.item() if hasattr(value, "item") else value)
                    for key, value in summary.items()
                },
            }
            fold_results.append(record)
            print("POSTPROCESS_RESULT", json.dumps(record, sort_keys=True), flush=True)
            all_results[fold_name] = {
                "input_dir": str(prediction_dir),
                "edge_distance_quantiles": distance_quantiles,
                "results": fold_results,
            }
            (WORK / "edge_postprocess_pilot_results.json").write_text(
                json.dumps(all_results, indent=2)
            )

best = {
    fold_name: max(data["results"], key=lambda row: row["score"])
    for fold_name, data in all_results.items()
}
manifest = {
    "inputs": {
        "fold0": "versavice/biohub-fold0-edge-oof-sweep version 2 edge100",
        "fold1": "versavice/biohub-fold1-edge-oof-sweep version 1 edge100",
    },
    "distance_gates": distance_gates,
    "best": best,
}
(WORK / "edge_postprocess_pilot_manifest.json").write_text(json.dumps(manifest, indent=2))
print("BEST_POSTPROCESS", json.dumps(best, sort_keys=True), flush=True)
print("EDGE_POSTPROCESS_PILOT_COMPLETE")
