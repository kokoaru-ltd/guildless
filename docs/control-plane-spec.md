# GUILDLESS Control Plane Specification

Status: implementation contract, version 0.1

This document defines the system that must exist before the mobile application matters. GUILDLESS is not a chat UI and not a collection of model prompts. It is a durable production control plane that lets one owner direct a software, game, media, or digital-product organization by outcomes and constraints.

## 1. Product claim

The owner supplies:

- an outcome;
- measurable success criteria;
- budget and deadline;
- risk and authority boundaries;
- optional product judgments and reference material.

The system owns:

- decomposition into work;
- assignment to specialized engines;
- workspace isolation;
- implementation and artifact production;
- independent review;
- deterministic verification;
- integration and release preparation;
- monitoring, incident response, maintenance, and learning.

The system must not claim completion because an agent said it was done. Completion means that evidence satisfies a versioned contract and an independent gate accepts that evidence.

## 2. Success definition

GUILDLESS succeeds only when one owner can operate a product normally requiring a multidisciplinary team while spending most human time on product direction, not coordination.

Primary benchmark:

- run a real product for 90 days;
- maintain at least 100,000 lines of source or an equivalent multi-asset game;
- produce a reproducible build every day;
- keep median mandatory owner intervention below 60 minutes per day;
- recover from injected model, build, test, deployment, and provider failures;
- never cross the declared monetary or authority limit silently;
- trace every released artifact to its task, inputs, producer, reviewer, and evidence.

This does not prove that every arbitrary enterprise can be replaced. It proves a bounded production organization can be operated by one person.

## 3. Non-goals

Version 1 does not:

- let a language model deploy or delete production data without a capability grant;
- accept subjective self-review as release evidence;
- promise correct legal, medical, financial, or safety-critical output;
- hide provider costs inside an unlimited subscription promise;
- require one model vendor;
- treat a long chat transcript as durable state;
- recursively spawn agents without a bounded work graph, depth, and budget.

## 4. Architectural shape

```text
Owner intent
    |
    v
Mission compiler -----> Decision queue <----- Policy engine
    |                                          |
    v                                          v
Versioned work graph <---- Event ledger ---- Budget + authority ledger
    |
    v
Scheduler ---> Capability router ---> Isolated worker runtimes
    |                                      |
    |                                      v
    |                              Artifact + evidence store
    |                                      |
    v                                      v
Independent critics <-------------- Verification runners
    |                                      |
    +--------------> Integration gate <----+
                            |
                            v
                    Release / operations
                            |
                            v
                  Telemetry creates missions
```

The control plane is deterministic orchestration around probabilistic workers. Models propose work and judgments. The control plane owns state transitions, permissions, budgets, retries, and release gates.

## 5. Core invariants

1. Every state change is appended to an event ledger before it is considered committed.
2. Every worker invocation is idempotent or carries a unique idempotency key.
3. A producer cannot approve its own output, even through a reused session or delegated descendant.
4. A task cannot be scheduled until all declared dependencies are accepted.
5. A task cannot be accepted without its required evidence types.
6. A release cannot contain an artifact whose provenance is missing.
7. Money is reserved before work begins and reconciled after it ends.
8. Tools are denied by default and granted to a task for a bounded time and scope.
9. An expired worker lease makes work eligible for recovery; it does not erase its history.
10. Graph changes are proposals. They require validation before becoming a new graph version.
11. A provider failure cannot corrupt mission state.
12. Human approval is required only by explicit policy, not because an agent feels uncertain.

## 6. Domain model

### 6.1 Mission

A mission is the durable business outcome.

```ts
type Mission = {
  id: string;
  objective: string;
  successMetrics: SuccessMetric[];
  constraints: Constraint[];
  deadline?: string;
  budget: BudgetPolicy;
  authorityPolicyId: string;
  repositoryRefs: RepositoryRef[];
  graphVersion: number;
  status: "draft" | "planning" | "running" | "paused" | "blocked" |
          "release_ready" | "operating" | "completed" | "cancelled";
};
```

### 6.2 Work graph

