<p align="right">
  <a href="../README.md">English</a> |
  <a href="./README.zh-CN.md">简体中文</a> |
  <b>日本語</b>
</p>

<div align="center">

# ActionAgent

<img src="https://img.shields.io/github/license/TheD0ubleC/ActionAgent?style=flat-square" />
<img src="https://img.shields.io/github/forks/TheD0ubleC/ActionAgent?style=flat-square" />

[クイックスタート](#始め方) · [プロンプト例](#プロンプト例) · [安全上の注意と回避策](#安全上の注意と回避策) · [トラブルシューティング](#トラブルシューティング) · [今後の目標](#今後の目標)

</div>

## なぜ ActionAgent が必要なのか

> Web 版 AI はコードを書いたり、問題を分析したり、スクリプトを生成したりするのが得意です。しかし、内蔵環境はその能力を`制限`します。直接`ネットワークにアクセス`したり、`依存関係をインストール`したり、`コマンドを実行`したり、`プラットフォームを切り替え`たりすることは難しく、実際の CI / ビルド環境を再現することも困難です。

たとえば、AI に次のようなことをしてほしい場合があります。

- 実際の GitHub リポジトリをクローンして完全にビルドする
- プロジェクト依存関係やシステムツールをインストールする
- 実際のネットワーク API にアクセスしてサービス状態を検証する
- Windows、macOS、Linux でそれぞれテストする
- x86_64、ARM64 など異なるアーキテクチャ間の違いを検証する
- 長時間のテスト、ビルド、ベンチマークを実行する
- 完全なログ、テストレポート、ビルド成果物を保存する

#### **ActionAgent が解決する問題は、Web 版 AI に操作可能な外部実行環境を持たせることです。**

これは、AI がチャット画面の中で直接コマンドを実行する仕組みではありません。AI が GitHub 経由で専用の ActionAgent リポジトリを変更し、「何を実行するか」をタスクとして書き込み、そのタスクを GitHub Actions Runner に渡して実行します。

```text
あなたが目標を伝える
↓
Web 版 AI が GitHub に接続する
↓
AI があなたの ActionAgent リポジトリを変更する
↓
GitHub Actions が一時 Runner を起動する
↓
ActionAgent がタスクを発見して実行する
↓
ログ、レポート、artifact を保存する
↓
ActionAgent が `.action-agent/result.json` を書き出す
↓
AI が結果ファイル、ログ抜粋、関連ログを読み取り、あなたに報告する
```

ActionAgent は次のように理解できます。

```text
ActionAgent = Web 版 AI のためのリモート実行ワークベンチ
```

Web 版サンドボックスと比べると、GitHub Actions Runner は一時的なクラウドマシンに近い環境です。依存関係のインストール、システムコマンドの実行、ネットワークアクセス、OS やアーキテクチャの切り替えができ、実行結果を安定した結果ファイル、ログ、artifact として保存できます。

デフォルトでは、ActionAgent はタスクが実行された場合に切り詰めたログ抜粋を `.action-agent/result.json` にコミットし、完全なログは artifact として保持します。`run = true` のタスクがない場合は、リポジトリ状態を変更せずに終了します。完全なログをリポジトリに残す必要がある場合は、タスクで `[output].commit = true` を明示的に設定できます。

これにより Web 版 AI は、単に「コマンドを書いてくれる」だけではなくなります。許可された範囲内で、実際の Runner にタスクを渡して実行し、実際の出力に基づいて分析を続けられます。

## 何ができるか

ActionAgent は、通常の内蔵環境では完了しにくいタスクを Web 版 AI に実行させるのに適しています。

- 実際のネットワーク API をリクエストし、API、サービス状態、ダウンロードリンクを検証する
- Python、Node、Rust、Go、.NET などのプロジェクト依存関係をインストールする
- `apt`、`brew`、`choco` などのシステムツールをインストールする
- コード片だけでなく、完全なプロジェクトをコンパイルする
- 実際のテスト、ビルドテスト、結合テスト、スモークテストを実行する
- Windows、macOS、Linux 上でプラットフォーム差異を検証する
- x86_64 と ARM64 Runner 上でアーキテクチャ差異を検証する
- SSH でアクセス権のあるサーバーに接続し、コマンドを実行する
- 長いログ、ビルド成果物、テスト結果、デバッグ出力を保存する

GitHub Actions の権限、プラットフォーム、タイムアウト、ネットワーク、安全境界の範囲内で、ActionAgent は Web 版 AI のリモート実行入口として利用できます。

## 始め方

> 以下の例は ChatGPT を前提にしています。他の Web 版 AI では GitHub への接続方法が異なる場合があります。

### 1. 自分の ActionAgent リポジトリを作成する

まず、このリポジトリを Fork して、自分の ActionAgent リポジトリを作成します。

[ここをクリックして ActionAgent を Fork](https://github.com/TheD0ubleC/ActionAgent/fork)

Fork 後、次の点を確認してください。

- このリポジトリへの書き込み権限があること
- GitHub Actions が有効になっていること
- リポジトリ内の ActionAgent workflow が実行できること
- 実行状態を自動コミットする必要がある場合、workflow にリポジトリ内容を書き込む権限があること

### 2. ChatGPT で GitHub に接続する

ChatGPT で GitHub App に接続し、ChatGPT があなたの ActionAgent リポジトリにアクセスできるように許可します。

ChatGPT の設定から Apps / アプリを開き、GitHub App を検索して GitHub アカウントに接続できます。

接続時は次の点に注意してください。

- 選択するのはあなたの ActionAgent リポジトリです
- ビルドやテストをしたい業務プロジェクトのリポジトリではありません
- 業務プロジェクトは通常、ActionAgent のタスク内で clone されます

### 3. チャット内で ActionAgent リポジトリを選択する

リポジトリ操作が必要な場合、インターフェースが GitHub の明示的な呼び出しに対応していれば、次のように入力できます。

```text
@GitHub
```

次に ActionAgent リポジトリを検索して、まだインデックスが作成されていないと表示されたら ActionAgent リポジトリをクリックして、表示されたページで `GitHub 上でインデックスをトリガー` をクリックします。その後、5 分待てば続けられます。

### 4. まず ChatGPT に ActionAgent のルールを学習させる

次のように送信します。

```text
@GitHub ActionAgent のリポジトリの AGENTS.md を読み、ActionAgent の使い方を学んでください。学習が完了したら、直接私に報告してください。タスクを実行したり、ファイルを変更したりしないでください。
```

ChatGPT が学習完了を報告したら、続けてタスク実行の依頼を送れます。

## プロンプト例

| 目的 | プロンプト |
| ---- | ---------- |
| ネットワークテスト | `ActionAgent を使って www.google.com に ping し、ネットワークが疎通しているか確認してください。` |
| プロジェクトビルド | `ActionAgent を使って https://github.com/Kinal-Lang/Kinal を clone し、Linux x86_64 ビルドを行い、ビルド成果物を artifact としてアップロードしてください。` |
| リポジトリのテスト | `ActionAgent を使ってこのリポジトリを clone し、依存関係をインストールしてテストを実行し、ログを .action-agent/output/ に保存してください。` |
| Runner 環境確認 | `ActionAgent を使って現在の Runner のシステム情報と、Python、Node、Git、Docker が利用可能かを確認してください。` |
| サーバー運用 | `ActionAgent を使い、GitHub Secrets に設定された SSH 情報で私の Ubuntu サーバーに接続し、CPU、メモリ、ディスク、負荷状況を確認してください。` |

## Secrets で機密情報を扱う

サーバーパスワード、Token、Cookie、秘密鍵などの機密情報を AI に直接送ることは推奨しません。また、それらをタスクファイルに書き込まないでください。

推奨手順:

1. あなたの ActionAgent リポジトリで GitHub Settings を開く
2. Secrets and variables に移動する
3. 必要な Secrets を追加する。例:
   - `SSH_HOST`
   - `SSH_USER`
   - `SSH_PRIVATE_KEY`
   - `API_TOKEN`

4. ActionAgent タスクが GitHub Actions Runner 内でこれらの Secrets を環境変数として使用できるようにする

注意事項:

- ChatGPT は Secrets の実際の内容を見るべきではありません
- Secrets は Runner 実行時にのみ使用してください
- Secrets の使用は安全ルールを回避する手段ではありません
- 対象サーバー、リポジトリ、API、ドメインは、あなたが所有しているか、明示的に操作を許可されている必要があります

## 安全上の注意と回避策

ActionAgent は Web 版 AI により強力な実行能力を与えるため、境界をより明確にする必要があります。

以下を守ってください。

- ActionAgent はプライベートリポジトリでの利用により適しています
- タスク内で secrets、tokens、cookies、秘密鍵を出力しない
- タスクに完全な環境変数を出力させない
- `curl xxx | bash` を盲目的に実行しない
- 無限ループを実行しない
- 未承認のペネトレーションテスト、スキャン、ブルートフォース、脆弱性利用を行わない
- 第三者システムに対して破壊的な操作を行わない
- サーバーに接続したり危険な操作を実行したりする前に、対象が自分のもの、または権限を持っているものだと確認する
- 公共の GitHub Actions リソースを大量の長時間タスクで占有しない

ChatGPT がリクエストを拒否した場合、通常、そのリクエストには次のような要素が含まれる可能性があります。

- 未承認の対象
- 平文の機密情報
- 高リスクなサーバー操作
- 破壊を引き起こす可能性のあるコマンド
- 安全ポリシーで許可されていない行為

その場合は、まずタスクの方法を調整してください。例:

- GitHub Secrets を使って機密情報を渡す
- 対象が自分の所有物、または許可を得たものだと明確に説明する
- タスクの権限を下げる
- まず読み取り専用の確認を行う
- 破壊的なコマンドを避ける
- 大きなタスクを、より小さく監査しやすいタスクに分割する

## トラブルシューティング

ActionAgent が実行されない場合は、次を確認してください。

- 自分のリポジトリに Fork 済みか
- ChatGPT で ActionAgent リポジトリに接続し、選択しているか
- GitHub Actions が有効になっているか
- workflow に実行状態をコミットする権限があるか
- `.action-agent/scratch.py` または `.action-agent/tasks/*.py` に `run = true` が含まれているか
- タスクファイルの先頭に有効な TOML メタデータが含まれているか
- GitHub Actions ログにエラーがないか
- `.action-agent/result.json` が更新されているか
- `.action-agent/output/` にログや artifact が生成されているか

ActionAgent 自体に問題があると思われる場合は、以下の情報を添えて Issue を送ってください。

- タスクファイルの内容
- `AGENTS.md`
- `.action-agent/run.toml`
- `.action-agent/result.json`
- GitHub Actions ログ
- `.action-agent/output/` 内のログ
- 再現手順

### 今後の目標

- GitHub Actions を通じて、Web 版 AI の能力を Codex や OpenCode などのユーザーのローカル環境へリバースプロキシし、AI サブスクリプションの最後の一滴まで価値を引き出す——Web 版対話をローカル Agent に接続する。

---

<div style="display: flex;gap: 8px;justify-content: center;">

### [Issue を送る](https://github.com/TheD0ubleC/ActionAgent/issues)

### |

### [Pull Request を送る](https://github.com/TheD0ubleC/ActionAgent/pulls)

### |

### [トップに戻る](#ActionAgent)

</div>
<div align="center">

**ActionAgent は MIT ライセンスに従います。Fork、利用、改善を歓迎しますが、安全境界と利用規範に注意してください。**

</div>
