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

# Keep NumPy out of this process until the offline wheel set has been installed.
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


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    assert count == 1, f"{label}: expected exactly one match, found {count}"
    return source.replace(old, new, 1)


train_path = REPO / "scripts/train_unet_transformer.py"
source = train_path.read_text()

old_pair = '''def _evaluate_pair(
    logits: torch.Tensor,
    target: torch.Tensor,
) -> tuple[float, int, int]:
    """Per-pair evaluation. Returns (loss, correct, total)."""
    active_rows = target.sum(dim=1) > 0
    active_cols = target.sum(dim=0) > 0
    if not active_rows.any():
        return 0.0, 0, 0

    loss = compute_loss(logits, target).item()
    probs = torch.softmax(logits, dim=0)
    preds = (probs > 0.5).float()

    mask = active_rows.unsqueeze(1) | active_cols.unsqueeze(0)
    correct = (preds[mask] == target[mask]).sum().item()
    total = mask.sum().item()

    return loss, correct, total
'''
new_pair = '''def _evaluate_pair(
    logits: torch.Tensor,
    target: torch.Tensor,
) -> tuple[float, int, int, int, int, float, int, float, float]:
    """Evaluate binary accuracy and parent-ranking quality for one frame pair."""
    active_rows = target.sum(dim=1) > 0
    active_cols = target.sum(dim=0) > 0
    if not active_cols.any():
        return 0.0, 0, 0, 0, 0, 0.0, 0, 0.0, 0.0

    loss = compute_loss(logits, target).item()
    probs = torch.softmax(logits, dim=0)
    preds = (probs > 0.5).float()

    mask = active_rows.unsqueeze(1) | active_cols.unsqueeze(0)
    correct = (preds[mask] == target[mask]).sum().item()
    total = mask.sum().item()

    top1_correct = 0
    positive_prob_sum = 0.0
    margin_sum = 0.0
    reciprocal_rank_sum = 0.0
    active_indices = torch.nonzero(active_cols, as_tuple=False).flatten()
    for col in active_indices:
        col_target = target[:, col] > 0
        col_probs = probs[:, col]
        positive_prob = col_probs[col_target].max()
        negative_probs = col_probs[~col_target]
        hard_negative = negative_probs.max() if negative_probs.numel() else positive_prob
        top1_correct += int(col_target[col_probs.argmax()].item())
        positive_prob_sum += float(positive_prob.item())
        margin_sum += float((positive_prob - hard_negative).item())
        rank = 1 + int((col_probs > positive_prob).sum().item())
        reciprocal_rank_sum += 1.0 / rank

    n_ranked = int(active_indices.numel())
    return (
        loss, correct, total, top1_correct, n_ranked,
        positive_prob_sum, n_ranked, margin_sum, reciprocal_rank_sum,
    )
'''
source = replace_once(source, old_pair, new_pair, "ranking metrics")

source = replace_once(
    source,
    '''    Returns (avg_loss, accuracy, node_recall).
    """
    model.eval()
    total_loss, correct, total, n_pairs = 0.0, 0, 0, 0
    gt_matched, gt_total = 0, 0
''',
    '''    Returns a dictionary containing detection and edge-ranking metrics.
    """
    model.eval()
    total_loss, correct, total, n_pairs = 0.0, 0, 0, 0
    gt_matched, gt_total = 0, 0
    top1_correct = top1_total = 0
    positive_prob_sum = margin_sum = reciprocal_rank_sum = 0.0
    positive_count = 0
''',
    "evaluate accumulators",
)

source = replace_once(
    source,
    '''                pair_loss, pair_correct, pair_total = _evaluate_pair(
                    pair_logits[b, :ns_b, :nt_b], pair_target[b, :ns_b, :nt_b],
                )
                total_loss += pair_loss
                correct += pair_correct
                total += pair_total
                n_pairs += 1

    node_recall = gt_matched / max(gt_total, 1)
    return total_loss / max(n_pairs, 1), correct / max(total, 1), node_recall
''',
    '''                (
                    pair_loss, pair_correct, pair_total,
                    pair_top1_correct, pair_top1_total,
                    pair_positive_prob_sum, pair_positive_count,
                    pair_margin_sum, pair_reciprocal_rank_sum,
                ) = _evaluate_pair(
                    pair_logits[b, :ns_b, :nt_b], pair_target[b, :ns_b, :nt_b],
                )
                total_loss += pair_loss
                correct += pair_correct
                total += pair_total
                top1_correct += pair_top1_correct
                top1_total += pair_top1_total
                positive_prob_sum += pair_positive_prob_sum
                positive_count += pair_positive_count
                margin_sum += pair_margin_sum
                reciprocal_rank_sum += pair_reciprocal_rank_sum
                n_pairs += 1

    return {
        "loss": total_loss / max(n_pairs, 1),
        "binary_accuracy": correct / max(total, 1),
        "node_recall": gt_matched / max(gt_total, 1),
        "edge_top1": top1_correct / max(top1_total, 1),
        "positive_probability": positive_prob_sum / max(positive_count, 1),
        "hard_negative_margin": margin_sum / max(positive_count, 1),
        "mrr": reciprocal_rank_sum / max(positive_count, 1),
        "ranked_edges": top1_total,
    }
''',
    "evaluate aggregation",
)

