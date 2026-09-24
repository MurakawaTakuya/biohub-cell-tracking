# 公開 Notebook の調査（2026-09-23）

## スコアの手がかり

- Kernel の一覧 API ではスコアを取得できない。`kaggle kernels list --competition biohub-cell-tracking-during-development --sort-by scoreDescending` の並び順だけが手がかりになる。
- 上位 7 本はそれぞれ別のスコア。そのあとは日付順に並ぶ 0.947 の同点ブロックが続く（8〜45 位、sjlee101/biohub-lf-dctta など）。
- **タイトルのスコアは当てにならない。** haideptry の「0.951 SOTA」「0.949+」「0.948+」や、「0.948 Reproduction」系は、スコア順では 0.947 より下にある。

## 上位（スコア順）

| 順 | Notebook | 備考 |
| --- | --- | --- |
| 1 | anvithpothula/biohub-x138 | 非公開データセット `biohub-v1284-head-s075` がないと自分で例外を投げて止まる。head を外した版が B003（0.946） |
| 2 | amanatar/biohub-geometric-fusion | 公開データセットだけで動く。Harmonic Fusion に weak-leaf pruning と拡張スイープを加えたもの。B002 / B004 のベース |
| 3 | evgendvorkin/biohub-0-947-lb-proxy-score-0-9490 | B001（0.947）。メタデータに空の kernel 依存があるが、コードでは使っていない |
| 4 | raunakdey07/biohub-harmonic-fusion-v3 | |
| 5 | flexonafft/biohub-harmonic-fusion | この系統の元になった Notebook |
| 6 | reyhanksatria/biohub-cell-tracking-0-947-lb | |
| 7 | flexonafft/biohub-lineage-forge-precision-tracking | |

どれも同じ系統: pilkwang の重み 3 つ（`biohub-deepcenter-unet3d-center-prior-v1`、`biohub-temporal-unet3d-seed314159-v1`、`biohub-tracking-support-pack-50ep-v1`）と、Harmonic Fusion の後処理（UNet3D による検出、node transformer によるエッジ推定、ILP、Hungarian による motion relink、safe division、ppsweep）。

## 分裂判定（DivNet）関連

- `giorgosi/biohub-divnet-v2`: `best_overall.pt`（1 fold 分、fold AUC 0.893）。学習コードは公開されていない。
- haideptry の DivNet 系の Notebook（例: `haideptry/biohub-sota-0-947-fast-2xt4-22m-divnet-3d`）では、gate が一度も発火していない。
  - 入力が 6 次元になる、キーが一致せず重みがランダムのまま、前処理が学習時と違う、という 3 つのバグがある。
  - 1 つ目は `zhincez/the-knob-you-passed-is-never-read` で指摘されている。
- `pawanmali/biohub-zhincez947-nodiv-ablation-v1`（分裂をすべて削除した版）は約 0.91 の帯にいる。

## そのほか

- pilkwang の学習コード: `pilkwang/biohub-tracking-support-pack-50ep-v1` の `source_scripts/train_full_frame_center_detector.py`、`repo/scripts/train_unet_transformer.py`。
- 新しい公開の重み（leonixis/biohub-v5-candidates、majidaleissa/biohub-bio122-cross-domain-secondary-v1 など）は、スコアの高い公開 Notebook で使われておらず、LB で効いた根拠がない。
- `andnyu/biohub-947-synthetic-edge`（合成データで学習した SWA モデルを使う）は、0.947 の同点ブロックにいる。
