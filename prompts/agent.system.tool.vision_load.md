## multimodal vision tools

### vision_load
load images into the model for visual reasoning
args: `paths` list of absolute image paths or ephemeral image refs, `query` optional string describing what to extract, `raw` optional boolean to force direct image injection
rules:
- `paths` MUST be a JSON array even for one image: `{"paths": ["/path/to/image.png"]}` — a bare string is also accepted for tolerance but array is preferred
- `query` is a focused instruction for the delegated vision helper when a dedicated vision model is configured (e.g. "read the top-right error toast", "locate the login button and describe where"). If empty, a generic precise description is returned.
- `raw` (default false): when true and a dedicated vision model is configured, bypass delegation and inject images directly into the main conversation (only use when you really need the main model to see pixels, e.g. side-by-side comparison). Ignored when no vision model is set.
- load all relevant images in one call when comparing screenshots or pages
- use when the task depends on screenshots, diagrams, scanned documents, charts, or photos
- only bitmaps are supported; convert other formats first if needed
- the tool result includes loaded/skipped image totals and corresponding path lists; when delegated, also includes a concise text capsule from the vision model
example:
```json
{
  "thoughts": [
    "I need to inspect the screenshot before answering."
  ],
  "headline": "Loading screenshot for visual analysis",
  "tool_name": "vision_load",
  "tool_args": {
    "paths": ["/path/to/screenshot.png"],
    "query": "read any error message visible in the top right"
  }
}
```
