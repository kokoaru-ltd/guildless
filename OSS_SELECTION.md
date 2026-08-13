# Guildless Council OSS selection

調査日: 2026-08-13

## 採用

### LangGraph

- Repository: https://github.com/langchain-ai/langgraph
- Runtime version: `langgraph==1.2.9`
- License: MIT
- 用途: Guildless MVPの状態機械。`research_github -> independent_proposals -> devils_advocate -> rebuttals -> judge` を明示的なGraphとして実行する。
- 採用理由: Python 3.11で利用でき、非同期処理、条件分岐、最大ラウンド、checkpointの骨格を既存実装で持つ。

## 設計参考のみ

### arbgjr/multi-agent-debate

- Repository: https://github.com/arbgjr/multi-agent-debate
- Inspected commit: `0ca74a53aeaa28cbb772c5fd5c430fd7e5bb0d89`
- License: MIT
- 参考箇所: Advocate/Critic/Synthesizer/Judge、最大3ラウンド、confidence/consensus threshold、Provider Protocol。
- 非採用理由: 2026-08-13時点で1 star、単一初期コミット。投票positionが文章先頭100文字なので、意味的に同じ案でも別案として集計される。初期提案も複数専門家の完全独立並列ではない。

### am-will/llm-council

- Repository: https://github.com/am-will/llm-council
- Inspected commit: `e4a756a28e1d98efdd592ff09f7a6fd966d9122c`
- 参考箇所: 独立Plan、匿名化、順序シャッフル、Judge統合、成果物保存。
- 非採用理由: checkout内にLICENSE/COPYING/NOTICEが存在しないため、コードは取り込まない。

### danielrosehill/Awesome-LLM-Council-Projects

- Repository: https://github.com/danielrosehill/Awesome-LLM-Council-Projects
- Inspected commit: `f21edd27d4eab758098d841cd87d8de530af94bd`
- 用途: 候補探索用インデックスのみ。コードは取り込まない。

## Guildless独自部分

- GitHub APIからの決定論的Repository選別
- License/activity/relevance/adoption/integrationの固定スコア
- READMEを命令ではなくuntrusted DATAとして扱う境界
- Research/Sales/Financeの独立回答
- Devil's Advocateと役割別再反論
- 別Provider Judgeの強制
- Candidateの未確定固定、外部作用ゼロ、監査成果物
