#!/bin/bash

# JETSON - ONE COMMAND FIX
# Copy and paste this entire command into Jetson terminal

sudo apt-get update && \
sudo apt-get install -y python3.8-venv python3.8-dev build-essential && \
rm -rf ~/visionpilot && \
python3.8 -m venv ~/visionpilot && \
source ~/visionpilot/bin/activate && \
pip install --upgrade pip setuptools wheel && \
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true && \
pip install torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 \
    --index-url https://download.pytorch.org/whl/cu118 && \
pip install numpy==1.21.6 scipy==1.7.3 opencv-python==4.6.0.66 && \
pip install PyQt5==5.15.7 pyserial==3.5 psutil==5.9.4 && \
echo "✅ FIX COMPLETE!" && \
echo "" && \
echo "Next:" && \
echo "  source ~/visionpilot/bin/activate" && \
echo "  cd ~/VisionPilot-XR-Linux" && \
echo "  python gui.py"

