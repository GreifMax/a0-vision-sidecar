#!/usr/bin/env bash
set -e
# Vision Sidecar — add Vision Model tab to Model Presets (optional, one-time)
# Run from Agent Zero root: bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
A0_ROOT="$(cd "$PLUGIN_DIR/../.." && pwd)"
# when plugin is a git clone at repo root, A0_ROOT is the repo itself
if [ ! -f "$A0_ROOT/plugins/_model_config/helpers/model_config.py" ]; then
  # fall back: assume we're already at A0 root
  A0_ROOT="$(pwd)"
fi
PATCH="$PLUGIN_DIR/patches/vision_preset.patch"
if [ ! -f "$PATCH" ]; then
  PATCH="$A0_ROOT/usr/plugins/vision_sidecar/patches/vision_preset.patch"
fi
if grep -q '"vision": "vision_model"' "$A0_ROOT/plugins/_model_config/helpers/model_config.py" 2>/dev/null; then
  echo "Vision slot already present — nothing to do."
  exit 0
fi
if [ ! -f "$PATCH" ]; then
  echo "ERROR: patch not found: $PATCH" >&2; exit 1
fi
cd "$A0_ROOT"
if command -v git >/dev/null 2>&1; then
  git apply --whitespace=nowarn "$PATCH" && echo "Patched plugins/_model_config (Main / Vision / Utility / Embedding). Restart Agent Zero and hard-refresh browser."
else
  patch -p1 < "$PATCH" && echo "Patched via patch(1)."
fi
