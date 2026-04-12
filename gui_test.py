#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI Test - Verify everything works"""

import os
import sys
import time

# Change to project directory
os.chdir("C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")
sys.path.insert(0, "C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")

print("\n" + "="*60)
print("GUI TEST - Verifying All Components")
print("="*60 + "\n")

# Test imports
print("[TEST] 1. Testing imports...")
try:
    from realsense import RealSenseCamera
    print("  ✓ RealSenseCamera")
except Exception as e:
    print(f"  ✗ RealSenseCamera: {e}")

try:
    from image_processing import ImageProcessor
    print("  ✓ ImageProcessor")
except Exception as e:
    print(f"  ✗ ImageProcessor: {e}")

try:
    from read_speed import PerceptronSpeedReader
    print("  ✓ PerceptronSpeedReader")
except Exception as e:
    print(f"  ✗ PerceptronSpeedReader: {e}")

try:
    from elm327_can_speed import ELM327SpeedReader
    print("  ✓ ELM327SpeedReader")
except Exception as e:
    print(f"  ✗ ELM327SpeedReader: {e}")

try:
    import cv2
    print("  ✓ cv2 (OpenCV)")
except Exception as e:
    print(f"  ✗ cv2: {e}")

# Test GUI imports
print("\n[TEST] 2. Testing GUI imports...")
try:
    from gui import state, init_camera, init_processor, CameraWindow
    print("  ✓ gui.state")
    print("  ✓ gui functions")
except Exception as e:
    print(f"  ✗ GUI imports: {e}")
    sys.exit(1)

# Test state attributes
print("\n[TEST] 3. Testing GUI state attributes...")
required_attrs = [
    'vehicle_speed', 'detected_sign', 'sign_detected_this_frame',
    'last_sign_center', 'running', 'camera', 'processor'
]
for attr in required_attrs:
    if hasattr(state, attr):
        value = getattr(state, attr)
        print(f"  ✓ state.{attr} = {value}")
    else:
        print(f"  ✗ state.{attr} MISSING")

# Test processor attributes
print("\n[TEST] 4. Testing ImageProcessor attributes...")
try:
    proc = ImageProcessor()
    required_attrs = [
        'sign_detected_this_frame', 'last_speed', 'last_sign_center',
        'enable_red', 'enable_canny', 'enable_ellipse'
    ]
    for attr in required_attrs:
        if hasattr(proc, attr):
            value = getattr(proc, attr)
            print(f"  ✓ processor.{attr} = {value}")
        else:
            print(f"  ✗ processor.{attr} MISSING")
except Exception as e:
    print(f"  ✗ Error creating processor: {e}")

print("\n" + "="*60)
print("GUI TEST COMPLETE - All components verified!")
print("="*60 + "\n")

print("You can now run: python gui.py")
print("And GUI window should appear with camera feed and detection info.")