The work graph is a versioned directed acyclic graph. Nodes describe contracts, not prompts.

```ts
type WorkItem = {
  id: string;
  missionId: string;
  graphVersion: number;
  kind: "decision" | "research" | "specification" | "test" | "code" |
        "asset" | "review" | "verification" | "integration" | "release" |
        "operation" | "incident";
  objective: string;
  inputs: ArtifactRef[];
  outputContract: OutputContract;
  acceptanceContract: AcceptanceContract;
  dependencies: string[];
  risk: "low" | "medium" | "high" | "critical";
  estimatedCost: MoneyRange;
  requiredCapabilities: string[];
  allowedToolScopes: ToolScope[];
  attemptPolicy: AttemptPolicy;
  status: WorkStatus;
};
```

A graph may be expanded while running, but it cannot be mutated in place. A planner emits a `GraphChangeProposal` containing added nodes, removed nodes, changed dependencies, justification, cost delta, and risk delta. The graph validator rejects cycles, orphaned outputs, unbudgeted work, or weakened acceptance criteria.

### 6.3 Artifact

An artifact is immutable once submitted for review. A correction creates a new version.

```ts
type Artifact = {
  id: string;
  version: number;
  workItemId: string;
  mediaType: string;
  uri: string;
  contentDigest: string;
  producerRunId: string;
  sourceArtifacts: ArtifactRef[];
  license?: string;
  createdAt: string;
};
```

Artifacts include source commits, patches, binaries, screenshots, test reports, videos, textures, 3D models, design tokens, research briefs, deployment manifests, and decision records.

### 6.4 Evidence

Evidence is typed and machine-readable.

```ts
type Evidence = {
  id: string;
  artifactId: string;
  type: "test_result" | "build_result" | "static_analysis" | "security_scan" |
        "visual_diff" | "performance_measurement" | "review_verdict" |
        "license_check" | "rollback_rehearsal" | "human_decision";
  runner: string;
  inputDigest: string;
  result: "pass" | "fail" | "inconclusive";
  metrics: Record<string, number | string | boolean>;
  logUri: string;
  createdAt: string;
};
```

Evidence becomes stale when its input digest no longer matches the artifact under consideration.

### 6.5 Run and lease

A run is one worker attempt. A lease prevents two workers from unknowingly owning the same attempt.

```ts
type Run = {
  id: string;
  workItemId: string;
  engineId: string;
  provider: string;
  parentRunId?: string;
  rootProducerRunId: string;
  workspaceId: string;
  promptDigest: string;
  status: "leased" | "running" | "submitted" | "failed" | "timed_out" |
          "cancelled" | "superseded";
  leaseExpiresAt: string;
  reservedCost: Money;
  actualCost?: Money;
};
```

`rootProducerRunId` follows delegation ancestry. It prevents a producer from creating a child reviewer that approves the parent's work.

### 6.6 Decision

A decision is a durable product or authority choice, not a chat message.

```ts
type Decision = {
  id: string;
  missionId: string;
  question: string;
  options: DecisionOption[];
  recommendation?: string;
  evidenceRefs: string[];
  owner: "system" | "human";
  deadline?: string;
  status: "open" | "decided" | "expired";
  selectedOption?: string;
  rationale?: string;
};
```

## 7. Mission compilation

Mission compilation is a sequence of constrained passes, not one large prompt.

1. **Intent normalization** converts the owner's outcome into explicit terms without inventing requirements.
2. **Unknown extraction** separates discoverable unknowns from product decisions that only the owner can make.
3. **Success contract** defines measurable product, delivery, reliability, cost, and operational metrics.
4. **Risk classification** identifies irreversible actions, external dependencies, privacy scope, and failure blast radius.
5. **Architecture proposal** defines systems and boundaries before tasks.
6. **Work graph generation** creates thin vertical slices before broad parallel work.
7. **Adversarial planning review** searches for missing work, circular assumptions, unverifiable outputs, and cost traps.
8. **Graph validation** applies deterministic rules.
9. **Budget reservation** reserves the first execution horizon, not the whole hypothetical plan.
10. **Owner gate** appears only if policy requires a product-defining or high-risk choice.

