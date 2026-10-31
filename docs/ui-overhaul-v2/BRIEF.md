# AI4BRAIN adventure UX rebuild

Status: User selected premium illustrated adventure on 19 October2026 and explicitly authorized full UI/game overhaul. Keep existing companion source and appearance unchanged. Source spec remains product evidence; the latest human request adds full-page, highly interactive play with direct entry and smooth automatic progression.

## Understanding and decisions

- Rebuild the product around an illustrated five-world practice journey for adults/teens; premium system typography, warm paper surfaces, cobalt/indigo actions, coral/mint supporting accents. Avoid childish worksheet aesthetics and repetitive KPI-card dashboards.
- Keep real canonical data, uncertainties, accessible evidence, fixed baseline formulas/counts, local privacy and provider-free operation. A perfect introductory result is not overall mastery. Do not rewrite saved results to make numbers lower.
- Preserve Companion.tsx and companion.css byte-for-byte, including all behavior and quiet scored states.
- Desktop: coherent navigation and home with a primary resume/play action above the fold. Mobile: reachable bottom navigation or deliberate menu; no clipped horizontal tab list. Game views occupy the usable page, with compact persistent exit/pause, family/set progress, readable instructions and touch controls.
- One clear entry action starts/resumes the next game. No Practice center detour followed by a second Start. Within sets, watch/recall/answer/next should flow automatically; pattern/rule choices auto-submit with guarded commitment; planning completes automatically at goal, with unfinished submission available from pause/menu. Explicit retry remains for ambiguous failures. Neutral transitions must not reveal scored correctness.
- Timed attention remains static and keeps the full window, including after an early press. No per-cue Ready/Next. Baseline 40/30Go/10NoGo remains unchanged. Optional pauses occur only outside active cue windows and retain canonical interruptions.
- Make games deeper through versioned, deterministic training forms: richer compound pattern reasoning, longer varied memory sequences, actual target/distractor attributes, multiple rule choices, and much richer BFS-verified planning boards. Keep old blocks replayable under their original versions. New blocks have varied forms persisted from a reproducible block seed.
- XP/milestones remain participation/evidence rewards. Journey art and completion markers must reflect saved progress; all baseline families remain reachable. Never generate fake streaks, invented social/avatar accounts, unsupported cognitive claims or artificial unlocks.

## Visual references

01-play-desktop-draft.png is the selected aesthetic direction, not an implemented screen. Its generated filler copy/avatar/streak/lock details are NOT requirements and will be corrected in later selected concepts. Further game/mobile references and source art are being generated. All mock data in concepts must be labelled DESIGN PREVIEW / SAMPLE DATA.

## Implementation batches

1. Shell/home/navigation and responsive progressive disclosure.
2. Full-page native game stages, direct entry, automatic round progression, guarded input and pacing.
3. Versioned deeper training banks, legacy replay and explicit meaning of introductory score ceilings.

GPT-6 Luna implements owned files; parent reviews actual rendered outputs, behavioral loops and canonical evidence independently. No separate user chats. No Docker changes or primary participant QA writes. Current root setup/start/stop remains Docker-free.

## QA acceptance

Desktop1440, tablet768/1024, mobile375/390/320: all destinations reachable, no clipped controls, primary resume abovefold, touch targets>=44px, keyboard/focus/reduced motion. Inspect every game visually and interactively. Test rapid/double input, held keys, slow POST/GET, exact saved retries, refresh/restore, blur/visibility, no scored hints, no premature signal advance, replayed old versions, new-form variety, correct deterministic scores, unchanged baseline indices, and full companion source hashes. Every result is software QA, not participant/clinical validation. Image concepts are not acceptance evidence.
