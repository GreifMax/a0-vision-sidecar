#!/usr/bin/env python3
"""Vision Sidecar - add the Vision Model slot to Model Presets (one-time, optional).

Self-contained: no git, no patch(1) needed. Works from any directory.
Usage:
  python3 enable_vision_slot.py            apply (idempotent)
  python3 enable_vision_slot.py --status   show state only
  python3 enable_vision_slot.py --restore  restore backups (.bak)
Docker: run INSIDE the Agent Zero container:
  docker exec -it <container> python3 usr/plugins/vision_sidecar/scripts/enable_vision_slot.py
Override root: A0_ROOT=/path/to/agent-zero python3 enable_vision_slot.py
"""
from __future__ import annotations
import os, shutil, sys
from pathlib import Path

REPO = "https://github.com/GreifMax/a0-vision-sidecar"

def find_a0_root(script_path: Path) -> Path | None:
    env = os.environ.get("A0_ROOT", "").strip()
    cands: list[Path] = []
    # Priority: A0_ROOT env, then CWD walk-up (explicit user intent), then script walk-up
    if env:
        cands.append(Path(env))
    cur = Path.cwd().resolve()
    for _ in range(8):
        cands.append(cur)
        cur = cur.parent
    cur = script_path.resolve()
    for _ in range(8):
        cands.append(cur)
        cur = cur.parent
    for c in cands:
        try:
            c = c.resolve()
        except Exception:
            continue
        if (c / "plugins" / "_model_config" / "helpers" / "model_config.py").is_file():
            return c
    return None

# --- edits ---------------------------------------------------------------
V = "Optional dedicated model for vision_load - used when Main has no vision. Leave empty to use Main's vision."

PY_EDITS = [
 dict(op="insert_after", anchor='    "chat": "chat_model",',
      payload='    "vision": "vision_model",\n', done='"vision": "vision_model"'),
 dict(op="insert_after", anchor="IMPLICIT_PRESET_SLOT_DEFAULTS = {",
      payload='    "vision": {\n        "rl_requests": 0,\n        "rl_input": 0,\n        "rl_output": 0,\n        "kwargs": {},\n    },\n',
      done='"vision": {\n        "rl_requests": 0'),
 dict(op="insert_after", anchor="            slot_clean = _strip_ui_fields(slot_config, strip_api_key=True)",
      payload='            if slot == "vision" and _slot_has_identity(slot_clean):\n                slot_clean["vision"] = True\n                if "max_embeds" not in slot_clean:\n                    slot_clean["max_embeds"] = 10\n',
      done='slot_clean["vision"] = True'),
 dict(op="replace", anchor='for section_name in ("chat_model", "utility_model", "embedding_model"):'.replace('"','\"'),
      new='for section_name in ("chat_model", "vision_model", "utility_model", "embedding_model"):'.replace('"','\"'),
      done='"chat_model", "vision_model", "utility_model"'),
 dict(op="insert_before", anchor="def is_chat_override_allowed",
      payload='def get_vision_model_config(agent=None) -> dict:\n    """Vision model config from the vision preset slot (Vision Sidecar)."""\n    return get_effective_config(agent).get("vision_model", {})\n\n\n',
      done="def get_vision_model_config"),
 dict(op="replace",
      anchor="""        slot_config = _get_preset_slot_config(preset, slot)
        if not _should_apply_preset_slot(slot, slot_config):
            continue
        config[section] = _merge_model_slot(
            slot,
            config.get(section, {}),
            slot_config,
            strip_api_key=strip_api_key,
        )""",
      new="""        slot_config = _get_preset_slot_config(preset, slot)
        if not _should_apply_preset_slot(slot, slot_config):
            if slot == "vision":
                # Vision Sidecar: vision is strictly per-preset — never inherit
                # the Default preset's vision model into other presets.
                config[section] = {}
            continue
        base_slot = config.get(section, {})
        if slot == "vision":
            # Vision Sidecar: merge vision over an empty base so a preset's own
            # vision model replaces, never accumulates on top of, another one.
            base_slot = {}
        config[section] = _merge_model_slot(
            slot,
            base_slot,
            slot_config,
            strip_api_key=strip_api_key,
        )""",
      done='if slot == "vision":'),
]

