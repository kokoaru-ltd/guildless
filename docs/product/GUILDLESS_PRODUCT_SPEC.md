# GUILDLESS Product Specification

Version: 0.3
Status: implementation contract
Last updated: 2026-07-26

## 1. Product definition

GUILDLESS is an operating system for a one-person digital company.

The owner states an outcome. GUILDLESS discovers the expertise, evidence, models,
skills, tools, and permissions required; forms a temporary AI organization; plans
and executes the work; independently reviews it; releases only with evidence; and
continues operating the result.

It is not:

- a multi-model chat interface;
- a prompt library;
- a fixed workflow builder;
- a collection of role-playing personas;
- a claim that current AI can replace every human judgment without measurement.

The product promise is:

> One owner defines intent and exceptional decisions. A governed AI organization
> performs the repeatable digital work with professional evidence.

## 2. Target users

### Primary

- solo founder building and operating a software company;
- owner of an existing small business needing digital production;
- creative director producing games, media, campaigns, or digital products;
- technical operator replacing fragmented agencies and contractors.

### Secondary

- small product team wanting autonomous execution with auditability;
- enterprise innovation team testing AI labor substitution safely;
- agency converting its own SOPs into reusable Expert Packs.

## 3. Jobs to be done

1. “I explain what I want once; assemble the right professionals.”
2. “Use the best model or tool for each artifact without making me manage them.”
3. “Match professional design, engineering, security, and growth standards.”
4. “Show why decisions were made and what evidence supports them.”
5. “Reject weak work before it reaches users.”
6. “Continue maintenance, customer response, marketing, and improvement.”
7. “Recover from provider limits, failures, and model changes.”

## 4. Product principles

### 4.1 Outcomes over prompts

The unit of work is a Mission Contract, not a message.

### 4.2 Expertise over personas

An expert is defined by evidence sources, decision rules, tools, rubrics,
permissions, failure patterns, and acceptance authority—not a system prompt saying
“act as a professional.”

### 4.3 Artifacts over activity

Progress is measured by inspectable outputs, executable tests, deployed previews,
and verified business metrics. Token streams and animated status messages are not
proof.

### 4.4 Separation of duties

The provider that implements an artifact cannot be its final reviewer. Security,
financial, destructive, and production decisions have explicit authority.

### 4.5 Fail closed

Missing evidence, missing rollback, unknown license, unscoped permissions, or an
unresolved blocking objection prevents release.

### 4.6 Models are replaceable

Roles and quality contracts are durable. Model assignments change with measured
performance, price, latency, availability, and independence.

## 5. Core objects

### 5.1 Mission Contract

| Field | Description |
| --- | --- |
| objective | user-visible business outcome |
| audience | customer or operator receiving the result |
| success metrics | measurable definition of success |
| scope | required and explicitly excluded work |
| budget | monetary, model, compute, and time limits |
| deadline | target and hard cutoff |
| references | approved examples and anti-examples |
| constraints | brand, legal, technical, platform, accessibility |
| authority | actions AI can execute and actions requiring owner approval |
| release evidence | tests and proof required before release |
| rollback | recovery requirements |

### 5.2 Expert Pack

| Field | Description |
| --- | --- |
| profession | e.g. Staff Engineer, Conversion Designer |
| industry | domain specialization |
| sources | verified knowledge and current evidence |
| decision rules | conditional professional judgments |
| rubric | scored acceptance criteria |
| tools | skills, MCP servers, software, models |
| permissions | maximum allowed authority |
| anti-patterns | known failures and prohibited shortcuts |
| escalation | when another expert or owner is required |
| freshness | review and expiration schedule |
| benchmark history | measured outcomes from prior missions |

### 5.3 Evidence Item

- immutable source URL and captured date;
- source class: primary, benchmark, implementation, issue, review, community;
- publisher and conflict-of-interest status;
- task fit;
- demonstrated quality;
- reproducibility;
- maintenance;
- adoption;
- freshness;
- manipulation risk;
- license and allowed use;
- supporting or opposing claim.

### 5.4 Artifact

- type and owner;
- source files;
- version and checksum;
- generated-media provenance;
- dependencies and licenses;
- preview;
- tests;
- expert reviews;
- release state;
- rollback target.

### 5.5 Mission Event

Every state change is append-only:

- event ID and timestamp;
- mission and stage;
- actor, model, provider, session;
- input artifact references;
- action and tool permissions;
- output artifact references;
- cost and latency;
- evidence;
- error and retry;
- approval or rejection.

## 6. Mission lifecycle

### Stage 0 — Intent capture

