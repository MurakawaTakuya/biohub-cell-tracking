# セッションの引き継ぎ

最終更新: 2026-09-26（JST の朝）

## 今の再開地点: 暫定の最終提出は E010 + E006

- 最高は **E010 = 0.958**（提出 56554089、`versavice/biohub-e010-x138-rescue07` v1）。61 位 / 3,914 チーム（2026-09-26 07:06 JST）。
- 暫定の最終提出: **E010（56554089）+ E006（56527266、0.955）**。ユーザーの方針は、公開 LB の高い方を選ぶこと。B005（DivNet なし）は、公開 LB が 0.002 低いので選ばない。
- 最終提出のチェックは、ユーザーが Kaggle の Submissions ページで行う。締切は 9/30 08:59 JST（9/29 23:59 UTC）。新しい提出は 9/28 のうちに出し終える。
- 実行中: E012（Geo 系 + rescue 0.7）と E013（rescue 0.5）。判断の基準は `runs/E012.md` と `runs/E013.md` に、結果を見る前に決めてある。
- 2026-09-26 に Codex CLI のレビューを受けた（`docs/codex_review_2026-09-26.md`）。

## 次の手順

1. E012 と E013 の Kernel が完了したら、出力を `local_outputs/e012-geo-gate03-rescue07`、`local_outputs/e013-x138-rescue05` に置き、次を確かめる。
   - traceback と `REPAIR FAILED` がないこと。
   - `DIVNET gate cumulative` の rescued の数。
   - `server/diff_outputs.py` で、E012 と E003 の差、E013 と E010 の差（最終的な分裂が変わったか）。
2. ユーザーに提出の OK をもらってから提出する。
3. 採点が出たら、runs に決めた基準で読み、最終提出の 2 本を決め直す。
4. 追加の比較実験の候補（まだ決めていない）: x138 の gate 0.0 + rescue 0.7。

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
