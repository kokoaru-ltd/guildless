# Architecture

GUILDLESS separates production policy from model providers so the system improves when the model market improves.

The implementation-level control-plane contract is defined in
[control-plane-spec.md](./control-plane-spec.md). This short document is only
the architectural summary.

## Control loop

1. **Mission compiler** converts an owner directive into milestones, dependency graphs, budgets, and acceptance tests.
2. **Studio scheduler** leases ready tasks to isolated workers and enforces concurrency and spend limits.
3. **Capability router** selects engines by measured quality, cost, latency, privacy, and availability.
4. **Workers** execute in isolated repositories, game projects, media workspaces, or browser environments.
5. **Critics** review outputs independently from the producing worker.
6. **Verification** runs deterministic tests, builds, simulations, and visual checks.
7. **Integrator** merges verified artifacts and produces a releasable build.
8. **Approval gateway** pauses irreversible, expensive, or product-defining decisions for the owner.
9. **Operations loop** watches production and creates repair or growth missions from real telemetry.

## Non-negotiable properties

- Every task has machine-checkable acceptance criteria where possible.
- Generated code and assets retain provenance.
- No worker can deploy, delete data, or exceed policy limits without an explicit capability grant.
- Model-provider outages do not destroy mission state.
- Outputs must remain editable by standard tools and transferable to human teams.
- Cost and quality are measured per completed artifact, not per token.

## First benchmark

One operator ships and operates a production-grade game or SaaS product over 90 days with:

- at least 100,000 lines of maintained source or an equivalent multi-asset game project
- daily reproducible builds
- automated regression coverage
- recovery from intentionally injected failures
- less than one hour of mandatory operator intervention per day
- a declared monthly compute budget that cannot be silently exceeded