Voice or text input. GUILDLESS asks only questions that materially change scope,
cost, permissions, or quality. It generates a draft Mission Contract.

### Stage 1 — Evidence discovery

Search primary sources, GitHub, issue trackers, benchmarks, public reviews, X when
available, academic research, product galleries, and industry-specific sources.
Contradictory evidence is preserved.

### Stage 2 — Capability procurement

Discover candidate models, Skills, MCP servers, APIs, libraries, templates, and
existing products. Score and sandbox them before use. Popularity is a weak signal,
not proof.

### Stage 3 — Expert formation

Select the minimum necessary professional council. Assign a Responsible expert,
Accountable release authority, Consulted reviewers, and Informed operator.

### Stage 4 — Planning

Create a dependency graph with artifact contracts, costs, permissions, fallbacks,
and evidence gates. The plan is resumable and idempotent.

### Stage 5 — Execution

Workers operate in scoped sandboxes. Each stage emits artifacts and events.
Failures trigger bounded retry, model fallback, plan repair, or owner escalation.

### Stage 6 — Independent review

Different providers inspect the complete artifact using profession-specific rubrics.
Reviewers can approve, request revision, or block. Blocking findings cannot be
silently overridden by the implementer.

### Stage 7 — Release

The release gate verifies:

- build success;
- deterministic tests;
- design and accessibility review;
- security review;
- license and provenance;
- cost budget;
- rollback;
- required owner approval;
- no unresolved blockers.

### Stage 8 — Operations

Monitor reliability, security, cost, user behavior, conversion, reviews, and market
signals. Generate repairs and experiments through the same governed lifecycle.

## 7. Expert formation examples

### Conversion website

- Industry Strategist
- UX Researcher
- Conversion Director
- Brand Designer
- Product Designer
- Design Engineer
- Frontend Engineer
- Accessibility Reviewer
- Security Reviewer
- Growth Operator

### SaaS application

- Product Manager
- Domain Expert
- Staff Architect
- Backend Engineer
- Frontend Engineer
- Data Engineer
- Security Engineer
- SRE
- QA Engineer
- Product Designer
- Customer Success Operator

### Game

- Creative Director
- Game Designer
- Technical Director
- Gameplay Engineer
- UI/UX Designer
- 2D/3D Art Director
- Audio Director
- QA and Balance Analyst
- Store and Growth Operator

## 8. Model routing

Routing inputs:

- artifact type;
- benchmark history for the exact task class;
- tool and modality requirements;
- context size;
- cost and latency budget;
- provider availability and limits;
- security and data residency;
- reviewer independence;
- historical human correction rate.

Routing outputs:

- chosen model and provider;
- assignment reason;
- expected cost and time;
- required permissions;
- fallback;
- reviewer;
- confidence.

Manual selection is an override. Auto Company is the default.

## 9. Evidence Engine

### Scoring dimensions

- task fit: 30%;
- demonstrated quality: 25%;
- reproducibility: 15%;
- maintenance: 10%;
- adoption: 10%;
- freshness: 10%;
- manipulation penalty: up to −25%.

Weights are configurable by mission type. Security and legal evidence can use
hard gates instead of averages.

### Evidence rules

- minimum three usable references;
- minimum two independent channels;
- at least one reproducible reference;
- at least one demonstrated-quality reference;
- direct reuse requires a compatible license;
- community reviews require deduplication and manipulation checks;
- absence of contrary evidence is not proof of quality.

## 10. Quality system

### Design

- hierarchy, typography, spacing, brand fit;
- information scent and primary-action clarity;
- responsive and touch behavior;
- accessibility;
- visual regression;
- task-specific conversion or usability test.

### Engineering

- architecture and typed boundaries;
- readability and maintainability;
- unit, integration, end-to-end, adversarial tests;
- performance budget;
- observability;
- failure recovery and rollback;
- dependency and secret scanning;
- least privilege.

### Marketing

- audience and positioning;
- evidence and claim substantiation;
- platform-native creative;
- hook and action clarity;
- reputation and compliance risk;
- experiment design;
- attributable outcome.

## 11. User experience

The mandatory visual and interaction contract is:

[`../design/CODEX_DESKTOP_UI_CONTRACT.md`](../design/CODEX_DESKTOP_UI_CONTRACT.md)

### Desktop shell

- left: navigation, projects, missions, settings;
- center: contract, trajectory, council, artifacts, composer;
- right: Changes, Evidence, Preview, Files, Activity, MCP.

### Mission creation