STORE_EDITS = [
 dict(op="insert_after", anchor="  { key: 'chat_model', title: 'Main Model', desc: 'Primary model for chat, reasoning, and browser tasks.' },",
      payload="  { key: 'vision_model', title: 'Vision Model', desc: \"" + V + "'s vision.' },\n".replace("'s vision.' }", "\\'s vision.' }", 0) if False else "  { key: 'vision_model', title: 'Vision Model', desc: \"Optional dedicated model for vision_load - used when Main has no vision. Leave empty to use Main\\'s vision.\" },\n",
      done="key: 'vision_model'"),
 dict(op="insert_after", anchor="const IMPLICIT_PRESET_SLOT_DEFAULTS = {",
      payload="  vision: {\n    rl_requests: 0,\n    rl_input: 0,\n    rl_output: 0,\n    kwargs: {},\n  },\n",
      done="  vision: {"),
 dict(op="insert_after", anchor="    ['chat', 'chat_model'],",
      payload="    ['vision', 'vision_model'],\n", done="['vision', 'vision_model']"),
 dict(op="insert_after", anchor="      chat_model: slot(rawDefault.chat),",
      payload="      vision_model: slot(rawDefault.vision),\n", done="vision_model: slot(rawDefault.vision)"),
 dict(op="insert_after", anchor="        chat: { ...slot(effective.chat_model), _kwargs_text: kwargsToText(effective.chat_model?.kwargs) },",
      payload="""        vision: {
          ...slot(effective.vision_model),
          // Vision Sidecar: display defaults (64000 / 0.7) when unset
          ...(hasModelIdentity(effective.vision_model || {})
            ? { ctx_length: Number(effective.vision_model?.ctx_length) || 64000, ctx_history: Number(effective.vision_model?.ctx_history ?? 0.7) }
            : { ctx_length: 64000, ctx_history: 0.7 }),
          _kwargs_text: kwargsToText(effective.vision_model?.kwargs),
        },
""",
      done="display defaults (64000 / 0.7) when unset"),
 dict(op="replace",
      anchor="""    const slot = preset?.[slotKey];
    if (!slot || typeof slot !== 'object') continue;
    if (!hasModelIdentity(slot)) continue;
    config[sectionKey] = mergeModelSlot(config[sectionKey] || {}, slot, stripApiKey, slotKey);""",
      new="""    const slot = preset?.[slotKey];
    const isVision = slotKey === 'vision';
    if (!slot || typeof slot !== 'object') {
      if (isVision) config.vision_model = {}; // Vision Sidecar: never inherit from Default
      continue;
    }
    if (!hasModelIdentity(slot)) {
      if (isVision) config.vision_model = {}; // Vision Sidecar: never inherit from Default
      continue;
    }
    // Vision Sidecar: merge vision over an empty base (strictly per-preset)
    config[sectionKey] = mergeModelSlot(isVision ? {} : (config[sectionKey] || {}), slot, stripApiKey, slotKey);""",
      done="const isVision = slotKey === 'vision';"),
 dict(op="replace", anchor="            chat: { provider: '', name: '', api_base: '', kwargs: {}, _kwargs_text: '' },",
      new="            chat: { provider: '', name: '', api_base: '', ctx_length: 200000, ctx_history: 0.7, kwargs: {}, _kwargs_text: '' },\n            vision: { provider: '', name: '', api_base: '', ctx_length: 64000, ctx_history: 0.7, vision: true, max_embeds: 10, kwargs: {}, _kwargs_text: '' },",
      done="vision: { provider: '', name: '', api_base: '', ctx_length: 64000"),
 dict(op="replace", anchor="            utility: { provider: '', name: '', api_base: '', kwargs: {}, _kwargs_text: '' },",
      new="            utility: { provider: '', name: '', api_base: '', ctx_length: 128000, ctx_input: 0.7, kwargs: {}, _kwargs_text: '' },",
      done="utility: { provider: '', name: '', api_base: '', ctx_length: 128000"),
 dict(op="insert_before", anchor="        const preset = {",
      payload="        // ensure Vision slot defaults for new presets (64000 / 0.7)\n        if (!base.vision || typeof base.vision.ctx_length === 'undefined') {\n          base.vision = { provider: '', name: '', api_base: '', ctx_length: 64000, ctx_history: 0.7, vision: true, max_embeds: 10, kwargs: {}, _kwargs_text: '', ...(base.vision || {}) };\n        }\n",
      done="base.vision = { provider: ''"),
 dict(op="replace", anchor="      for (const slot of ['chat', 'utility']) {",
      new="      for (const slot of ['chat', 'vision', 'utility']) {",
      done="['chat', 'vision', 'utility']"),
 dict(op="replace", anchor="          if (hasModelIdentity(rest)) c[slot] = rest;",
      new="          if (hasModelIdentity(rest)) {\n            if (slot === 'vision') { rest.vision = true; if (!('max_embeds' in rest)) rest.max_embeds = 10; }\n            c[slot] = rest;\n          }",
      done="rest.vision = true"),
 dict(op="insert_after", anchor="      { icon: 'chat', title: 'Main', cfg: preset?.chat, pList: chatP },",
      payload="      { icon: 'eye', title: 'Vision', cfg: preset?.vision, pList: chatP },\n",
      done="title: 'Vision'"),
 dict(op="replace",
      anchor="""    ].map(s => ({ icon: s.icon, title: s.title, provider: label(s.pList, s.cfg?.provider), name: s.cfg?.name || '\\u2014' }));""",
      new="""    ].map(s => {
      const overridden = s.title === 'Vision'
        && (s.cfg?.provider || s.cfg?.name)
        && preset?.chat?.vision
        && preset?.chat?.vision_override;
      return {
        icon: s.icon,
        title: s.title,
        provider: label(s.pList, s.cfg?.provider),
        name: s.cfg?.name || '\\u2014',
        note: overridden ? 'Overwritten by Main' : '',
      };
    });""",
      done="note: overridden"),
]

