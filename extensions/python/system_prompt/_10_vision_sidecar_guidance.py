from helpers.extension import Extension

_D = "Vision Sidecar active: a dedicated Vision Model IS configured (Model Presets -> Vision Model). vision_load DELEGATES:"
_D += chr(10) + "- send a focused query about the images (e.g. read the top-right error toast, locate the login button and give its position) - you will get a concise text capsule, not pixels."
_D += chr(10) + "- if Main cannot see images, ~1500 tok/image stays out of your context (capsule only); if Main is vision-capable, the images are also attached to history alongside the capsule. Use raw=true only when you need pixels without a capsule (e.g. side-by-side comparison)."
_GUIDANCE_DELEGATED = _D


class VisionSidecarGuidance(Extension):
    async def execute(self, system_prompt: list[str] | None = None, **kwargs):
        # With no dedicated Vision Model the plugin is fully stock: no guidance,
        # stock prompt, stock result format.
        if system_prompt is None:
            return
        try:
            from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model
            if not has_vision_model(self.agent):
                return
        except Exception:
            return
        system_prompt.append(_GUIDANCE_DELEGATED)
