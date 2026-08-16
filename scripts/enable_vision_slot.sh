#!/usr/bin/env bash
# Vision Sidecar - add the Vision Model slot to Model Presets (one-time, optional)
# Thin wrapper: all logic lives in enable_vision_slot.py (no git / patch(1) needed).
# Run AFTER installing the plugin, from ANY directory:
#   bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
#   bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh --status
#   bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh --restore
# Docker (run INSIDE the container):
#   docker exec -it <container> bash usr/plugins/vision_sidecar/scripts/enable_vision_slot.sh
# Force a root when auto-detect fails:  A0_ROOT=/path/to/agent-zero bash ./enable_vision_slot.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SCRIPT_DIR/enable_vision_slot.py"
if [ ! -f "$PY" ]; then
  echo "ERROR: enable_vision_slot.py not found next to this script." >&2
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$PY" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$PY" "$@"
else
  echo "ERROR: python3 not found in PATH." >&2
  exit 1
fi
