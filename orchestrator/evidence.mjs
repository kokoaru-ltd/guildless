const clamp = (value, minimum = 0, maximum = 1) => Math.min(maximum, Math.max(minimum, value));

function freshness(updatedAt, now) {
  if (!updatedAt) return 0;
  const ageDays = Math.max(0, (now.getTime() - new Date(updatedAt).getTime()) / 86_400_000);
  return Math.exp(-ageDays / 365);
}

function adoption(candidate) {
  const github = Math.log10((candidate.metrics?.stars ?? 0) + 1) / 5;
  const xViews = Math.log10((candidate.metrics?.views ?? 0) + 1) / 7;
  const xSaves = Math.log10((candidate.metrics?.bookmarks ?? 0) + 1) / 4;
  const usage = Math.log10((candidate.metrics?.downloads ?? 0) + 1) / 8;
  return clamp(Math.max(github, xViews * 0.6 + xSaves * 0.4, usage));
}

export function scoreEvidenceCandidate(candidate, options = {}) {
  const now = options.now ?? new Date();
  const requiresReuseLicense = options.requiresReuseLicense ?? false;
  if (requiresReuseLicense && !candidate.license) return { score: 0, rejected: "missing-license" };
  if (!candidate.url || !candidate.channel) return { score: 0, rejected: "missing-provenance" };

  const dimensions = {
    taskFit: clamp(candidate.taskFit ?? 0),
    demonstratedQuality: clamp(candidate.demonstratedQuality ?? 0),
    adoption: adoption(candidate),
    freshness: freshness(candidate.updatedAt, now),
    reproducibility: clamp(candidate.reproducibility ?? 0),
    maintenance: clamp(candidate.maintenance ?? 0),
  };
  const manipulationPenalty = clamp(candidate.manipulationRisk ?? 0);
  const score =
    dimensions.taskFit * 0.30 +
    dimensions.demonstratedQuality * 0.25 +
    dimensions.reproducibility * 0.15 +
    dimensions.maintenance * 0.10 +
    dimensions.adoption * 0.10 +
    dimensions.freshness * 0.10 -
    manipulationPenalty * 0.25;

  return { score: clamp(score), dimensions, rejected: null };
}

export function buildEvidencePack({ question, candidates, now = new Date(), requiresReuseLicense = false }) {
  if (!question?.trim()) throw new Error("Evidence question is required");
  const ranked = candidates
    .map((candidate) => ({ ...candidate, evaluation: scoreEvidenceCandidate(candidate, { now, requiresReuseLicense }) }))
    .filter((candidate) => !candidate.evaluation.rejected)
    .sort((left, right) => right.evaluation.score - left.evaluation.score);

  const channels = new Set(ranked.map((candidate) => candidate.channel));
  const warnings = [];
  if (ranked.length < 3) warnings.push("fewer-than-three-usable-references");
  if (channels.size < 2) warnings.push("single-channel-evidence");
  if (!ranked.some((candidate) => candidate.reproducibility >= 0.7)) warnings.push("no-reproducible-reference");
  if (!ranked.some((candidate) => candidate.demonstratedQuality >= 0.7)) warnings.push("no-quality-demonstration");

  return {
    question,
    createdAt: now.toISOString(),
    candidates: ranked,
    warnings,
    decisionReady: warnings.length === 0,
  };
}

export function assertDecisionEvidence(pack) {
  if (!pack?.decisionReady) {
    throw new Error(`Decision evidence is insufficient: ${(pack?.warnings ?? ["missing-pack"]).join(", ")}`);
  }
  return true;
}
