#!/bin/bash
# JETSON - DIRECT MLP FIX

echo "=========================================="
echo "JETSON MLP FIX - STARTING"
echo "=========================================="
echo ""

# Set LD_PRELOAD FIRST - MUST BE BEFORE ANY PYTHON
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
echo "LD_PRELOAD=$LD_PRELOAD"
echo ""

# Go to project
cd ~/Desktop/VisionPilot-XR-Linux

# Clean and pull
echo "[1/4] Pulling latest code..."
git fetch origin
git reset --hard origin/main
git pull origin main
echo "✓ Pulled"
echo ""

# Clean cache
echo "[2/4] Cleaning cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
echo "✓ Cleaned"
echo ""

# Test model
echo "[3/4] Checking model file..."
if [ -f dataset/mlp_speed_model_dataset_split.pt ]; then
    echo "✓ Model file exists"
else
    echo "✗ Model file MISSING!"
    ls -la dataset/
    exit 1
fi
echo ""

echo "[4/4] Starting application with LD_PRELOAD..."
echo "=========================================="
echo ""

# Run main.py with LD_PRELOAD in same process
python3 main.py