The first graph horizon should cover one releasable vertical slice. Later horizons are planned using evidence from actual execution.

## 8. Scheduling

### 8.1 Readiness

A work item is ready only when:

- every dependency has status `accepted`;
- required input artifacts exist and match declared digests;
- a compatible isolated workspace is available;
- cost can be reserved;
- an engine satisfies capabilities, data policy, and separation rules;
- required tools can be granted safely;
- the mission and item are not paused.

### 8.2 Priority score

The scheduler uses an explainable score:

```text
priority = critical_path_weight
         + deadline_pressure
         + dependency_unblock_value
         + incident_severity
         - estimated_cost_penalty
         - risk_penalty
         - retry_penalty
```

Hard constraints are applied before scoring. A cheap model must never be chosen if it violates privacy, capability, or independence requirements.

### 8.3 Concurrency

Concurrency is limited by:

- mission budget burn rate;
- provider rate limits;
- repository conflict domains;
- shared environment capacity;
- task risk;
- owner-defined maximum parallelism.

Two code tasks may run concurrently only if their declared ownership regions do not overlap or an integration strategy exists. Optimistic parallel edits without ownership are forbidden for high-risk branches.

### 8.4 Leasing and recovery

The scheduler grants a renewable lease. Workers heartbeat with progress, spend, current action, and newly discovered risk. When a lease expires:

1. mark the run timed out;
2. preserve workspace and logs;
3. inspect whether a valid artifact was already produced;
4. resume from checkpoint if safe;
5. otherwise create a new attempt with failure context;
6. escalate only after the retry policy is exhausted or authority is missing.

## 9. Capability routing

Routing is based on measured capability, not brand preference.

Each engine profile contains:

- supported modalities and tools;
- headless or interactive execution;
- context and output limits;
- price model and observed cost;
- latency and availability;
- benchmark scores by work-item kind;
- recent acceptance, rollback, and defect-escape rates;
- privacy and data-retention policy;
- compatibility with required artifact formats;
- current account quota and rate limits.

Candidate selection:

```text
eligible = capability AND tool AND privacy AND quota AND independence
utility  = quality_probability * completion_probability
           - normalized_cost
           - latency_penalty
           - correlated_failure_penalty
```

Static defaults are allowed only during bootstrap. Production routing learns from outcomes. Scores decay so old model performance does not dominate after model upgrades.

Provider subscriptions and user-installed CLIs use bring-your-own-account mode. Hosted API mode is optional and separately billed. Interactive-only products may assist a human decision but cannot hold an unattended scheduler lease.

## 10. Evidence scout and human-quality judgment

Before a subjective product, design, technology, or model-routing decision, an
evidence scout constructs an `EvidencePack`. Grok is the preferred scout when X
search is available because it can search public conversation and code-oriented
sources; GitHub search and product/reference crawlers remain independent tools.
The scout never makes the final decision alone.

Evidence sources include:

- GitHub repositories, releases, issues, forks, stars, dependency use, license,
  security posture, maintenance, and reproducible demos;
- X posts, threads, replies, views, likes, reposts, and especially bookmarks,
  with timestamp and author provenance;
- shipped products, store ratings, case studies, conversion or retention data,
  performance traces, accessibility audits, and user tests;
- reference galleries such as motionsites.ai when an actual shipped result and
  source provenance can be inspected;
- internal GUILDLESS outcomes: acceptance rate, defect escapes, cost, latency,
  visual-review verdicts, and owner overrides.

Stars, likes, and views are discovery signals, not proof of quality. They can be
old, bought, botted, driven by an author's audience, or unrelated to the exact
task. Ranking weights task fit, demonstrated output quality, reproducibility,
maintenance, adoption, freshness, license, and manipulation risk. Task fit and
demonstrated quality must outweigh raw popularity.

```ts
type EvidenceCandidate = {
  url: string;
  channel: "github" | "x" | "product" | "store" | "benchmark" | "internal";
  capturedAt: string;
  author?: string;
  artifactType: string;
  metrics: Record<string, number>;
  taskFit: number;
  demonstratedQuality: number;
  reproducibility: number;
  maintenance: number;
  license?: string;
  manipulationRisk: number;
};
```

