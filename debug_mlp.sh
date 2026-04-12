#!/bin/bash
# Debug script - check MLP speed reading

echo "[DEBUG] Testing MLP speed reading on Jetson..."
echo ""

# Test 1: Check if model exists
echo "[TEST 1] Checking model file..."
MODEL_PATH="$HOME/Desktop/VisionPilot-XR-Linux/dataset/mlp_speed_model_dataset_split.pt"
if [ -f "$MODEL_PATH" ]; then
    echo "✓ Model found: $MODEL_PATH"
    ls -lh "$MODEL_PATH"
else
    echo "✗ Model NOT found at: $MODEL_PATH"
fi
echo ""

# Test 2: Check PyTorch
echo "[TEST 2] Checking PyTorch..."
python3 -c "import torch; print(f'✓ PyTorch {torch.__version__}'); print(f'  CUDA available: {torch.cuda.is_available()}')" 2>&1 || echo "✗ PyTorch not available"
echo ""

# Test 3: Test MLP import
echo "[TEST 3] Testing MLP import..."
cd "$HOME/Desktop/VisionPilot-XR-Linux"
python3 << 'EOF'
try:
    from read_speed import PerceptronSpeedReader
    print("✓ PerceptronSpeedReader imported successfully")

    # Try to load model
    try:
        reader = PerceptronSpeedReader()
        print(f"✓ Model loaded: {reader.labels}")
        print(f"  Min margin: {reader.min_margin}")
        print(f"  Min votes: {reader.min_votes}")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
except ImportError as e:
    print(f"✗ Import failed: {e}")
EOF
echo ""

echo "[DEBUG] Debug complete"

