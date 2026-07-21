export const defaultEngines = [
  { id: "claude-engineer", provider: "anthropic", capabilities: ["architecture", "coding", "code-review", "security"], priority: 10, relativeCost: 8, enabled: true },
  { id: "codex-engineer", provider: "openai", capabilities: ["architecture", "coding", "testing", "code-review", "security"], priority: 20, relativeCost: 6, enabled: true },
  { id: "node-verifier", provider: "local", capabilities: ["deterministic-verification"], priority: 1, relativeCost: 0, enabled: true },
];

export function engineCommand(engineId, prompt, workspace) {
  if (engineId === "claude-engineer") {
    return { command: "claude", args: ["--print", "--permission-mode", "acceptEdits", "--no-session-persistence", prompt], cwd: workspace };
  }
  if (engineId === "codex-engineer") {
    return { command: "codex", args: ["exec", "--sandbox", "workspace-write", "--ask-for-approval", "never", "-C", workspace, prompt], cwd: workspace };
  }
  throw new Error(`Engine ${engineId} is not an AI command engine`);
}
