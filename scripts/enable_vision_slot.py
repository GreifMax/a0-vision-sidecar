#!/usr/bin/env python3
"""Vision Sidecar — add Vision Model tab to Model Presets (optional, one-time).
Run AFTER installing the plugin, from ANY directory."""
from pathlib import Path
import subprocess, sys

script = Path(__file__).resolve()
plugin_dir = script.parents[1]  # .../vision_sidecar

def find_a0_root() -> Path | None:
    candidates = []
    # walk up from plugin_dir (installed: /a0/usr/plugins/vision-sidecar -> /a0)
    cur = plugin_dir
    for _ in range(6):
        candidates.append(cur)
        cur = cur.parent
    # also walk up from CWD (repo-clone or manual run)
    cur = Path.cwd()
    for _ in range(6):
        candidates.append(cur)
        cur = cur.parent
    # plus explicit plugin_dir/../../.. for installed layout
    candidates.append(plugin_dir / "../../..")
    candidates.append(plugin_dir.parents[2] if len(plugin_dir.parents) > 2 else plugin_dir)
    for c in candidates:
        try:
            c = c.resolve()
        except Exception:
            continue
        if (c / "plugins/_model_config/helpers/model_config.py").exists():
            return c
    return None

a0_root = find_a0_root()
if a0_root is None:
    print("ERROR: cannot find Agent Zero root (plugins/_model_config/helpers/model_config.py not found).", file=sys.stderr)
    print(f"  plugin_dir={plugin_dir}  CWD={Path.cwd()}", file=sys.stderr)
    sys.exit(1)

target = a0_root / "plugins/_model_config/helpers/model_config.py"
print(f"Plugin dir: {plugin_dir}")
print(f"A0 root:    {a0_root}")
patch = plugin_dir / "patches/vision_preset.patch"
if not patch.exists():
    patch = a0_root / "usr/plugins/vision_sidecar/patches/vision_preset.patch"
if not patch.exists():
    patch = a0_root / "patches/vision_preset.patch"
print(f"Patch:      {patch}")

if '"vision": "vision_model"' in target.read_text():
    print("Vision slot already present — nothing to do.")
    sys.exit(0)
if not patch.exists():
    print(f"ERROR: patch not found: {patch}", file=sys.stderr); sys.exit(1)
print("Applying patch...")
try:
    subprocess.run(["git","apply","--whitespace=nowarn", str(patch)], cwd=str(a0_root), check=True)
    print("Patched plugins/_model_config (Main / Vision / Utility / Embedding). Restart Agent Zero and hard-refresh browser (Ctrl+Shift+R).")
    sys.exit(0)
except FileNotFoundError:
    pass
except subprocess.CalledProcessError as e:
    # git apply failed (not a git repo or patch doesn't apply) — try patch(1)
    print(f"git apply failed ({e}), trying patch(1)...", file=sys.stderr)
try:
    subprocess.run(["patch","-p1","-i", str(patch)], cwd=str(a0_root), check=True)
    print("Patched via patch(1). Restart Agent Zero and hard-refresh browser (Ctrl+Shift+R).")
except FileNotFoundError:
    print("ERROR: neither git nor patch found", file=sys.stderr); sys.exit(1)
