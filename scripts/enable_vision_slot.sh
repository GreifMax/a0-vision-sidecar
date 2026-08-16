#!/usr/bin/env bash
set -e
# Vision Sidecar — add Vision Model tab to Model Presets (optional, one-time)
# Run AFTER installing the plugin, from ANY directory:
#   bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
#   bash /a0/usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
#   bash ./enable_vision_slot.sh  (when cd'd into scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find A0 root: walk up from PLUGIN_DIR (covers installed case: .../usr/plugins/vision-sidecar)
# and also from CWD (covers repo-clone case). Max 6 levels.
find_a0_root() {
  local d
  for d in "$PLUGIN_DIR" "$PLUGIN_DIR/.." "$PLUGIN_DIR/../.." "$PLUGIN_DIR/../../.." "$PLUGIN_DIR/../../../.." "$(pwd)" "$(pwd)/.." "$(pwd)/../.."; do
    d="$(cd "$d" 2>/dev/null && pwd || true)"
    if [ -f "$d/plugins/_model_config/helpers/model_config.py" ]; then
      echo "$d"; return 0
    fi
  done
  return 1
}
A0_ROOT="$(find_a0_root || true)"
if [ -z "$A0_ROOT" ]; then
  echo "ERROR: cannot find Agent Zero root (plugins/_model_config/helpers/model_config.py not found)." >&2
  echo "  PLUGIN_DIR=$PLUGIN_DIR  CWD=$(pwd)" >&2
  echo "  Run from the Agent Zero root, e.g.:  bash a0/usr/plugins/vision-sidecar/scripts/enable_vision_slot.sh" >&2
  exit 1
fi
PATCH="$PLUGIN_DIR/patches/vision_preset.patch"
if [ ! -f "$PATCH" ]; then PATCH="$A0_ROOT/usr/plugins/vision_sidecar/patches/vision_preset.patch"; fi
if [ ! -f "$PATCH" ]; then PATCH="$A0_ROOT/patches/vision_preset.patch"; fi

echo "Plugin dir: $PLUGIN_DIR"
echo "A0 root:    $A0_ROOT"
echo "Patch:      $PATCH"

if grep -q '"vision": "vision_model"' "$A0_ROOT/plugins/_model_config/helpers/model_config.py" 2>/dev/null; then
  echo "Vision slot already present — nothing to do."
  exit 0
fi
if [ ! -f "$PATCH" ]; then echo "ERROR: patch not found: $PATCH" >&2; exit 1; fi
cd "$A0_ROOT"
echo "Applying patch..."
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git apply --whitespace=nowarn "$PATCH" && echo "Patched plugins/_model_config (Main / Vision / Utility / Embedding). Restart Agent Zero and hard-refresh browser (Ctrl+Shift+R)."
else
  # fallback to patch utility
  if ! command -v patch >/dev/null 2>&1; then echo "ERROR: neither git nor patch found" >&2; exit 1; fi
  patch -p1 < "$PATCH" && echo "Patched via patch(1). Restart Agent Zero and hard-refresh browser."
fi
