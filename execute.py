"""Vision Sidecar — manual maintenance script.

Triggered from Settings → Plugins → Vision Sidecar (Execute). Useful after an
A0 update that overwrote plugins/_model_config: re-applies the Vision-slot
patch idempotently (already-patched files are skipped). The install hook does
this automatically on plugin install, so most users never need this.
"""
import sys
from pathlib import Path


def main() -> int:
    try:
        hooks = Path(__file__).resolve().parent / "hooks.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("vision_sidecar_hooks", hooks)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.install()
        print("Vision Sidecar maintenance completed successfully.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
