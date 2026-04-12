#!/usr/bin/env python3
"""
Comprehensive MLP Speed Reading Debug Test
Tests each step of the pipeline to find why speed reading fails
"""

import sys
import os
from pathlib import Path
import numpy as np
import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("[TEST] ============================================")
print("[TEST] MLP Speed Reading Debug Test")
print("[TEST] ============================================\n")

# Test 1: Check PyTorch
print("[TEST 1] Checking PyTorch...")
try:
    import torch
    print(f"✓ PyTorch {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"✗ PyTorch not available: {e}")
    sys.exit(1)

# Test 2: Import MLP Reader
print("\n[TEST 2] Importing PerceptronSpeedReader...")
try:
    from read_speed import PerceptronSpeedReader
    print("✓ PerceptronSpeedReader imported")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 3: Load Model
print("\n[TEST 3] Loading MLP Model...")
try:
    reader = PerceptronSpeedReader()
    print(f"✓ Model loaded")
    print(f"  Classes: {reader.labels}")
    print(f"  Count: {len(reader.labels)}")
    print(f"  Image size: {reader.img_size}")
    print(f"  Min margin: {reader.min_margin}")
    print(f"  Min votes: {reader.min_votes}")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    sys.exit(1)

# Test 4: Create synthetic ellipse crop
print("\n[TEST 4] Creating synthetic test crop...")
try:
    # Create a test crop - white circle on black background
    test_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    cv2.circle(test_crop, (32, 32), 28, (255, 255, 255), -1)
    print(f"✓ Created synthetic crop: {test_crop.shape}")
    print(f"  Min: {test_crop.min()}, Max: {test_crop.max()}")
except Exception as e:
    print(f"✗ Failed to create crop: {e}")
    sys.exit(1)

# Test 5: Test preprocessing
print("\n[TEST 5] Testing preprocessing...")
try:
    from read_speed import preprocess_inner_mask, RUNTIME_PREPROCESS_VARIANTS

    for name, cfg in RUNTIME_PREPROCESS_VARIANTS:
        inner_scale = reader.inner_scale if cfg.get("inner_scale") is None else float(cfg["inner_scale"])
        focus_scale = reader.focus_scale if cfg.get("focus_scale") is None else float(cfg["focus_scale"])
        crop_mode = cfg.get("crop_mode", "crop")

        patch = preprocess_inner_mask(
            test_crop,
            out_size=reader.img_size,
            inner_scale=inner_scale,
            focus_scale=focus_scale,
            crop_mode=crop_mode,
        )

        if patch is not None:
            print(f"✓ Variant '{name}': {patch.shape}, min={patch.min()}, max={patch.max()}")
        else:
            print(f"✗ Variant '{name}' returned None")
except Exception as e:
    print(f"✗ Preprocessing failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Test MLP prediction
print("\n[TEST 6] Testing MLP prediction on synthetic crop...")
try:
    # Run prediction multiple times to test stabilization
    predictions = []
    for i in range(10):
        speed = reader.predict_from_crop(test_crop)
        predictions.append(speed)
        print(f"  Attempt {i+1}: {speed}")

    print(f"\n✓ Predictions: {predictions}")
    print(f"  Unique values: {set(predictions)}")
    print(f"  Most common: {max(set(predictions), key=predictions.count) if predictions else None}")

except Exception as e:
    print(f"✗ Prediction failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Check reader internals
print("\n[TEST 7] Checking reader internal state...")
try:
    print(f"  last_stable: {reader.last_stable}")
    print(f"  pred_hist: {list(reader.pred_hist)}")
    print(f"  Model device: {next(reader.model.parameters()).device}")
except Exception as e:
    print(f"✗ Failed to check state: {e}")

# Test 8: Test with real camera crop if available
print("\n[TEST 8] Attempting to load real camera feed...")
try:
    from realsense import RealSenseCamera

    print("  Starting RealSense camera...")
    camera = RealSenseCamera(width=1920, height=1080, fps=30)
    camera.start()

    print("  Waiting for frame...")
    for i in range(5):
        ok, frame = camera.read()
        if ok and frame is not None:
            print(f"✓ Got frame {i+1}: {frame.shape}")

            # Create a test crop from frame center
            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2
            crop = frame[cy-50:cy+50, cx-50:cx+50]

            print(f"  Testing MLP on real frame crop...")
            speed = reader.predict_from_crop(crop)
            print(f"  Predicted speed: {speed}")
            break

    camera.stop()
    print("✓ Real camera test completed")
except ImportError:
    print("  RealSense not available - skipping")
except Exception as e:
    print(f"⚠ Real camera test failed: {e}")

print("\n[TEST] ============================================")
print("[TEST] Debug test complete!")
print("[TEST] ============================================\n")

print("Summary:")
print("  - If 'Predicted speed: None' → margin too high or no valid predictions")
print("  - If predictions vary wildly → stabilization not working")
print("  - Check min_margin and min_votes values")