OVERVIEW_EDITS = [
 dict(op="replace",
      anchor="""          <span class="model-preset-identity">
            <span class="model-preset-provider" x-text="model.provider"></span>
            <span class="model-preset-separator">/</span>
            <span x-text="model.name"></span>
          </span>""",
      new="""          <span class="model-preset-identity">
            <template x-if="model.note">
              <span class="model-preset-note" x-text="model.note"></span>
            </template>
            <template x-if="!model.note">
              <span class="model-preset-plain">
                <span class="model-preset-provider" x-text="model.provider"></span>
                <span class="model-preset-separator">/</span>
                <span x-text="model.name"></span>
              </span>
            </template>
          </span>""",
      done="model-preset-note"),
 dict(op="replace",
      anchor="""    .model-preset-separator {
      margin: 0 0.25rem;
    }""",
      new="""    .model-preset-separator {
      margin: 0 0.25rem;
    }

    .model-preset-note {
      opacity: 0.65;
      font-style: italic;
    }""",
      done=".model-preset-note {"),
]

MAIN_SECTION = (
"            <section class=\"preset-model-section\">\n"
"              <div class=\"preset-model-heading\">\n"
"                <div class=\"section-title\">Vision Model</div>\n"
"                <div class=\"section-description\">" + V + "</div>\n"
"              </div>\n"
"              <div x-data=\"{ get model() { return selectedPreset.vision; }, modelType: 'vision', providers: $store.modelConfig.chatProviders, searchType: 'chat', apiKeyMode: 'store', get providerFallback() { return selectedPreset.chat.provider; }, get apiBaseFallback() { return selectedPreset.chat.api_base; } }\">\n"
"                <x-component path=\"/plugins/_model_config/webui/model-field.html\"></x-component>\n"
"              </div>\n"
"            </section>\n"
"\n"
)

MAIN_EDITS = [
 dict(op="insert_before_back", anchor="Utility Model</div>", back='<section class="preset-model-section">',
      payload=MAIN_SECTION, done="section-title\">Vision Model</div>"),
]

