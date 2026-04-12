#!/bin/bash
# Run MLP debug test on Jetson

echo "[JETSON] Running MLP Speed Reading Debug Test"
echo ""

cd ~/Desktop/VisionPilot-XR-Linux

# Run test
python3 test_mlp_debug.py

echo ""
echo "[JETSON] Test completed - check output above"
echo ""
echo "If speed is None:"
echo "  1. Check min_margin (currently 0.15)"
echo "  2. Check min_votes (currently 4)"
echo "  3. Look at margin value in debug output"
echo ""

