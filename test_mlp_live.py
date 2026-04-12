#!/usr/bin/env python3
"""
MLP Test - Without NumPy conversion (works around PyTorch NumPy API issue)
"""

import os
import sys

# Fix LD_PRELOAD
if sys.platform.startswith('linux'):
    for lib_path in [
        '/usr/lib/aarch64-linux-gnu/libgomp.so.1',
        '/usr/lib/aarch64-linux-gnu/libgomp.so',
        '/usr/lib/libgomp.so.1',
    ]:
        if os.path.exists(lib_path):
            os.environ['LD_PRELOAD'] = lib_path
            break

print("[SETUP] LD_PRELOAD set")
print()

# Test MLP directly on live camera
print("[TEST] Direct MLP Test on Live Camera Feed")
print("[TEST] ============================================\n")

try:
    from realsense import RealSenseCamera
    print("✓ RealSense available")
except:
    print("✗ RealSense not available")
    sys.exit(1)

try:
    import torch
    from read_speed import PerceptronSpeedReader
    print("✓ PyTorch and PerceptronSpeedReader loaded")
except Exception as e:
    print(f"✗ Failed to load: {e}")
    sys.exit(1)

# Load model
try:
    reader = PerceptronSpeedReader()
    print(f"✓ Model loaded: {len(reader.labels)} classes")
    print(f"  Min margin: {reader.min_margin}")
    print(f"  Min votes: {reader.min_votes}\n")
except Exception as e:
    print(f"✗ Model load failed: {e}")
    sys.exit(1)

# Start camera and test
print("[TEST] Starting camera for real-time test...\n")

try:
    camera = RealSenseCamera(width=1920, height=1080, fps=30)
    camera.start()

    print("[TEST] Capturing frames and testing MLP...\n")

    predictions_collected = []
    frame_count = 0

    for i in range(30):  # 30 frames
        ok, frame = camera.read()
        if not ok or frame is None:
            continue

        frame_count += 1

        # Extract center crop as potential ellipse
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        crop_size = 100
        crop = frame[cy-crop_size:cy+crop_size, cx-crop_size:cx+crop_size]

        if crop.shape[0] < 64 or crop.shape[1] < 64:
            continue

        # Test MLP
        try:
            speed = reader.predict_from_crop(crop)
            predictions_collected.append(speed)

            if speed is not None:
                print(f"[FRAME {frame_count}] ✓ Predicted: {speed} km/h")
            else:
                print(f"[FRAME {frame_count}] - No prediction (margin/votes too low)")
        except Exception as e:
            print(f"[FRAME {frame_count}] ✗ Error: {str(e)[:50]}")

    camera.stop()

    print("\n[TEST] ============================================")
    print(f"[TEST] Results:")
    print(f"  Frames processed: {frame_count}")
    print(f"  Predictions: {len([p for p in predictions_collected if p is not None])}")
    print(f"  None (rejected): {len([p for p in predictions_collected if p is None])}")

    if any(p is not None for p in predictions_collected):
        print(f"\n✓ MLP IS WORKING!")
        print(f"  Predicted speeds: {[p for p in predictions_collected if p is not None]}")
    else:
        print(f"\n⚠ MLP not accepting predictions")
        print(f"  Check min_margin ({reader.min_margin}) and min_votes ({reader.min_votes})")
        print(f"\n  RECOMMENDED:")
        print(f"    self.min_margin = 0.10  (lower from 0.15)")
        print(f"    self.min_votes = 2      (lower from 4)")

    print("[TEST] ============================================\n")

except KeyboardInterrupt:
    print("\n[TEST] Interrupted by user")
except Exception as e:
    print(f"[TEST] Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        camera.stop()
    except:
        pass