source = replace_once(
    source,
    '''    unet_weights: Path | None = None,
    downsample: tuple[int, ...] = (1, 4, 4),
''',
    '''    unet_weights: Path | None = None,
    resume_weights: Path | None = None,
    downsample: tuple[int, ...] = (1, 4, 4),
''',
    "resume signature",
)

source = replace_once(
    source,
    '''    model = UNetNodeTransformer(
        unet=unet,
        unet_out_channels=unet_out_channels,
        pos_feat_dim=pos_feat_dim,
    ).to(device)

    # Simple multi-GPU: split the heavy UNet pass across all visible GPUs.
''',
    '''    model = UNetNodeTransformer(
        unet=unet,
        unet_out_channels=unet_out_channels,
        pos_feat_dim=pos_feat_dim,
    ).to(device)
    if resume_weights is not None:
        state = torch.load(resume_weights, map_location=device, weights_only=True)
        model.load_state_dict(state, strict=True)
        print(f"Resumed full model from {resume_weights}", flush=True)

    # Simple multi-GPU: split the heavy UNet pass across all visible GPUs.
''',
    "resume load",
)

old_loop = '''    best_score = 0.0
    save_path = output_dir / "edge_predictor_best.pth"
    pbar = tqdm(range(n_epochs), desc="Training", disable=False)
    print(f"Detection loss: weight={det_loss_weight}, neg_weight={det_neg_weight}", flush=True)

    for epoch in pbar:
        t0 = time.monotonic()
        edge_loss, det_loss = train_epoch(
            model, train_loader, optimizer, device, det_loss_weight, det_neg_weight,
            max_iters=max_iters, pool_kernel_um=pool_kernel_um,
        )
        train_time = time.monotonic() - t0

        t0 = time.monotonic()
        test_loss, test_acc, test_recall = evaluate(model, test_loader, device, pool_kernel_um=pool_kernel_um)
        test_time = time.monotonic() - t0

        score = test_acc * test_recall
        is_best = score >= best_score

        if is_best:
            best_score = score
            # Normalise any DataParallel "unet.module." prefix to "unet." so the
            # checkpoint loads on a single GPU (e.g. in the prediction script).
            torch.save(
                {k.replace("unet.module.", "unet.", 1): v for k, v in model.state_dict().items()},
                save_path,
            )

        marker = "*" if is_best else " "
        pbar.set_postfix(edge=f"{edge_loss:.4f}", det=f"{det_loss:.4f}", acc=f"{test_acc:.4f}")
        print(
            f"  Epoch {epoch:3d}/{n_epochs} | edge={edge_loss:.4f} | det={det_loss:.4f} | "
            f"test_loss={test_loss:.4f} | acc={test_acc:.4f} | recall={test_recall:.4f} | best={best_score:.4f} {marker} | "
            f"train={train_time:.1f}s test={test_time:.1f}s",
            flush=True,
        )

    print(f"\\nBest score (acc*recall): {best_score:.4f}, saved to {save_path}", flush=True)
'''
new_loop = '''    best_score = -1.0
    save_path = output_dir / "edge_predictor_best.pth"
    last_path = output_dir / "edge_predictor_last.pth"
    history_path = output_dir / "training_history.json"
    history = []
    pbar = tqdm(range(n_epochs), desc="Training", disable=False)
    print(f"Detection loss: weight={det_loss_weight}, neg_weight={det_neg_weight}", flush=True)

    for epoch in pbar:
        t0 = time.monotonic()
        edge_loss, det_loss = train_epoch(
            model, train_loader, optimizer, device, det_loss_weight, det_neg_weight,
            max_iters=max_iters, pool_kernel_um=pool_kernel_um,
        )
        train_time = time.monotonic() - t0

        t0 = time.monotonic()
        metrics = evaluate(model, test_loader, device, pool_kernel_um=pool_kernel_um)
        test_time = time.monotonic() - t0

        score = metrics["edge_top1"] * metrics["node_recall"]
        is_best = score >= best_score
        state = {k.replace("unet.module.", "unet.", 1): v for k, v in model.state_dict().items()}
        torch.save(state, last_path)
        if is_best:
            best_score = score
            torch.save(state, save_path)

        record = {
            "epoch": epoch, "train_edge_loss": edge_loss,
            "train_detection_loss": det_loss, "selection_score": score,
            **metrics, "train_seconds": train_time, "test_seconds": test_time,
        }
        history.append(record)
        history_path.write_text(json.dumps(history, indent=2))

        marker = "*" if is_best else " "
        pbar.set_postfix(edge=f"{edge_loss:.4f}", top1=f"{metrics['edge_top1']:.4f}", mrr=f"{metrics['mrr']:.4f}")
        print(
            f"  Epoch {epoch:3d}/{n_epochs} | edge={edge_loss:.4f} | det={det_loss:.4f} | "
            f"test_loss={metrics['loss']:.4f} | recall={metrics['node_recall']:.4f} | "
            f"top1={metrics['edge_top1']:.4f} | mrr={metrics['mrr']:.4f} | "
            f"pos_p={metrics['positive_probability']:.6f} | margin={metrics['hard_negative_margin']:.6f} | "
            f"ranked={metrics['ranked_edges']} | best={best_score:.4f} {marker} | "
            f"train={train_time:.1f}s test={test_time:.1f}s",
            flush=True,
        )

    print(f"\\nBest score (edge_top1*recall): {best_score:.4f}, saved to {save_path}", flush=True)
'''
source = replace_once(source, old_loop, new_loop, "checkpoint selection")

