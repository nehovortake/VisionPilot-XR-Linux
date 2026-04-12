#!/usr/bin/env python3
"""
MLP Margin Debug Test - Track why predictions are rejected
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

print("[MARGIN TEST] MLP Margin Analysis")
print("[MARGIN TEST] ============================================\n")

# Load model
try:
    from read_speed import PerceptronSpeedReader
    reader = PerceptronSpeedReader()
    print(f"✓ Model loaded: {len(reader.labels)} classes")
    print(f"  Min margin required: {reader.min_margin}")
    print(f"  Min votes required: {reader.min_votes}\n")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    sys.exit(1)

# Patch predict_from_crop to log margin values
original_predict = reader.predict_from_crop

margin_values = []
rejected_count = 0
accepted_count = 0

def predict_with_logging(crop_bgr):
    """Wrapper to log margin values"""
    global margin_values, rejected_count, accepted_count

    try:
        if crop_bgr is None or crop_bgr.size == 0:
            return reader.last_stable

        if reader.model is None or reader.labels is None:
            return reader.last_stable

        best_label = None
        best_margin = -1e9
        best_maxlogit = -1e9

        from read_speed import RUNTIME_PREPROCESS_VARIANTS, preprocess_inner_mask
        import torch

        for _name, cfg in RUNTIME_PREPROCESS_VARIANTS:
            inner_scale = reader.inner_scale if cfg.get("inner_scale") is None else float(cfg["inner_scale"])
            focus_scale = reader.focus_scale if cfg.get("focus_scale") is None else float(cfg["focus_scale"])
            crop_mode = cfg.get("crop_mode", "crop")

            patch = preprocess_inner_mask(
                crop_bgr,
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

            # TRACK MARGIN
            margin_values.append(margin)

            if (margin > best_margin) or (margin == best_margin and maxlogit > best_maxlogit):
                best_margin = margin
                best_maxlogit = maxlogit
                best_label = pred_label

        if best_label is None:
            rejected_count += 1
            return reader.last_stable

        # CHECK MARGIN GATE
        if best_margin < reader.min_margin:
            rejected_count += 1
            print(f"  [REJECTED] margin={best_margin:.3f} < threshold={reader.min_margin} (label={best_label})")
            return reader.last_stable

        # ADD TO HISTORY
        reader.pred_hist.append(best_label)
        counts = {}
        for v in reader.pred_hist:
            counts[v] = counts.get(v, 0) + 1

        winner, votes = max(counts.items(), key=lambda kv: kv[1])

        if votes < reader.min_votes:
            rejected_count += 1
            print(f"  [REJECTED] votes={votes} < threshold={reader.min_votes} (winner={winner})")
            return reader.last_stable

        accepted_count += 1
        reader.last_stable = winner
        print(f"  [ACCEPTED] margin={best_margin:.3f}, votes={votes}, speed={winner}")
        return reader.last_stable

    except Exception as e:
        print(f"  [ERROR] {e}")
        return reader.last_stable

reader.predict_from_crop = predict_with_logging

# Test with synthetic crops
print("[MARGIN TEST] Testing with synthetic crops...\n")

import cv2

for i in range(10):
    # Create random synthetic ellipse
    crop = np.random.randint(0, 100, (64, 64, 3), dtype=np.uint8)
    radius = np.random.randint(15, 30)
    cv2.circle(crop, (32, 32), radius, (200, 200, 200), -1)

    print(f"[TEST {i+1}]")
    result = reader.predict_from_crop(crop)
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
    print("\n⚠ All predictions rejected!")
    print("  Possible fixes:")
    print(f"    1. Lower min_margin from {reader.min_margin} to {min(margin_values)*0.9:.3f}")
    print(f"    2. Lower min_votes from {reader.min_votes} to 1-2")
else:
    print("\n✓ Some predictions accepted!")

print("[MARGIN TEST] ============================================\n")