SWITCHER_BLOCK = (
"                    <template x-if=\"preset.vision?.name && !(preset.chat?.vision && preset.chat?.vision_override)\">\n"
"                      <div class=\"model-switcher-model-row\">\n"
"                        <span class=\"model-switcher-model-label\">Vision</span>\n"
"                        <span class=\"model-switcher-model-value\">\n"
"                          <span x-text=\"preset.vision.provider\" style=\"opacity:0.5;\"></span>\n"
"                          <span style=\"opacity:0.3; margin:0 3px;\">/</span>\n"
"                          <span x-text=\"preset.vision.name\"></span>\n"
"                        </span>\n"
"                      </div>\n"
"                    </template>\n"
)
SWITCHER_EDITS = [
 dict(op="replace_optional", anchor='<template x-if="preset.vision?.name">',
      new='<template x-if="preset.vision?.name && !(preset.chat?.vision && preset.chat?.vision_override)">',
      done="preset.vision?.name && !(preset.chat?.vision && preset.chat?.vision_override)"),
 dict(op="insert_before", anchor='<template x-if="preset.utility?.name">', payload=SWITCHER_BLOCK,
      done="preset.vision?.name && !(preset.chat?.vision && preset.chat?.vision_override)"),
]

FIELD_EDITS = [
 dict(op="replace_occurrence", anchor='<template x-if="modelType === \'chat\'">', occurrence=2,
      new='<template x-if="modelType === \'chat\' || modelType === \'vision\'">',
      done="modelType === 'chat' || modelType === 'vision'"),
 dict(op="replace", anchor='<template x-if="model.vision">',
      new='<template x-if="model.vision || modelType === \'vision\'">',
      done="model.vision || modelType === 'vision'"),
 dict(op="replace", anchor="Maximum number of embedded images used by the chat model. Set to 0 for unlimited.",
      new="Maximum number of embedded images used by the model. Set to 0 for unlimited.",
      done="used by the model. Set to 0"),
]

FIELD_OVERRIDE_BLOCK = ("""    <!-- Vision Model override (Main chat only) -->
    <template x-if="modelType === 'chat' && model.vision">
      <div class="field">
        <div class="field-label">
          <div class="field-title">Overrides Vision Model</div>
          <div class="field-description">If enabled, this model's native vision is always used and the preset's Vision Model is ignored. If disabled, the dedicated Vision Model handles vision when configured.</div>
        </div>
        <div class="field-control">
          <label class="toggle">
            <input type="checkbox" x-model="model.vision_override" />
            <span class="toggler"></span>
          </label>
        </div>
      </div>
    </template>

""")

FIELD_EDITS.append(dict(op="insert_before", anchor="<!-- Context window size (main and utility only) -->",
      payload=FIELD_OVERRIDE_BLOCK, done="Overrides Vision Model"))

RESPONSES_EDITS = [
 # New A0 (2026-08+): stock _vision_tool_prompt exists -> make it Vision Sidecar aware.
 dict(op="replace_optional",
      anchor='def _vision_tool_prompt(agent: Any) -> str:\n    try:\n        from plugins._model_config.helpers.model_config import get_chat_model_config\n\n        if not get_chat_model_config(agent).get("vision", False):\n            return ""\n        return agent.read_prompt("agent.system.tools_vision.md")\n    except Exception:\n        return ""\n\n\n',
      new='def _vision_tool_prompt(agent: Any) -> str:\n    try:\n        from plugins._model_config.helpers.model_config import get_chat_model_config\n    except Exception:\n        return ""\n    # Vision Sidecar: a dedicated Vision Model takes precedence over main vision.\n    try:\n        from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model\n\n        if has_vision_model(agent):\n            return agent.read_prompt("vision_sidecar.delegated.md")\n    except Exception:\n        pass\n    try:\n        if not get_chat_model_config(agent).get("vision", False):\n            return ""\n        return agent.read_prompt("agent.system.tools_vision.md")\n    except Exception:\n        return ""\n\n\n',
      done='Vision Sidecar: a dedicated Vision Model takes precedence over main vision.'),
 # Older A0: no _vision_tool_prompt -> insert the sidecar-aware function.
 dict(op="insert_before", anchor="def _include_local_tool_prompt(",
      payload='def _vision_tool_prompt(agent: Any) -> str:\n    try:\n        from plugins._model_config.helpers.model_config import get_chat_model_config\n    except Exception:\n        return ""\n    # Vision Sidecar: a dedicated Vision Model takes precedence over main vision.\n    try:\n        from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model\n\n        if has_vision_model(agent):\n            return agent.read_prompt("vision_sidecar.delegated.md")\n    except Exception:\n        pass\n    try:\n        if not get_chat_model_config(agent).get("vision", False):\n            return ""\n        return agent.read_prompt("agent.system.tools_vision.md")\n    except Exception:\n        return ""\n\n\n',
      done='Vision Sidecar: a dedicated Vision Model takes precedence over main vision.'),
 # Older A0: hook the vision prompt into _local_tool_prompts.
 dict(op="replace_optional",
      anchor='        tool_name = _tool_name_from_prompt(prompt, fallback=fallback_name)\n        if not _include_local_tool_prompt(agent, tool_name):\n            continue\n        result.append((tool_name, prompt))\n    return result',
      new='        tool_name = _tool_name_from_prompt(prompt, fallback=fallback_name)\n        if not _include_local_tool_prompt(agent, tool_name):\n            continue\n        result.append((tool_name, prompt))\n\n    vision_prompt = _vision_tool_prompt(agent)\n    if vision_prompt:\n        result.append(("vision_load", vision_prompt))\n    return result',
      done='vision_prompt = _vision_tool_prompt(agent)'),
]

