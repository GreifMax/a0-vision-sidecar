# Vision Sidecar

![Vision Sidecar](webui/thumbnail.jpg)

Tolerant `vision_load` + optional dedicated Vision Model.

## Why

Two recurring pain points in Agent Zero:

1. **Bare-string bug.** Core `vision_load` requires `paths` as a list. A bare string `"/a.png"` is iterated char-by-char, loads 0 images, and wastes a turn with no error.
2. **No vision, no images.** Frontier reasoners (GLM 5.2/5.3, DeepSeek V4 Flash/Pro) are cheap and strong but have no vision. On stock A0 that means no `vision_load` at all — even though a cheap `gpt-4o-mini` or `qwen2-vl` could read the image for pennies.

Vision Sidecar fixes both in one plugin.

## What it does

### 1. Tolerant `vision_load`

`vision_load` now accepts `paths` as `string` or `list[str]`.

- `{"paths": "/a.png"}` is treated as `["/a.png"]`
- Handles harness quirks: JSON-encoded array strings (`"[\"/a.png\"]"`), quoted single paths (`"\"/a.png\""`) 
- Wrong types return a clear tool error — never a `Message misformat`

### 2. Delegated Vision Model

Configure an optional **Vision Model** in **Settings → Model Presets → Vision Model**.

> Optional dedicated model for vision_load — used when Main has no vision. Leave empty to use Main's vision.

When set:

- `vision_load(paths, query?, raw?)` materializes images, calls the Vision Model with `query + images`, and returns a **text capsule** instead of injecting `~1500 tok/image` into the main history.
- Your Main (GLM, DeepSeek) never sees raw pixels — only ~300 tokens of focused text. Saves thousands of tokens per future turn.
- `query` is a focused instruction: `"read the top-right error toast"`, `"locate the login button and give coordinates"`. Empty → generic precise description.
- `raw=true` bypasses delegation and injects images directly into Main. Use for side-by-side comparison when Main must see pixels.
- Large images over ~900 KB are auto-compressed to 1280×960 JPEG before the vision call to avoid `Request Entity Too Large` (4 MB PNG → ~250 KB).

When empty: legacy path — images are injected as `RawMessage` for `chat_model.vision == true`, appearance identical to stock A0.

Preset defaults for the Vision slot: **64000 context, 70% for history** (new presets only). Existing presets are untouched.

## Requirements

- Agent Zero. If your **Settings → Model Presets → Edit** already shows **Main / Vision / Utility / Embedding** (only if you're updating the plugin), nothing else to do.
- If it only shows **Main / Utility / Embedding** (on any A0 instance), run the one-time Vision-slot patch below — otherwise Vision Sidecar still works, but `vision_load` falls back to tolerant direct injection (no delegation).
- Any LiteLLM-compatible vision model for the Vision slot (tested with `openai/gpt-4o-mini`, `qwen2-vl`).

## Installation

### From ZIP

1. Download `vision_sidecar.zip` from Releases
2. Agent Zero → **Settings → Plugins → Install → From ZIP** → select the ZIP
3. Add the Vision slot via the script (check below)
4. Restart the WebUI (`Ctrl+Shift+R`)

### From Git

```bash
git clone https://github.com/GreifMax/a0-vision-sidecar
cp -r a0-vision_sidecar /a0/usr/plugins/vision_sidecar
# restart Agent Zero
```

### Add Vision slot

The installer is **self-contained pure Python** — no git or `patch(1)` required, idempotent, and creates `.vision_sidecar.bak` backups of every modified file.

```bash
# any directory works; it auto-finds the Agent Zero root
bash /a0/usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
# or:  python3 /a0/usr/plugins/vision_sidecar/scripts/enable_vision_slot.py
```

Docker (run **inside** the Agent Zero container, not on the host — `plugins/` only exists in the image):

```bash
docker exec -it <agent-zero-container> bash /a0/usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
```

Options:

| Command | Effect |
| --- | --- |
| (no args) | Apply patch (skips files already patched) |
| `--status` | Show per-file state without changing anything |
| `--restore` | Restore all original files from `.bak` backups |

If auto-detection fails, point it at your install: `A0_ROOT=/path/to/agent-zero bash enable_vision_slot.sh`.

Then restart Agent Zero and hard-refresh the browser (Ctrl+Shift+R). Model Presets will show **Main / Vision / Utility / Embedding**.

> Note: A0 updates can overwrite `plugins/_model_config`. After updating, rerun the script — it is idempotent and will re-apply cleanly.

## Configuration

1. **Settings → Model Presets → Edit** → fill **Vision Model** with your cheap vision helper (provider + name + key). Leave empty to use Main's vision.
2. **Settings → Plugins → Vision Sidecar** → tune the delegated system prompt and timeout if needed.

New presets automatically get `Vision: 64000 / 0.7`. Current presets keep their values.

## Usage (By A0)

```json
{
  "tool_name": "vision_load",
  "tool_args": {
    "paths": ["/a0/usr/uploads/screenshot.png"],
    "query": "read the error message in the top-right"
  }
}
```

- With Vision Model set → chat shows thumbnails + `Loaded images: 1 … [Vision analysis via dedicated vision model — query: "…"]` + capsule text.
- With `raw=true` → forces direct injection even when Vision Model is set.
- Without Vision Model → standard `Loaded images: N` with thumbnails for Main vision.

## File layout

```
plugin.yaml
default_config.yaml
LICENSE
README.md
thumbnail.jpg              ← plugin list image (256×256, ≤20 KB)
helpers/vision_model.py    ← preset-aware vision dispatch + compression
tools/vision_load.py       ← tolerant paths + delegation
prompts/agent.system.tool.vision_load.md
extensions/python/system_prompt/_10_vision_sidecar_guidance.py
webui/config.html
webui/thumbnail.jpg/png
```

## License

MIT — see [LICENSE](LICENSE).
