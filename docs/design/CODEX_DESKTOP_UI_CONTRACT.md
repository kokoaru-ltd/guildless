# GUILDLESS Codex Desktop UI Contract

Status: mandatory design contract  
Reference: Codex desktop application supplied by the owner  
Applies to: desktop shell, browser workspace, onboarding, settings, missions

## Product intent

GUILDLESS must feel like a native professional work environment, not a miniature
dashboard and not a themed imitation of Manus. Codex desktop is the interaction
reference. GUILDLESS adds expert orchestration, evidence, model routing, and
operations without weakening the clarity of that shell.

## Non-negotiable layout

- Left navigation rail: `232–248px`.
- Main work canvas: fluid, minimum `720px`, reading column `720–780px`.
- Environment rail: `304–336px`, visually above the canvas, independently scrollable.
- Desktop viewport target: `1440×900` and above.
- Below `1100px`, collapse the environment rail behind a toggle instead of squeezing text.
- Below `760px`, use a mobile navigation shell; never scale desktop UI down.

## Typography

- Primary family: Geist, Inter, `-apple-system`, `Segoe UI`, sans-serif.
- Japanese fallback: `"Noto Sans JP"`, `"Yu Gothic UI"`, sans-serif.
- Body copy: `14px`, line-height `1.65`.
- Navigation and controls: `13px`, never below `12px`.
- Metadata: `11px`, allowed minimum `10px`.
- Page title: `14px`, semibold.
- Section title: `13px`, semibold.
- Long-form output: maximum line length `76ch`.
- Monospace is limited to commit IDs, metrics, code, model IDs, and timestamps.

No production text may use `6–9px`. Tiny type was the largest visible failure in the
first prototype.

## Spacing and geometry

- Base spacing unit: `4px`.
- Primary rhythm: `8 / 12 / 16 / 24 / 32px`.
- Navigation row: `36px`.
- Toolbar: `48–56px`.
- Message separation: `24–32px`.
- Cards: `12px` radius; inputs and floating panels: `16px`.
- Borders: neutral gray at low contrast; elevation only for floating layers.
- Content must breathe. Do not compensate for missing hierarchy by shrinking type.

## Color

- App background: cool neutral `#f5f6f8`.
- Main canvas: `#ffffff`.
- Sidebar: `#f4f5f7`.
- Primary text: `#24262b`.
- Secondary text: `#656a73`.
- Hairline: `#e1e4e8`.
- Success, warning, and failure colors communicate state only.
- Avoid decorative gradients except for generated media or rare onboarding moments.

## Interaction

- Every visible button has an action, disabled state, or explanatory tooltip.
- Press feedback: `scale(.97)` for `100–160ms`.
- Frequent navigation and keyboard actions are instant.
- Popovers: `150–200ms` ease-out, originating from their trigger.
- Modals: centered, `200–240ms`; no bounce.
- Only transform and opacity may be animated for routine UI.
- Respect `prefers-reduced-motion`.

## Desktop information architecture

### Left rail

New task, search, missions, agents, connectors, project list, task history, account
and settings. Labels remain stable. Language is never a floating top-level control.

### Main canvas

Mission contract, user request, production trajectory, expert council, deliverables,
and composer. The reading order must remain obvious without card overload.

### Environment rail

Changes, Evidence, Preview, Files, Activity, and MCP. It is a working surface, not a
decorative status panel. Browser preview belongs here.

## Onboarding

Onboarding is a three-step first-run experience, not a feature tour carousel.

1. **State the outcome** — voice or text; explain that GUILDLESS forms the company.
2. **Connect capabilities** — local workspace first, then optional model/MCP accounts.
3. **Approve the operating contract** — budget, permissions, evidence, and release authority.

Rules:

- one decision per screen;
- visible progress (`1 of 3`);
- always offer Skip and Back;
- preserve partial choices;
- reopen from Settings;
- never block local exploration behind account creation;
- use real controls and examples instead of illustrations that cannot be interacted with.

## Quality gate

Before a UI change is accepted:

1. Compare at `1440×900` and `1920×1080`.
2. Verify no body/control text is below the minimum sizes.
3. Test keyboard navigation, focus visibility, empty/loading/error states.
4. Test Japanese and English from Settings.
5. Verify all buttons and tabs have behavior.
6. Verify main and environment panels scroll independently.
7. Verify reduced motion.
8. Capture a screenshot and compare hierarchy, not merely component presence.

Any change that violates this contract must be rejected by the Product Designer
or Design Engineering reviewer before release.
