# Biohub Cell Tracking During Development

コンペ: <https://www.kaggle.com/competitions/biohub-cell-tracking-during-development>（コードコンペ。締切 2026-09-29）
チーム: Mositaku（`versavice`）

## 今の再開地点（2026-09-27 19:35 JST）

- 最高は **E013 = 0.959**（E006 + DivNet rescue 0.5）。**97 位 / 3,948 チーム**（2026-09-27 19:33 JST。銀は 195 位まで、その順位のスコアは 0.955。金は 17 位まで、同 0.967）。
- E011（E006 + スムージング後の weak-leaf pruning）は 0.955 で、E006 と同じ。
- 最終提出は、事前に決めた基準により **E013（56566441）+ E010（56554089）**。2026-09-27 に Kaggle で選択済み（2/2）。E012（0.950）、E014（0.957）でも rescue の効果を確かめた。E015（rescue 0.3）は 0.959 で E013 と同点なので、変えない。9/27 の 2×2 の比較（E016〜E019）は、divergence の緩和も gate 0.5 も下がり、E017（最近傍の制限なし）は同点だった。統一ルールにより、最終提出は変えない。次の手順は [docs/session_handoff.md](docs/session_handoff.md)。
- 2026-09-26 に Codex CLI（gpt-6-astra high）のレビューを受けた: [docs/codex_review_2026-09-26.md](docs/codex_review_2026-09-26.md)

## 結果の一覧

