import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EventLedger } from "../orchestrator/ledger.mjs";
import { engineCommand } from "../orchestrator/engines.mjs";

test("SQLite event ledger preserves ordered mission events", () => {
  const dir = mkdtempSync(join(tmpdir(), "guildless-ledger-"));
  try {
    const ledger = new EventLedger(join(dir, "events.sqlite"));
    ledger.append("m1", "voice.transcript.accepted", "owner", { transcript: "hello" });
    ledger.append("m1", "mission.completed", "runtime", { status: "completed" });
    assert.deepEqual(ledger.events("m1").map(event => event.type), [
      "voice.transcript.accepted",
      "mission.completed",
    ]);
    ledger.close();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("Claude engine uses stdin and removes API-key override", () => {
  const previous = process.env.ANTHROPIC_API_KEY;
  process.env.ANTHROPIC_API_KEY = "must-not-leak";
  try {
    const command = engineCommand("claude-engineer", "hello", process.cwd());
    assert.equal(command.command, "claude");
    assert.equal(command.stdin, "hello");
    assert.equal(command.env.ANTHROPIC_API_KEY, undefined);
    assert.equal(command.args.includes("--print"), true);
  } finally {
    if (previous === undefined) delete process.env.ANTHROPIC_API_KEY;
    else process.env.ANTHROPIC_API_KEY = previous;
  }
});

test("Codex reviewer is read-only and consumes stdin", () => {
  const command = engineCommand("codex-engineer", "review", process.cwd());
  assert.equal(command.stdin, "review");
  assert.equal(command.args.includes("read-only"), true);
  assert.equal(command.args.at(-1), "-");
});
