#!/bin/bash
# Quick setup and verification script for Jetson deployment

echo "======================================"
echo "VisionPilot XR - Jetson Quick Setup"
echo "======================================"
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  Found: $PYTHON_VERSION"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "  ✗ ERROR: Python 3.8+ required"
    exit 1
fi
echo "  ✓ Python version OK"
echo ""

# Check if Jetson
echo "[2/5] Checking platform..."
if [ -f "/etc/nv_tegra_release" ]; then
    echo "  ✓ NVIDIA Jetson detected"
    JETSON_MODEL=$(cat /sys/devices/virtual/dmi/id/board_name 2>/dev/null || echo "Unknown")
    echo "  Device: $JETSON_MODEL"
else
    echo "  ℹ Regular Linux/Windows detected"
fi
echo ""

# Check key dependencies
echo "[3/5] Checking dependencies..."
python3 -c "import cv2; print('  ✓ OpenCV')" 2>/dev/null || echo "  ✗ OpenCV missing"
python3 -c "import torch; print('  ✓ PyTorch')" 2>/dev/null || echo "  ✗ PyTorch missing"
python3 -c "import PyQt5; print('  ✓ PyQt5')" 2>/dev/null || echo "  ✗ PyQt5 missing"
python3 -c "import pyrealsense2; print('  ✓ RealSense SDK')" 2>/dev/null || echo "  ℹ RealSense SDK optional"
echo ""

# Verify paths
echo "[4/5] Verifying directory structure..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/dataset" ]; then
    echo "  ✓ dataset/ found"
else
    echo "  ℹ dataset/ not found (will be created when needed)"
fi

if [ -d "$SCRIPT_DIR/gui_assets/signstocluster" ]; then
    echo "  ✓ gui_assets/signstocluster found"
else
    echo "  ℹ gui_assets/signstocluster not found"
fi

if [ -f "$SCRIPT_DIR/main.py" ]; then
    echo "  ✓ main.py found"
else
    echo "  ✗ main.py not found"
    exit 1
fi
echo ""

# Test syntax
echo "[5/5] Checking Python syntax..."
python3 -m py_compile main.py 2>/dev/null && echo "  ✓ main.py syntax OK" || echo "  ✗ main.py syntax error"
python3 -m py_compile read_speed.py 2>/dev/null && echo "  ✓ read_speed.py syntax OK" || echo "  ✗ read_speed.py syntax error"
echo ""

echo "======================================"
echo "✓ Setup verification complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Install missing dependencies: pip install -r requirements_jetson.txt"
echo "  2. Run application: python3 main.py"
echo "  3. Press ESC or Ctrl+C to stop"
echo ""

