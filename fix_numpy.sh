#!/bin/bash
# Fix NumPy compatibility issue with PyTorch on Jetson

echo "[FIX] NumPy compatibility issue detected"
echo "[FIX] PyTorch expects specific NumPy version"
echo ""

echo "[FIX] Upgrading NumPy to compatible version..."
pip install --upgrade numpy

echo ""
echo "[FIX] Installing additional dependencies..."
pip install numpy==1.21.6

echo ""
echo "[FIX] Done! Now run:"
echo "  python3 test_with_fix.py"

