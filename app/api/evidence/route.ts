export const runtime = "nodejs";

type Candidate = {
  url?: string;
  channel?: string;
  taskFit?: number;
  demonstratedQuality?: number;
  reproducibility?: number;
  maintenance?: number;
  manipulationRisk?: number;
  updatedAt?: string;
  license?: string;
  metrics?: Record<string, number>;
};

type EvidenceModule = {
  buildEvidencePack(input: {
    question: string;
    candidates: Candidate[];
    requiresReuseLicense?: boolean;
  }): {
    question: string;
    createdAt: string;
    candidates: Array<Candidate & { evaluation: { score: number; dimensions: Record<string, number> } }>;
    warnings: string[];
    decisionReady: boolean;
  };
};

function validCandidate(value: unknown): value is Candidate {
  if (!value || typeof value !== "object") return false;
  const item = value as Candidate;
  return typeof item.url === "string" && /^https?:\/\//.test(item.url) &&
    typeof item.channel === "string" && item.channel.length <= 40;
}

export async function POST(request: Request) {
  let body: { question?: string; candidates?: unknown[]; requiresReuseLicense?: boolean };
  try { body = await request.json(); }
  catch { return Response.json({ error: "bad_request" }, { status: 400 }); }

  const question = String(body.question ?? "").trim().slice(0, 500);
  const candidates = (body.candidates ?? []).filter(validCandidate).slice(0, 100);
  if (!question || candidates.length === 0) {
    return Response.json({ error: "question_and_candidates_required" }, { status: 400 });
  }

  const evidenceModule = await import("../../../orchestrator/evidence.mjs") as EvidenceModule;
  const pack = evidenceModule.buildEvidencePack({
    question,
    candidates,
    requiresReuseLicense: body.requiresReuseLicense === true,
  });
  const confidence = pack.candidates.length
    ? Math.round(pack.candidates.reduce((sum, item) => sum + item.evaluation.score, 0) / pack.candidates.length * 100)
    : 0;

  return Response.json({
    ...pack,
    confidence,
    releaseGate: pack.decisionReady ? "review-required" : "blocked",
  });
}
