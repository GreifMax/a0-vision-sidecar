## multimodal vision tools

### vision_load
load images into the model for visual reasoning via the dedicated vision model
args: `paths` list of absolute image paths or ephemeral image refs, `query` optional string describing what to extract, `raw` optional boolean to force direct image injection
Input schema for tool_args:
```json
{
  "type": "object",
  "properties": {
    "paths": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Absolute image paths or ephemeral image refs. A single bare string is also accepted."
    },
    "query": {
      "type": "string",
      "description": "Focused instruction for the vision model, e.g. 'read the top-right error toast' or 'locate the login button and give its position'. If omitted, a generic precise description is returned."
    },
    "raw": {
      "type": "boolean",
      "description": "If true, bypass delegation and inject the images directly into the main model (only when the main model can see images)."
    }
  },
  "required": ["paths"],
  "additionalProperties": false
}
```
rules:
- the focus argument is named exactly `query` — never `Prompt`, `question`, or any other name
- `paths` as a JSON array even for one image: `{"paths": ["/path/to/image.png"]}` — a bare string is also accepted
- a dedicated Vision Model IS configured: you will NOT see the images; vision_load returns a concise text capsule answering your `query`
- write a focused `query` (e.g. "read the top-right error toast", "locate the login button and give its position"); if omitted, a generic precise description is returned
- `raw=true` (default false) bypasses delegation and injects images directly — only use when Main can see images and truly needs pixels (e.g. side-by-side comparison)
- load all relevant images in one call when comparing screenshots or pages; only bitmaps are supported
- large images are auto-compressed before sending
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
