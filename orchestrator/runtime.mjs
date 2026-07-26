#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { EventLedger } from "./ledger.mjs";
import { engineCommand } from "./engines.mjs";

const ROOT = resolve(import.meta.dirname, "..");
const STATE = join(ROOT, ".guildless");
const RUNS = join(STATE, "runs");
const DB = process.env.GUILDLESS_DB ?? join(STATE, "events.sqlite");
const TIMEOUT = Number(process.env.GUILDLESS_ENGINE_TIMEOUT_MS ?? 180_000);
mkdirSync(RUNS, { recursive: true });

function execute(spec, timeout = TIMEOUT) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd,
      env: spec.env ?? process.env,
      shell: process.platform === "win32",
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "", stderr = "", settled = false;
    child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.on("data", chunk => { stderr += chunk; });
    child.on("error", reject);
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      reject(new Error(`${spec.command} timed out after ${timeout}ms`));
    }, timeout);
    child.on("close", code => {
      clearTimeout(timer);
      if (settled) return;
      settled = true;
      resolvePromise({ exitCode: code ?? 1, stdout, stderr });
    });
    if (spec.stdin) child.stdin.write(spec.stdin, "utf8");
    child.stdin.end();
  });
}

function safeLog(result) {
  return { exitCode: result.exitCode, stdout: result.stdout.slice(-8000), stderr: result.stderr.slice(-4000) };
}

export async function runHelloWorldMission({ transcript, inputMode = "voice" }, options = {}) {
  if (inputMode !== "voice") throw new Error("GUILDLESS-001 requires inputMode=voice");
  if (!transcript?.trim()) throw new Error("voice transcript is required");
  const missionId = options.missionId ?? `hello-${Date.now()}-${randomUUID().slice(0, 8)}`;
  const workspace = join(RUNS, missionId, "workspace");
  mkdirSync(workspace, { recursive: true });
  const ledger = new EventLedger(options.dbPath ?? DB);
  ledger.append(missionId, "voice.transcript.accepted", "owner", { transcript, inputMode });
  ledger.append(missionId, "mission.created", "runtime", { objective: transcript, workspace });

  try {
    const claudePrompt = `You are the implementer. In the current empty workspace, build a minimal dependency-free Node.js CLI for this objective: ${transcript}\nRequirements: create package.json, cli.mjs, and tests/cli.test.mjs using node:test. Running \"node cli.mjs\" must print exactly \"Hello, world!\" followed by a newline. npm test must pass. Do not ask questions. Do not use markdown-only answers: create the files and then briefly report what you changed.`;
    ledger.append(missionId, "work.started", "claude", { role: "implementer" });
    const claude = await execute(engineCommand("claude-engineer", claudePrompt, workspace));
    ledger.append(missionId, "work.finished", "claude", safeLog(claude));
    if (claude.exitCode !== 0) throw new Error(`Claude failed with ${claude.exitCode}`);

    const reviewPrompt = `You are an independent read-only reviewer. Inspect every file in this workspace. Verify the implementation matches: dependency-free Node.js CLI; node cli.mjs prints exactly Hello, world! plus newline; node:test coverage exists; no secrets or unsafe behavior. Do not edit files. First line must be exactly PASS or FAIL. Then concise findings.`;
    ledger.append(missionId, "review.started", "codex", { role: "reviewer", independentFrom: "claude" });
    const codex = await execute(engineCommand("codex-engineer", reviewPrompt, workspace));
    const reviewPassed = codex.exitCode === 0 && /^PASS\b/i.test(codex.stdout.trimStart());
    ledger.append(missionId, "review.finished", "codex", { ...safeLog(codex), passed: reviewPassed });
    if (!reviewPassed) throw new Error("Codex review failed");

    ledger.append(missionId, "verification.started", "node", {});
    const tests = await execute({ command: "npm", args: ["test"], cwd: workspace, stdin: "" }, 60_000);
    const cli = await execute({ command: "node", args: ["cli.mjs"], cwd: workspace, stdin: "" }, 30_000);
    const verified = tests.exitCode === 0 && cli.exitCode === 0 && cli.stdout === "Hello, world!\n";
    ledger.append(missionId, "verification.finished", "node", {
      passed: verified,
      tests: safeLog(tests),
      cli: safeLog(cli),
    });
    if (!verified) throw new Error("Deterministic verification failed");

    const evidence = { missionId, status: "completed", workspace, implementer: "claude", reviewer: "codex", output: cli.stdout };
    writeFileSync(join(RUNS, missionId, "evidence.json"), JSON.stringify(evidence, null, 2));
    ledger.append(missionId, "mission.completed", "runtime", evidence);
    return { ...evidence, events: ledger.events(missionId) };
  } catch (error) {
    ledger.append(missionId, "mission.failed", "runtime", { message: error.message });
    error.missionId = missionId;
    throw error;
  } finally {
    ledger.close();
  }
}

function json(response, status, body) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "http://localhost:3000",
    "access-control-allow-headers": "content-type",
    "access-control-allow-methods": "GET,POST,OPTIONS",
  });
  response.end(JSON.stringify(body));
}

export function startRuntimeServer(port = Number(process.env.GUILDLESS_PORT ?? 43117)) {
  const server = createServer(async (request, response) => {
    if (request.method === "OPTIONS") return json(response, 204, {});
    if (request.method === "GET" && request.url === "/health") {
      return json(response, 200, { ok: true, runtime: "guildless-local", claudeAuth: "claude.ai", ledger: DB });
    }
    if (request.method === "POST" && request.url === "/missions/hello-world") {
      let raw = "";
      for await (const chunk of request) raw += chunk;
      try { return json(response, 200, await runHelloWorldMission(JSON.parse(raw || "{}"))); }
      catch (error) { return json(response, 500, { error: error.message, missionId: error.missionId }); }
    }
    return json(response, 404, { error: "not_found" });
  });
  server.listen(port, "127.0.0.1", () => console.log(`GUILDLESS runtime listening on http://127.0.0.1:${port}`));
  return server;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  if (process.argv[2] === "run-once") {
    const transcript = process.argv.slice(3).join(" ") || "hello worldなCLIツールを作って";
    runHelloWorldMission({ transcript, inputMode: "voice" })
      .then(result => console.log(JSON.stringify(result, null, 2)))
      .catch(error => { console.error(error); process.exitCode = 1; });
  } else startRuntimeServer();
}
