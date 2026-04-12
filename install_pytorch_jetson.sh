#!/bin/bash
# Install PyTorch on Jetson Orin Nano for Python 3.8

echo "[JETSON] Installing PyTorch for Jetson Orin Nano (Python 3.8)..."
echo ""

# PyTorch precompiled for Jetson (ARM64)
# Official Jetson PyTorch wheel

echo "[1/2] Installing PyTorch 2.1.0 (ARM64 for Jetson)..."
pip install torch==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html

echo ""
echo "[2/2] Installing torchvision and torchaudio..."
pip install torchvision==0.16.0 torchaudio==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html

echo ""
echo "✓ PyTorch installation complete!"
echo ""

# Verify
python3 -c "import torch; print(f'✓ PyTorch {torch.__version__}'); print(f'  Available: {torch.cuda.is_available()}')"

echo ""
echo "Now run:"
echo "  cd ~/Desktop/VisionPilot-XR-Linux"
echo "  export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1"
echo "  python3 main.py"