PARALLEL_EDITS = [
 dict(op="replace",
      anchor='    try:\n        job.log_item.update(content=content)\n    except Exception:\n        pass\n',
      new='    try:\n        # Avoid duplicating text that the tool already placed in the "result"\n        # kvps row of the step table. When the tool\'s result row matches the\n        # job result, skip the body content write so the step shows the text\n        # only once (inside the Result row).\n        existing_result = (job.log_item.kvps or {}).get("result") if job.state == "success" else None\n        if existing_result is not None and str(existing_result).strip() == str(content).strip():\n            return\n        job.log_item.update(content=content)\n    except Exception:\n        pass\n',
      done="Avoid duplicating text that the tool already placed"),
]

TOOLSPROMPT_EDITS = [
 # Vision block is identical in old and new stock.
 dict(op="replace",
      anchor='    # vision support\n    from plugins._model_config.helpers.model_config import get_chat_model_config\n\n    chat_cfg = get_chat_model_config(agent)\n    if chat_cfg.get("vision", False):\n        prompt += "\\n\\n" + agent.read_prompt("agent.system.tools_vision.md")\n',
      new='    # vision support (Vision Sidecar: dedicated Vision Model takes precedence)\n    from plugins._model_config.helpers.model_config import get_chat_model_config\n\n    chat_cfg = get_chat_model_config(agent)\n    try:\n        from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model\n\n        has_sidecar = has_vision_model(agent)\n    except Exception:\n        has_sidecar = False\n    if has_sidecar:\n        prompt += "\\n\\n" + agent.read_prompt("vision_sidecar.delegated.md")\n    elif chat_cfg.get("vision", False):\n        prompt += "\\n\\n" + agent.read_prompt("agent.system.tools_vision.md")\n',
      done='(Vision Sidecar: dedicated Vision Model takes precedence)'),
]

FILES = [
 ("plugins/_model_config/helpers/model_config.py", PY_EDITS),
 ("plugins/_model_config/webui/model-config-store.js", STORE_EDITS),
 ("plugins/_model_config/webui/main.html", MAIN_EDITS),
 ("plugins/_model_config/extensions/webui/chat-input-progress-start/model-switcher.html", SWITCHER_EDITS),
 ("plugins/_model_config/webui/model-field.html", FIELD_EDITS),
 ("plugins/_model_config/webui/preset-overview.html", OVERVIEW_EDITS),
 ("helpers/responses_tools.py", RESPONSES_EDITS),
 ("extensions/python/system_prompt/_11_tools_prompt.py", TOOLSPROMPT_EDITS),
 ("helpers/parallel_tools.py", PARALLEL_EDITS),
]

def line_start(text: str, idx: int) -> int:
    return text.rfind("\n", 0, idx) + 1

