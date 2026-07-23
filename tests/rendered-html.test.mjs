import assert from "node:assert/strict";
import test from "node:test";

async function worker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  return (await import(workerUrl.href)).default;
}

const env = {
  ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
};
const ctx = { waitUntil() {}, passThroughOnException() {} };

test("server-renders the Guildless expert workspace", async () => {
  const app = await worker();
  const response = await app.fetch(new Request("http://localhost/", {
    headers: { accept: "text/html" },
  }), env, ctx);
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>GUILDLESS/);
  assert.match(html, /Expert council/);
  assert.match(html, /ENVIRONMENT/);
  assert.match(html, /Evidence/);
  assert.match(html, /Builders cannot approve their own release/);
});

test("evidence API scores diverse sources and returns a release gate", async () => {
  const app = await worker();
  const response = await app.fetch(new Request("http://localhost/api/evidence", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      question: "Is this implementation ready?",
      candidates: [
        { url: "https://github.com/example/project", channel: "github", taskFit: .9, demonstratedQuality: .9, reproducibility: .9, maintenance: .9, updatedAt: new Date().toISOString(), metrics: { stars: 10000 }, license: "MIT" },
        { url: "https://example.com/reviews", channel: "community", taskFit: .8, demonstratedQuality: .75, reproducibility: .7, maintenance: .7, updatedAt: new Date().toISOString(), metrics: { views: 100000 } },
        { url: "https://example.com/benchmark", channel: "benchmark", taskFit: 1, demonstratedQuality: 1, reproducibility: 1, maintenance: .8, updatedAt: new Date().toISOString(), metrics: { downloads: 50000 } },
      ],
    }),
  }), env, ctx);
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.decisionReady, true);
  assert.equal(result.releaseGate, "review-required");
  assert.ok(result.confidence >= 70);
  assert.equal(result.candidates.length, 3);
});

test("evidence API rejects requests without provenance", async () => {
  const app = await worker();
  const response = await app.fetch(new Request("http://localhost/api/evidence", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "Unsafe", candidates: [{ channel: "unknown" }] }),
  }), env, ctx);
  assert.equal(response.status, 400);
});
