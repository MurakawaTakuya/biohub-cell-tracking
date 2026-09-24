# Biohub Cell Tracking Roadmap

Updated: 2026-07-16

## Current position

- Best submission: Public LB 0.902 (submission 54694871)
- D4 edge TTA: 0.901, rejected
- Rule-based CV baseline: 44b6 0.8093065271, 6bba 0.8230984698, combined 0.8209746512
- Duplicate-frame identity linking: no score change, rejected
- Global-shift linking: 44b6 0.8099436513 (+0.0006371243); 6bba was still running

## Retrospective

Reproducing the public 0.902 notebook, validating the submission schema, using
the code-competition submission path, and building an official-metric CV loop
were useful foundations.

Recent rule-based experiments are not the main path to a large gain. The 0.902
submission is produced by a learned pipeline:

1. TemporalUNet3D cell-center detection
2. Node cross-attention transformer edge scoring
3. ILP graph construction
4. Motion relinking, gap recovery, conservative divisions, and smoothing

The existing learned-model CV is invalid: an earlier evaluation produced about
0.0058 score and 0.008 node recall, which is incompatible with the 0.902 public
submission. The immediate priority is to reproduce the learned inference
pipeline faithfully on training data.

## Main roadmap

### 1. Build a faithful learned-pipeline OOF evaluator

- Run the public 0.902 inference path unchanged on train samples.
- Use the same 50-epoch checkpoint, detection threshold, transformer, ILP, and graph repair.
- Evaluate 44b6 and 6bba with the official metric.
- Save per-sample node, edge, division, gap, and graph-repair diagnostics.
- Do not begin long training runs until the extreme node-recall failure is fixed.

Acceptance:

- Node recall is no longer near zero.
- Learned pipeline clearly exceeds the 0.821 rule-based combined CV.
- Ablation ordering is stable across both embryos.

### 2. Train two cross-embryo folds

- Fold A: train on 44b6, validate on 6bba.
- Fold B: train on 6bba, validate on 44b6.
- Start with a 5-10 epoch runtime and correctness pilot.
- If healthy, train 100-300 epochs on Kaggle GPU.
- Track detection loss, edge loss, node recall, adjusted edge Jaccard, and division Jaccard separately.
- Add brightness, flip, global-shift, and missing-frame augmentations after the faithful baseline is fixed.

### 3. Ensemble checkpoints before graph construction

- Average detection logits, then extract one shared candidate set.
- Average edge logits on those shared candidates.
- Solve ILP once after averaging.
- Compare public 50ep, fold A, fold B, and their combinations.
- Do not blend completed CSV graphs as the primary ensemble.

### 4. Optimize graph construction with cached predictions

Cache detections and edge logits, then search without repeating GPU inference:

- detection threshold
- ILP edge, appearance, disappearance, and division costs
- learned-edge motion bonus
- tight and relaxed motion radii
- velocity weight
- one-frame and two-frame gap recovery
- minimum component length
- division geometry and addition caps

Selection requires improvement on the official combined score without a large
drop on either embryo.

### 5. Improve division prediction

After edge tracking is stable, train or calibrate a division-specific predictor
using parent motion, daughter symmetry, sister distance, intensity change, and
learned edge probabilities.

## Score targets

- First target: Public LB 0.905+
- Second target: Public LB 0.915-0.925
- Ambitious target: Public LB 0.94+

The current leaderboard top observed on 2026-07-16 was 0.970, but that is not a
guaranteed reachable target.

## Submission gate

Submit only when:

1. official combined OOF improves;
2. neither embryo drops materially;
3. output schema and graph invariants pass;
4. the change is algorithmically active in run statistics;
5. the candidate is meaningfully different from the current 0.902 anchor.

## Immediate next action

Collect the 6bba global-shift result, then stop rule-based micro-tuning and build
the faithful learned-pipeline OOF evaluator.