def apply_edit(text: str, e: dict):
    done = e.get("done", "")
    if done and done in text:
        return text, "already"
    op, anchor = e["op"], e["anchor"]
    if op == "replace":
        if anchor not in text: return text, "ANCHOR NOT FOUND"
        return text.replace(anchor, e["new"], 1), "ok"
    if op == "replace_occurrence":
        occ, cur, seen = e["occurrence"], -1, 0
        while True:
            cur = text.find(anchor, cur + 1)
            if cur < 0: break
            seen += 1
            if seen == occ:
                return text[:cur] + e["new"] + text[cur + len(anchor):], "ok"
        return text, f"OCCURRENCE {occ} NOT FOUND ({seen} total)"
    if op == "replace_optional":
        if anchor not in text:
            return text, "skip"
        return text.replace(anchor, e["new"], 1), "ok"
    if op == "insert_after":
        idx = text.find(anchor)
        if idx < 0: return text, "ANCHOR NOT FOUND"
        nl = text.find("\n", idx + len(anchor))
        ins = nl + 1 if nl >= 0 else len(text)
        return text[:ins] + e["payload"] + text[ins:], "ok"
    if op == "insert_before":
        idx = text.find(anchor)
        if idx < 0: return text, "ANCHOR NOT FOUND"
        ins = line_start(text, idx)
        return text[:ins] + e["payload"] + text[ins:], "ok"
    if op == "insert_before_back":
        pos = text.find(e["anchor"])
        if pos < 0: return text, "ANCHOR NOT FOUND"
        back = text.rfind(e["back"], 0, pos)
        if back < 0: return text, "BACK ANCHOR NOT FOUND"
        ins = line_start(text, back)
        return text[:ins] + e["payload"] + text[ins:], "ok"
    return text, "UNKNOWN OP"

def run(status_only: bool = False, restore: bool = False) -> int:
    root = find_a0_root(Path(__file__))
    print(f"Vision Sidecar patcher  |  repo: {REPO}")
    if root is None:
        print("ERROR: Agent Zero root not found (plugins/_model_config/helpers/model_config.py).", file=sys.stderr)
        print("  - run from inside the Agent Zero folder (or its container):", file=sys.stderr)
        print("    docker exec -it <container> python3 usr/plugins/vision_sidecar/scripts/enable_vision_slot.py", file=sys.stderr)
        print("  - or set A0_ROOT=/path/to/agent-zero", file=sys.stderr)
        return 1
    print(f"A0 root: {root}\n")
    any_fail, changed = False, []
    for rel, edits in FILES:
        p = root / rel
        if not p.is_file():
            print(f"  MISSING FILE: {rel}"); any_fail = True; continue
        bak = p.with_suffix(p.suffix + ".vision_sidecar.bak")
        if restore:
            if bak.is_file():
                current = ""
                try:
                    current = p.read_text(encoding="utf-8")
                except Exception:
                    pass
                still_patched = any(e.get("done", "") and e["done"] in current for e in edits)
                if still_patched:
                    shutil.copy2(bak, p); bak.unlink(); print(f"  restored  {rel}")
                else:
                    print(f"  skipped   {rel} (no Vision Sidecar edits present — core may have been updated; keeping current file)")
            else:
                print(f"  no backup {rel}")
            continue
        text = p.read_text(encoding="utf-8")
        report, modified = [], False
        for e in edits:
            text, res = apply_edit(text, e)
            if res == "ok": modified = True
            report.append(res)
        if status_only:
            print(f"  {rel}: " + ", ".join(report)); continue
        if modified:
            if not bak.is_file():
                shutil.copy2(p, bak)
            p.write_text(text, encoding="utf-8")
            changed.append(rel)
        bad = [r for r in report if r not in ("ok", "already", "skip")]
        icon = "FAIL" if bad else ("PATCHED" if modified else "already")
        print(f"  {icon:8} {rel}" + (f"  ({'; '.join(bad)})" if bad else ""))
        if bad: any_fail = True
    if restore: return 0
    print()
    if any_fail:
        print("Some anchors were not found - your A0 version may be newer/older than supported.")
        print(f"Restore originals with --restore, or open an issue: {REPO}/issues")
        return 1
    if changed:
        print("Done. Restart Agent Zero, then hard-refresh the browser (Ctrl+Shift+R).")
        print("Model Presets now shows: Main / Vision / Utility / Embedding.")
        return 0
    print("Everything already patched - nothing to do.")
    return 0

def main():
    status_only = "--status" in sys.argv
    restore = "--restore" in sys.argv
    rc = run(status_only=status_only, restore=restore)
    if rc:
        sys.exit(rc)


if __name__ == "__main__":
    main()
