# Guildless UI provenance

## Adopted source

Guildless uses the TypeScript/Vite/shadcn component base from
`satnaing/shadcn-admin` at the fixed commit below.

- Repository: https://github.com/satnaing/shadcn-admin
- Commit: `e16c87f213a5ba5e45964e9b67c792105ec74d26`
- License: MIT
- Reused boundary: Vite application structure, Tailwind theme, shadcn UI
  components, accessible button/card primitives, responsive app-shell approach
- Guildless-specific work: Japanese navigation, operation pipeline, Council,
  artifact verification, audit views, API binding and all workflows

## Design reference

- Repository: https://github.com/marmelab/atomic-crm
- Commit: `167a4cdb652b1ab2b4b030831cfa7adcf2099321`
- License: MIT
- Referenced boundary: operational list/detail/activity information hierarchy
- No Atomic CRM source module is bundled into the Guildless runtime.

## Cloudflare OS UI source

Guildless now directly adapts selected home-composer interaction and semantic
design tokens from `cloudflare/cloudflare-os` at a fixed commit.

- Repository: https://github.com/cloudflare/cloudflare-os
- Commit: `c04843f97cd07a8c869312058fc59a00b5d5b5cb`
- License: Apache-2.0
- Source files inspected and adapted:
  - `packages/workshop-frontend/src/components/AppShell/HomeTaskSuggestions.tsx`
  - `packages/workshop-frontend/src/components/SectionEyebrow.tsx`
  - `packages/workshop-frontend/src/styles.css`
- Guildless derived file:
  - `frontend/src/cloudflare-os/home-task-suggestions.tsx`
- Retained behavior: a suggested task fills the composer but never sends it
  automatically; the user may edit or cancel it.
- Retained design rule: neutral enterprise surfaces with the orange brand color
  reserved for intent, focus, and primary action.

Cloudflare OS is not shipped as a separate product or screen. These parts are
integrated into the single Guildless CEO desk.

## Generated visual asset

- File: `frontend/public/guildless-company-map.png`
- Generated for Guildless with OpenAI image generation on 2026-08-13.
- Purpose: a non-textual visual explanation of company operations flowing from
  customers and teams to reviewed outcomes.
- This asset is original to Guildless and is not copied from Cloudflare OS.

## Rejected source

`twentyhq/twenty` was not used because its current repository contains AGPL and
commercial-license boundaries that are unsuitable for direct extraction into
this product without a separate licensing review.
