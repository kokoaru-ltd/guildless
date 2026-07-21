# Fugu baseline and GUILDLESS extension

GUILDLESS treats [Sakana Fugu's published orchestration capabilities](https://sakana.ai/fugu/) as a baseline, not as the final product category. This document prevents the project from quietly degrading into a fixed role router.

## Published Fugu capabilities to match

| Capability | GUILDLESS requirement | Status |
| --- | --- | --- |
| Dynamic model selection | Route by measured capability, cost, latency, privacy, and availability | Registry exists; live scoring pending |
| Delegation | Compile work into explicit dependent tasks and assign engines | Initial mission compiler implemented |
| Verification | Use independent model review plus deterministic evidence | Initial policy implemented |
| Synthesis | Integrate verified artifacts into one product state | Pending integrator |
| Recursive orchestration | Allow bounded sub-missions and subagents | Depth policy added; runtime pending |
| Provider opt-out | Exclude providers for privacy, policy, or availability | Implemented in mission planning |
| Cost-performance optimization | Measure cost per accepted artifact, not token price alone | Pending telemetry |
| Learned coordination | Improve routing from historical task outcomes | Pending evaluation store |
| Review ensembles | Obtain independent reviews and resolve disagreement | Pending ensemble runner |
| Long-running work | Persist state across failures, restarts, and provider outages | Pending event store |

## Where GUILDLESS must go beyond Fugu

Fugu is presented as a multi-agent system delivered through a model-compatible API. GUILDLESS must own durable production state and produce operating artifacts:

- Git branches, worktrees, commits, tests, builds, migrations, and rollbacks;
- editable game and media projects with asset provenance;
- least-privilege tool grants, budgets, approvals, and audit logs;
- production telemetry, incident repair, release management, and growth experiments;
- months-long architectural memory that remains usable when every model provider is replaced.

Matching a good answer is insufficient. The acceptance unit is a verified, releasable, maintainable artifact.