source = replace_once(
    source,
    '''    parser.add_argument("--unet-weights", type=str, default=None,
                        help="Path to pretrained UNet weights; loaded with strict=False.")
''',
    '''    parser.add_argument("--unet-weights", type=str, default=None,
                        help="Path to pretrained UNet weights; loaded with strict=False.")
    parser.add_argument("--resume-weights", type=str, default=None,
                        help="Path to a full model checkpoint to resume from.")
''',
    "resume cli",
)
source = replace_once(
    source,
    '''    unet_weights = Path(args.unet_weights) if args.unet_weights else None
    debug_video = Path(args.debug_video) if args.debug_video else None
''',
    '''    unet_weights = Path(args.unet_weights) if args.unet_weights else None
    resume_weights = Path(args.resume_weights) if args.resume_weights else None
    debug_video = Path(args.debug_video) if args.debug_video else None
''',
    "resume parse",
)
source = replace_once(
    source,
    '''            unet_weights=unet_weights,
            downsample=downsample,
''',
    '''            unet_weights=unet_weights,
            resume_weights=resume_weights,
            downsample=downsample,
''',
    "resume call",
)

train_path.write_text(source)
subprocess.run([sys.executable, "-m", "py_compile", str(train_path)], check=True)
print("Patched training script with edge-ranking metrics and full-model resume")


def embryo_id(name: str) -> str:
    return name.removesuffix(".zarr").split("_", 1)[0]


samples = sorted(path.name.removesuffix(".zarr") for path in TRAIN.glob("*.zarr"))
embryos = sorted({embryo_id(name) for name in samples})
assert embryos == ["44b6", "6bba"], embryos
held_out_samples = [name for name in samples if embryo_id(name) == "6bba"]
pilot_size = 8
pilot_indices = [round(i * (len(held_out_samples) - 1) / (pilot_size - 1)) for i in range(pilot_size)]
pilot_test = [held_out_samples[i] for i in pilot_indices]
split = [{
    "held_out_embryo": "6bba",
    "train": [name for name in samples if embryo_id(name) == "44b6"],
    "test": pilot_test,
}]
(REPO / "dataset_splits.json").write_text(json.dumps(split, indent=2))

all_checkpoints = sorted(INPUT_ROOT.rglob("edge_predictor_best.pth"))
resume_candidates = [path for path in all_checkpoints if "fold0-pilot" in str(path).lower()]
assert len(resume_candidates) == 1, resume_candidates
resume_path = resume_candidates[0]
print({"train_clips": len(split[0]["train"]), "pilot_test_clips": len(pilot_test)})
print("Resuming from", resume_path)

train_cmd = [
    sys.executable, "scripts/train_unet_transformer.py",
    "--data-dir", str(TRAIN), "--splits", "dataset_splits.json", "--split", "0",
    "--epochs", "20", "--max-iters", "50", "--batch-size", "4", "--num-workers", "4",
    "--resume-weights", str(resume_path), "--single-gpu",
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
    "train_embryo": "44b6",
    "held_out_embryo": "6bba",
    "resumed_from": str(resume_path),
    "additional_epochs": 20,
    "max_iters_per_epoch": 50,
    "validation_clips": pilot_test,
    "best_weights": str(output_dir / "edge_predictor_best.pth"),
    "last_weights": str(output_dir / "edge_predictor_last.pth"),
    "history": str(output_dir / "training_history.json"),
}
(WORK / "fold0_edge_training_manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
print("EDGE_TRAINING_COMPLETE")
