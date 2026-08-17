from __future__ import annotations

from typing import Any

import models

DEFAULT_DELEGATED_SYSTEM = (
    "You are a precise vision analyst. Answer only what was asked about the image(s). "
    "Be concise, factual, mention positions/coordinates when asked to locate."
)

def get_behaviour(agent: Any = None) -> dict[str, Any]:
    from helpers import plugins
    cfg = plugins.get_plugin_config("vision_sidecar", agent=agent) or {}
    b = cfg.get("behaviour") or {}
    if not isinstance(b, dict):
        b = {}
    return {
        "delegated_system": str(b.get("delegated_system") or DEFAULT_DELEGATED_SYSTEM),
        "max_tokens": int(b.get("max_tokens") or 2000),
        "timeout": float(b.get("timeout") or 300),
    }

def get_vision_model_config(agent: Any = None) -> dict[str, Any]:
    """Read Vision Model from Model Presets (vision slot), not from sidecar config.

    Preset storage is in _model_config plugin: PRESET_SLOT_CONFIG_SECTIONS["vision"] = "vision_model".
    Uses get_effective_config so per-chat overrides are respected.
    """
    try:
        from plugins._model_config.helpers.model_config import get_effective_config
        cfg = get_effective_config(agent) or {}
        vm = cfg.get("vision_model") or {}
        if not isinstance(vm, dict):
            return {}
        provider = str(vm.get("provider") or "").strip()
        name = str(vm.get("name") or "").strip()
        if not provider and not name:
            return {}
        return vm
    except Exception:
        return {}

def has_vision_model(agent: Any = None) -> bool:
    vm = get_vision_model_config(agent)
    if not (vm.get("provider") and vm.get("name")):
        return False
    try:
        from plugins._model_config.helpers.model_config import get_chat_model_config
        chat_cfg = get_chat_model_config(agent) or {}
        if chat_cfg.get("vision", False) and chat_cfg.get("vision_override", False):
            return False  # Main's native vision overrides the Vision Model
    except Exception:
        pass
    return True

def build_vision_model(agent: Any = None):
    vm = get_vision_model_config(agent)
    if not vm:
        return None
    from plugins._model_config.helpers.model_config import build_model_config
    mc = build_model_config(vm, models.ModelType.CHAT)
    mc.vision = True
    return models.get_chat_model(mc.provider, mc.name, model_config=mc, **mc.build_kwargs())

async def call_vision_model(
    agent: Any,
    images_a0_paths: list[str],
    query: str,
    delegated_system: str | None = None,
    timeout: float = 300,
) -> str:
    """Call the dedicated vision preset model with images + query, return text capsule."""
    import asyncio
    from langchain_core.messages import HumanMessage, SystemMessage

    model = build_vision_model(agent)
    if model is None:
        raise RuntimeError("vision_model not configured — set it in Model Presets → Vision Model")

    behaviour = get_behaviour(agent)
    system = (delegated_system or behaviour["delegated_system"]).strip() or DEFAULT_DELEGATED_SYSTEM
    if query and query.strip():
        user_text = query.strip()
    else:
        user_text = "Describe the image(s) precisely. Be concise, mention key objects, text, and layout."

    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for pa in images_a0_paths:
        url = pa
        try:
            import base64
            from pathlib import Path as _Path
            from helpers import files as _files
            from helpers.images import compress_image as _compress
            raw = str(pa or "").strip()
            cand = None
            if raw.startswith("/a0/"):
                cand = _Path(_files.fix_dev_path(raw) if hasattr(_files, "fix_dev_path") else raw)
                if not cand.exists():
                    cand = _Path(raw)
            else:
                cand = _Path(raw)
            if cand and cand.exists() and cand.is_file():
                data = cand.read_bytes()
                if len(data) > 900 * 1024:
                    try:
                        c = _compress(data, max_pixels=1280*960, quality=80)
                        b64 = base64.b64encode(c).decode()
                        url = f"data:image/jpeg;base64,{b64}"
                    except Exception:
                        url = pa
                else:
                    url = pa
        except Exception:
            url = pa
        content.append({"type": "image_url", "image_url": {"url": url}})

    messages = [SystemMessage(content=system), HumanMessage(content=content)]

    async def _call():
        kwargs = {"max_tokens": int(behaviour["max_tokens"])}
        resp, _reason = await model.unified_call(messages=messages, explicit_caching=False, **kwargs)
        return resp
    try:
        return await asyncio.wait_for(_call(), timeout=float(timeout or behaviour["timeout"]))
    except asyncio.TimeoutError:
        raise TimeoutError(f"vision_model timed out after {timeout}s")
