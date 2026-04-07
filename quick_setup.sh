#!/bin/bash

# Quick setup for Jetson Orin Nano with Python 3.8
# This is a simplified version of install_jetson.sh for experienced users

set -e

echo "🚀 VisionPilot XR - Jetson Quick Setup (Python 3.8)"
echo "===================================================="

# Detect if running on Jetson
if [ ! -f "/etc/nv_tegra_release" ]; then
    echo "⚠️  Not running on Jetson. Continue anyway? (y/n)"
    read -n1 ans
    if [ "$ans" != "y" ]; then exit 1; fi
fi

VENV="$HOME/visionpilot"

# 1. System packages
echo ""
echo "📦 Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3.8 python3.8-venv python3.8-dev build-essential git

# 2. Virtual environment
echo ""
echo "🔧 Setting up Python 3.8 virtual environment..."
if [ -d "$VENV" ]; then
    read -p "Remove existing venv? (y/n) " -n1 rm_venv
    [ "$rm_venv" = "y" ] && rm -rf "$VENV"
fi
python3.8 -m venv "$VENV"
source "$VENV/bin/activate"

# 3. Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel

# 4. PyTorch (CRITICAL - Python 3.8 version)
echo ""
echo "🔥 Installing PyTorch 1.13.1 (ARM64)..."
pip install torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 \
    --index-url https://download.pytorch.org/whl/cu118

# 5. Dependencies
echo ""
echo "📚 Installing dependencies..."
if [ -f "requirements_jetson.txt" ]; then
    pip install -r requirements_jetson.txt
else
    echo "Installing manually..."
    pip install numpy==1.21.6 scipy==1.7.3 opencv-python==4.6.0.66
    pip install PyQt5==5.15.7 pyserial==3.5 psutil==5.9.4
fi

# 6. Serial device permissions
echo ""
echo "🔌 Setting up serial device permissions..."
sudo tee /etc/udev/rules.d/50-elm327.rules > /dev/null << 'EOF'
SUBSYSTEMS=="usb", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", MODE="0666", GROUP="dialout"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="dialout"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -a -G dialout ubuntu

# 7. Verification
echo ""
echo "✅ Installation Complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Logout and login: logout"
echo "   2. Activate venv: source ~/visionpilot/bin/activate"
echo "   3. Test: python jetson_test.py"
echo "   4. Run: export DISPLAY=:0 && python gui.py"

