#!/usr/bin/env python3
"""
MLP Test Runner - Automatically fixes LD_PRELOAD issue
"""

import os
import sys
import subprocess

# Fix LD_PRELOAD for PyTorch on Jetson
print("[SETUP] Fixing LD_PRELOAD for PyTorch...")

# Set LD_PRELOAD to fix TLS memory issue
os.environ['LD_PRELOAD'] = '/usr/lib/aarch64-linux-gnu/libgomp.so.1'
print(f"[SETUP] LD_PRELOAD = {os.environ.get('LD_PRELOAD')}")

# Also try alternative paths if first one doesn't exist
alt_paths = [
    '/usr/lib/aarch64-linux-gnu/libgomp.so.1',
    '/usr/lib/aarch64-linux-gnu/libgomp.so',
    '/usr/lib/libgomp.so.1',
]

for path in alt_paths:
    if os.path.exists(path):
        os.environ['LD_PRELOAD'] = path
        print(f"[SETUP] Using: {path}")
        break

print()

# Now run the actual test
print("[TEST] Starting MLP margin debug test...\n")

# Import after setting LD_PRELOAD
sys.path.insert(0, '/home/feit/Desktop/VisionPilot-XR-Linux')

try:
    import torch
    print(f"✓ PyTorch loaded: {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}\n")
except Exception as e:
    print(f"✗ PyTorch still failed: {e}")
    sys.exit(1)

# Now run the margin debug test
from pathlib import Path
import numpy as np
import cv2
from read_speed import PerceptronSpeedReader, RUNTIME_PREPROCESS_VARIANTS, preprocess_inner_mask

print("[MARGIN TEST] MLP Margin Analysis")
print("[MARGIN TEST] ============================================\n")

try:
    reader = PerceptronSpeedReader()
    print(f"✓ Model loaded: {len(reader.labels)} classes")
    print(f"  Min margin required: {reader.min_margin}")
    print(f"  Min votes required: {reader.min_votes}\n")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    sys.exit(1)

# Test predictions
margin_values = []
rejected_count = 0
accepted_count = 0

for i in range(10):
    # Create random synthetic ellipse
    crop = np.random.randint(0, 100, (64, 64, 3), dtype=np.uint8)
    radius = np.random.randint(15, 30)
    cv2.circle(crop, (32, 32), radius, (200, 200, 200), -1)

    print(f"[TEST {i+1}]")

    best_label = None
    best_margin = -1e9
    best_maxlogit = -1e9

    try:
        for _name, cfg in RUNTIME_PREPROCESS_VARIANTS:
            inner_scale = reader.inner_scale if cfg.get("inner_scale") is None else float(cfg["inner_scale"])
            focus_scale = reader.focus_scale if cfg.get("focus_scale") is None else float(cfg["focus_scale"])
            crop_mode = cfg.get("crop_mode", "crop")

            patch = preprocess_inner_mask(
                crop,
                out_size=reader.img_size,
                inner_scale=inner_scale,
                focus_scale=focus_scale,
                crop_mode=crop_mode,
            )
            if patch is None:
                continue

            x = (patch.astype(np.float32) / 255.0).reshape(1, -1)
            x_tensor = torch.from_numpy(x)
            try:
                x_tensor = x_tensor.to(next(reader.model.parameters()).device)
            except:
                pass

            with torch.no_grad():
                out = reader.model(x_tensor)

            logits = out.squeeze(0).cpu().numpy()
            idx = int(np.argmax(logits))

            if idx < 0 or idx >= len(reader.labels):
                continue

            pred_label = int(reader.labels[idx])
            margin = reader._margin_top1_top2(logits)
            maxlogit = float(logits[idx])

            margin_values.append(margin)

            if (margin > best_margin) or (margin == best_margin and maxlogit > best_maxlogit):
                best_margin = margin
                best_maxlogit = maxlogit
                best_label = pred_label

        if best_label is None:
            rejected_count += 1
            print(f"  [REJECTED] No valid label")
        elif best_margin < reader.min_margin:
            rejected_count += 1
            print(f"  [REJECTED] margin={best_margin:.3f} < {reader.min_margin} (label={best_label})")
        else:
            reader.pred_hist.append(best_label)
            counts = {}
            for v in reader.pred_hist:
                counts[v] = counts.get(v, 0) + 1

            winner, votes = max(counts.items(), key=lambda kv: kv[1])

            if votes < reader.min_votes:
                rejected_count += 1
                print(f"  [REJECTED] votes={votes} < {reader.min_votes} (winner={winner})")
            else:
                accepted_count += 1
                reader.last_stable = winner
                print(f"  [ACCEPTED] margin={best_margin:.3f}, votes={votes}, speed={winner}")
    except Exception as e:
        print(f"  [ERROR] {e}")
        rejected_count += 1

    print()

# Summary
print("[MARGIN TEST] ============================================")
print("[MARGIN TEST] Summary:")
print(f"  Margin values collected: {len(margin_values)}")
if margin_values:
    print(f"  Margin min: {min(margin_values):.4f}")
    print(f"  Margin max: {max(margin_values):.4f}")
    print(f"  Margin avg: {np.mean(margin_values):.4f}")
    print(f"  Margin threshold: {reader.min_margin}")
    print(f"  Values below threshold: {sum(1 for m in margin_values if m < reader.min_margin)}")
print(f"\n  Accepted predictions: {accepted_count}")
print(f"  Rejected predictions: {rejected_count}")

if rejected_count > 0 and accepted_count == 0:
    if margin_values:
        recommended_margin = min(margin_values) * 0.9
        print(f"\n⚠ All predictions rejected!")
        print(f"  RECOMMENDED FIX:")
        print(f"    1. In read_speed.py, change:")
        print(f"       self.min_margin = {recommended_margin:.3f}")
        print(f"    2. Also lower min_votes to 2")
else:
    print(f"\n✓ Some predictions accepted!")

print("[MARGIN TEST] ============================================\n")

