#!/usr/bin/env python3
"""Vision Sidecar — add Vision Model tab to Model Presets (optional, one-time)."""
from pathlib import Path
import subprocess, sys
plugin_dir = Path(__file__).resolve().parents[1]
# A0 root is 3 parents up from usr/plugins/vision_sidecar/scripts/
candidates = [plugin_dir.parents[2], Path.cwd(), plugin_dir.parent.parent.parent]
a0_root = None
for c in candidates:
    if (c / "plugins/_model_config/helpers/model_config.py").exists():
        a0_root = c; break
if a0_root is None:
    print("ERROR: cannot find plugins/_model_config — run from Agent Zero root.", file=sys.stderr); sys.exit(1)
target = a0_root / "plugins/_model_config/helpers/model_config.py"
if '"vision": "vision_model"' in target.read_text():
    print("Vision slot already present — nothing to do."); sys.exit(0)
patch = plugin_dir / "patches/vision_preset.patch"
if not patch.exists():
    patch = a0_root / "usr/plugins/vision_sidecar/patches/vision_preset.patch"
if not patch.exists():
    print(f"ERROR: patch not found: {patch}", file=sys.stderr); sys.exit(1)
try:
    subprocess.run(["git","apply","--whitespace=nowarn", str(patch)], cwd=str(a0_root), check=True)
    print("Patched plugins/_model_config (Main / Vision / Utility / Embedding). Restart Agent Zero and hard-refresh browser.")
except FileNotFoundError:
    subprocess.run(["patch","-p1","-i", str(patch)], cwd=str(a0_root), check=True)
    print("Patched via patch(1).")
