# NEON DRIFT — iOS multi-model pilot

## Product

NEON DRIFT is a portrait, one-thumb arcade game built with Expo React Native.
A run lasts 60 real seconds. The player drags an orb to collect shards, build a
combo, and avoid moving mines. Three hits end the run.

## Model handoff used

1. Kimi (`k3-agent`, logged-in desktop runtime) produced the game loop, state
   machine, balance constants, acceptance criteria, and failure modes.
2. Claude Code (logged-in CLI subscription) implemented the Expo application,
   pure game rules, and tests.
3. Codex (logged-in CLI subscription) reviewed without write permission.
4. Claude corrected the first review failures.
5. Codex rejected the second version for two remaining correctness issues.
6. The timer and visual/collision geometry were corrected and Codex returned
   `PASS`.
7. Node, TypeScript, and Expo performed deterministic verification.

Grok was not executed. No Grok CLI or `XAI_API_KEY` is available in the current
machine, so the runtime correctly reports that engine as unavailable instead of
fabricating a result.

## Verification

- Pure rules: 34 Node tests.
- Static compatibility: `tsc --noEmit`.
- Packaging: Expo web export succeeds.
- Independent review: final Codex gate is `PASS`.

## API requirement

An API is not inherently required. Claude, Codex, and Kimi were invoked through
the user's authenticated local subscriptions/runtimes. Automation needs one
headless interface per model: a logged-in CLI, an OAuth-capable MCP connector,
or an API key. Grok currently needs one of those interfaces before it can join
the automated pipeline.

## iOS boundary on Windows

The shared React Native code is iOS-compatible and can run through Expo Go.
Windows cannot run Xcode or the iOS Simulator. A signed App Store `.ipa` still
requires an Apple Developer account and a macOS/Xcode or EAS cloud build step.
Those are distribution constraints, not game-code constraints.

## Acceptance criteria

- Menu, play, pause, resume, game-over, and retry states work.
- Backgrounding pauses the run and excludes background time.
- Foreground frame gaps count fully toward the authoritative 60-second clock;
  physics uses a separately clamped delta.
- Mine and shard spawns guarantee safe distance when the arena permits it.
- Animated solid visuals never extend beyond their collision geometry.
- Score, combo, health, difficulty ramp, haptics, and session best are present.

