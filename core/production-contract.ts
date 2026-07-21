import type { Capability } from "./model-registry";

export type ApprovalPolicy = {
  monthlyBudgetYen: number;
  requireApprovalForProduction: boolean;
  requireApprovalForDestructiveActions: boolean;
  requireApprovalAboveYen: number;
};

export type ProductionTask = {
  id: string;
  objective: string;
  capability: Capability;
  dependsOn: string[];
  acceptanceTests: string[];
  status: "blocked" | "ready" | "running" | "review" | "done" | "failed";
  attempts: number;
  engineId?: string;
  artifactPaths: string[];
};

export type Mission = {
  id: string;
  objective: string;
  deadline?: string;
  policy: ApprovalPolicy;
  tasks: ProductionTask[];
};
