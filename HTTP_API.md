# Generic Council Service HTTP API

Council Service is an asynchronous, read-only advisory service. It stores every result as `assistant_council_candidate` with `promotion_status=unconfirmed`. Automatic promotion to a confirmed decision is not supported.

## Start

```powershell
cd D:\guildless_council
.\.venv\Scripts\python -m council serve --host 127.0.0.1 --port 8780
```

Guildless UI: `http://127.0.0.1:8780/guildless`

The production UI is built from `frontend/` (React + TypeScript + Vite) and is
served from `frontend/dist/`. Its fixed OSS source and license provenance are
recorded in `UI_SOURCES.md` and `THIRD_PARTY_NOTICES.md`.

Job detail views use these read-only endpoints:

- `GET /v1/guildless/jobs/{job_id}/council`
- `GET /v1/guildless/jobs/{job_id}/artifacts`
- `GET /v1/guildless/jobs/{job_id}/audit`

The existing CLI uses the same `CouncilOrchestrator`:

```powershell
.\.venv\Scripts\python -m council ask --task-type general --mode fast --question "..." --allowed-provider deepseek --allowed-provider codex
```

## Start a run

`POST /v1/council/runs`

```json
{
  "task_type": "general",
  "mode": "fast",
  "question": "What should we do?",
  "context": {
    "facts": ["Only explicitly supplied facts are visible"]
  },
  "allowed_providers": ["deepseek", "codex"]
}
```

The API accepts inline JSON context only. It has no file-path parameter and never dereferences strings inside `context`. Direct reads from `D:\guildless_sim` and `D:\founder_memory` remain forbidden.

## Read status and result

- `GET /v1/council/runs/{run_id}`
- `GET /v1/council/runs/{run_id}/events?after=0`

The events endpoint supports incremental polling. Use `next_after` as the next `after` value and `poll_after_ms` as the suggested interval.

Run states are:

`queued / preparing_context / proposing / criticizing / judging / completed / degraded / failed`

If a called provider is unavailable, the run continues with remaining allowed providers when an independent Judge is still available. The terminal state is then `degraded`. If no proposer or independent Judge remains, the run is `failed`.
