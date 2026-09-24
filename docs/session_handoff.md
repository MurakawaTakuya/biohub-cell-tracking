# セッションの引き継ぎ

最終更新: 2026-09-24

## 今の再開地点: B004 と E002 が scoring 中

- 提出 56508399（B004、`versavice/biohub-geo-fast` v1）と 56508400（E002、`versavice/biohub-geo-divnet-fast` v1）を 2026-09-24 01:34 UTC に提出した。
- どちらも Kernel の実行は約 35 分。出力は元の版（B002、E001）と全行一致することを確認済み。
- 再提出はしない。PENDING のまま待つ。

### 次にやること

1. スコアを確認する。表の表示だけでは失敗が分からないので、API の `errorDescription` も見る。

```bash
python3 - <<'EOF'
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi(); api.authenticate()
for s in api.competition_submissions('biohub-cell-tracking-during-development')[:6]:
    d = s.to_dict()
    print(d['ref'], d.get('description', '')[:50], d.get('status'), d.get('publicScore'), (d.get('errorDescription') or '')[:60])
EOF
```

2. 最終提出の 2 本を、ユーザーと相談して決める。Kaggle の Submissions ページでユーザーがチェックする。
   - 案: B004（0.948 が出た場合）と、E002 か B001（0.947）。
3. 時間が残っていれば、次の候補（下記）を検討する。

## 次の候補

- **E003（gate 0.3）と E004（DivNet による並べ替え）は準備済みで、push していない**（`runs/E003.md`、`runs/E004.md`）。B004 と E002 のスコアを見てから、どちらを出すか決める。
  - E002 が B004 より低い場合: E004 を優先する。
  - E002 が B004 より高い場合: E003 を優先する。
- 注意: `submit-geo-divnet/make_notebook.py` に並べ替えの機能を足したため、ローカルの `geo-divnet.ipynb` は push した E001 と少し違う。重みの既定値は 0 なので、動作は同じ。`server/make_fast.py` を実行し直すと `submit-geo-divnet-fast/` も作り直される。
- **DivNet を学習し直す**: 動画単位で hold-out を作って学習し直し、候補を捨てる基準を CV で決める。サーバーで行う。GPU を使う前にユーザーの承認をとる。

## 安全に打てる確認コマンド

```bash
kaggle competitions submissions biohub-cell-tracking-during-development | head -8
kaggle kernels status versavice/biohub-geo-fast
ssh 139-home 'tmux ls | grep biohub; nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader'
```

## サーバーの状態（2026-09-24）

- データは `/mnt/HDD18TB/murakawa/biohub-cell-tracking/`。学習データのコピーが NVMe の `~/biohub_fast/train` にある。
- 実行中の biohub ジョブはない（tmux の `biohub-download`、`biohub-copy`、`biohub-divnet-check` はすべて終了済み）。
