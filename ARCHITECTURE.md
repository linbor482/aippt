# Structure and Coupling Notes

## Runtime boundaries

`app.py` stays the Flask/Vercel entry point. It creates the Flask app, installs CORS,
registers the two route modules, and retains imports used by older local scripts.

| Module | Responsibility | Dependencies |
| --- | --- | --- |
| `settings.py` | Load `.env` and expose process configuration | Environment only |
| `json_api.py` | Legacy preview, outline and generation JSON routes | Outline service, validators, PPTX export |
| `generation_api.py` | NDJSON routes, response headers, timeout and stream error framing | Shared generation rules and PPTX export |
| `generation_service.py` | Request/outline/option validation and streamed AI outline events | Outline provider and HTTP client |
| `outline_service.py` | Prompt construction, AI outline request and deterministic placeholder | Settings |
| `image_service.py` | Search/AI image requests, validation, ranking and visual match | Settings and request-scoped network budget |
| `pptx_export.py` | Scene orchestration, image embedding and in-memory PPTX creation | Scene renderer and image service |
| `presentation_design.py` | Shared scene planning and editable element rendering | `style_layouts.py` |
| `style_layouts.py` | Four independent slide composition families | No route or network modules |

The browser preview and PPTX export still consume the same scene description. JSON and
NDJSON requests share their outline and generation-option validation. Providers read
immutable process configuration; request deadlines remain isolated through `ContextVar`.
No job database, local output file, or cross-request mutable generation state was added.

## Keep / merge / split decisions

| Area | Decision | Reason |
| --- | --- | --- |
| Flask entry point | Keep `app.py` | Local startup and Vercel already target it. |
| JSON and NDJSON validation | Merge through `generation_service.py` | Prevents drift in page, template, image and outline rules. |
| Scene model | Keep in `presentation_design.py` | It is the compatibility contract for HTML and PPTX. |
| Four layout families | Keep independent in `style_layouts.py` | Structural differences are a product requirement. |
| Image providers | Split into `image_service.py` | Network calls, ranking and optional vision checks share one boundary. |
| PPTX export | Split into `pptx_export.py` | Export owns in-memory document assembly and scene/image coordination. |

## Verification

The main directory passes 28 unit tests (`python -B -m unittest discover`). Browser checks
covered the four template styles at 390/768/1440/1920 pixels and the image-search-failure
choices. The UI companion project passed its SSR accessibility tests, lint, and build.

No live AI/image provider calls or Vercel deployment were used in verification.
