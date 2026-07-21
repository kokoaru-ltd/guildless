# GUILDLESS

**One person. Full studio.**

GUILDLESS is an AI-native production operating system designed to let one human direct work that previously required a full software company or game studio.

The operator defines goals, constraints, taste, budget, and release decisions. GUILDLESS plans the work, chooses the best available model for each task, runs specialized agents in parallel, verifies their output, and escalates only decisions that require human judgment.

## Product thesis

Models are replaceable engines. The durable product is the control plane around them:

- persistent product memory and architectural decisions
- dependency-aware planning across thousands of tasks
- isolated parallel workspaces and safe integration
- automated tests, reviews, playtests, and quality gates
- cost-, latency-, and quality-aware model routing
- human approval for destructive, expensive, or irreversible actions
- continuous release, operations, and growth loops

## Capability routing

| Capability | Preferred engine today | Typical work |
| --- | --- | --- |
| Visual generation | GPT Image | concept art, UI, textures, marketing assets |
| Engineering | Claude / Codex | architecture, implementation, refactoring, review |
| Low-cost operations | Kimi | monitoring, triage, maintenance, research |
| Multimodal context | Gemini | video understanding, large repositories, media workflows |
| Motion generation | Seedance and available video engines | trailers, ads, cinematics, social clips |

These defaults are policy, not hard-coded loyalty. Every engine is replaceable based on benchmark quality, availability, price, privacy, and task constraints.

## Scope

GUILDLESS targets complete production loops:

1. Research and product strategy
2. Specification and architecture
3. Software or game implementation
4. Visual, audio, and video asset production
5. Automated testing and playtesting
6. Infrastructure, release, and operations
7. Store presence, campaigns, content, and analytics
8. Continuous maintenance and improvement

## Current status

This repository contains the initial mission-control prototype and the first platform contracts. It does not yet claim autonomous production. Progress is measured by reproducible solo-production benchmarks, not demo output.

## Local development

```bash
npm install
npm run dev
```

## License

Proprietary during the initial research and product-validation phase.
