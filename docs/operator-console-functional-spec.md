# GUILDLESS Operator Console Functional Specification

Status: implementation-ready contract, version 1.0  
Scope: desktop and responsive web operator console

## 1. Purpose

The Operator Console is the owner-facing client for the GUILDLESS control plane. It captures an outcome, compiles a governed mission, exposes its real execution state, and presents artifacts and evidence without implying that unconfigured or unexecuted model work has occurred.

The console is not a simulated agent dashboard. Every status, count, artifact, and provider label must be derived from persisted control-plane data or explicitly identified as a preview, sample, unavailable capability, or local-only operation.

## 2. Product principles

1. One owner instruction becomes a traceable mission, not an unbounded chat.
2. Navigation changes the working view; no navigation item may be decorative.
3. Japanese and English are first-class, persistent interface languages.
4. A producer cannot review, approve, or verify its own output.
5. Browser-only planning and local execution are visibly different states.
6. “Created,” “ready,” “running,” “reviewed,” and “complete” have distinct meanings.
7. Voice input never bypasses transcript review, policy, or authority gates.
8. Keyboard, screen-reader, reduced-motion, zoom, and touch use are supported.

## 3. Information architecture

The left sidebar contains four primary destinations in this order:

- **Command**: capture, edit, validate, and commit an owner directive.
- **Missions**: browse missions and inspect their work graphs and current state.
- **Evidence**: inspect evidence, artifacts, provenance, and release-gate results.
- **Agents**: inspect registered engines, capabilities, credentials, availability, and role eligibility.

Selecting a destination must update the URL (`/command`, `/missions`, `/evidence`, `/agents`) or an equivalent router state that supports browser Back/Forward, deep links, reload, and focus restoration. The active item must expose `aria-current="page"`.

The sidebar may collapse to an icon rail. Collapse state is persisted locally and must not remove accessible names or tooltips. On narrow screens it becomes an off-canvas drawer, closes after navigation, traps focus while open, and returns focus to its trigger when closed.

Recent missions show at most five real persisted missions ordered by `updatedAt` descending. Selecting one opens its Missions detail view. Empty state copy must say that no missions exist; it must not display fabricated examples unless the application is explicitly in demo mode.

## 4. Language switching

### 4.1 Required behavior

The header or sidebar settings area provides a language control with `日本語` and `English`. Changing it immediately updates all console-owned visible strings, accessible names, validation messages, status labels, dates, number formatting, and voice-recognition locale.

The selected locale is persisted under `guildless.locale` with allowed values `ja` and `en`. Resolution order is:

1. valid persisted value;
2. authenticated user preference, when available;
3. browser language beginning with `ja`;
4. `en` fallback.

The document root `lang` attribute must be `ja` or `en`. Locale switching must not reset unsaved command text, navigation, selected mission, filters, or running voice capture. If recognition cannot change language during an active session, stop safely, preserve the transcript, update the locale, and tell the user to resume.

No user-facing console string may be hard-coded inside view components. Strings live in typed `ja` and `en` dictionaries with identical keys. Mission content and model-produced artifacts are not automatically translated; their source language is shown. Translation, if added later, creates a derived artifact with provenance and never overwrites the source.

### 4.2 Formatting

Use `Intl.DateTimeFormat` and `Intl.NumberFormat` for the active locale. Store timestamps as UTC and data values independent of display language. Do not use locale-formatted strings as identifiers or state values.

## 5. Command view

The Command view contains:

- outcome/directive editor;
- microphone control and voice state;
- optional success criteria, deadline, budget, and constraints fields;
- validation and ambiguity summary;
- mission preview;
- explicit **Create mission** action;
- runtime capability notice.

Typed and dictated text share one editable transcript. Creating a mission requires non-whitespace input and an explicit user action. The action creates a persisted mission in `draft` or `planning`; it does not start external research or model execution unless the runtime is local, execution is configured, policy permits it, and the owner invokes a separately labelled start action.

While submission is pending, disable duplicate submission and use an idempotency key. On success, navigate to the created mission. On failure, preserve all input, show a recoverable error, and keep focus near the failed action.

