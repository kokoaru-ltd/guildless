# GUILDLESS Agent & Skill Intelligence

Updated: 2026-07-23

## Honest current-state assessment

The current UI is an interactive product prototype, not yet a complete autonomous
company. Navigation, model selection, connector state, local sign-in state,
execution evidence views, settings, and preview transitions work. Real provider
OAuth, durable execution, remote sandboxes, billing, crash recovery, and production
release authority still require backend implementation.

## The product thesis

GUILDLESS is not another model picker or general-purpose chat agent.

It turns one founder's outcome into a governed production system:

1. Discover the required capabilities.
2. Find candidate Skills, MCP servers, models, and existing software.
3. Score them for task fit, quality, security, license, recency, cost, and evidence.
4. Assemble a temporary company for the mission.
5. Separate planning, implementation, review, and release authority.
6. Reject weak work and automatically repair or re-plan it.
7. Preserve every artifact, decision, test, and model handoff.
8. Continue operating the released product.

The durable advantage is the selection and governance layer, not access to models.

## Why switching agents matters

Switching is valuable only when it changes the outcome. Each route must be justified
by an observable capability, price, latency, tool access, context requirement, or
independence requirement.

| Stage | Default role | Why a different agent helps | Required evidence |
|---|---|---|---|
| Product definition | Kimi / long-context model | Cheap synthesis across large research and product context | cited brief, acceptance tests |
| Live research | Grok + browser/research agent | current X/web discovery and market signals | URLs, dates, engagement, source class |
| Architecture | Codex / strongest reasoning model | repository-wide constraints and implementation plan | ADR, dependency graph, risks |
| Implementation | Claude/Codex selected by benchmark | code generation and repository operation | patch, build, tests |
| Visual production | image/video/3D specialist | general LLMs should not fabricate media capability | generated asset, provenance, license |
| Independent review | a model that did not implement | reduces self-approval and correlated mistakes | rejection reasons, rubric score |
| Operations | low-cost reliable model + deterministic monitors | frequent repetitive work should not consume frontier-model budget | SLO, incident trail, escalation |

Manual switching is an escape hatch. Auto-routing is the main product and must show
the reason, expected cost, permissions, and fallback for every assignment.

## Sources worth integrating

### Orchestration and durable execution

- LangGraph: durable execution, state, human interruption, memory, tracing, and
  long-running workflows. Use as a reference or runtime candidate for resumable
  mission graphs. https://github.com/langchain-ai/langgraph
- OpenHands: mature software-agent runtime, sandboxing, repository execution,
  extension registry, and trajectory visualization. Use adapters instead of
  rebuilding every coding-agent primitive. https://github.com/OpenHands/OpenHands
- SWE-agent / mini-SWE-agent: small, benchmark-oriented coding loops and
  configurable tools. Use for isolated issue-solving workers and evaluation
  baselines. https://github.com/SWE-agent/SWE-agent

### Browser and computer use

- BrowserOS: local Chromium-based agent browser, provider portability, CLI/MCP,
  and many browser tools. License must be reviewed before product embedding.
  https://github.com/browseros-ai/BrowserOS
- browser-use: browser-agent runtime plus a public benchmark. Use the benchmark
  shape and recovery-loop ideas, not marketing claims. https://github.com/browser-use/browser-use
- open-computer-use implementations: candidates for desktop control through MCP.
  They require security review, sandboxing, and OS-specific validation before use.

### Skills and capability supply

- Hugging Face Skills: cross-agent skills for Hub search, models, datasets, Spaces,
  and compute. First candidate is `hf-cli`, loaded only for relevant missions.
  https://github.com/huggingface/skills
- Microsoft Skills: large catalog with an acceptance-criteria test harness. Its
  most important lesson is selective loading: indiscriminate skill loading causes
  context rot. https://github.com/microsoft/skills
- NVIDIA Skills: official, vendor-verified skills with agent-targeted installation.
  Prefer verified vendor skills for specialized GPU workflows.
  https://github.com/NVIDIA/skills
- MCP Apps: official interactive UI protocol for tools embedded in agent clients.
  https://github.com/modelcontextprotocol/ext-apps

## Skill procurement gate

No discovered skill may run immediately. A Skill Registry must record:

- source repository and immutable commit
- publisher identity and repository age
- stars/forks as weak social signals, never quality proof
- last release and maintenance activity
- license compatibility
- requested files, commands, network hosts, secrets, and write permissions
- prompt-injection and exfiltration scan
- deterministic acceptance criteria
- isolated trial result
- task-specific quality score
- rollback path

Only the minimum relevant skills are mounted into a worker. Skills never receive
all workspace secrets by default.

## Quality system: the actual Manus differentiation

Manus-class execution is the baseline. GUILDLESS must add:

1. **Capability procurement** — discovers and tests Skills/MCP/OSS before planning.
2. **Conflict-of-interest control** — the builder cannot approve its own work.
3. **Evidence contracts** — every deliverable defines proof before execution.
4. **Model portfolio routing** — route by measured task performance, cost, latency,
   availability, and independence rather than brand.
5. **Adversarial release gates** — red-team tests, visual comparison, security scan,
   performance budget, and rollback check.
6. **Durable operations** — scheduled health checks, incidents, repairs, dependency
   updates, marketing experiments, and cost controls continue after release.
7. **Organizational memory** — reusable decisions, failures, rubrics, assets, and
   customer evidence; not a raw chat transcript.

## Required UI changes

The interface must expose truth instead of decorative activity:

- Mission contract: outcome, constraints, budget, deadline, release evidence.
- Procurement: candidate Skills/MCP/OSS and why each was accepted or rejected.
- Company graph: stages, assigned agent, reason, permissions, fallback, cost.
- Live trajectory: actions and artifacts, not hidden chain-of-thought.
- Review gate: rubric, failures, owner, repair loop, and release authority.
- Operations: deployed version, SLO, incidents, spend, experiments, and next action.
- Benchmark card: compare route A/B on the same task before changing defaults.

## Implementation order

### P0 — prove one real vertical slice

Voice request → research → skill procurement → architecture → implementation in a
sandbox → independent review → visual/browser QA → GitHub artifact → resumable run.

### P1 — production reliability

Durable event store, retries, idempotency, permission broker, provider OAuth/BYOK,
cost limits, cancellation, crash recovery, and audit export.

### P2 — quality learning

Mission rubrics, benchmark datasets, route experiments, failure taxonomy, model and
skill scorecards, and organization memory.

### P3 — autonomous operations

Deployment monitors, incident response, dependency maintenance, analytics,
marketing experiments, customer feedback synthesis, and scheduled re-planning.

## Non-negotiable acceptance test

GUILDLESS is not complete when the UI says “passed.” It is complete when a clean
machine can replay a mission from its contract and event ledger, reproduce the
artifacts, verify the tests and visual output, inspect all external permissions,
resume after a forced crash, and prove that the final reviewer was independent
from the implementer.
