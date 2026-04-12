#!/bin/bash
# Jetson - Pull code from GitHub and Run

echo "[JETSON] VisionPilot XR - Pull & Run Instructions"
echo "=============================================="
echo ""

# Step 1: Clone or Pull
echo "[STEP 1] Getting code from GitHub..."
echo ""

# Check if already cloned
if [ -d "$HOME/Desktop/VisionPilot-XR-Linux" ]; then
    echo "[STEP 1] Repository already exists - pulling updates..."
    cd ~/Desktop/VisionPilot-XR-Linux
    git pull origin main
else
    echo "[STEP 1] Cloning repository..."
    cd ~/Desktop
    git clone https://github.com/nehovortake/VisionPilot-XR-Linux.git
    cd VisionPilot-XR-Linux
fi

echo "✓ Code ready"
echo ""

# Step 2: Install dependencies
echo "[STEP 2] Installing dependencies..."
echo ""
pip install --upgrade pip
pip install numpy==1.21.6
pip install pyserial
echo "✓ Dependencies installed"
echo ""

# Step 3: Set LD_PRELOAD for PyTorch
echo "[STEP 3] Setting up environment..."
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
echo "✓ LD_PRELOAD set"
echo ""

# Step 4: Run main.py
echo "[STEP 4] Running VisionPilot XR..."
echo ""
python3 main.py

