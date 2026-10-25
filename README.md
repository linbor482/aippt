# FORM / AI PPT

A Flask presentation workspace with an editable outline and editable PPTX export.

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The existing Vercel entry point remains `app.py`.

## Structure

- `app.py`: Flask/Vercel entry point with compatibility exports for local scripts.
- `json_api.py`: legacy JSON routes and HTTP response compatibility.
- `generation_service.py`: shared outline, request and generation-option validation.
- `generation_api.py`: NDJSON streaming transport, deadlines and stream errors.
- `outline_service.py`: outline prompt and deterministic placeholder content.
- `image_service.py`: image providers, ranking and optional visual matching.
- `pptx_export.py`: shared scene-to-PPTX rendering and in-memory export.
- `presentation_design.py`: deterministic scene planning and editable PowerPoint rendering.
- `style_layouts.py`: four independent composition families (business, minimal, creative, proposal).
- `index.html`: workspace and dialogs.
- `static/tokens.css`: design tokens (colors, radii, shadows, motion).
- `static/base.css`: dialog and form structure.
- `static/studio.css`: workspace layout and responsive scene structure.
- `static/studio-redesign.css`: the dark "projection room" visual theme (loaded last).
- `static/studio.js`: outline editing, navigation, preview and downloads.

`POST /api/preview` returns the same scene descriptions used by PPTX export.
Text wraps are calculated once. Design previews show image placement; the generation workspace
shows the images actually embedded in PPTX as each page completes. Font rendering can vary
between browsers and PowerPoint, especially if Microsoft YaHei is unavailable.

Content slides accept `layout: auto | editorial | columns | timeline`. Automatic layout uses
dated points for timelines, concise points for columns, and longer points for numbered rows.
Dense content continues onto additional slides, so final page count can exceed outline count.
All content is retained. No factual metrics or charts are inferred from plain text.

The default image mode is `none`, which uses no image services. Existing `blank`, `real`,
and `ai` options remain available. Pure layout and preview have no model/API charges.
Optional content generation uses the existing `DEEPSEEK_API_KEY`; vision checking uses
`VISION_API_KEY`. A local `config.json` written by the optional in-app "API 密钥设置" page
takes priority over environment variables, which in turn override `.env`.

## Prompt and live generation — 2026-10-08

The topic field accepts a 1–200 character brief with audience, goals and constraints.
AI is enabled by default. A missing key or failed AI request is shown explicitly; it no
longer silently substitutes a template. Turn AI off to create a clearly labelled placeholder
outline. Page count is enforced strictly (exactly N pages); an explicit count written in
the brief overrides the form, otherwise the form's N is enforced.

`POST /api/outline/stream` streams NDJSON stage updates and complete outline pages to the
outline dialog. Only actual output and processing stages are displayed. After editing,
`POST /api/generate/stream` streams completed scenes to the normal PPT workspace, followed
by the PPTX download. Both use request-scoped generators, with no job database, instance-local
polling or filesystem output. Cancel closes the browser request; an in-flight provider call
may continue until it returns or reaches its timeout. Legacy JSON routes remain available.

## Vercel

Keep `app.py` as the Flask entry point and install `requirements.txt`. Set the AI keys in
the Vercel environment settings. The checked-in configuration requests a 300-second function
duration; confirm the selected plan/runtime allows it and enables streaming before deployment.
The stream uses a 240-second work budget and the browser stops waiting at 285 seconds.
Image requests share that budget, image downloads are capped at 8 MiB and images are resized
to at most 1280×960. PPTX output is capped at 3 MiB and total NDJSON at 4.2 MB, including
preview images and base64 overhead. Split large decks or use pure layout if a limit is reached.

API responses are not cached. Static assets have a one-hour cache and versioned URLs;
update the URL version when editing assets. `.vercelignore` excludes secrets, backups,
review files and local test scripts. No Vercel deployment was performed for this change.

```powershell
python -B -m unittest discover -v
node --check static/studio.js
```

## Verification

```powershell
python -m unittest test_design -v
```

Tests cover preview/export consistency, editable text, element bounds, dense content,
image insertion, API generation and one-page output. Browser verification was performed
with Playwright and installed Microsoft Edge at 390, 768, 1440 and 1920 pixels, including
template switching, outline editing and PPTX download. No paid APIs were used for verification.

## Design update — 2026-10-03

Each style has independent cover, content and closing compositions. Business uses a navy
side panel and structured cards; minimal uses whitespace, thin rules and light headings;
creative uses editable circles, poster typography and staggered pastel cards; proposal uses
dark chapter sidebars and separate argument modules. Timelines vary between horizontal
and vertical layouts. Long points continue across pages. No factual charts are invented.

The workspace now includes a page rail, canvas and design inspector, with actual generated
style thumbnails, purpose descriptions, outline editing and a clear create action. Imported
outlines appear immediately. Both configuration and workspace selections stay in sync.
The interface adapts to mobile; dialogs support keyboard focus containment and Escape.

Public reference: https://pitch.com/ (viewed 2026-10-03), for visual hierarchy, presentation
showcases and emphasis on the primary creation action. Original implementation; no external
template assets were copied. SlidesCarnival's HTML was reachable, but its browser view timed out.

`python -B -m unittest discover -v` checks scene/export consistency, text retention, bounds,
image insertion, structural style differences and access-password behaviour. Screenshots,
sample PPTX and comparison images are generated locally into `review/` (not committed).