A decision is evidence-ready only when it has at least three usable references,
at least two independent channels, one reproducible implementation or procedure,
and one demonstrated high-quality result. Direct reuse additionally requires a
compatible license. Screenshots and quoted posts are stored with capture time so
later edits or deletions do not silently rewrite the decision history.

### 10.1 Judgment roles

```text
Scout (Grok/search tools)
  -> collects candidates and counterexamples
Analyst (Kimi or low-cost independent model)
  -> normalizes evidence, detects hype and missing proof
Director (best available reasoning/vision model)
  -> proposes a decision against the product contract
Critic (different provider)
  -> attacks usability, originality, feasibility, and accessibility
Verifier (deterministic tools + real user/owner evidence)
  -> measures the built result
```

Kimi may judge routine choices only after calibration against owner decisions.
Its score is tracked by agreement, later owner reversals, user outcomes, defects,
and business metrics. Agreement with another model is not human-equivalent taste.
When confidence or calibration is insufficient, the owner receives two or three
concrete rendered alternatives rather than an abstract question.

### 10.2 Artifact-level routing

Routing happens at artifact level, not project level:

- GPT Image produces original imagery, button art, textures, icons, or visual
  variants when raster generation is useful;
- Claude/Fable or another measured coding engine implements the product;
- Kimi handles economical monitoring, triage, maintenance, and calibrated
  evidence analysis;
- Seedance or Kling produces video backgrounds, cinematic sequences, trailers,
  or reference-driven motion clips;
- Motion, GSAP, native iOS animation, or CSS implements interactive UI motion;
- deterministic tools measure bundle size, frame rate, contrast, accessibility,
  tests, and conversion events.

Using Seedance for a button press or encoding interactive text inside a video is
a routing error. Using CSS animation for a cinematic generated background may be
an equally bad routing error. The output contract decides.

### 10.3 Example: premium landing page

For a prompt such as the attached Wintage specification, the system must:

1. extract the business goal, audience, conversion event, performance budget,
   accessibility contract, and originality constraints before visual details;
2. inspect the named reference and find separately validated alternatives;
3. check every supplied media URL, license, availability, and mobile cost;
4. search X for recent demonstrated motion/video workflows and failure reports;
5. search GitHub for maintained, licensed implementations and inspect issues;
6. assign generated background video to Seedance/Kling only when video is part of
   the concept; assign interactive motion to a UI animation runtime;
7. generate original visual assets rather than tracing the reference;
8. have one engine implement and another critique the rendered result;
9. verify real screenshots, reduced motion, touch behavior, Web Vitals, contrast,
   keyboard use, and CTA analytics;
10. retain the EvidencePack and explain why each reference or engine was chosen.

The output target is not “looks close to the prompt.” It is a usable, original,
measured product that a human audience demonstrably prefers.

## 11. Worker protocol

Workers never receive the entire organization transcript. They receive a bounded work packet:

```ts
type WorkPacket = {
  missionSummary: string;
  workItem: WorkItem;
  inputManifest: ArtifactRef[];
  repositoryState: { baseCommit: string; branch: string };
  relevantDecisions: Decision[];
  constraints: string[];
  toolGrants: CapabilityGrant[];
  outputSchema: object;
  checkpointIntervalSeconds: number;
};
```

The required worker response is structured:

```ts
type WorkSubmission = {
  summary: string;
  artifactManifest: ArtifactRef[];
  evidenceManifest: EvidenceRef[];
  changedAssumptions: string[];
  discoveredRisks: string[];
  proposedGraphChanges: GraphChangeProposal[];
  cost: Money;
  status: "submitted" | "blocked" | "failed";
};
```

Free-form prose may accompany the response but cannot replace the schema.

## 12. Workspace isolation

Every mutating run executes in an isolated workspace derived from an immutable base revision.

Software workspace:

