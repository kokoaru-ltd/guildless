import { randomUUID } from "node:crypto";
import { assertSeparationOfDuties } from "./policy.mjs";

const roleCapabilities = {
  specifier: "architecture",
  "test-author": "testing",
  implementer: "coding",
  reviewer: "code-review",
  "security-reviewer": "security",
  fixer: "coding",
  verifier: "deterministic-verification",
};

function chooseEngine(engines, capability, excludedProviders = new Set()) {
  const candidates = engines
    .filter((engine) => engine.enabled && engine.capabilities.includes(capability))
    .filter((engine) => engine.execution !== "interactive")
    .filter((engine) => !excludedProviders.has(engine.provider))
    .sort((a, b) => a.priority - b.priority || a.relativeCost - b.relativeCost);
  if (!candidates.length) throw new Error(`No independent engine available for ${capability}`);
  return candidates[0];
}

export function compileMission(mission, engines) {
  if (!mission?.objective?.trim()) throw new Error("Mission objective is required");

  const excludedProviders = new Set(mission.policy?.excludedProviders ?? []);
  const eligibleEngines = engines.filter((engine) => !excludedProviders.has(engine.provider));
  const implementer = chooseEngine(eligibleEngines, "coding");
  const independent = new Set([implementer.provider]);
  const selected = {
    specifier: chooseEngine(eligibleEngines, "architecture"),
    "test-author": chooseEngine(eligibleEngines, "testing", independent),
    implementer,
    reviewer: chooseEngine(eligibleEngines, "code-review", independent),
    "security-reviewer": chooseEngine(eligibleEngines, "security", independent),
    fixer: chooseEngine(eligibleEngines, "coding", independent),
    verifier: chooseEngine(eligibleEngines, "deterministic-verification"),
  };

  const assignments = Object.entries(selected).map(([role, engine]) => ({
    role,
    engineId: engine.id,
    provider: engine.provider,
    sessionId: randomUUID(),
    canApproveOwnOutput: false,
  }));
  assertSeparationOfDuties(assignments);

  const dependencies = {
    specifier: [],
    "test-author": ["specifier"],
    implementer: ["specifier", "test-author"],
    reviewer: ["implementer"],
    "security-reviewer": ["implementer"],
    fixer: ["reviewer", "security-reviewer"],
    verifier: ["fixer"],
  };

  return {
    id: mission.id ?? randomUUID(),
    objective: mission.objective,
    budget: mission.budget,
    policy: {
      selfApproval: "forbidden",
      crossProviderReview: "required",
      deterministicVerification: "required",
      productionApproval: "human",
      excludedProviders: [...excludedProviders],
      maximumDelegationDepth: mission.policy?.maximumDelegationDepth ?? 3,
    },
    stages: assignments.map((assignment) => ({
      ...assignment,
      capability: roleCapabilities[assignment.role],
      dependsOn: dependencies[assignment.role],
      status: "pending",
    })),
  };
}
