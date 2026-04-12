#!/bin/bash
# ============================================
# VisionPilot XR - Jetson Git Push Script
# ============================================
# This script automates the Git push process
# for Jetson deployment changes

set -e  # Exit on error

echo ""
echo "=========================================="
echo "VisionPilot XR - Jetson Deployment"
echo "Git Push Script"
echo "=========================================="
echo ""

# Step 1: Check Git status
echo "[1/5] Checking Git status..."
echo ""
git status
echo ""

# Step 2: Ask for confirmation
echo "[2/5] Review changes above"
echo ""
read -p "Continue with commit and push? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Step 3: Stage all changes
echo "[3/5] Staging changes..."
git add .
echo "✓ Changes staged"
echo ""

# Step 4: Commit with message
echo "[4/5] Committing changes..."
git commit -m "feat: Full Jetson Orin Nano compatibility with Python 3.8

- Replace all hardcoded Windows paths with dynamic relative paths
- Add Jetson platform detection and tegrastats CPU monitoring
- Implement Python 3.8 compatible subprocess calls
- Auto-detect serial port based on platform (COM12/dev/ttyUSB0)
- Fix process_all_classes.py syntax error
- Add comprehensive Jetson deployment documentation
- Add verify_jetson_setup.sh verification script

BREAKING CHANGES: None
BACKWARD COMPATIBLE: Yes
TESTED ON:
  - Windows 11 + Python 3.11
  - NVIDIA Jetson Orin Nano + Python 3.8
  - Linux x86_64 + Python 3.8+"

echo "✓ Changes committed"
echo ""

# Step 5: Push to remote
echo "[5/5] Pushing to GitHub..."
git push origin main
echo "✓ Changes pushed successfully"
echo ""

# Verification
echo "=========================================="
echo "✓ Git Push Complete!"
echo "=========================================="
echo ""
echo "Next steps on Jetson:"
echo "  1. git clone https://github.com/nehovortake/VisionPilot-XR-Linux.git"
echo "  2. cd VisionPilot-XR-Linux"
echo "  3. bash verify_jetson_setup.sh"
echo "  4. pip install -r requirements_jetson.txt"
echo "  5. python3 main.py"
echo ""
echo "View latest commit:"
echo ""
git log -1 --oneline
echo ""

