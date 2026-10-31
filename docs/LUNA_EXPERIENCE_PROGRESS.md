# Luna experience progress

## Batch 1 - existing games visual refinement

Completed the initial Memory, Planning, Reasoning, Attention and Flexibility review. No task geometry, canonical state adapter, scored rule or backend behavior was changed.

The approved-asset manifest currently records 55 prepared sprites from eight source sheets. A fresh read-only check verified every source and output SHA-256, all 55 output files, zero recorded crop-edge/alpha-ring failures, 165 per-asset preview paths, and six group contact sheets. Receipt: output/verification/luna-completion/experience/batch-1-asset-integrity.json.

Memory's saved visual packet dated 21 October contains 217 passing assertions across 320/375/390/768/812-landscape/1024/1440 widths. It confirms zero cue scroll offsets, all nine tile bounds visible, and keyboard focus-ring visibility/non-clipping. This packet predates the ring-overlay patch below, so it is not evidence for the new ring rendering. The 21 October live source already has phase-specific copy and a ResizeObserver-based truthful scroll label. The previously reported crop assertion weakness is not present in the newer saved packet: current assertions require zero offsets, and bounds are explicitly measured.

Changes in this batch:
- Added native concentric engraved rings over the prepared diamond stone artwork in Memory, retaining the approved image texture and keeping the board's existing size cap.
- Added Motion hover/press feedback only for learner-activated Memory, Reasoning, Attention and Flexibility controls. Reduced-motion preferences disable the added movement. The timed Attention signal and Memory cue sequence remain untouched.
- Corrected Memory phase/status separators and punctuation that were stored as mojibake.

Verification run: npm run build passed (TypeScript and Vite production build; 2051 modules). Vite emitted its existing greater-than-500 kB main-chunk advisory. No integrated browser rerun was performed in this worker; the supervisor owns live browser QA and should inspect the ring overlay and interactive motion after refreshing the active QA app.

Remaining visual differences for follow-up review:
- Reasoning's approved plate is a separate 3x3 crystal-count task; preserve the existing 2x2 geometry baseline. The new versioned crystal form is in the parallel gameplay worker's scope.
- Memory's current composition still uses the approved nested scene/board/dock composition and does not reproduce every plate detail. The new concentric layer needs a fresh browser capture before closing its mismatch.
- Planning and the three prepared-art families use their approved scene and sprite layers. Existing saved B3 screenshots predate the latest application display-name integration and are reference evidence only, not current acceptance captures.
- Human visual/audible acceptance remains open.

## Batch 2 - Home, companion scale, and short-viewport Memory fix

Reference review used `01-home.png`, `09-plan.png`, `08-insights-quest.png`, `11-evidence.png`, `12-collaboration.png`, `13-privacy.png`, and `docs/ui-reframe/07-companion-states.png`. CUA reported no available browsers in this worker, so I could not capture a fresh mounted comparison; saved page captures in `output/verification/ui-rebuild/games/full-audit/**` are stale and were not treated as current UI acceptance evidence.

Changes:
- `frontend/src/companion.css`: matched the approved companion's 56x40px face within a 64x48px minimum trigger. Existing popover behavior and responsive bounds are unchanged.
- `frontend/src/home.css`: changed the desktop summary from a fixed 522px box to a 522px minimum with intrinsic growth, preserving the two-card mobile layout. This prevents longer live plan/participation content from being compressed by the fixed-height panel.
- `frontend/src/redesign/games/memory-game.css`: corrected the invalid desktop CSS height-cap arithmetic (`calc(100dvh - 346px)`) and accounted for grid gaps, frame, padding, and slab when capping tile size. This is a narrow per-game CSS correction requested after the supervisor observed an internal scrollbar at 1280x720; not browser-verified in this worker.

Verification: existing page fixtures passed 36/36 isolated server-rendered checks. PostCSS parsed all four reviewed CSS files. The production build is currently blocked by a concurrent worker's TypeScript error at `frontend/src/redesign/hybrid/SupplementalGames.tsx:29` (`HarborBoard` is undefined); no changes were made to that file. Browser screenshots and current mounted page comparisons remain with the supervisor.

## Batch 3 - Analytics/Quest world strip and approved scene reuse

Reviewed the supervisor's fresh mobile captures (`output/verification/luna-completion/supervisor/analytics-current.png`, `quest-current.png`, `plan-current.png`, `evidence-current.png`, `collaboration-current.png`) against approved refs 07–13. Analytics/Quest had no prominent shared five-world selector; its Quest-only miniature branch map duplicated the existing task list and differed from the approved cross-world presentation. Both modes now render one connected five-world selector directly from the current task coverage rows, with existing world cutouts, selected-state and truthful status/evidence count. Quest's duplicate small-map visual has been removed. Clicking a stop calls the same selection callback and continues to drive the existing detail panel.

The fresh Collaboration capture and Quest/Analytics hero used the generic open-water game landscape, leaving the bridge/portal scene substantially unlike the approved page art. Insights and Collaboration now reuse the already-approved Home hero plate 40; Plan's route map reuses the same bridge plate to better match reference 09. No new or source artwork was created or altered. Companion control and Home sizing changes plus the short-viewport Memory CSS fix from batch 2 remain as documented above.

Verification after the world-strip change: page fixtures passed 36/36 (isolated server-rendered checks), updated Insights CSS parsed, and production `npm run build` passed with 2062 modules. Existing main-bundle advisory remains. The fresh captures are pre-change; this worker had no browser available and does not claim mounted screenshot verification after the latest strip/scene updates. Remaining review: refresh Analytics/Quest/Plan/Collaboration after the changes; verify the 1280x720 Memory board and short landscape in the supervisor's browser; inspect Evidence against its desktop graph composition and Privacy at mobile size; human visual/audio acceptance remains open.
