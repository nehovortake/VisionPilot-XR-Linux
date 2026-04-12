#!/bin/bash
# Ultimate PyTorch TLS fix for Jetson

# Method 1: Set in environment
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

# Method 2: Preload before Python
if [ -f /usr/lib/aarch64-linux-gnu/libgomp.so.1 ]; then
    export LD_PRELOAD="/usr/lib/aarch64-linux-gnu/libgomp.so.1:$LD_PRELOAD"
fi

# Method 3: Set Python flags
export PYTHONHASHSEED=0

echo "[LAUNCHER] Environment set:"
echo "  LD_PRELOAD=$LD_PRELOAD"
echo ""

cd ~/Desktop/VisionPilot-XR-Linux

echo "[LAUNCHER] Running VisionPilot XR..."
echo ""

# Run main.py
python3 main.py

