import { existsSync } from "node:fs";
import { join } from "node:path";

const localAppData = process.env.LOCALAPPDATA ?? "";
const appData      = process.env.APPDATA      ?? "";
const kimiDaimon   = join(appData, "kimi-desktop", "daimon-bundle", "bin", "kimi-daimon.cmd");
const kimiConfig   = join(appData, "kimi-desktop", "daimon-share",  "daimon", "config.json");
const kimiNode     = join(localAppData, "Programs", "kimi-desktop", "resources", "resources", "runtime", "node.exe");
const xaiAdapter   = join(import.meta.dirname, "adapters", "xai.mjs");

export const defaultEngines = [
  {
    id: "claude-engineer", provider: "anthropic",
    capabilities: ["architecture", "coding", "code-review", "security"],
    priority: 10, relativeCost: 8, enabled: true, execution: "headless",
  },
  {
    id: "codex-engineer", provider: "openai",
    capabilities: ["architecture", "coding", "testing", "code-review", "security"],
    priority: 20, relativeCost: 6, enabled: true, execution: "headless",
  },
  {
    id: "kimi-operator", provider: "moonshot",
    capabilities: ["operations", "research", "testing", "code-review", "security", "coding"],
    priority: 30, relativeCost: 2,
    enabled: existsSync(kimiDaimon) && existsSync(kimiConfig),
    execution: "headless", supportsSwarm: true,
  },
  {
    id: "grok-builder", provider: "xai",
    capabilities: ["architecture", "coding", "testing", "code-review", "security", "research"],
    priority: 35, relativeCost: 3,
    enabled: Boolean(process.env.XAI_API_KEY), execution: "headless",
  },
  {
    id: "gemini-antigravity", provider: "google",
    capabilities: ["architecture", "coding", "testing", "code-review", "multimodal"],
    priority: 40, relativeCost: 3,
    enabled: process.platform === "win32", execution: "interactive",
  },
  {
    id: "node-verifier", provider: "local",
    capabilities: ["deterministic-verification"],
    priority: 1, relativeCost: 0, enabled: true, execution: "deterministic",
  },
];

/**
 * Returns { command, args, cwd, stdin }
 * stdin = string → pipe to the process's stdin instead of passing as argument.
 * This avoids Windows command-line length / escaping limits for long prompts.
 */
export function engineCommand(engineId, prompt, workspace) {
  // Claude Code reads stdin in print mode. Remove ANTHROPIC_API_KEY so a stale
  // pay-as-you-go key cannot override the user's authenticated claude.ai plan.
  if (engineId === "claude-engineer") {
    const { ANTHROPIC_API_KEY: _ignored, ...claudeEnv } = process.env;
    return {
      command: "claude",
      args: [
        "--print",
        "--permission-mode", "bypassPermissions",
        "--output-format", "text",
      ],
      cwd:   workspace,
      stdin: prompt,
      env: claudeEnv,
    };
  }

  // Codex: reads prompt from stdin when prompt arg is "-"
  if (engineId === "codex-engineer") {
    return {
      command: "codex",
      args: [
        "exec",
        "--sandbox", "read-only",
        "--ephemeral",
        "-C", workspace,
        "-",                 // "-" = read from stdin
      ],
      cwd:   workspace,
      stdin: prompt,
    };
  }

  // Kimi daimon: --prompt "-" → stdin
  if (engineId === "kimi-operator") {
    return {
      command: kimiDaimon,
      args: ["run", "--config", kimiConfig, "--prompt", "-"],
      cwd:   workspace,
      stdin: prompt,
      env:   { ...process.env, DAIMON_NODE: kimiNode },
    };
  }

  if (engineId === "grok-builder") {
    return {
      command: process.execPath,
      args:  [xaiAdapter, "--model", "grok-build-0.1"],
      cwd:   workspace,
      stdin: prompt,
    };
  }

  throw new Error(`Engine ${engineId} has no headless command definition`);
}

export function installedEngineSummary() {
  return defaultEngines.map(({ id, provider, enabled, execution, supportsSwarm = false }) => ({
    id, provider, enabled, execution, supportsSwarm,
  }));
}
