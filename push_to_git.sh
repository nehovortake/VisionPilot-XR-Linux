#!/bin/bash
# Git Push Instructions for VisionPilot XR

echo "[GIT] Pushing changes to GitHub..."
echo ""

cd ~/Desktop/VisionPilot-XR-Linux

# 1. Check status
echo "[1/4] Checking status..."
git status
echo ""

# 2. Add all changes
echo "[2/4] Adding all files..."
git add .
echo "✓ Files added"
echo ""

# 3. Commit
echo "[3/4] Committing..."
git commit -m "fix: Use working Windows read_speed.py for Jetson

- Copy working Windows version to Linux
- Uses margin-based selection (not softmax)
- Multi-variant preprocessing (crop + pad)
- Proper majority vote stabilization
- Backward compatible with model formats
- PyTorch TLS fix with LD_PRELOAD
- Tested on Jetson Orin Nano"

echo ""
echo "[4/4] Pushing to GitHub..."
git push origin main

echo ""
echo "✓ Push complete!"
echo ""
echo "Verify on GitHub: https://github.com/nehovortake/VisionPilot-XR-Linux"

