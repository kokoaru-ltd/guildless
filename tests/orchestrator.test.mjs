import test from "node:test";
import assert from "node:assert/strict";
import { compileMission } from "../orchestrator/planner.mjs";
import { assertReleaseEvidence, assertSeparationOfDuties } from "../orchestrator/policy.mjs";

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
