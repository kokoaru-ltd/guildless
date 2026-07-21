import { existsSync } from "node:fs";
import { join } from "node:path";

const localAppData = process.env.LOCALAPPDATA ?? "";
const appData = process.env.APPDATA ?? "";
const kimiNode = join(localAppData, "Programs", "kimi-desktop", "resources", "resources", "runtime", "node.exe");
const kimiDaimon = join(appData, "kimi-desktop", "daimon-bundle", "bin", "kimi-daimon.cmd");
const kimiConfig = join(appData, "kimi-desktop", "daimon-share", "daimon", "config.json");
const xaiAdapter = join(import.meta.dirname, "adapters", "xai.mjs");

export const defaultEngines = [
  { id: "claude-engineer", provider: "anthropic", capabilities: ["architecture", "coding", "code-review", "security"], priority: 10, relativeCost: 8, enabled: true, execution: "headless" },
  { id: "codex-engineer", provider: "openai", capabilities: ["architecture", "coding", "testing", "code-review", "security"], priority: 20, relativeCost: 6, enabled: true, execution: "headless" },
  { id: "kimi-operator", provider: "moonshot", capabilities: ["operations", "research", "testing", "code-review", "security", "coding"], priority: 30, relativeCost: 2, enabled: existsSync(kimiNode) && existsSync(kimiDaimon) && existsSync(kimiConfig), execution: "headless", supportsSwarm: true },
  { id: "grok-builder", provider: "xai", capabilities: ["architecture", "coding", "testing", "code-review", "security", "research"], priority: 35, relativeCost: 3, enabled: Boolean(process.env.XAI_API_KEY), execution: "headless", model: "grok-build-0.1" },
  { id: "gemini-antigravity", provider: "google", capabilities: ["architecture", "coding", "testing", "code-review", "multimodal"], priority: 40, relativeCost: 3, enabled: process.platform === "win32", execution: "interactive" },
  { id: "node-verifier", provider: "local", capabilities: ["deterministic-verification"], priority: 1, relativeCost: 0, enabled: true, execution: "deterministic" },
];

export function engineCommand(engineId, prompt, workspace) {
  if (engineId === "claude-engineer") {
    return { command: "claude", args: ["--print", "--permission-mode", "acceptEdits", "--no-session-persistence", prompt], cwd: workspace };
  }
  if (engineId === "codex-engineer") {
    return { command: "codex", args: ["exec", "--sandbox", "workspace-write", "--ask-for-approval", "never", "-C", workspace, prompt], cwd: workspace };
  }
  if (engineId === "kimi-operator") {
    return {
      command: kimiDaimon,
      args: ["--node", kimiNode, "run", "--config", kimiConfig, "--prompt", prompt],
      cwd: workspace,
      supportsSwarm: true,
    };
  }
  if (engineId === "gemini-antigravity") {
    return {
      command: "antigravity",
      args: ["chat", "--mode", "agent", "--new-window", prompt],
      cwd: workspace,
      interactive: true,
    };
  }
  if (engineId === "grok-builder") {
    return {
      command: process.execPath,
      args: [xaiAdapter, "--model", "grok-build-0.1", "--prompt", prompt],
      cwd: workspace,
    };
  }
  throw new Error(`Engine ${engineId} is not an AI command engine`);
}

export function installedEngineSummary() {
  return defaultEngines.map(({ id, provider, enabled, execution, supportsSwarm = false }) => ({ id, provider, enabled, execution, supportsSwarm }));
}