- Git worktree or ephemeral clone;
- task-specific branch;
- dependency cache mounted read-only where possible;
- secret broker, never plaintext secrets in prompts;
- network egress allowlist;
- CPU, memory, time, and disk limits;
- command log and filesystem diff captured.

Game and media workspace:

- project snapshot and engine version pinned;
- deterministic import settings where supported;
- asset source, model, prompt digest, seed, license, and transformations recorded;
- preview rendering separated from release rendering;
- large artifacts stored outside Git with content-addressed references.

No worker writes directly to the integration branch or production environment.

## 13. Review and verification

### 13.1 Separation rules

- specification, test authorship, implementation, review, fixing, and final verification are distinct roles;
- reviewer provider must differ from producer provider for medium or higher risk;
- reviewer session and delegation ancestry must not overlap the producer;
- deterministic verification runs outside model control;
- critical work requires two independent review verdicts or one review plus a domain-specific deterministic gate;
- fixes invalidate affected evidence and return to review.

### 13.2 Review contract

A reviewer must output findings with severity, location, violated criterion, evidence, and proposed verification. Vague approval is inconclusive.

```ts
type ReviewVerdict = {
  result: "accept" | "reject" | "inconclusive";
  criteria: { id: string; result: "pass" | "fail"; evidenceRefs: string[] }[];
  findings: Finding[];
  confidence: number;
};
```

### 13.3 Acceptance gate

The gate computes acceptance from policy:

```text
accepted = required_artifacts_present
        AND required_evidence_fresh
        AND deterministic_checks_pass
        AND independent_review_accepts
        AND no_unwaived_blocking_findings
        AND budget_reconciled
        AND provenance_complete
```

Models cannot override this expression. A human may waive a criterion only by creating a signed decision record with scope, reason, and expiry.

### 13.4 Beyond code

UI and visual assets require:

- reference and design-token compliance;
- screenshots at defined devices and states;
- automated accessibility checks;
- visual regression thresholds;
- interaction recordings for gesture and motion work;
- an independent visual critic;
- real-device evidence before release when touch, camera, GPU, or platform behavior matters.

Game work additionally requires performance budgets, deterministic smoke scenes, save compatibility checks, controller/input coverage, content validation, and playtest telemetry.

## 14. Integration

The integrator is a control-plane service, not the implementation agent.

1. Verify every candidate artifact against its recorded base.
2. Order changes by declared dependency and ownership.
3. Rebase in disposable integration workspace.
4. Resolve trivial mechanical conflicts only.
5. Convert semantic conflicts into new work items.
6. Run the full integration contract.
7. Produce a signed integration artifact and release candidate.
8. Preserve rollback target and migration compatibility evidence.

Direct model-authored merges to the protected branch are prohibited.

## 15. Authority model

Authority is expressed as capability grants:

```ts
type CapabilityGrant = {
  subjectRunId: string;
  capability: string;
  resourcePattern: string;
  actions: string[];
  environment: "sandbox" | "staging" | "production";
  maximumSpend?: Money;
  expiresAt: string;
  issuedBy: "policy" | "human";
};
```

Default autonomy levels:

| Level | Allowed |
| --- | --- |
| A0 Observe | Read and propose only |
| A1 Sandbox | Create artifacts and run tests in isolation |
| A2 Integrate | Open PRs and create release candidates |
| A3 Staging | Deploy to staging and run synthetic checks |
| A4 Production | Bounded reversible production actions |
| A5 Irreversible | Always requires explicit human grant |

Payments, public publishing, legal acceptance, credential changes, destructive data operations, and irreversible migrations never inherit authority from a broad mission instruction.

## 16. Budget control

Budgeting operates at mission, horizon, work item, run, provider, and external-service levels.

Before a run:

1. estimate a range;
2. reserve the upper bound or policy-defined percentile;
3. reject scheduling if the reservation breaks a hard limit;
4. stream observed spend where the provider supports it;
5. stop safely at the run ceiling;
6. reconcile actual spend and release unused reservation.

The system reports cost per accepted artifact and cost per escaped defect, not just tokens. Retry storms trigger a circuit breaker. The planner must propose scope reduction or a cheaper strategy before asking for more money.

## 17. Durable execution and event ledger

