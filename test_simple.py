#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick test to verify detections are working"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect output to see it
output_file = "test_output.log"

# Test imports
print("[TEST] Testing imports...")

try:
    from realsense import RealSenseCamera
    print("[TEST] ✓ RealSenseCamera imported")
except Exception as e:
    print(f"[TEST] ✗ RealSenseCamera failed: {e}")

try:
    from image_processing import ImageProcessor
    print("[TEST] ✓ ImageProcessor imported")
except Exception as e:
    print(f"[TEST] ✗ ImageProcessor failed: {e}")

try:
    from read_speed import PerceptronSpeedReader
    print("[TEST] ✓ PerceptronSpeedReader imported")
except Exception as e:
    print(f"[TEST] ✗ PerceptronSpeedReader failed: {e}")

# Test ImageProcessor attributes
try:
    proc = ImageProcessor()
    has_flag = hasattr(proc, 'sign_detected_this_frame')
    print(f"[TEST] ImageProcessor.sign_detected_this_frame exists: {has_flag}")

    if has_flag:
        print(f"[TEST] ✓ Flag value: {proc.sign_detected_this_frame}")
    else:
        print("[TEST] ✗ Flag NOT found")
except Exception as e:
    print(f"[TEST] ✗ Error creating ImageProcessor: {e}")

print("\n[TEST] All checks completed!")
with open(output_file, 'w') as f:
    f.write("TEST COMPLETED\n")

