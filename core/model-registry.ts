export type Capability =
  | "architecture"
  | "coding"
  | "visual-generation"
  | "video-generation"
  | "research"
  | "operations"
  | "marketing";

export type Engine = {
  id: string;
  provider: string;
  capabilities: Capability[];
  relativeCost: "free" | "low" | "medium" | "high";
  privacy: "local" | "cloud";
  enabled: boolean;
};

export const engineRegistry: Engine[] = [
  { id: "gpt-image", provider: "openai", capabilities: ["visual-generation", "marketing"], relativeCost: "medium", privacy: "cloud", enabled: false },
  { id: "claude-code", provider: "anthropic", capabilities: ["architecture", "coding"], relativeCost: "high", privacy: "cloud", enabled: false },
  { id: "codex", provider: "openai", capabilities: ["architecture", "coding"], relativeCost: "medium", privacy: "cloud", enabled: false },
  { id: "kimi", provider: "moonshot", capabilities: ["research", "operations", "coding"], relativeCost: "low", privacy: "cloud", enabled: false },
  { id: "gemini", provider: "google", capabilities: ["research", "video-generation", "marketing"], relativeCost: "low", privacy: "cloud", enabled: false },
  { id: "seedance", provider: "bytedance", capabilities: ["video-generation", "marketing"], relativeCost: "medium", privacy: "cloud", enabled: false },
];

export function candidatesFor(capability: Capability) {
  return engineRegistry.filter((engine) => engine.enabled && engine.capabilities.includes(capability));
}
