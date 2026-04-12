#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test main detection with live camera"""

import os
import sys
import time
import threading

sys.path.insert(0, "C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")
os.chdir("C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux")

print("[LIVE DETECTION TEST] Starting...")
print("=" * 60)

try:
    from realsense import RealSenseCamera
    from image_processing import ImageProcessor
    from read_speed import PerceptronSpeedReader
    from elm327_can_speed import ELM327SpeedReader
    from image_processing import set_vehicle_speed

    print("[TEST] All modules imported successfully")
except Exception as e:
    print(f"[TEST] Import failed: {e}")
    sys.exit(1)

# Initialize components
print("\n[TEST] Initializing components...")

try:
    camera = RealSenseCamera(width=1920, height=1080, fps=30, auto_exposure=True)
    camera.start()
    print("[TEST] ✓ Camera initialized")
except Exception as e:
    print(f"[TEST] ✗ Camera failed: {e}")
    sys.exit(1)

try:
    processor = ImageProcessor()
    print("[TEST] ✓ Processor initialized")
except Exception as e:
    print(f"[TEST] ✗ Processor failed: {e}")
    sys.exit(1)

try:
    speed_reader = PerceptronSpeedReader()
    processor.speed_reader = speed_reader
    print("[TEST] ✓ Speed reader initialized")
except Exception as e:
    print(f"[TEST] ✗ Speed reader failed: {e}")

# Run test
print("\n[TEST] Running detection test for 15 seconds...")
print("-" * 60)

processor.enable_red = True
processor.enable_canny = True
processor.enable_ellipse = True
processor.read_sign_enabled = True

start_time = time.time()
frame_count = 0
detection_count = 0
last_detected_speed = None

try:
    while time.time() - start_time < 15:
        ok, frame = camera.read()
        if not ok:
            continue

        # Reset flag
        processor.sign_detected_this_frame = False

        # Process
        result = processor.process(frame)

        frame_count += 1

        # Check detection
        if processor.sign_detected_this_frame:
            detection_count += 1
            detected_speed = getattr(processor, 'last_speed', None)
            if detected_speed != last_detected_speed:
                print(f"[{frame_count:4d}] DETECTED! Speed = {detected_speed} km/h")
                last_detected_speed = detected_speed

        # Print every 30 frames
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"[{frame_count:4d}] {elapsed:.1f}s | FPS: {fps:.1f} | Detections: {detection_count}")

except KeyboardInterrupt:
    print("\n[TEST] Interrupted by user")

finally:
    camera.stop()

elapsed = time.time() - start_time
print("\n" + "=" * 60)
print(f"[TEST] Test complete!")
print(f"  Frames processed: {frame_count}")
print(f"  Detections: {detection_count}")
print(f"  Elapsed time: {elapsed:.1f}s")
print(f"  Average FPS: {frame_count/elapsed:.1f}")