The source of truth is an append-only event stream plus rebuildable projections.

Minimum events:

- `MissionCreated`, `MissionPolicyChanged`, `MissionPaused`;
- `GraphProposed`, `GraphValidated`, `GraphActivated`;
- `WorkBecameReady`, `RunLeased`, `RunHeartbeat`, `RunSubmitted`, `RunFailed`;
- `ArtifactRegistered`, `EvidenceRecorded`, `ReviewRecorded`;
- `WorkAccepted`, `WorkRejected`, `WorkSuperseded`;
- `BudgetReserved`, `BudgetReconciled`, `BudgetDenied`;
- `DecisionRequested`, `DecisionRecorded`;
- `IntegrationStarted`, `ReleaseCandidateCreated`, `ReleaseApproved`;
- `DeploymentRecorded`, `IncidentOpened`, `RollbackRecorded`.

Each event contains sequence number, aggregate version, actor, correlation ID, causation ID, timestamp, payload version, and payload. Consumers must tolerate duplicate delivery. Projection rebuild from event zero is a required disaster-recovery test.

Checkpoints store worker-continuation data but never replace events. A checkpoint includes repository revision, pending tool call, partial artifact manifest, spend, and a provider-neutral summary so another engine can resume.

## 18. Failure handling

| Failure | Automatic response | Escalation condition |
| --- | --- | --- |
| Provider unavailable | Route to eligible alternative | No compliant engine exists |
| Worker timeout | Preserve workspace, resume or retry | Attempts exhausted |
| Context overflow | Compact to artifact-backed packet | Required context cannot be represented |
| Tests fail | Create bounded fix work | Repeated failure or requirement conflict |
| Reviews disagree | Third critic or deterministic experiment | Product judgment remains |
| Merge conflict | Mechanical retry, then conflict task | Semantic decision required |
| Budget near limit | Stop new leases, replan scope | More funds or deadline change required |
| Bad production signal | Freeze releases, rollback, open incident | Rollback unsafe or unavailable |
| Compromised credential | Revoke grants and rotate through broker | Human authority required |
| Corrupt projection | Rebuild from ledger | Ledger integrity fails |

Retries must change something: engine, context, decomposition, tool, or hypothesis. Blindly replaying the same failed prompt is prohibited.

## 19. Operations loop

After release, telemetry is normalized into signals:

- availability, latency, errors, saturation;
- crash and performance data;
- security events;
- user behavior and funnel metrics;
- support requests and sentiment;
- infrastructure and model spend;
- store reviews and release health.

Rules convert signals into incidents, maintenance items, experiments, or growth missions. An operational work item goes through the same production contracts as feature work. Emergency rollback may be automatic only when it is pre-authorized, reversible, and supported by a deterministic trigger.

The system maintains runbooks as versioned artifacts. Every incident must update or validate a runbook and record detection time, mitigation time, owner interruption, and recurrence prevention.

## 20. Memory and organizational learning

GUILDLESS stores four different forms of memory:

1. **Facts**: repository structure, APIs, schemas, environments, and constraints.
2. **Decisions**: selected options and rationale with supersession links.
3. **Procedures**: verified runbooks and task templates.
4. **Performance**: engine outcomes by task type, cost, latency, defects, and reviewer calibration.

Unverified model prose is not promoted to organizational memory. Facts require a source. Procedures require successful evidence. Decisions are immutable and may only be superseded. Performance data is time-decayed and segmented by model version.

## 21. Human attention design

The owner inbox contains only:

- product choices with materially different user or business outcomes;
- authorization requests outside current grants;
- policy, budget, or deadline conflicts;
- unresolved high-risk uncertainty;
- incident decisions without a safe runbook.

Every request must include the decision deadline, recommended option, alternatives, evidence, cost of delay, default safe action, and whether it blocks the critical path. Notification volume and owner minutes are tracked as system defects.

### 21.1 Voice directive layer

Voice is the primary capture interface for owner intent, but a transcript is not
an executable mission. The voice layer is an intent compiler with an explicit
commit boundary.