## 6. Missions view

### 6.1 List

The Missions list displays objective, status, last update, progress based on accepted work items, execution location, and blocking reason when present. It supports status filtering, text search, keyboard selection, and truthful empty/loading/error states.

### 6.2 Detail

Mission detail shows:

- objective, success criteria, constraints, budget, deadline, and policy;
- current mission status and last committed event time;
- versioned work graph;
- work item owner role and assigned engine, if actually assigned;
- dependencies, attempts, artifacts, evidence, and blocking reason;
- available commands such as compile, start, pause, resume, retry, or cancel, gated by state and authority;
- an append-only activity timeline.

The initial separation-of-duties graph may be previewed before execution, but preview nodes must be labelled `planned`. A node becomes `ready`, `running`, or later only from control-plane events.

### 6.3 Mission state machine

Canonical mission states are:

```text
draft -> planning -> running -> release_ready -> operating -> completed
                    |   ^             |
                    v   |             v
                  paused            running
                    |
                    v
                  running

planning|running|paused|release_ready|operating -> blocked
blocked -> planning|running|paused
draft|planning|running|paused|blocked|release_ready -> cancelled
```

Rules:

- `draft`: persisted intent exists; no validated graph is active.
- `planning`: compilation or graph validation is in progress.
- `running`: at least one active graph exists and execution is permitted; it does not imply a worker is currently running.
- `paused`: no new leases may start; current run handling follows policy.
- `blocked`: progress requires a decision, configuration, budget, authority, or recovery action; a structured reason is required.
- `release_ready`: all required fresh evidence passed and the release gate accepted the candidate.
- `operating`: a release is deployed and monitored.
- `completed`: success contract is satisfied and terminal closeout is recorded.
- `cancelled`: terminal cancellation is recorded; history remains available.

Only the control plane may commit transitions. The UI sends commands, renders pending intent separately, and reconciles from the returned event/projection sequence. Invalid transitions are disabled and rejected server-side. Reloading the page must reproduce the same state.

Work items use `blocked`, `ready`, `running`, `review`, `done`, and `failed` in the current production contract. `done` means its acceptance contract passed; it must not be inferred from a model response alone.

## 7. Evidence view

The Evidence view lists persisted evidence and artifacts, filterable by mission, work item, type, result, freshness, and producer. Each evidence record shows:

- type and pass/fail/inconclusive result;
- producing runner, provider, model/version where applicable;
- input and artifact digests;
- creation time and freshness;
- linked logs or artifacts;
- associated acceptance criterion;
- independent reviewer identity and provider where applicable.

Stale evidence is visibly marked and cannot satisfy a release gate. Missing build, tests, independent review, or rollback evidence appears as **missing**, not pending or passed. The release summary computes its state from persisted evidence and policy. Download actions must retrieve a real artifact; unavailable artifacts use a disabled control with an explanation.

## 8. Agents view

The Agents view is a registry and capability view, not a marketing logo wall. For every configured or supported engine, show:

- provider and engine/model identifier;
- connection state: `connected`, `unconfigured`, `unavailable`, `degraded`, or `local`;
- last successful health check, when known;
- supported capabilities;
- eligible production roles;
- execution location and data boundary;
- credential requirement without exposing credential values;
- recent success, latency, and cost only when backed by telemetry.

“Connected” requires a successful configured adapter health check. Browser availability, an interactive website session, or a provider name in source code is not a connection. Configuration controls may link to local setup instructions; browser-hosted deployment must not solicit secret API keys unless an approved secret broker exists.

## 9. Model responsibility separation

The work graph treats responsibilities as roles, independently of brand names:

| Role | Responsibility | Independence requirement |
| --- | --- | --- |
| Specifier | Convert intent into testable contracts | Must expose assumptions and unknowns |
| Researcher | Gather cited external evidence | Sources remain untrusted inputs |
| Test author | Define acceptance tests before implementation | Different provider and session from implementer |
| Implementer | Produce the artifact | Cannot approve its output |
| Reviewer | Find contract violations and issue verdict | Different provider, session, and producer ancestry |
| Fixer | Address accepted findings | Different provider from original implementer under current policy |
| Verifier | Run deterministic build/test/security checks | Runs outside model control |
| Integrator | Assemble a release candidate | Control-plane service, not an implementation model |

