# Guildless 自律ジョブ

Guildlessへ目的を1件渡すと、次の処理を一続きで実行します。

1. GitHubから候補を収集し、ライセンス・更新状況・機能を固定ルールで評価する
2. 複数AIが独立提案、反論、再検討、最終判定を行う
3. 採用候補を固定コミットで `D:\guildless\workspaces` に取得する
4. Action Agentが実コードとライセンスを読み、実装ファイル一式を構造化して返す
5. Guildless本体がパスを検査し、`output/` 内だけへファイルを適用する
6. 言語を自動判定し、許可済みのPythonまたはTypeScript検証を実行する
7. 失敗時はエラーをAction Agentへ返し、1回だけ自動修正する
8. 元OSSのハッシュ、成果物、テスト、トークン、時間、外部作用の有無を監査記録へ保存する

## 一命令での実行

```powershell
cd D:\guildless
.\.venv\Scripts\python.exe -m council job `
  --objective "目的をここに書く" `
  --github-query "GitHub検索語" `
  --allowed-provider claude `
  --allowed-provider codex
```

HTTPでは `POST /v1/guildless/jobs` へ同じ内容をJSONで渡します。状態は
`GET /v1/guildless/jobs/{job_id}`、進行イベントは
`GET /v1/guildless/jobs/{job_id}/events` で取得できます。

## Command Center UI

```powershell
.\.venv\Scripts\python.exe -m council serve --host 127.0.0.1 --port 8780
```

ブラウザで `http://127.0.0.1:8780/guildless` を開くと、目的入力、参加モデル、
探索から監査までの進行、実行ログ、成果物、テスト数、外部作用、過去ジョブを日本語で
確認できます。画面は約1秒間隔で現在状態を更新します。

## 権限境界

- Action Agent自身は読み取り専用です。
- 書き込みはGuildless本体が検証済みパスへ行い、範囲は各ジョブの `output/` のみです。
- `D:\guildless_sim`、`D:\founder_memory`、OneDrive、顧客データへアクセスしません。
- 外部送信、Git push、PR作成、公開、デプロイ、契約、決済は自動実行しません。
- 外部作用が必要な場合は `approval_requests` に残し、承認待ちで停止します。
- Councilの結論は `assistant_council_candidate` のままで、確定方針へ自動昇格しません。

## 対応実行環境

- Python: `compileall` と `unittest`
- TypeScript: Node.jsの型除去・構文検査と `node:test`
- TypeScript Compiler: プロジェクト内に固定された `tsc` があれば `tsc --noEmit`
- 依存解決: lockfileがある場合だけ、`pnpm/npm`のオフラインモードかつlifecycle script無効で実行

`package.json` の任意scriptは実行しません。生成されたscriptへ外部送信・削除・公開処理を
混入できないよう、実行コマンドはGuildless本体の固定allowlistから選択します。
