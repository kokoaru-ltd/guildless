# Third Party Notices

## Guildless web interface

The Guildless web interface is built on the component structure and source
distribution of **satnaing/shadcn-admin**, fixed at commit
`e16c87f213a5ba5e45964e9b67c792105ec74d26`.

- Source: https://github.com/satnaing/shadcn-admin
- License: MIT
- Copyright (c) 2024 Sat Naing
- Local license copy: `frontend/LICENSE`

The information architecture for list/detail/activity views was informed by
**marmelab/atomic-crm**, inspected at commit
`167a4cdb652b1ab2b4b030831cfa7adcf2099321`. No Atomic CRM runtime or customer
data is included.

- Source: https://github.com/marmelab/atomic-crm
- License: MIT
- Copyright (c) 2024-present, Francois Zaninotto, Marmelab

## Cloudflare OS

Selected interaction and visual-system code in the Guildless CEO desk is
adapted from **cloudflare/cloudflare-os**, fixed at commit
`c04843f97cd07a8c869312058fc59a00b5d5b5cb`.

- Source: https://github.com/cloudflare/cloudflare-os
- License: Apache License 2.0
- Derived file: `frontend/src/cloudflare-os/home-task-suggestions.tsx`
- Adapted sources: `HomeTaskSuggestions.tsx`, `SectionEyebrow.tsx`, and Kumo
  semantic tokens from `styles.css`

The Cloudflare OS copyright and Apache License 2.0 terms remain applicable to
these derived portions. A complete copy of the license is included at
`frontend/CLOUDFLARE_OS_LICENSE`.

## LangGraph

This product uses LangGraph 1.2.9.

- Project: https://github.com/langchain-ai/langgraph
- Copyright: Copyright (c) 2024 LangChain, Inc.
- License: MIT License

The MIT license text is available at:
https://github.com/langchain-ai/langgraph/blob/main/LICENSE

## faster-whisper

Guildless local voice transcription uses **SYSTRAN/faster-whisper** from a
local source checkout pinned to the v1.2.1 release commit.

- Source: https://github.com/SYSTRAN/faster-whisper
- Commit: `65882eee9f5cdbeeb2d877f1131d48cf241b327d`
- License: MIT
- Copyright (c) 2023 SYSTRAN
- Optional pinned source checkout: `third_party/faster-whisper` (created locally by setup and excluded from Git)
- Setup: `scripts/setup_local_voice.ps1`

Recorded audio is sent only to Guildless's own `/v1/audio/transcriptions`
endpoint. The endpoint invokes this local checkout and does not call an
external speech API.

## Research references

The following repositories were inspected but no source code was copied into this project:

- arbgjr/multi-agent-debate (`0ca74a53aeaa28cbb772c5fd5c430fd7e5bb0d89`)
- am-will/llm-council (`e4a756a28e1d98efdd592ff09f7a6fd966d9122c`)
- danielrosehill/Awesome-LLM-Council-Projects (`f21edd27d4eab758098d841cd87d8de530af94bd`)
