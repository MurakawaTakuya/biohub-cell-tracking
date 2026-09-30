# セッションの引き継ぎ

最終更新: 2026-09-30 13:00 JST

## 状態: コンペは終了した（2026-09-29 23:59 UTC 締切）

- **最終成績: 非公開 LB 0.917、1,059 位 / 4,017 チーム**（公開 LB 0.960、126 位）。メダルなし（銅の目安の 400 位は 0.920）。
- 最終提出: E028（56641962、公開 0.960 / 非公開 0.917）と E013（56566441、公開 0.959 / 非公開 0.916）。
- 全 33 提出の非公開 LB は 0.911〜0.918。どれを選んでもメダル圏には届かなかった。
- 振り返り: `docs/retrospective.md`。共通の教訓は、ルートの `../README.md` の「公開LBの小さな差を信じすぎない」。
- 説明用のページ: `docs/competition-explainer.html`（最終結果と、公開と非公開の散布図を入れた）。
- 全提出の公開 / 非公開スコア: `local_outputs/final_scores.json`（コミットしない）。

## 残っていること（任意）

1. 上位チームの解法を読む（discussion に公開されたら）。1 位は非公開 0.977。自前の学習や、胚ごとに分けた検証をしていたかを確認し、`docs/retrospective.md` に追記する。
2. ローカルとサーバーの片付け（ユーザーの判断待ち）。
   - サーバー（139-home）: `/mnt/HDD18TB/murakawa/biohub-cell-tracking/`（89 GB、うちデータ 82 GB）、NVMe のコピー `~/biohub_fast/`（81 GB）。実行中のジョブはない（2026-09-30 に確認）。
   - ローカル: `local_outputs/`（1.3 GB、Kernel の出力。コミットしていない）。
3. Kaggle 上の非公開 Kernel（`versavice/biohub-*`、約 35 本）は、残しておいても害はない。

## 安全に打てる確認コマンド

```bash
python3 - <<'EOF'
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi(); api.authenticate()
for s in api.competition_submissions('biohub-cell-tracking-during-development')[:6]:
    d = s.to_dict()
    print(d['ref'], d.get('description', '')[:50], d.get('status'), d.get('publicScore'), (d.get('errorDescription') or '')[:60])
EOF
kaggle competitions leaderboard biohub-cell-tracking-during-development -d -p local_outputs/lb
```

## 注意（2026-09-25 の外部レビューで指摘された点）

- A001 の AUC 0.832 は、学習済みの動画が大半を占める動作確認であり、CV ではない。gate が本番の候補に対してどれだけ正しく判定できているかの証拠でもない。
- DivNet gate の +0.002 は 2 つの系統で出たが、どちらも同じ公開テスト上の結果。Private での改善幅は予測できない。
- gate は、対称性のチェック、並べ替え、上限の処理より前に入っている。そのため、候補を捨てると別の候補が採用されることがあり、分裂数の差 = 誤った分裂を消した数、とは言えない。
- `safe_division_skipped_cap` が増えるのは、全体の上限で打ち切ったときだけ。フレームごとの上限で打ち切ったときは増えない。
- 分裂の数が数件違うだけでも、分裂の評価は分母が小さいので、スコアへの影響が小さいとは限らない。

## サーバーの状態（2026-09-24）

- データは `/mnt/HDD18TB/murakawa/biohub-cell-tracking/`。学習データのコピーが NVMe の `~/biohub_fast/train` にある。
- 実行中の biohub ジョブはない。
