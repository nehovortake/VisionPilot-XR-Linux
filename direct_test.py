#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Direct test of detection by importing and running"""

import os
import sys

sys.path.insert(0, "C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")
os.chdir("C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

print("[DIRECT TEST] Importing modules...")

try:
    from image_processing import ImageProcessor
    print("[TEST] ✓ ImageProcessor imported")
except Exception as e:
    print(f"[TEST] ✗ Failed: {e}")
    sys.exit(1)

try:
    from realsense import RealSenseCamera
    print("[TEST] ✓ RealSenseCamera imported")
except Exception as e:
    print(f"[TEST] ✗ Failed: {e}")

# Create processor and test flag
print("\n[DIRECT TEST] Creating ImageProcessor...")
try:
    proc = ImageProcessor()
    print(f"[TEST] ✓ ImageProcessor created")
    print(f"[TEST] sign_detected_this_frame = {proc.sign_detected_this_frame}")
    print(f"[TEST] last_speed = {proc.last_speed}")
    print(f"[TEST] enable_ellipse = {proc.enable_ellipse}")
except Exception as e:
    print(f"[TEST] ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test detection logic
print("\n[DIRECT TEST] Testing detection logic...")
proc.enable_red = True
proc.enable_canny = True
proc.enable_ellipse = True
proc.read_sign_enabled = False

print(f"[TEST] Processor ready for processing")
print(f"[TEST] sign_detected_this_frame (should be False initially) = {proc.sign_detected_this_frame}")

print("\n[DIRECT TEST] Test completed successfully!")

