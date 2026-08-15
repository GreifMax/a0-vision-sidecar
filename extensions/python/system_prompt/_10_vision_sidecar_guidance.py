from helpers.extension import Extension

_GUIDANCE_DELEGATED = (
    "Vision Sidecar active: vision_load accepts paths as string or list (array preferred) and offers `query` + `raw`.\n"
    "- A dedicated Vision Model IS configured (Model Presets \u2192 Vision Model): vision_load will DELEGATE. Send a focused `query` about the images\n"
    "  (e.g. \"read the top-right error toast\", \"locate the login button and describe where\") \u2014 you'll get a concise text capsule, not raw pixels in main.\n"
    "  This saves ~1500 tok/image. Use `raw=true` only when you truly need main to see pixels (side-by-side comparison).\n"
)
_GUIDANCE_DIRECT = (
    "Vision Sidecar active: vision_load accepts paths as string or list (array preferred) and offers `query` + `raw`.\n"
    "- No dedicated Vision Model set; vision_load injects images directly for Main's vision. Leave Vision empty to use Main's vision;\n"
    "  set Model Presets \u2192 Vision Model to enable query-conditioned delegation (recommended when Main has no vision, e.g. GLM/DeepSeek).\n"
    "  Use `query` to be specific with delegation, `raw=true` to force direct injection even when delegated.\n"
)
_NO_VISION_MSG = (
    "Vision note: Main has no vision and no Vision Model is set (Model Presets \u2192 Vision Model). "
    "vision_load is available but Main may not see images. Configure a cheap Vision Model in Model Presets to enable query-conditioned delegation. "
    "Delegated calls return a text capsule; use raw=true to inject pixels directly if needed."
)

class VisionSidecarGuidance(Extension):
    async def execute(self, system_prompt: list[str] | None = None, **kwargs):
        if system_prompt is None:
            return
        try:
            from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model
            from plugins._model_config.helpers.model_config import get_chat_model_config
            has_sidecar = has_vision_model(self.agent)
            main_vision = bool(get_chat_model_config(self.agent).get("vision", False))
            if has_sidecar:
                system_prompt.append(_GUIDANCE_DELEGATED)
            elif main_vision:
                system_prompt.append(_GUIDANCE_DIRECT)
            else:
                system_prompt.append(_NO_VISION_MSG)
        except Exception:
            try:
                system_prompt.append(_GUIDANCE_DIRECT)
            except Exception:
                pass