The router selects an eligible engine by capability, policy, availability, cost, and data boundary. UI copy may display a current assignment, but must not permanently equate a role with Codex, Claude, Kimi, Grok, Gemini, or any other provider. The policy layer rejects self-review, shared-session review, and delegated identity laundering.

## 10. Voice input

Use the Web Speech API only as an optional browser capture mechanism. Feature detection is required. The microphone control has idle, requesting-permission, listening, processing, error, and unavailable states.

Requirements:

- `ja-JP` for Japanese UI and `en-US` for English UI by default;
- visible live/final transcript and an always-available text editor;
- explicit start and stop; listening must never begin on page load;
- permission denial, no-speech, device loss, and unsupported-browser messages;
- `aria-pressed`, a changing accessible label, and a non-color recording indicator;
- preserve existing text and append final results without duplicating prior results;
- stop recognition on route change, component teardown, or microphone toggle;
- never create, start, authorize, publish, pay, or delete from speech alone;
- require review and explicit Create mission activation;
- read back or highlight high-value entities such as dates, amounts, percentages, environments, and destructive verbs before commit.

The browser prototype need not upload or retain audio. If audio retention is introduced, obtain explicit consent and persist the audio digest, language, timestamps, recognizer/version, transcript, and retention policy.

## 11. Runtime honesty

The console must always show one of these runtime modes:

- **Browser preview**: UI and client-side mission preview only. No filesystem, shell, local credentials, durable scheduler, or external model execution is available.
- **Browser connected**: connected to a real control-plane API. Capabilities are derived from its health response.
- **Local runtime**: downloaded application or local server with verified access to its configured adapters and workspace.
- **Disconnected**: previously connected data may be shown as stale; mutations and execution are unavailable.

The displayed mode is detected, not hard-coded. A public hosted page must default to Browser preview until a health handshake succeeds. The label **LOCAL RUNTIME** is prohibited in a hosted browser unless the client has positively connected to a loopback/local control-plane endpoint and verified its instance identity.

Mission compilation in the browser must be labelled **preview** if it is not durably persisted. External calls are never represented by timed animations or optimistic state changes. Status may advance only from acknowledged commands and committed events. Source ZIP download is labelled **Download source**; it is not called a desktop app or installer. Windows/macOS installer controls appear only when real signed artifacts exist.

## 12. Accessibility

Target WCAG 2.2 AA. At minimum:

- semantic landmarks, one page `h1`, hierarchical headings, and real buttons/links;
- complete keyboard operation with visible focus and logical order;
- skip link to main content;
- minimum 4.5:1 normal-text and 3:1 large-text/UI contrast;
- minimum 44 by 44 CSS pixel touch targets where practical;
- status never conveyed by color alone;
- form labels, descriptions, inline errors, and error summary;
- polite live regions for voice state and non-critical mission updates;
- no automatic focus movement for background status updates;
- usable at 200% browser zoom and 400% text zoom without loss of content;
- respect `prefers-reduced-motion`; no essential meaning depends on animation;
- decorative icons use empty alt text; icon-only controls have accessible names;
- localized accessible names change with the interface language.

## 13. Responsive behavior

### Desktop (>= 1200 px)

Show navigation sidebar, main view, and optional inspector simultaneously. The main content owns remaining width and does not shrink below a readable minimum. Inspector content must not cover primary actions.

### Tablet (768–1199 px)

Use collapsed navigation by default and move the inspector to a dismissible drawer or below the main content. Preserve all actions and data; do not replace tables with horizontal page overflow when a card/list representation is practical.

### Mobile (< 768 px)

Use one content column and an off-canvas navigation drawer. Sticky controls may be used only if they do not cover form fields or browser UI. Work graphs become ordered vertical steps. Tables become labelled cards. Command editor and primary action remain fully visible when the software keyboard is open.

Across breakpoints, resize must not reset locale, draft text, selected mission, filters, or scroll-independent state. Orientation changes must not cancel an active submission. The UI supports pointer, touch, and keyboard input.