```text
Microphone
  -> local voice activity detection
  -> streaming draft transcript
  -> finalized transcript + immutable audio artifact
  -> intent segmentation
  -> facts / assumptions / goals / constraints / decisions / open questions
  -> contradiction and high-value entity check
  -> mission preview spoken and displayed back to the owner
  -> explicit owner commit
  -> MissionCreated event
```

Required properties:

- the owner may ramble, revise, interrupt, or say “forget that”; the compiler
  preserves chronology and emits the final intended state;
- partial transcripts are never executable and may be revised visually as
  recognition improves;
- the original audio, final transcript, transcription engine/version, language,
  timestamps, and content digest remain attached to the decision provenance;
- dates, amounts, percentages, names, environments, publishing targets, and
  destructive verbs are extracted as high-value entities and read back;
- ambiguous references such as “that”, “next week”, or “make it cheaper” are
  resolved against a visible candidate or turned into one focused question;
- the compiler distinguishes an idea, a hypothesis, a preference, a hard
  constraint, and an authorization;
- speaking an idea does not grant production, payment, publication, credential,
  or deletion authority;
- voice identity may improve convenience but cannot be the only authorization
  factor for irreversible actions;
- every committed interpretation is editable and reversible before work begins;
- language switching and Japanese/English product vocabulary are evaluated with
  real owner speech, background noise, numbers, and proper nouns.

Recommended transcription routing:

1. Run voice activity detection and a streaming recognizer on device when
   available, preserving privacy and keeping first feedback immediate.
2. Use a higher-accuracy local or hosted second pass after the utterance closes.
3. Compare high-value entities between passes. A disagreement blocks automatic
   commit and highlights only the uncertain fields.
4. Use the control plane's model router for intent compilation; do not couple
   mission semantics to the transcription provider.
5. Retain a text input and transcript editor as equal-authority fallbacks.

The interaction target is not a conversational assistant that keeps talking.
It is a quiet chief of staff: listen, structure, expose consequential ambiguity,
read back the intended company action, and then execute after one clear commit.

## 22. Storage and services

Bootstrap deployment may be a modular monolith, but boundaries are explicit:

- PostgreSQL: missions, graph versions, projections, budgets, policies, decisions;
- append-only event table: transactional outbox and durable history;
- object store: artifacts, logs, screenshots, binaries, checkpoints;
- queue: ready work and verification jobs;
- worker supervisor: isolated process/container execution;
- secret broker: short-lived credentials and audit;
- Git provider adapter: branches, commits, PRs, checks;
- telemetry adapter: production signals;
- model adapters: provider-neutral structured invocation.

SQLite is acceptable for a local single-machine prototype. It is not the target for horizontally scheduled production workers.

## 23. API surface

Minimum commands or endpoints:

```text
POST /missions
POST /missions/:id/compile
GET  /missions/:id
GET  /missions/:id/graph?version=n
POST /missions/:id/pause
POST /missions/:id/resume
GET  /missions/:id/decisions
POST /decisions/:id/resolve
GET  /work-items/:id
POST /work-items/:id/retry
GET  /runs/:id
GET  /artifacts/:id
GET  /evidence/:id
GET  /budgets/:missionId
POST /releases/:id/approve
POST /webhooks/git
POST /webhooks/telemetry
```

All mutations require idempotency keys. Reads expose provenance and current projection sequence so clients can detect stale state.

## 24. Security baseline

- deny tools and networks by default;
- short-lived scoped credentials from a broker;
- prompt-injection boundaries around external content;
- sanitize secrets from prompts, logs, and artifacts;
- signed artifact digests and immutable audit events;
- dependency and license scanning;
- sandbox untrusted builds and generated code;
- require approval for permission expansion;
- protect control-plane policy from worker modification;
- test cross-tenant and cross-mission isolation;
- retain a kill switch that stops leases and revokes active grants.

External pages, issues, emails, assets, and repository content are data, not instructions. A worker cannot expand its tool grants based on text found in those sources.

## 25. Observability and service objectives

Control-plane metrics:

- ready-to-lease latency;
- run success and timeout rate;
- acceptance rate by engine and task kind;
- review disagreement rate;
- escaped defect and rollback rate;
- stale-evidence rejection count;
- cost per accepted artifact;
- critical-path delay;
- owner decisions and owner minutes per day;
- recovery time by failure class;
- event projection lag.

Initial service objectives:

- no acknowledged event loss;
- 99.9% of leases recoverable after supervisor restart;
- budget overrun of zero beyond explicitly configured tolerance;
- complete provenance for every release artifact;
- median ready-to-lease under 10 seconds locally;
- safe pause of new work within 30 seconds.

## 26. Implementation sequence

### Milestone 0: Replace the toy planner

Deliver:

- SQLite event ledger and projections;
- schemas for mission, graph, work item, run, artifact, evidence, decision, grant, and budget;
- graph validator with cycle, dependency, budget, and acceptance checks;
- command-line mission creation, compile, status, pause, resume, and decision resolution;
- migration path to PostgreSQL.

Exit test: kill the process during every state transition, restart it, rebuild projections, and obtain the same valid mission state.

### Milestone 1: One verified vertical slice

Deliver:

- isolated Git worktrees;
- Codex, Claude, and Kimi headless adapters behind one protocol;
- test-author, implementer, reviewer, fixer, verifier separation;
- structured submissions and artifact digests;
- deterministic local build and test evidence;
- PR creation without direct merge.

Exit test: submit a repository issue; receive a PR that passes tests, independent review, provenance, and rollback requirements with no manual coordination.

### Milestone 2: Durable parallel production

Deliver:

- leases, heartbeats, checkpoints, retries, and circuit breakers;
- conflict-domain scheduling;
- graph change proposals;
- cost reservations and provider quotas;
- crash and provider-outage recovery.

Exit test: run 20 dependent tasks, kill half the workers, disable one provider, restart the control plane, and finish without duplicate accepted work or lost state.

### Milestone 3: Integration and release

Deliver:

- protected integration service;
- full-suite and security evidence;
- release candidates, staging deployment, rollback rehearsal;
- approval gateway and signed waivers.

Exit test: ship to staging, inject a regression, block release, fix it through a different producer/reviewer chain, then release and roll back reproducibly.

### Milestone 4: Operations

Deliver:

- telemetry ingestion;
- incident generation and runbooks;
- safe automated rollback;
- maintenance and dependency-update missions;
- owner-attention measurements.

Exit test: inject five defined production failures and meet the recovery objective without shell access by the owner.

### Milestone 5: Games and multimodal production

Deliver:

- asset provenance and license manifests;
- image, video, audio, UI, and 3D adapters;
- game-engine batch build and smoke scenes;
- performance, save-compatibility, input, and visual gates;
- playtest telemetry feeding graph changes.

Exit test: produce and operate one small commercial-quality vertical slice. Only after this passes should scope expand toward the 90-day large-project benchmark.

## 27. Required test matrix

Every control-plane release must test:

- duplicate commands and events;
- out-of-order event delivery;
- process death before and after event commit;
- expired and duplicated leases;
- stale artifact and evidence digests;
- graph cycles and missing dependencies;
- provider outage and quota exhaustion;
- malicious tool-expansion request in external content;
- producer/reviewer identity laundering through delegation;
- budget reservation races;
- concurrent repository conflicts;
- reviewer disagreement;
- rollback failure;
- projection rebuild;
- pause and kill-switch latency.

## 28. Go/no-go gates

Do not add broad UI or more provider logos until the corresponding gate is satisfied.

1. **Durability gate**: state survives forced termination.
2. **Evidence gate**: no task completes without fresh evidence.
3. **Independence gate**: identity ancestry prevents self-approval.
4. **Recovery gate**: worker and provider failures recover automatically.
5. **Budget gate**: concurrent runs cannot overspend the hard ceiling.
6. **Integration gate**: only the integration service can create a release candidate.
7. **Operations gate**: production telemetry can create and close verified repair work.
8. **Scale gate**: the 90-day benchmark meets owner-attention and reliability targets.

The mobile application is a client of this control plane. It is not evidence that the system exists.
