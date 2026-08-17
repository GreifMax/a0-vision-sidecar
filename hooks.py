"""Vision Sidecar lifecycle hooks.

install()    - auto-applies the Vision-slot patch when the plugin is installed
               via the Plugins UI ("Install from ZIP/Git"). No manual script
               needed anymore; scripts/enable_vision_slot.py remains as a
               fallback/debug tool.
pre_update() - re-applies the patch idempotently (A0 updates may overwrite
               plugins/_model_config).
uninstall()  - restores the original _model_config files from .bak backups,
               but only if the current files still contain our edits (never
               clobbers a core update that already replaced them).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HOOKS_CONTEXT: dict = {}


def _run_patcher(**kwargs) -> tuple[bool, str]:
    """Import and run scripts/enable_vision_slot.py::run(). Returns (ok, log)."""
    plugin_dir = Path(__file__).resolve().parent
    patcher = plugin_dir / "scripts" / "enable_vision_slot.py"
    spec = importlib.util.spec_from_file_location("vision_sidecar_patcher", patcher)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lines: list[str] = []
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.run(**kwargs)  # type: ignore[attr-defined]
    lines = [l for l in buf.getvalue().splitlines() if l.strip()]
    return (rc == 0), "\n".join(lines)


def install(hook_context: dict | None = None, **kwargs):
    try:
        ok, log = _run_patcher()
        print("[vision_sidecar] install:")
        print(log)
        if not ok:
            print(
                "[vision_sidecar] Vision-slot patch could not be fully applied. "
                "vision_load still works (tolerant, direct injection); run "
                "scripts/enable_vision_slot.py manually to retry, or report at "
                "https://github.com/GreifMax/a0-vision-sidecar/issues"
            )
    except Exception as e:  # never break the installer
        print(f"[vision_sidecar] install hook skipped: {e}")
    _HOOKS_CONTEXT["installed"] = True
    return None


def pre_update(hook_context: dict | None = None, **kwargs):
    try:
        ok, log = _run_patcher()
        print("[vision_sidecar] pre_update:")
        print(log)
    except Exception as e:
        print(f"[vision_sidecar] pre_update hook skipped: {e}")
    return None


def uninstall(hook_context: dict | None = None, **kwargs):
    try:
        ok, log = _run_patcher(restore=True)
        print("[vision_sidecar] uninstall:")
        print(log)
    except Exception as e:
        print(f"[vision_sidecar] uninstall hook skipped: {e}")
    return None
