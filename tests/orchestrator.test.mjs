import test from "node:test";
import assert from "node:assert/strict";
import { compileMission } from "../orchestrator/planner.mjs";
import { assertReleaseEvidence, assertSeparationOfDuties } from "../orchestrator/policy.mjs";
import { assertDecisionEvidence, buildEvidencePack, scoreEvidenceCandidate } from "../orchestrator/evidence.mjs";

const engines = [
  { id: "claude", provider: "anthropic", capabilities: ["architecture", "coding", "code-review", "security"], priority: 1, relativeCost: 4, enabled: true },
  { id: "codex", provider: "openai", capabilities: ["architecture", "coding", "testing", "code-review", "security"], priority: 2, relativeCost: 2, enabled: true },
  { id: "local", provider: "local", capabilities: ["deterministic-verification"], priority: 1, relativeCost: 0, enabled: true },
];

test("mission planning separates implementer from test, review, and repair providers", () => {
  const plan = compileMission({ objective: "Ship a verified feature" }, engines);
  const byRole = Object.fromEntries(plan.stages.map((stage) => [stage.role, stage]));
  assert.notEqual(byRole.implementer.provider, byRole["test-author"].provider);
  assert.notEqual(byRole.implementer.provider, byRole.reviewer.provider);
  assert.notEqual(byRole.implementer.provider, byRole.fixer.provider);
  assert.equal(plan.policy.selfApproval, "forbidden");
});

test("planning fails closed when no independent reviewer exists", () => {
  const oneProvider = engines.filter((engine) => engine.provider !== "openai");
  assert.throws(() => compileMission({ objective: "Unsafe plan" }, oneProvider), /No independent engine/);
});

test("policy rejects same-provider self review", () => {
  const assignments = ["test-author", "implementer", "reviewer", "fixer"].map((role, index) => ({ role, provider: "same", sessionId: String(index), canApproveOwnOutput: false }));
  assert.throws(() => assertSeparationOfDuties(assignments), /different provider/);
});

test("release remains blocked until deterministic evidence exists", () => {
  assert.throws(() => assertReleaseEvidence({ build: true, tests: true, independentReview: true, rollbackPlan: false, testExitCode: 0 }), /rollbackPlan/);
  assert.throws(() => assertReleaseEvidence({ build: true, tests: true, independentReview: true, rollbackPlan: true, testExitCode: 1 }), /tests failed/);
  assert.equal(assertReleaseEvidence({ build: true, tests: true, independentReview: true, rollbackPlan: true, testExitCode: 0 }), true);
});

test("mission policy can exclude a provider completely", () => {
  const providerDiverse = [...engines, { id: "kimi", provider: "moonshot", capabilities: ["architecture", "coding", "testing", "code-review", "security"], priority: 3, relativeCost: 1, enabled: true }];
  const plan = compileMission({ objective: "Provider-restricted mission", policy: { excludedProviders: ["anthropic"] } }, providerDiverse);
  assert.equal(plan.stages.some((stage) => stage.provider === "anthropic"), false);
});

test("interactive engines are visible but never scheduled for unattended work", () => {
  const withInteractive = [...engines, { id: "ui", provider: "google", capabilities: ["coding", "testing", "code-review", "security"], priority: 0, relativeCost: 0, enabled: true, execution: "interactive" }];
  const plan = compileMission({ objective: "Unattended mission" }, withInteractive);
  assert.equal(plan.stages.some((stage) => stage.engineId === "ui"), false);
});

test("evidence ranking values task fit and reproducibility above raw popularity", () => {
  const now = new Date("2026-07-22T00:00:00Z");
  const viralButWeak = scoreEvidenceCandidate({
    url: "https://x.com/example/status/1", channel: "x", taskFit: 0.2,
    demonstratedQuality: 0.2, reproducibility: 0.1, maintenance: 0.1,
    updatedAt: "2026-07-20T00:00:00Z", metrics: { views: 10_000_000, bookmarks: 20_000 },
  }, { now });
  const provenImplementation = scoreEvidenceCandidate({
    url: "https://github.com/example/proven", channel: "github", taskFit: 1,
    demonstratedQuality: 0.9, reproducibility: 1, maintenance: 0.9,
    updatedAt: "2026-06-20T00:00:00Z", metrics: { stars: 5_000 }, license: "MIT",
  }, { now });
  assert.ok(provenImplementation.score > viralButWeak.score);
});

test("decision evidence requires diverse channels and reproducible quality", () => {
  const pack = buildEvidencePack({
    question: "Choose an onboarding motion system",
    now: new Date("2026-07-22T00:00:00Z"),
    candidates: [
      { url: "https://github.com/a/one", channel: "github", taskFit: 1, demonstratedQuality: .9, reproducibility: 1, maintenance: .9, updatedAt: "2026-07-01", metrics: { stars: 10_000 }, license: "MIT" },
      { url: "https://x.com/a/status/1", channel: "x", taskFit: .8, demonstratedQuality: .8, reproducibility: .7, maintenance: .5, updatedAt: "2026-07-02", metrics: { views: 100_000, bookmarks: 2_000 } },
      { url: "https://product.example/case-study", channel: "product", taskFit: .9, demonstratedQuality: .9, reproducibility: .8, maintenance: .8, updatedAt: "2026-06-01", metrics: { downloads: 100_000 } },
    ],
  });
  assert.equal(pack.decisionReady, true);
  assert.equal(assertDecisionEvidence(pack), true);
});

test("unlicensed references cannot be selected for direct reuse", () => {
  const pack = buildEvidencePack({
    question: "Reuse a landing-page implementation",
    requiresReuseLicense: true,
    candidates: [{ url: "https://github.com/example/no-license", channel: "github", taskFit: 1, demonstratedQuality: 1, reproducibility: 1, maintenance: 1, metrics: { stars: 100_000 } }],
  });
  assert.equal(pack.candidates.length, 0);
  assert.throws(() => assertDecisionEvidence(pack), /insufficient/);
});