| ID | Kernel | 内容 | 提出 ID | 公開 LB |
| --- | --- | --- | --- | --- |
| B001 | `versavice/biohub-proxy-0947-fork` v1 | 公開 Notebook（evgendvorkin の proxy 0.9490）をそのまま fork | 56492055 | **0.947** |
| B002 | `versavice/biohub-geometric-fusion-fork` v1 | 公開 Notebook（amanatar/biohub-geometric-fusion）をそのまま fork | 56492051, 56492058 | 失敗: 実行時間の制限を超過 |
| B003 | `versavice/biohub-x138-nohead` v1 | anvithpothula/biohub-x138 から、非公開の V1284 head を外したもの | 56493175 | 0.946 |
| B004 | `versavice/biohub-geo-fast` v1 | B002 の後処理設定を固定し、validator を切ったもの（出力は B002 と同一） | 56508399 | **0.947** |
| E001 | `versavice/biohub-geo-divnet` v1 | B002 + DivNet gate 0.5 | 提出していない（4.55 時間かかり、時間切れの恐れがある） | — |
| E002 | `versavice/biohub-geo-divnet-fast` v1 | E001 の短時間版（出力は E001 と同一） | 56508400 | 0.946 |
| E003 | `versavice/biohub-e003-divnet-gate03` v1 | B004 + DivNet gate 0.3（分裂 71 件） | 56513351 | **0.949** |
| E004 | `versavice/biohub-e004-divnet-rank` v1 | B004 + DivNet による並べ替え | 提出していない（B004 と 19 行しか違わない） | — |
| E005 | `versavice/biohub-e005-divnet-rescue07` v1 | B004 + DeepCenter で捨てた候補を DivNet 0.7 以上で救済（分裂 +6） | 実行済み・提出していない | — |
| B005 | `versavice/biohub-x138-full` v1 | x138 をそのまま fork（V1284 head が公開された） | 56518233 | **0.953** |
| E006 | `versavice/biohub-e006-x138-gate03` v1 | B005 + DivNet gate 0.3（分裂 62 → 34） | 56527266 | **0.955** |
| E007 | `versavice/biohub-e007-x138-gate05` v1 | B005 + DivNet gate 0.5（分裂 30） | 56539425 | 0.954 |
| E008 | `versavice/biohub-e008-x138-gate04` v1 | B005 + DivNet gate 0.4（分裂 31） | 実行済み・提出していない | — |
| E009 | `versavice/biohub-e009-x138-gate03-leaf03` v1 | E006 + weak-leaf pruning 0.3（513 ノード削除） | 56540659 | 0.955 |
| E010 | `versavice/biohub-e010-x138-rescue07` v1 | E006 + DivNet rescue 0.7（分裂 34 → 54、純粋な追加） | 56554089 | **0.958** |
| E011 | `versavice/biohub-e011-x138-leafpost03` v1 | E006 + weak-leaf pruning 0.3（スムージングの後。E006 から 513 ノード削除のみ） | 56554092 | 0.955 |
| E012 | `versavice/biohub-e012-geo-gate03-rescue07` v1 | E003 + DivNet rescue 0.7（分裂 71 → 78、純粋な追加） | 56566446 | 0.950 |
| E013 | `versavice/biohub-e013-x138-rescue05` v1 | E010 の rescue を 0.5 に（分裂 54 → 62、純粋な追加） | 56566441 | **0.959** |
| E014 | `versavice/biohub-e014-x138-rescue07-nogate` | B005 + DivNet rescue 0.7 のみ（gate なし。分裂 62 → 81） | 56567903 | 0.957 |
| E015 | `versavice/biohub-e015-x138-rescue03` | E013 の rescue を 0.3 に（分裂 62 → 64、純粋な追加） | 56579132 | 0.959 | — |
| E016 | `versavice/biohub-e016-x138-r05-diverge125` | E013 + divergence 1.25 µm | 56596031 | 0.956 |
| E017 | `versavice/biohub-e017-x138-r05-nomutualnn` | E013 + 最近傍の制限なし | 56596041 | 0.959 |
| E018 | `versavice/biohub-e018-x138-r05-gate05` | E013 + gate 0.5 | 56596038 | 0.957 |
| E019 | `versavice/biohub-e019-x138-r05-gate05-diverge125` | E013 + gate 0.5 + divergence 1.25 µm | 56596034 | 0.955 |
| E020 | `versavice/biohub-e020-x138-r07-diverge125` | E016 + rescue 0.7（9/28 の条件付きの候補） | 実行済み・提出していない | — |
| E021 | `versavice/biohub-e021-x138-r07-gate05-diverge125` | E019 + rescue 0.7（9/28 の条件付きの候補） | 実行済み・提出していない | — |
| E022 | `versavice/biohub-e022-x138-r05-diverge175` | E013 + divergence 1.75 µm（9/28 の条件付きの候補） | 実行済み・提出していない | — |
| E023 | `versavice/biohub-e023-x138-r05-gate05-diverge175` | E018 + divergence 1.75 µm（9/28 の条件付きの候補） | 実行済み・提出していない | — |
| E024 | `versavice/biohub-e024-x138-r05-nnfallback` | E013 + 最近傍の候補が失格したときだけ 2 番目を試す（9/28 の条件付きの候補） | 実行済み・提出していない | — |
| A003 | サーバー（`server/gt_division_check.py`） | 可視の 4 動画で、予測した分裂を正解と照合 | — | 正解の分裂が 3 件しかなく、どの版も一致 0 件。判断できない |
| A001 | サーバー（`server/divnet_check.py`） | 公開 DivNet の重みを学習データの正解ラベルで検証 | — | AUC 0.832（学習済みの動画が大半を占める、前処理と動作の確認。汎化性能の CV ではない） |

7 月の提出（最高 0.901）は [docs/roadmap_2026-07.md](docs/roadmap_2026-07.md) を参照。

## 順位

今の再開地点を参照。

## ドキュメント

- [docs/session_handoff.md](docs/session_handoff.md): 再開する地点と、次に打つコマンド
- [docs/decisions.md](docs/decisions.md): 守るべき判断
- [docs/public_notebooks.md](docs/public_notebooks.md): 公開 Notebook の調査
- [docs/discussion_research.md](docs/discussion_research.md): discussion の調査
- [docs/server_environment.md](docs/server_environment.md): 研究室サーバー（`139-home`）での作業手順
- `runs/<ID>.md`: 実験ごとの記録

## ディレクトリ

- `submit-*/`: Kaggle に push する Notebook と `kernel-metadata.json`
- `server/`: サーバーや Mac で使うスクリプト（`divnet_check.py`、`make_fast.py`）
- `local_outputs/`: Kernel の出力（`submission.csv`、ログ、`ppsweep_selected.json`）。コミットしない
- それ以外の古いディレクトリ（`cv-*`、`rule-based-*` など）は 7 月の作業のもの
