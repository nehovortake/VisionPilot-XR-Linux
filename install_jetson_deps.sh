#!/bin/bash
# Install missing dependencies for Jetson

echo "Installing missing dependencies for VisionPilot XR on Jetson..."
echo ""

# Update pip
echo "[1/3] Updating pip..."
pip install --upgrade pip

# Install pyserial (needed for ELM327)
echo "[2/3] Installing pyserial for ELM327 support..."
pip install pyserial==3.5

# Install remaining dependencies
echo "[3/3] Installing other dependencies..."
pip install numpy opencv-python PyQt5 psutil

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run VisionPilot XR:"
echo "  python3 main.py"

