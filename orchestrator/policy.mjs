export const productionRoles = Object.freeze([
  "specifier",
  "test-author",
  "implementer",
  "reviewer",
  "security-reviewer",
  "fixer",
  "verifier",
]);

export function assertSeparationOfDuties(assignments) {
  const byRole = new Map(assignments.map((assignment) => [assignment.role, assignment]));
  const required = ["test-author", "implementer", "reviewer", "fixer"];

  for (const role of required) {
    if (!byRole.has(role)) throw new Error(`Missing required production role: ${role}`);
  }

  const implementer = byRole.get("implementer");
  for (const role of ["test-author", "reviewer", "fixer"]) {
    const inspector = byRole.get(role);
    if (inspector.provider === implementer.provider) {
      throw new Error(`${role} must use a different provider from implementer`);
    }
    if (inspector.sessionId === implementer.sessionId) {
      throw new Error(`${role} cannot reuse the implementer session`);
    }
  }

  const reviewer = byRole.get("reviewer");
  if (reviewer.canApproveOwnOutput) throw new Error("A reviewer can never approve its own output");

  return true;
}

export function assertReleaseEvidence(evidence) {
  const required = ["build", "tests", "independentReview", "rollbackPlan"];
  const missing = required.filter((key) => !evidence[key]);
  if (missing.length) throw new Error(`Release blocked; missing evidence: ${missing.join(", ")}`);
  if (evidence.testExitCode !== 0) throw new Error("Release blocked; deterministic tests failed");
  return true;
}