## 14. Persistence and data contracts

Persist durable domain state through the control-plane API/event ledger. Browser storage is limited to presentation preferences and recoverable drafts:

- `guildless.locale`: `ja | en`;
- `guildless.sidebarCollapsed`: boolean;
- `guildless.commandDraft`: optional locally recoverable text, cleared after confirmed creation.

Do not store provider secrets, authority grants, authoritative mission status, evidence verdicts, or release decisions in browser storage. API reads include projection sequence/version. Mutations include an idempotency key. The client discards stale responses and refreshes after version conflict.

## 15. Error, loading, and empty states

Every view provides a non-blocking skeleton or progress label for initial load, a retryable error state, and a real empty state. Never substitute sample data after an API error. Network loss changes runtime mode to Disconnected and preserves unsent user input. Commands with uncertain outcomes are reconciled by idempotency key before the user is invited to retry.

## 16. Acceptance tests

The release is accepted only when the following tests pass in both locales where applicable.

### 16.1 Language

1. With no preference and a Japanese browser locale, first load renders Japanese and `html[lang="ja"]`.
2. Switching to English changes every console-owned visible and accessible string without reload and persists after reload.
3. Switching language preserves a partially written command, selected route, mission, and filters.
4. Translation dictionaries have identical typed keys; the build fails on a missing key.
5. Dates and numbers use the selected locale while stored data remains unchanged.

### 16.2 Navigation and views

6. Each left navigation item opens its distinct functional view; Back, Forward, reload, and direct URLs restore it.
7. Collapsed navigation remains keyboard and screen-reader usable; mobile drawer traps and restores focus.
8. Mission selection opens persisted detail, not placeholder content.
9. Evidence filters return real records and stale evidence cannot satisfy the release summary.
10. Agents reports an unconfigured adapter as unconfigured, never connected.

### 16.3 Mission lifecycle

11. Blank directives cannot be submitted and expose a localized inline error.
12. Double activation creates one mission because the submission uses one idempotency key.
13. Creating a mission produces `draft` or `planning`, never `running` or `complete` solely from the UI.
14. An invalid state transition is unavailable in the UI and rejected by the API.
15. Reload during every state reproduces the persisted projection and activity history.
16. A blocked mission displays its structured reason and allowed recovery action.
17. `release_ready` is impossible without fresh build, test, independent-review, and rollback evidence required by policy.

### 16.4 Voice

18. Unsupported browsers retain full typed-command functionality and show a localized explanation.
19. Microphone permission denial returns the control to idle/error without losing text.
20. Final speech results append once, use the active locale, and remain editable.
21. Route change and unmount stop microphone capture.
22. A spoken directive cannot create or start a mission without explicit user activation.

### 16.5 Runtime honesty and responsibility

23. A hosted page without a successful control-plane handshake displays Browser preview and no connected agents.
24. A local label appears only after a verified local handshake.
25. No status advances from animation, timeout, or an unacknowledged request.
26. Source ZIP is labelled source; installer actions are absent without signed installer artifacts.
27. Assigning implementer and reviewer to the same provider/session/producer ancestry is rejected.
28. Model-authored prose cannot mark deterministic tests passed.

### 16.6 Accessibility and responsive behavior

29. Automated accessibility checks find no critical WCAG A/AA violations on all four views.
30. A keyboard-only user can change language, navigate, dictate via the microphone control, create a mission, inspect evidence, and close drawers.
31. At 200% zoom and 320 CSS-pixel width, no primary control or content is clipped or obscured.
32. With reduced motion enabled, navigation and status remain understandable without motion.
33. Screen-reader announcements identify voice state and command errors without repeatedly announcing background updates.

## 17. Definition of done

This console increment is done when all four navigation views operate on persisted or explicitly labelled preview data; Japanese/English switching is complete and persistent; voice input degrades safely; mission transitions are server-authoritative; model role separation is enforced; runtime mode is verified and truthful; responsive and WCAG acceptance tests pass; and no visible status or download claim exceeds the capability actually delivered.
