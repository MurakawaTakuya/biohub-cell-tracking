from collections import Counter
from pathlib import Path
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


def audit_graph(graph) -> dict:
    keys = td.DEFAULT_ATTR_KEYS
    node_attrs = graph.node_attrs(
        attr_keys=[keys.NODE_ID, "t", "z", "y", "x"]
    )
    edge_attrs = graph.edge_attrs(
        attr_keys=[keys.EDGE_SOURCE, keys.EDGE_TARGET, "edge_prob", "edge_dist"]
    )

    nodes = {
        int(row[keys.NODE_ID]): row
        for row in node_attrs.iter_rows(named=True)
    }
    indegree = Counter()
    outdegree = Counter()
    missing_endpoints = 0
    invalid_time_edges = 0
    invalid_probabilities = 0
    invalid_distances = 0

    for edge in edge_attrs.iter_rows(named=True):
        source = int(edge[keys.EDGE_SOURCE])
        target = int(edge[keys.EDGE_TARGET])
        indegree[target] += 1
        outdegree[source] += 1
        if source not in nodes or target not in nodes:
            missing_endpoints += 1
            continue
        if int(nodes[target]["t"]) != int(nodes[source]["t"]) + 1:
            invalid_time_edges += 1
        probability = float(edge["edge_prob"])
        distance = float(edge["edge_dist"])
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            invalid_probabilities += 1
        if not math.isfinite(distance) or distance < 0.0:
            invalid_distances += 1

    invalid_coordinates = sum(
        not all(math.isfinite(float(row[key])) for key in ("z", "y", "x"))
        for row in nodes.values()
    )
    max_indegree = max(indegree.values(), default=0)
    max_outdegree = max(outdegree.values(), default=0)
    violations = {
        "duplicate_node_ids": len(node_attrs) - len(nodes),
        "missing_edge_endpoints": missing_endpoints,
        "nonconsecutive_time_edges": invalid_time_edges,
        "invalid_edge_probabilities": invalid_probabilities,
        "invalid_edge_distances": invalid_distances,
        "invalid_node_coordinates": invalid_coordinates,
        "indegree_over_1": sum(value > 1 for value in indegree.values()),
        "outdegree_over_2": sum(value > 2 for value in outdegree.values()),
    }
    return {
        "num_nodes": graph.num_nodes(),
        "num_edges": graph.num_edges(),
        "max_indegree": max_indegree,
        "max_outdegree": max_outdegree,
        "violations": violations,
        "passed": all(value == 0 for value in violations.values()),
    }


folds = {
    "fold0": {
        "kernel": "biohub-fold0-full-oof-ilp",
        "method": "unet_transformer_fold0_full_ilp_det990_edge100",
        "candidate_method": "unet_transformer_fold0_full_ilp_det990_edge100_candidates",
        "expected_clips": 128,
    },
    "fold1": {
        "kernel": "biohub-fold1-full-oof-ilp",
        "method": "unet_transformer_fold1_full_ilp_det990_edge100",
        "candidate_method": "unet_transformer_fold1_full_ilp_det990_edge100_candidates",
        "expected_clips": 71,
    },
}

combined_rows = []
fold_results = {}
sample_audits = {}
all_names = []
per_sample_records = []
candidate_graph_summary = {}

for fold_name, cfg in folds.items():
    prediction_dir = find_prediction_dir(cfg["kernel"], cfg["method"])
    candidate_dir = find_prediction_dir(cfg["kernel"], cfg["candidate_method"])
    pred_paths = sorted(prediction_dir.glob("*.geff"))
    candidate_paths = sorted(candidate_dir.glob("*.geff"))
    assert len(pred_paths) == cfg["expected_clips"], (
        fold_name, prediction_dir, len(pred_paths)
    )
    assert len(candidate_paths) == cfg["expected_clips"], (
        fold_name, candidate_dir, len(candidate_paths)
    )
    assert {path.stem for path in candidate_paths} == {path.stem for path in pred_paths}
    candidate_graph_summary[fold_name] = {
        "directory": str(candidate_dir),
        "expected": cfg["expected_clips"],
        "actual": len(candidate_paths),
        "names_match_solved_graphs": True,
    }
    fold_rows = []
    fold_audits = {}
    print(f"{fold_name}: {prediction_dir} ({len(pred_paths)} clips)", flush=True)

    for index, pred_path in enumerate(pred_paths, start=1):
        name = pred_path.stem
        all_names.append(name)
        loaded = td.graph.IndexedRXGraph.from_geff(pred_path)
        graph = loaded[0] if isinstance(loaded, tuple) else loaded
        fold_audits[name] = audit_graph(graph)

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
        per_sample_records.append({
            "fold": fold_name,
            "sample": name,
            **{
                key: (value.item() if hasattr(value, "item") else value)
                for key, value in row.items()
            },
        })
        fold_rows.append(row)
        combined_rows.append(row)

        if index % 16 == 0 or index == len(pred_paths):
            print(f"{fold_name}: {index}/{len(pred_paths)}", flush=True)

    fold_results[fold_name] = {
        key: (value.item() if hasattr(value, "item") else value)
        for key, value in summarise(fold_rows).items()
    }
    sample_audits[fold_name] = fold_audits

combined = {
    key: (value.item() if hasattr(value, "item") else value)
    for key, value in summarise(combined_rows).items()
}
failed_audits = {
    f"{fold_name}/{name}": audit
    for fold_name, audits in sample_audits.items()
    for name, audit in audits.items()
    if not audit["passed"]
}
audit_summary = {
    "expected_total_clips": 199,
    "actual_total_clips": len(all_names),
    "unique_clip_names": len(set(all_names)),
    "duplicate_clip_names": len(all_names) - len(set(all_names)),
    "graphs_passing": len(all_names) - len(failed_audits),
    "graphs_failing": len(failed_audits),
    "failed_graphs": failed_audits,
    "passed": (
        len(all_names) == 199
        and len(set(all_names)) == 199
        and not failed_audits
    ),
}

result = {
    "folds": fold_results,
    "combined": combined,
    "audit": audit_summary,
    "candidate_graphs": candidate_graph_summary,
}
(WORK / "ilp_combined_oof_result.json").write_text(json.dumps(result, indent=2))
(WORK / "ilp_graph_audits.json").write_text(json.dumps(sample_audits, indent=2))
(WORK / "ilp_per_sample_metrics.json").write_text(
    json.dumps(per_sample_records, indent=2)
)
print("ILP_COMBINED_RESULT", json.dumps(combined, sort_keys=True), flush=True)
print("ILP_GRAPH_AUDIT", json.dumps(audit_summary, sort_keys=True), flush=True)
print("ILP_COMBINED_AUDIT_COMPLETE")
