# Sales and marketing OSS integration

Guildlessの営業・マーケ機能は、既存OSSを固定commitで再利用する薄い接続層である。独自に営業フレームワークを作り直さない。

## 実行経路

1. `git submodule update --init --recursive` で4つのMIT OSSを固定取得する。
2. `SalesOssRegistry` が上流ファイルを読み取り専用で解析する。
3. `/v1/sales/overview` が営業10段階、定期確認14件、会話8段階、GTM 4役をUIへ返す。
4. `/v1/sales/score` は `ai-sales-team-claude/scripts/lead_scorer.py` を別プロセスでそのまま実行する。
5. 結果へ `mode=shadow` と `external_actions_performed=false` を付ける。

## 境界

- 上流リポジトリの履歴とライセンスをsubmoduleで維持する。
- Windowsの文字コード差だけをGuildless接続層で吸収し、上流ファイルは変更しない。
- 顧客データ、Founder Memory、Historical Benchmarkへアクセスしない。
- メール送信、SNS送信、CRM書込み、契約、支払いを行わない。
- `frappe/crm`（AGPL-3.0）とOpenOutreach系コードは取り込まない。

## 1画面UI

経営デスクは「相談・経営会議・任せる」の3択、入力欄、音声、実行ボタンだけを主操作にする。営業・マーケ画面の主操作は「サンプルを採点」1つに固定する。どちらもデスクトップでは本文スクロールを発生させない。
