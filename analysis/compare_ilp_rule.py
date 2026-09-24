from pathlib import Path
import csv
import json
import statistics


ROOT = Path(__file__).resolve().parents[1]
ILP_PATH = ROOT / "ilp-combined-audit-output-v2/ilp_per_sample_metrics.json"
RULE_PATHS = {
    "44b6": ROOT / "rule-based-cv-44b6-global-shift-output/rule_based_cv_per_sample.csv",
    "6bba": ROOT / "rule-based-cv-6bba-global-shift-output/rule_based_cv_per_sample.csv",
}


ilp = {row["sample"]: row for row in json.loads(ILP_PATH.read_text())}
rule = {}
for embryo, path in RULE_PATHS.items():
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            row["embryo"] = embryo
            for key in row.keys() - {"dataset", "embryo"}:
                row[key] = float(row[key])
            rule[row["dataset"]] = row

assert set(ilp) == set(rule), (len(ilp), len(rule), set(ilp) ^ set(rule))

records = []
for sample in sorted(ilp):
    learned = ilp[sample]
    baseline = rule[sample]
    records.append({
        "sample": sample,
        "embryo": baseline["embryo"],
        "ilp_adj": learned["adj_edge_jaccard"],
        "rule_adj": baseline["adjusted_edge_jaccard"],
        "delta": learned["adj_edge_jaccard"] - baseline["adjusted_edge_jaccard"],
        "ilp_raw": learned["edge_jaccard"],
        "rule_raw": baseline["raw_edge_jaccard"],
        "ilp_tp": learned["edge_tp"],
        "rule_tp": int(baseline["edge_tp"]),
        "ilp_fp": learned["edge_fp"],
        "rule_fp": int(baseline["edge_fp"]),
        "ilp_fn": learned["edge_fn"],
        "rule_fn": int(baseline["edge_fn"]),
        "ilp_nodes": learned["num_pred_nodes"],
        "rule_nodes": int(baseline["pred_nodes"]),
        "ilp_total_node_ratio": learned["total_node_ratio"],
        "ilp_node_recall": learned["node_recall"],
    })


def summarise(rows):
    deltas = [row["delta"] for row in rows]
    return {
        "samples": len(rows),
        "ilp_wins": sum(delta > 0 for delta in deltas),
        "ties": sum(delta == 0 for delta in deltas),
        "rule_wins": sum(delta < 0 for delta in deltas),
        "mean_delta": statistics.fmean(deltas),
        "median_delta": statistics.median(deltas),
        "mean_ilp_adj": statistics.fmean(row["ilp_adj"] for row in rows),
        "mean_rule_adj": statistics.fmean(row["rule_adj"] for row in rows),
        "sum_ilp_tp": sum(row["ilp_tp"] for row in rows),
        "sum_rule_tp": sum(row["rule_tp"] for row in rows),
        "sum_ilp_fp": sum(row["ilp_fp"] for row in rows),
        "sum_rule_fp": sum(row["rule_fp"] for row in rows),
        "sum_ilp_fn": sum(row["ilp_fn"] for row in rows),
        "sum_rule_fn": sum(row["rule_fn"] for row in rows),
        "sum_ilp_nodes": sum(row["ilp_nodes"] for row in rows),
        "sum_rule_nodes": sum(row["rule_nodes"] for row in rows),
        "mean_ilp_total_node_ratio": statistics.fmean(
            row["ilp_total_node_ratio"] for row in rows
        ),
        "mean_ilp_node_recall": statistics.fmean(row["ilp_node_recall"] for row in rows),
    }


report = {
    "overall": summarise(records),
    "by_embryo": {
        embryo: summarise([row for row in records if row["embryo"] == embryo])
        for embryo in RULE_PATHS
    },
    "largest_ilp_wins": sorted(records, key=lambda row: row["delta"], reverse=True)[:10],
    "largest_rule_wins": sorted(records, key=lambda row: row["delta"])[:10],
}
print(json.dumps(report, indent=2))
