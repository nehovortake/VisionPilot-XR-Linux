#!/bin/bash
# Wrapper script - sets LD_PRELOAD in shell BEFORE Python starts

export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

echo "[WRAPPER] LD_PRELOAD=$LD_PRELOAD"
echo ""

cd ~/Desktop/VisionPilot-XR-Linux

python3 test_mlp_live.py

