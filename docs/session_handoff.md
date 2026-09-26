# セッションの引き継ぎ

最終更新: 2026-09-26 19:30 JST

## 今の再開地点: 最終提出は E013 + E010

- 最高は **E013 = 0.959**（提出 56566441、`versavice/biohub-e013-x138-rescue05` v1）。75 位 / 3,924 チーム（2026-09-26 19:29 JST）。
- 最終提出: **E013（56566441）+ E010（56554089、0.958）**。`runs/E013.md` に事前に決めた基準（0.959 以上なら E013 が 1 本目、E010 が 2 本目）による。
- 確かめたこと: E012（Geo 系 + rescue）0.950（E003 より +0.001）、E014（gate なし + rescue）0.957（B005 より +0.004、E010 より −0.001）。rescue は、別の系統でも、gate がなくても効いた。gate を足すとさらに少し上がる。
- 最終提出のチェックは、ユーザーが Kaggle の Submissions ページで行う。締切は 9/30 08:59 JST（9/29 23:59 UTC）。新しい提出は 9/28 のうちに出し終える。
- 2026-09-26 に Codex CLI のレビューを受けた（`docs/codex_review_2026-09-26.md`）。

## 次の手順

1. rescue の閾値をさらに下げる候補（0.3 など）を試すかは、ユーザーと相談して決める。
2. 新しい版を作ったら、実行 → traceback と `REPAIR FAILED` の確認 → `server/diff_outputs.py` で E013 と比べる → ユーザーの OK をもらってから提出。
3. 最終提出の 2 本を、ユーザーが Kaggle でチェックする。

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
