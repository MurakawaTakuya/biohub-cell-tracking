# Biohub Cell Tracking の作業ルール

## セッションの最初に読むもの

1. `README.md`: 今の再開地点と結果の一覧
2. `docs/session_handoff.md`: 次にやること、安全に打てるコマンド
3. `docs/decisions.md`: 守るべき判断
4. 作業に関係する `runs/<ID>.md`、`docs/server_environment.md`

Kaggle の状態（Kernel、提出、スコア、順位）はドキュメントから推測しない。報告する前に CLI で今の状態を確認する。

## 状態の書き分け

`prepared`（ローカルで準備した）、`pushed`、`running`、`complete`（Kernel の実行が完了した）、`validated`（出力を確認した）、`submitted`（PENDING）、`scored`（公開 LB あり）、`failed`（エラーや時間切れ）は、それぞれ別の状態として扱い、混同しない。

- Kernel が complete でも、提出したことにはならない。
- 提出が COMPLETE でも、`publicScore` が空で `errorDescription` がある場合は failed。提出一覧を表で見るだけでは分からないので、API の `errorDescription` を確認する。

## 外部への操作

- 提出は、実行結果を確認してからユーザーに「提出してよいか」を聞く。OK が出たら Claude が `kaggle competitions submit` を実行する（2026-09-25 のユーザーの指示）。push は auto mode の権限チェックで止められることがあるので、止められたらコマンドをユーザーに渡し、`! <コマンド>` で実行してもらう。
- 提出するたびに、どの Kernel のどの version か、何のための提出か、提出枠を 1 回使うことを明示する。PENDING の提出を再提出しない。
- 研究室サーバーの GPU を使う前に、使う GPU の番号と時間の目安を毎回ユーザーに確認する。
- Kaggle の API 呼び出しは 1 分あたり 30 回以下に抑え、呼び出しの間に 3 秒程度空ける。

## 実験の決まり

- 検証込みの公開 Notebook（validator や ppsweep で学習データに対してパイプラインを実行し直すもの）は、非公開テストで時間切れになる。fork したら、まず `server/make_fast.py` の方法で設定を固定し、短くする（D003）。
- 設定を固定した版は、元の版と `submission.csv` が完全に一致することを確かめてから提出する。
- 公開の検出器は学習データの 199 動画すべてで学習されているので、学習データを使ったローカル CV は in-sample になる（D002）。

## 記録の更新（大きな作業の区切りや、外部の状態が変わるたびに行う）

1. `README.md` の再開地点と結果の一覧を更新する。
2. `docs/session_handoff.md` に、次に再開する地点と安全に打てるコマンドを書く。
3. 該当する `runs/<ID>.md` を更新する（なければ作る）。
4. 守るべき判断が変わったときだけ、`docs/decisions.md` に追記する。
5. 日付や状態が変わる値には、観測した日付を付ける。
6. 小さな単位でコミットし、非公開リポジトリ `MurakawaTakuya/biohub-cell-tracking` の `main` に push する（ユーザーから許可済み）。コミットする前に `git status` で、データや出力が混ざっていないか確認する。

## コミットしてはいけないもの

Kaggle の認証情報、コンペのデータ、モデルの重み、Kernel の出力、`submission.csv`、大きな生成物。Kernel の出力は `local_outputs/` に置く。
