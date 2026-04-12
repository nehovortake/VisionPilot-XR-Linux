#!/bin/bash
# VisionPilot XR - Launcher
# Fixes: cannot allocate memory in static TLS block (Jetson/aarch64)
# LD_PRELOAD MUST be set before Python starts, not inside Python code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1) system libgomp (Jetson aarch64) ---
SYS_GOMP="/usr/lib/aarch64-linux-gnu/libgomp.so.1"

# --- 2) PyTorch bundled libgomp (exact path from your error) ---
TORCH_GOMP_GLOB=$(python3 -c "
import glob, sys
pattern = '/home/*/.local/lib/python3.8/site-packages/torch/torch.libs/libgomp*.so*'
matches = glob.glob(pattern)
# also try site-packages/torch/lib/../torch.libs/
pattern2 = '/home/*/.local/lib/python3.8/site-packages/torch.libs/libgomp*.so*'
matches += glob.glob(pattern2)
if matches:
    print(matches[0])
" 2>/dev/null)

# fallback: hardcode from your error message
if [ -z "$TORCH_GOMP_GLOB" ]; then
    TORCH_GOMP_GLOB="/home/feit/.local/lib/python3.8/site-packages/torch/torch.libs/libgomp-6e1a1d1b.so.1.0.0"
fi

# --- 3) also preload libstdc++ ---
STDCPP="/usr/lib/aarch64-linux-gnu/libstdc++.so.6"

# Build LD_PRELOAD
PRELOAD=""
for lib in "$SYS_GOMP" "$TORCH_GOMP_GLOB" "$STDCPP"; do
    if [ -f "$lib" ]; then
        if [ -z "$PRELOAD" ]; then
            PRELOAD="$lib"
        else
            PRELOAD="$PRELOAD:$lib"
        fi
        echo "[LAUNCHER] Preloading: $lib"
    else
        echo "[LAUNCHER] Not found (skip): $lib"
    fi
done

export LD_PRELOAD="$PRELOAD"
echo "[LAUNCHER] LD_PRELOAD=$LD_PRELOAD"
echo "[LAUNCHER] Starting VisionPilot XR..."
echo ""

cd "$SCRIPT_DIR"
exec python3 main.py "$@"
