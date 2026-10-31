# Antigravity — Pixel-Art App Explainer Starter

**Objective:** Make a real, polished explanatory video of the app in this repository. Run it locally, observe what it actually does, capture the UI, create an ORIGINAL pixel-art host and animated highlights, produce narration and word-synchronized animation, and export final MP4 files.

This starter is independently written. It is NOT a copy of the Clief Notes paid animation workspace or any restricted course downloads. It follows the public five-stage concept: **Voice → Words → Cues → Scene → Render**, with an additional app-inspection phase.

## Quick start

1. Download [Google Antigravity](https://antigravity.google/download) for your OS, install and sign in. You can use the Antigravity app or IDE.
2. Open the **root of your actual app repository** in Antigravity. Keep your app source and this starter in the same workspace.
3. Copy the contents of this ZIP **into the root of that app repository** (merge directories; do not overwrite the app's existing AGENTS.md; merge its guidance manually). The directories `.agents/skills/` and `video-studio/` should be directly under the repository root. If an AGENTS.md already exists, follow both sets of rules and resolve conflicts by prioritizing project safety.
4. Read the `PROMPT_FOR_ANTIGRAVITY.md` file. Paste that full prompt in Antigravity, or tell the agent: `Read PROMPT_FOR_ANTIGRAVITY.md and execute it fully. Invoke the relevant workspace skills.`
5. Grant only required approvals for installing trusted dependencies and local execution. Never provide production credentials or approve real-world sends/purchases to create a video.
6. Review outputs at `video-studio/output/`.

## Downloads / prerequisites

| Need | Source | Install strategy |
|---|---|---|
| Antigravity | https://antigravity.google/download | Install yourself; sign in |
| Node.js current LTS | https://nodejs.org/en/download | Agent may install if missing, with permission |
| Git | https://git-scm.com/downloads | Agent may install if missing |
| FFmpeg + ffprobe | https://ffmpeg.org/download.html | Agent may install vetted binaries; check PATH |
| Python 3.11+ | https://www.python.org/downloads/ | Optional for word alignment and diagnostics; agent may install |
| Chromium / Playwright | https://playwright.dev/docs/intro | Install in isolated capture folder; use `npx playwright install chromium` |
| Remotion | https://www.remotion.dev/docs/ | Scaffold *inside* `video-studio/engine/`, not in app root |
| Remotion agent skills | https://www.remotion.dev/docs/ai/skills | Official `npx remotion skills add` inside engine, or official `npx skills add remotion-dev/skills` |
| Optional voice alignment | https://github.com/SYSTRAN/faster-whisper | CPU model `tiny` or `base` with `word_timestamps=True`, optional |

**Machine constraints:** Prefer CPU-friendly methods and initial 720p preview with 2 render workers. On Windows 10, the Antigravity app may run, but the **current official Playwright requirements list Windows 11+**. If Chromium launch is unsupported, try Antigravity's browser tooling or WSL2/Ubuntu 22.04; do not pretend an unsupported setup works. Remotion may require current Node, Chromium and system libraries; diagnose first.

## Agent skills (already included)

These are *project-local skills* in `.agents/skills/` and will be discovered by Antigravity:
- `app-runtime-discovery`: inspect and boot the real app safely
- `safe-ui-capture`: browser capture and semantic targeting
- `storyboard-and-voice`: accurate app narrative and word-aligned storyboard
- `pixel-art-motion`: cinematic pixel sprite + kinetic typography + highlights
- `render-and-review`: quality gates, MP4 exports, QA loop

The agent can install **official Remotion Skills** in addition to these, but shouldn't silently pull unreviewed third-party skill repositories.

## What you get

The agent should create these from your real project:

- `video-studio/output/app-explainer-16x9.mp4` — 1920×1080, 30 fps, with narration
- `video-studio/output/app-explainer-9x16.mp4` — 1080×1920, 30 fps, with narration; separate mobile-safe layout
- `video-studio/output/app-explainer-silent.mp4` — silent 16:9 for speaking over live
- `video-studio/output/preview.mp4` — quick low-resolution test render
- `video-studio/output/contact-sheet.png` — representative frames to inspect
- `video-studio/output/QA_REPORT.md` — captured routes, assertions, FFprobe checks, problems solved
- Editable `video-studio/engine/`, `video-studio/storyboard.json`, and asset files

Outputs won't exist until Antigravity has access to **your app** and successfully runs and renders it. The ZIP is a ready-to-use project starter and prompt, not a pre-rendered video.

## Inspect this machine first

```
python video-studio/tools/doctor.py
```

If it needs FFprobe validation:

```
python video-studio/tools/verify_render.py video-studio/output/app-explainer-16x9.mp4 --width 1920 --height 1080 --fps 30 --audio required
```

## Reference material

- Original Reel: https://www.instagram.com/reel/Dd6qU9exCpY/
- Clief Notes public lesson/course: https://www.skool.com/cliefnotes/classroom/d3907117?md=menu
- Public workflow quick reference: https://www.skool.com/cliefnotes/classroom/d3907117?md=9c4b772439eb435485cab0cb1aca6e95
- Creator explainer: https://www.youtube.com/watch?v=EhWlGingCl0

Use the links for inspiration/structure, not for scraping paid assets or lifting the creator's characters. If an accessible local copy of the Reel is supplied, analyze its composition and transition patterns without copying its proprietary art.
