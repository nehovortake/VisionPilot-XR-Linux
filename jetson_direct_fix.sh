#!/bin/bash
# JETSON - DIRECT MLP FIX

echo "=========================================="
echo "JETSON MLP FIX - STARTING"
echo "=========================================="
echo ""

# Set LD_PRELOAD FIRST
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

# Go to project
cd ~/Desktop/VisionPilot-XR-Linux

# Clean and pull
echo "[1/5] Pulling latest code..."
git fetch origin
git reset --hard origin/main
git pull origin main
echo "✓ Pulled"
echo ""

# Clean cache
echo "[2/5] Cleaning cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
echo "✓ Cleaned"
echo ""

# Test PyTorch
echo "[3/5] Testing PyTorch..."
python3 -c "import torch; print('✓ PyTorch', torch.__version__)" || {
    echo "✗ PyTorch missing!"
    exit 1
}
echo ""

# Test model
echo "[4/5] Checking model file..."
if [ -f dataset/mlp_speed_model_dataset_split.pt ]; then
    echo "✓ Model file exists"
else
    echo "✗ Model file MISSING!"
    ls -la dataset/
    exit 1
fi
echo ""

# Test MLP load
echo "[5/5] Testing MLP load..."
python3 << 'MLPTEST'
try:
    from read_speed import PerceptronSpeedReader
    reader = PerceptronSpeedReader()
    print("✓ MLP loaded successfully")
    print(f"  Classes: {reader.labels}")
    print(f"  Min softmax: {reader.min_softmax_prob}")
except Exception as e:
    print(f"✗ MLP load failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
MLPTEST

echo ""
echo "=========================================="
echo "✓ All checks passed - starting application"
echo "=========================================="
echo ""

python3 main.py
