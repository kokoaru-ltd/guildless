# GUILDLESS-001 First Successful Autonomous Run

Status: completed locally on 2026-07-23 JST.

## Authentication diagnosis

Claude Code CLI was installed and the user was logged in with a Claude Max
`claude.ai` account. A process-level `ANTHROPIC_API_KEY` took precedence over
that login and routed unattended calls through a depleted pay-as-you-go API
balance. GUILDLESS now removes only `ANTHROPIC_API_KEY` from the Claude child
process, allowing the existing `claude.ai` authentication to be used.

Proof command:

```powershell
$env:ANTHROPIC_API_KEY=$null
'Reply with exactly CLAUDE_OK and nothing else.' | claude --print --permission-mode bypassPermissions --output-format text
```

Observed result: exit code `0`, output `CLAUDE_OK`.

## Runtime

Start the loopback-only runtime:

```powershell
npm run guildless:runtime
```

It binds to `127.0.0.1:43117` and exposes:

- `GET /health`
- `POST /missions/hello-world`

The mission endpoint accepts a reviewed voice transcript:

```json
{
  "inputMode": "voice",
  "transcript": "hello worldなCLIツールを作って"
}
```

## Verified run

Mission `hello-1784750390669-3ce145f0` was started through the local HTTP API.
It completed without human intervention:

1. Runtime accepted the voice transcript.
2. Claude created `package.json`, `cli.mjs`, and `tests/cli.test.mjs`.
3. Codex independently reviewed the workspace in read-only mode and returned
   `PASS`.
4. Node ran `npm test` successfully.
5. Node executed the CLI and observed exactly `Hello, world!\n`.
6. Runtime wrote `mission.completed`.

All nine events are stored in `.guildless/events.sqlite`. The generated files
and `evidence.json` are stored under `.guildless/runs/<mission-id>/`.

The SQLite ledger and run artifacts are local runtime data and are intentionally
not committed to Git.
