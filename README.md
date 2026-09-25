# Biohub Cell Tracking During Development

コンペ: <https://www.kaggle.com/competitions/biohub-cell-tracking-during-development>（コードコンペ。締切 2026-09-29）
チーム: Mositaku（`versavice`）

## 今の再開地点（2026-09-25）

- 最高は **E006 = 0.955**（x138 + V1284 head + DivNet gate 0.3）。87 位 / 3,894 チームで銀圏（01:26 UTC）。
- 暫定の最終提出は **E006 + B005**（外部レビューでも推奨された）。
- 次の手順は [docs/session_handoff.md](docs/session_handoff.md)。

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
| E007 | `versavice/biohub-e007-x138-gate05` v1 | B005 + DivNet gate 0.5（分裂 30） | 56539425 | scoring 中 |
| E008 | `versavice/biohub-e008-x138-gate04` v1 | B005 + DivNet gate 0.4（分裂 31） | 実行済み・提出していない | — |
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
