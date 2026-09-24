# Leakage-safe CV plan

The train set contains clips from only two embryo IDs.  This project uses
leave-one-embryo-out evaluation (LOEO), never a clip-level random split.

1. Generate `embryo_loco_splits.json` from the Kaggle `train/` mount.
2. For each fold, train the temporal UNet + edge model only on the non-held-out
   embryo, infer every held-out clip, then score with the official metric.
3. Train the DeepCenter repair gate on that same fold's training embryo and
   compare its add-only repair policy against the exact baseline graph.

The public DeepCenter checkpoint is useful for an execution smoke test, but it
must not be used for CV because it may have seen both embryos.  Each CV fold
therefore needs its own DeepCenter checkpoint.

Kaggle is the execution environment for the full data and GPU workload.  This
directory remains the source of truth for split generation and aggregated
results downloaded from each run.