1. state outcome;
2. review extracted objective and constraints;
3. connect required capabilities only;
4. approve operating contract;
5. start.

### Required states

- first run;
- empty workspace;
- planning;
- waiting for connection;
- running;
- retrying;
- blocked by evidence;
- waiting for owner;
- review failed;
- release ready;
- released;
- incident;
- offline/provider unavailable.

## 12. Permissions

Permission classes:

1. read local context;
2. write local workspace;
3. execute local commands;
4. external read;
5. external write;
6. financial action;
7. production deployment;
8. destructive action;
9. secret access;
10. identity or communication on behalf of owner.

Permissions are stage-scoped, time-limited, logged, and revocable. Skills never
inherit all workspace secrets.

## 13. Reliability

- append-only SQLite/D1 event ledger;
- deterministic stage IDs;
- idempotency keys for writes;
- bounded retries with exponential backoff;
- checkpoint after every artifact;
- provider fallback without losing mission state;
- cancellation and resume;
- forced-crash replay test;
- artifact checksums;
- rollback verification.

## 14. Security

- treat model output and external Skills as untrusted input;
- sandbox file, network, and command access;
- allowlist external hosts per mission;
- scan prompts and tool descriptions for injection;
- redact secrets from model context and logs;
- no secrets in Git remotes, prompts, screenshots, or artifacts;
- dependency, license, and provenance scan;
- separate production credentials from build workers;
- security blockers require an independent authority to clear.

## 15. Data and privacy

- owner controls retention per workspace;
- local-first mode stores preferences and mission state locally;
- hosted mode encrypts data in transit and at rest;
- model providers receive only minimum required context;
- evidence captures source metadata without copying prohibited content;
- deletion propagates to stored artifacts where technically possible;
- audit export is machine-readable.

## 16. Metrics

### North star

Human Intervention Rate:

`human decisions or corrections / total governed stages`

It must decrease without reducing outcome quality.

### Quality

- first-pass acceptance;
- reviewer disagreement;
- escaped defects;
- visual regression failures;
- security findings;
- human correction minutes;
- reproducibility rate.

### Business

- mission completion;
- time and cost to outcome;
- autonomous operation days;
- conversion or revenue lift;
- cost avoided versus external labor;
- retention by mission type.

## 17. MVP acceptance

A clean machine must be able to:

1. receive a voice or text mission;
2. create a Mission Contract;
3. form an expert council;
4. produce a diverse Evidence Pack;
5. select and explain model assignments;
6. execute implementation in a sandbox;
7. have another provider review it;
8. repair rejected work;
9. run build and browser tests;
10. persist artifacts and event history;
11. survive a forced crash and resume;
12. block release without rollback or required evidence;
13. publish only with authorized approval;
14. begin scheduled operations.

## 18. Current implementation status

### Implemented

- Codex-style desktop shell;
- local preference and onboarding state;
- model and expert routing UI;
- connectors and scoped state;
- mission trajectory;
- Expert Council with blocking opinions;
- Evidence Engine scoring API;
- release-policy primitives;
- SQLite event ledger;
- independent-provider planning tests;
- browser preview and artifact surfaces.

### Partial

- provider adapters;
- model account connection;
- real mission execution from UI;
- evidence collection;
- durable hosted persistence;
- authentication.

### Not implemented

- production OAuth;
- secure secret broker;
- remote sandbox fleet;
- automatic Skill procurement and malware analysis;
- billing;
- scheduled operations;
- real deployment approval workflow;
- customer analytics feedback loop;
- multi-tenant access control.

The UI must label partial and unavailable capabilities honestly.

## 19. Roadmap

### P0 — complete vertical slice

Mission Contract → Evidence → Expert Council → Plan → sandbox execution → independent
review → repair → browser QA → GitHub artifact → resume after forced crash.

### P1 — production foundation

Identity, persistence, secret broker, permissions, remote sandboxes, cost limits,
provider fallbacks, and deployment approval.

### P2 — learning system

Expert Pack registry, model/skill benchmarks, human-correction learning, organization
memory, and route experiments.

### P3 — autonomous company operations

Monitoring, incident repair, dependency maintenance, support, marketing experiments,
review mining, financial controls, and scheduled strategy updates.

## 20. Definition of done

No feature is done because an AI said it is done. It is done only when:

- user-visible behavior works;
- empty, loading, success, error, and recovery states exist;
- accessibility and keyboard behavior pass;
- deterministic tests pass;
- relevant expert rubrics pass;
- evidence and provenance are inspectable;
- security and permission boundaries pass;
- failure and rollback are tested;
- documentation matches the implementation.
