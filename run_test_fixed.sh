#!/bin/bash
# Fix PyTorch TLS memory issue on Jetson with Python 3.8

export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

echo "[FIX] LD_PRELOAD set to: $LD_PRELOAD"
echo ""

cd ~/Desktop/VisionPilot-XR-Linux

echo "[TEST] Running MLP Debug Test with LD_PRELOAD fix..."
python3 test_margin_debug.py

echo ""
echo "[DONE] Test complete"

