# 研究室サーバーでの作業手順（Biohub Cell Tracking）

作成: 2026-09-23。サーバーの状態は同日の観測値で、割り当てを保証するものではない。

公開用に、サーバーの接続先とパスは `<server>`（SSH の接続名）と `<ROOT>`（作業ディレクトリ）に置き換えている。

## 役割分担

| 場所 | 役割 |
| --- | --- |
| Mac（このディレクトリ） | 操作の起点、コードの編集・レビュー、Kaggle CLI、ドキュメント |
| `<server>`（研究室の GPU サーバー） | データの保存、学習、OOF 評価、後処理パラメータの探索（tmux 上で長時間実行） |
| Kaggle Notebook | 非公開テストでの推論と提出（コードコンペなので最終推論は必ず Kaggle 上の T4 で行う） |

サーバーで作った `submission.csv` は提出できない。サーバーで作った重みや設定は Kaggle の **Private Dataset** にアップロードし、Notebook から読み込んで提出する。

## 接続

- `ssh <server>` で接続する（学外からは研究室の VPN を経由する設定を `~/.ssh/config` に書いておく）。
- 疎通確認:

```bash
ssh <server> 'hostname; nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv,noheader'
```

## サーバーの状況（2026-09-23 に確認）

- GPU: NVIDIA RTX A6000（48 GB）× 4 枚。確認時は 4 枚とも空き（15 MiB、0%）
- CPU 96 コア、メモリ 251 GB
- データ用の HDD に十分な空きがある
- Python 3.12.3、`/usr/bin/tmux` あり
- Kaggle 認証情報: `~/.kaggle/access_token`（パーミッション 600、Git 管理外）
- Kaggle CLI 用の venv: ほかのコンペで作ったものを流用するか、下の Biohub 専用 venv を作る

GPU が空いていても、このプロジェクトに割り当てられているわけではない。GPU を使うジョブを始める前に、**使う GPU の番号と時間の目安を毎回ユーザーに確認する**。

## ディレクトリ構成（予定）

```
<ROOT>/
├── data/          # コンペのデータ（kaggle competitions download）
├── inputs/        # pilkwang の重み、divnet などの公開データセット
├── code/          # Mac から rsync したコード
├── runs/<ID>/     # 実験ごとの出力、ログ、設定
└── .venv/         # Biohub 専用の Python 環境
```

## 初期セットアップ（2026-09-23 に実施済み。読み込みを速くするため、学習データを NVMe にもコピーした。コンペ終了後に削除済み）

```bash
ssh <server>
ROOT=<ROOT>
mkdir -p $ROOT/{data,inputs,code,runs}
python3 -m venv $ROOT/.venv && source $ROOT/.venv/bin/activate
pip install kaggle   # ほかの依存（torch、tracksdata、ILP ソルバーなど）は公開 Notebook の import 文に合わせて追加する

# コンペのデータ（ダウンロード前にサイズと空き容量を確認する）
cd $ROOT/data && kaggle competitions download -c biohub-cell-tracking-during-development && unzip -q *.zip

# 公開の重み
cd $ROOT/inputs
for d in pilkwang/biohub-deepcenter-unet3d-center-prior-v1 \
         pilkwang/biohub-temporal-unet3d-seed314159-v1 \
         pilkwang/biohub-tracking-support-pack-50ep-v1 \
         giorgosi/biohub-divnet-v2; do
  kaggle datasets download -d $d -p ${d#*/} --unzip; sleep 3
done
```

Kaggle の API 呼び出しは 1 分あたり 30 回以下に抑え、呼び出しの間に 3 秒程度空ける。

## 長時間ジョブの実行（tmux）

```bash
ssh <server>
tmux new -s biohub-<ID>        # 再接続: tmux attach -t biohub-<ID>、一覧: tmux ls
cd <ROOT>
source .venv/bin/activate
CUDA_VISIBLE_DEVICES=<承認された GPU 番号> python code/<script>.py ... 2>&1 | tee runs/<ID>/log.txt
# Ctrl-b d でデタッチ。Mac の電源を落としてもジョブは続く
```

Mac からの状態確認:

```bash
ssh <server> 'tmux ls; tail -5 <ROOT>/runs/<ID>/log.txt; nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader'
```

## コードと成果物の受け渡し

```bash
# Mac → サーバー（コード）
rsync -av --exclude '*output*' ./code/ <server>:<ROOT>/code/
# サーバー → Mac（小さい結果ファイルだけ）
rsync -av <server>:<ROOT>/runs/<ID>/summary.json ./runs/<ID>/
```

## サーバーの成果を Kaggle で提出するまで

1. サーバーで重みと設定を用意し、`dataset-metadata.json` を書く（`"isPrivate": true` にする）。
2. `kaggle datasets create -p <dir>`（2 回目以降は `kaggle datasets version -p <dir> -m "<msg>"`）。**外部へのアップロードなので、事前にユーザーの承認をとる。**
3. 提出用 Notebook（例: `submit-geo-fast/` を複製したもの。検証込みの Notebook は D003 に従って短時間版にする）の `kernel-metadata.json` の `dataset_sources` にその Dataset を追加し、Mac から `kaggle kernels push`。
4. 実行が完了したら `submission.csv` を確認し、`kaggle competitions submit ... -k <kernel> -v <version> -f submission.csv -m "<msg>"` で提出する。
   - Kaggle への push と提出は、Claude Code の自動モードでは権限チェックで止められる。ユーザーが `! <コマンド>` で実行する。
   - 採点は 1 回あたり約 4 時間かかる。提出回数には 1 日の上限がある。

## CV についての注意

- 公開の検出器（pilkwang の seed314159 など）は、学習データの 199 動画すべてで学習されている（discussion 742064）。そのため、学習データから取った hold-out で公開の重みを評価すると in-sample になり、LB の予測に使えない。
- 信頼できるローカル CV が必要な場合は、評価に使う動画を学習から外して、自分で学習し直したモデルだけで測る。

## Kaggle の状態

提出の履歴と結果は `README.md` の表と `runs/` にまとめている。

```bash
kaggle competitions submissions biohub-cell-tracking-during-development | head -8
```

## 次の候補

- DivNet（`giorgosi/biohub-divnet-v2`）を動画単位の hold-out で学習し直すか調整し、Geometric Fusion の safe-division 候補の再スコアに使う。サーバーで学習と CV を回し、重みを Private Dataset として Kaggle に載せて提出する。
