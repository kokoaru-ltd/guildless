#!/usr/bin/env node

function readArgument(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

const apiKey = process.env.XAI_API_KEY;
const model = readArgument("--model") ?? "grok-build-0.1";
const prompt = readArgument("--prompt");

if (!apiKey) {
  console.error("XAI_API_KEY is not configured; Grok worker is unavailable");
  process.exit(2);
}
if (!prompt) {
  console.error("Missing --prompt");
  process.exit(2);
}

const response = await fetch("https://api.x.ai/v1/responses", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model,
    input: prompt,
    reasoning_effort: "medium",
  }),
});

const payload = await response.json();
if (!response.ok) {
  console.error(JSON.stringify({ provider: "xai", status: response.status, error: payload.error?.message ?? "request failed" }));
  process.exit(1);
}

const text = payload.output
  ?.flatMap((item) => item.content ?? [])
  .filter((item) => item.type === "output_text")
  .map((item) => item.text)
  .join("\n");

console.log(JSON.stringify({ provider: "xai", model, responseId: payload.id, output: text ?? "", usage: payload.usage ?? null }));
