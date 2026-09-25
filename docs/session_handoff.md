# セッションの引き継ぎ

最終更新: 2026-09-25 02:00 UTC ごろ

## 今の再開地点: 最終提出の暫定の 2 本は E006 + B005

- 最高は **E006 = 0.955**（提出 56527266、`versavice/biohub-e006-x138-gate03` v1）。87 位 / 3,894 チームで銀圏（2026-09-25 01:26 UTC）。
- 暫定の最終提出: **E006（56527266）と B005（56518233、0.953）**。外部レビュー（`docs/consult_2026-09-25.md` への回答）でも、この組み合わせが推奨された。
  - B005 は E006 から DivNet gate だけを除いたもの。DivNet が Private で外れたときの保険になる。
  - E003（0.949、Geometric Fusion 系）は、E003 にも DivNet gate が入っていて、E006 と同じ失敗をかぶる。公開 LB でも 0.004 低いので、2 本目には選ばない。
- 最終提出のチェックは、ユーザーが Kaggle の Submissions ページで行う。9/28 までに確定させる。
- E007（gate 0.5）は 0.954、E009（E006 + weak-leaf pruning）は 0.955 で、どちらも E006 を上回らなかった。E008（gate 0.4）は実行済みで、提出していない。scoring 中の提出はない。

## 次の候補（優先順）

1. **E007 を 1 本だけ提出して確認する**（ユーザーの OK が必要）。
   - 同点なら E006 を維持する。下がっても「0.3 が最適」とは解釈しない。上がったら、変わったイベントを診断してから置き換えを検討する（B005 は保険として残す）。
   - E008 は E006 と E007 の中間なので、続けて出さない。
2. **B005、E006、E007 の差分を診断する**: ノード、エッジ、分裂イベント（親と 2 つの娘）について、共通、削除、新規を分けて集計する。捨てた候補（動画、時刻、親、DivNet のスコア、最終的に採用されたか）と、変更が特定の動画に偏っていないかを見る。CSV の総行数だけで判断しない。
3. **条件付き**: E006 に weak-leaf pruning（Geometric Fusion の `prune_weak_leaf_nodes`、閾値 0.3、スイープしない）だけを移植する。x138 にはこの処理がない。削除対象が実際にあり、削除前後のグラフを確認できた場合だけ提出する。
4. **やらない**: DivNet の学習し直しを主戦略にすること、3 本目の検出器の追加、Geometric Fusion の設定一式の移植、複数の変更の同時投入。

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
