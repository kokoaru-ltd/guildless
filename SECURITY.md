# Security Policy

## Reporting a vulnerability

セキュリティ上の問題を公開Issueへ貼らないでください。リポジトリ所有者へGitHubの非公開連絡手段で、影響範囲、再現方法、確認したバージョンを連絡してください。

APIキー、顧客データ、Founder Memory、Historical Benchmarkの実データは添付しないでください。必要な場合は、秘密を除いた最小の再現データを作ってください。

## Default safety boundaries

- UIは既定で `127.0.0.1` のみにbindします。
- `.env`、実行ログ、ローカルモデル、生成物はGit管理外です。
- 外部送信、契約、支払い、公開、顧客連絡は明示承認なしに実行しません。
- Councilの出力は候補であり、確定方針へ自動昇格しません。
- テレメトリは既定で無効です。

## Supported version

現時点ではGitHubの最新 `main` のみを対象に修正します。
