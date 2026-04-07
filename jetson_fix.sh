#!/bin/bash

# VisionPilot XR - Jetson Fix Script
# Fixes incomplete installation and PyTorch version

set -e

echo "🔧 VisionPilot XR - Jetson Fix Script"
echo "======================================"
echo ""

# FIRST: Install missing system packages
echo "0. Installing missing system packages..."
sudo apt-get update
sudo apt-get install -y python3.8-venv python3.8-dev build-essential
echo "   ✓ System packages installed"
echo ""

# Check Python
echo "1. Python version:"
python3.8 --version
echo ""

# Remove old venv if exists
echo "2. Setting up virtual environment..."
if [ -d "$HOME/visionpilot" ]; then
    echo "   Removing old venv..."
    rm -rf "$HOME/visionpilot"
fi

echo "   Creating new venv..."
python3.8 -m venv "$HOME/visionpilot"
source "$HOME/visionpilot/bin/activate"
echo "   ✓ Venv created and activated"
echo ""

# Upgrade pip
echo "3. Upgrading pip..."
pip install --upgrade pip setuptools wheel
echo "   ✓ Pip upgraded"
echo ""

# CRITICAL: Remove wrong PyTorch and install correct version
echo "4. Fixing PyTorch (CRITICAL)..."
echo "   Removing PyTorch 2.4.1..."
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true

echo "   Installing PyTorch 1.13.1 (ARM64)..."
pip install torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 \
    --index-url https://download.pytorch.org/whl/cu118 -v
echo "   ✓ PyTorch 1.13.1 installed"
echo ""

# Verify PyTorch
echo "5. Verifying PyTorch..."
python -c "
import torch
print(f'   PyTorch version: {torch.__version__}')
print(f'   CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'   CUDA device: {torch.cuda.get_device_name(0)}')
"
echo ""

# Install requirements
echo "6. Installing dependencies..."
if [ -f "requirements_jetson.txt" ]; then
    pip install -r requirements_jetson.txt
else
    echo "   requirements_jetson.txt not found!"
    echo "   Installing manually..."
    pip install numpy==1.21.6 scipy==1.7.3 opencv-python==4.6.0.66
    pip install PyQt5==5.15.7 pyserial==3.5 psutil==5.9.4
fi
echo "   ✓ Dependencies installed"
echo ""

# Verify installation
echo "7. Verification..."
python -c "
import torch
import cv2
import PyQt5
import numpy as np
import scipy
print('   ✓ PyTorch', torch.__version__)
print('   ✓ OpenCV', cv2.__version__)
print('   ✓ PyQt5 installed')
print('   ✓ NumPy', np.__version__)
print('   ✓ SciPy', scipy.__version__)
"
echo ""

echo "✅ Fix complete!"
echo ""
echo "Next steps:"
echo "  source ~/visionpilot/bin/activate"
echo "  cd ~/VisionPilot-XR-Linux"
echo "  python visionpilot_headless.py"

