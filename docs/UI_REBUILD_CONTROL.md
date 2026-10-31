# Current UI completion objective

## Latest staffing correction

The human now directs keeping only ONE implementation chat to reduce token use. Retain `AI4BRAIN games visual rebuild` (01a155fa-b56b-7aa2-8dc7-562f68919720); it handles games first and remaining product pages sequentially after a safe handoff. `AI4BRAIN product pages visual rebuild` (01a155fc-1ec5-7bc0-bb55-57deba44e11b) has been instructed to stop all children, preserve partial work and pause its scoped goal. Do not transfer its files until its stopped handoff is confirmed. Earlier two-lane parallel staffing below is historical and superseded.

The product-pages coordinator explicitly acknowledged stopping its work and subagents; the parent archived it and independently observed its turn interrupted and thread inactive. Partial files remain preserved. The retained games chat has been authorized to reuse those partial page components after its game queue.

Keep at most one implementation subagent active in the retained chat. That coordinator performs its own source review; the parent handles independent integration/browser QA and asset generation. No new chats, extra concurrent review agents or model-setting changes without explicit human direction.

Human direction on 19 October 2026: continue the approved redesign across all pages and games until the development work is done; coordinate two additional chats with multiple agents; assign a separate Home scroll-overlap repair. This supersedes the earlier instruction to hold all other pages behind Home. Home fidelity and its newly reported scroll defect remain open acceptance items, not waived requirements.

## Goal-service limitation

The parent chat still has an unfinished, usage-limited legacy project goal. The goal service rejected replacement. This file records the updated objective without marking unfinished work complete. The two newly created work chats are instructed to establish their own explicit, unbudgeted completion goals.

## Objective and acceptance

Complete the approved illustrated-adventure UI across Home, all five existing games, Analytics, Quest, Plan, practice entry/completion, Evidence, Collaboration, Privacy and pause/recovery states. Reuse the approved assets and existing companion. Preserve immutable evidence, baseline/training separation, unassessed/unavailable states, canonical backend correctness, hint eligibility, true puzzle geometry, timing, retry and interrupted exclusion.

Use readable typed React components, a shared world catalog, small reusable visual primitives and explicit data adapters. Preserve useful game complexity and smooth progression; do not replace actual item configurations with simplified illustrative boards. Keep future hybrid game designs/resources tracked separately; do not silently claim their implementation from existing games.

Every surface needs independent rendered comparison to its approved reference, desktop/mobile layouts, real empty/populated/loading/failure states, keyboard/focus checks, reduced-motion behavior and relevant interaction regression checks. Specifically test at scroll top, mid-page and bottom: sticky/fixed navigation, companion, overlays and decorative full-bleed art must not obscure content or controls. A successful build alone is insufficient.

Publication, committee submission and final recording remain deferred under prior human direction. Do not mark the entire original specification complete on the strength of this UI work.

## File ownership and coordination

The repository has no initial Git commit. All lanes use the existing local project with disjoint ownership; do not create an empty worktree or commit unrelated/untracked files just to enable worktrees.

| Lane | Owns | Must not edit |
| --- | --- | --- |
| Home repair agent | Home-specific CSS/composition and output/verification/ui-rebuild/home-scroll | Routing, shared navigation, task logic, backend/data, other lanes |
| Games chat | frontend/src/redesign/games/** and output/verification/ui-rebuild/games/** | App.tsx, TaskComponents.tsx, existing global CSS, shared UI contracts, other lanes |
| Product-pages chat | frontend/src/redesign/pages/** and output/verification/ui-rebuild/pages/** | App.tsx, task components, existing global CSS, shared UI contracts, other lanes |
| Parent supervisor | Shared visual contracts/primitives, routing integration, existing state-machine adapters and final verification | Other lane's owned files while its implementation agent is editing |

Each work chat may use a GPT-6 Luna implementation agent and a separate read-only review agent. Assign only one writer per file. Build existing dependencies; do not install a state framework or change backend contracts for styling. Agents prepare real reusable components with typed props and integration instructions; the parent connects them to canonical state. Each page/game gets a local review before its lane proceeds. The parent independently reviews and can request repairs without silently accepting known differences.

Both chats read docs/IMPLEMENTATION_PLAN.md, docs/REQUIREMENTS.md, docs/SPRINT_STATUS.md and the approved package output/visual-design-review-2026-10-19. Reject boards 32/33. Consult ASSET_MAP.md for known generated-copy mistakes and source-art preparation limits. Never invent learner history or screenshot values.

Write lane progress and review evidence to the owned output folder so the parent can monitor without cross-thread message loops. The parent is explicitly authorized to send follow-up assignments to both chats. Browser QA and live integration are coordinated by the parent; workers must not change the parent's browser viewport or existing server processes.

## Safety and runtime boundaries

Preserve primary learner data and source documents. No .env reads in outputs, no provider keys, no Docker changes, no deletes outside isolated QA. Keep Companion.tsx and companion.css unchanged. Use .venv Python for backend work; installed frontend dependencies for builds. No destructive lifecycle test on primary data. Temporary QA servers/databases require isolated paths and explicit ownership in review notes.
