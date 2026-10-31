# AI4BRAIN UI reframe

Status: APPROVED by the user. Implement this direction in reviewed batches. These images are generated design concepts, not implemented-feature screenshots. All visible profile values/history are illustrative sample data.

## Direction

- A quiet desktop workspace with warm white surfaces, graphite type, a single system-blue accent and hairline dividers.
- Slim horizontal navigation replaces the large dark sidebar. Use deliberate spacing and a few clear sections rather than grids of metric cards.
- The assessment focuses on one task. Score/evidence details remain available after completion.
- Analytics and Quest share the exact same underlying data. Quest changes presentation and participation rewards only.
- The two-brain diagram remains small, typed and inspectable, with a restrained evidence inspector.
- A tiny original graphite companion with two white eyes persists across app screens. It opens a small coach popover when invited and rests during scored tasks.

## Proposed design tokens

Canvas #FAFAFA; text #1D1D1F; secondary text #6E6E73; dividers #E5E5EA; primary action #007AFF. Readable system sans typography, body16-18px, headings32-44px, 8px spacing rhythm, content width1180-1280px. Controls have at least44px tap areas, visible keyboard focus and restrained hover/focus states. Translucency is limited to floating overlays. Reduced motion must be supported.

## Companion behavior

Visual footprint56x40px inside an accessible minimum64x48px control. Idle blinking and subtle pointer-following use cursor coordinates, not a camera. The companion can be moved to safe corners by drag or keyboard/menu controls, can be hidden, and never covers Submit or a stimulus. Clicking opens the coach. System states: idle, looking, thinking, speaking, quiet assessment, success, offline and hidden. These describe interaction/service states, not inferred learner emotions. During scored baselines it remains still, closed-eyed or hidden, with no hint or correctness reaction. Training may offer evidence-grounded help; hinted attempts remain ineligible for difficulty promotion.

## Screen set

1. 01-welcome.png: concise explanation, consent, local-data notice and view choice.
2. 02-assessment.png: focused reasoning matrix with selected answer and quiet companion.
3. 03-overview.png: five task-specific estimates, evidence, uncertainty, history, plan and activity.
4. 04-brain-twin.png: learner/estimate/dimension/evidence/exercise/strategy relationships.
5. 05-practice-coach.png: guided practice with compact floating coach.
6. 06-quest.png: restrained practice path with engagement XP separate from task indices.
7. 07-companion-states.png: expressive state/size/popover study.

## Review and implementation boundaries

At concept approval, no React UI had yet been replaced. No companion package was installed. The human approved the complete visual direction. Images are composition references; real frontend code must use live state, correct task logic and accessible controls. The generated graph and training concepts were repaired to correct arrow semantics and ensure distinct answer options. If implementing, preserve readable mobile layouts and incomplete/unassessed states, not just the complete illustrative samples.

The user requested Neo4j working as a separate current task. The live database is now independently verified; this does not imply its UI is integrated in the application during the preceding pause.

## GitHub research

- Agent Robot Avatar: https://github.com/CX-ArtLab/agent-robot-avatar . SVG/vanilla-JS Web Component with zero runtime dependencies, blinking, pointer-following and reduced-motion support. Repository labels source as MIT and separately describes its character identity. Strong behavior/API reference; our generated two-eye visual remains a separate concept.
- CursorBuddy: https://github.com/jasonkneen/CursorBuddy . Browser embed and Electron overlay, damped cursor following, anchor movement and speech bubbles. Repository labels its license AGPL-3.0-only. Useful movement/interaction reference; no code copied or installed.
- Minimal eyes experiment: https://github.com/jayeclark/eyes . Plain HTML/CSS/JS pointer-following eyes; repository labels MIT. A small mechanism reference rather than a complete assistant.

Research checked18 October2026. Repository claims were read, not installation-tested.

## Generation

Built-in image-generation tool was used for all seven final images. Original generated files remain under the Codex generated_images folder; selected outputs are copied here. See PROMPTS.md for the final prompt set. Preview index.html for the complete gallery.

