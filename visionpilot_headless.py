#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Headless CLI Mode (No GUI)
Runs red nulling, canny, ellipse detection, and speed reading
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

print("[INIT] VisionPilot XR - Headless Mode (No GUI)")
print("=" * 60)

# ============================================================
# Try to import all modules - skip gracefully if missing
# ============================================================

print("[INIT] Loading modules...")

try:
    from image_processing import ImageProcessor, start_process_log, stop_process_log, set_vehicle_speed
    print("✓ ImageProcessor loaded")
except Exception as e:
    print(f"✗ ImageProcessor error: {e}")
    ImageProcessor = None

try:
    from read_speed import PerceptronSpeedReader
    print("✓ Speed reader loaded")
except Exception as e:
    print(f"✗ Speed reader error: {e}")
    PerceptronSpeedReader = None

try:
    from realsense import RealSenseCamera
    print("✓ RealSense camera loaded")
except Exception as e:
    print(f"✗ RealSense error: {e}")
    RealSenseCamera = None

try:
    from elm327_can_speed import ELM327SpeedReader
    print("✓ ELM327 reader loaded")
except Exception as e:
    print(f"✗ ELM327 reader error: {e}")
    ELM327SpeedReader = None

print()

# ============================================================
# Initialize Camera
# ============================================================

print("[CAMERA] Initializing camera...")

camera = None
if RealSenseCamera:
    try:
        camera = RealSenseCamera()
        print("✓ RealSense camera initialized")
    except Exception as e:
        print(f"✗ RealSense failed: {e}")
        print("[FALLBACK] Trying OpenCV webcam...")
        try:
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                raise Exception("Webcam not available")
            print("✓ Webcam (OpenCV) initialized")
        except Exception as e2:
            print(f"✗ Webcam failed: {e2}")
            camera = None
else:
    try:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            raise Exception("Webcam not available")
        print("✓ Webcam (OpenCV) initialized")
    except Exception as e:
        print(f"✗ Webcam failed: {e}")
        camera = None

print()

# ============================================================
# Initialize Image Processor
# ============================================================

print("[PROCESSOR] Initializing image processor...")

processor = None
if ImageProcessor:
    try:
        processor = ImageProcessor()
        if start_process_log:
            start_process_log()
        print("✓ Image processor initialized")
        print(f"  - Red nulling: ENABLED")
        print(f"  - Canny edge: ENABLED")
        print(f"  - Ellipse detection: ENABLED")
    except Exception as e:
        print(f"✗ Image processor error: {e}")
        processor = None
else:
    print("✗ Image processor not available")

print()

# ============================================================
# Initialize Speed Reader
# ============================================================

print("[SPEED] Initializing speed reader...")

speed_reader = None
if PerceptronSpeedReader:
    try:
        speed_reader = PerceptronSpeedReader()
        print("✓ Speed reader initialized")
    except Exception as e:
        print(f"✗ Speed reader error: {e}")
        speed_reader = None
else:
    print("✗ Speed reader not available")

print()

# ============================================================
# Initialize ELM327 (CAN Speed)
# ============================================================

print("[ELM327] Initializing ELM327 reader...")

elm_reader = None
if ELM327SpeedReader:
    try:
        # Detect port based on platform
        if sys.platform == "linux" or sys.platform == "linux2":
            elm_port = "/dev/ttyUSB0"
        elif sys.platform == "darwin":
            elm_port = "/dev/cu.usbserial"
        else:
            elm_port = "COM12"

        elm_reader = ELM327SpeedReader(port=elm_port, baudrate=9600)
        print(f"✓ ELM327 reader initialized (port: {elm_port})")
    except Exception as e:
        print(f"✗ ELM327 error: {e}")
        print("  (This is OK if ELM327 adapter is not connected)")
        elm_reader = None
else:
    print("✗ ELM327 reader not available")

print()

# ============================================================
# Main Processing Loop
# ============================================================

print("[START] Processing frames...")
print("=" * 60)
print("Press Ctrl+C to stop")
print()

frame_count = 0
speed_history = []

try:
    while True:
        # Read frame
        if isinstance(camera, cv2.VideoCapture):
            ret, frame = camera.read()
            if not ret:
                print("[ERROR] Failed to read frame from camera")
                break
        elif hasattr(camera, 'get_frame'):
            frame = camera.get_frame()
            if frame is None:
                print("[ERROR] No frame from RealSense")
                break
        else:
            print("[ERROR] Unknown camera type")
            break

        frame_count += 1

        # ============================================================
        # Process Frame (Red Nulling, Canny, Ellipse Detection)
        # ============================================================

        vehicle_speed_elm = None
        detected_speed = None

        if processor:
            try:
                # Process frame through pipeline
                processor.process(frame)

                # Red nulling + Canny + Ellipse detection happens inside process()

                # Get detected speed if available
                if hasattr(processor, 'last_speed') and processor.last_speed is not None:
                    detected_speed = processor.last_speed

                # Get processing time
                if hasattr(processor, 'process_ms'):
                    process_ms = processor.process_ms
                else:
                    process_ms = 0

            except Exception as e:
                print(f"[PROCESS ERROR] {e}")
                process_ms = 0
        else:
            process_ms = 0

        # ============================================================
        # Read Speed from ELM327
        # ============================================================

        if elm_reader:
            try:
                vehicle_speed_elm = elm_reader.read_speed()
            except Exception as e:
                # Silently fail - serial connection might be intermittent
                vehicle_speed_elm = None

        # ============================================================
        # Read Speed from Image (MLP)
        # ============================================================

        if speed_reader and processor and hasattr(processor, 'last_crop'):
            try:
                crop = processor.last_crop
                if crop is not None and crop.size > 0:
                    detected_speed = speed_reader.predict_from_crop(crop)
            except Exception as e:
                pass

        # ============================================================
        # Display Output
        # ============================================================

        # Only print every N frames to reduce spam
        if frame_count % 5 == 0:
            output = f"[Frame {frame_count:06d}]"

            if process_ms > 0:
                output += f" Process: {process_ms:.1f}ms"

            if vehicle_speed_elm is not None:
                output += f" | ELM327: {vehicle_speed_elm:.0f} km/h"
                speed_history.append(vehicle_speed_elm)

            if detected_speed is not None:
                output += f" | Detected: {detected_speed} km/h"

            print(output)

except KeyboardInterrupt:
    print()
    print("=" * 60)
    print("[STOP] Interrupted by user")
except Exception as e:
    print()
    print("=" * 60)
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

finally:
    # ============================================================
    # Cleanup
    # ============================================================

    print()
    print("[CLEANUP] Closing resources...")

    if isinstance(camera, cv2.VideoCapture):
        camera.release()
        print("✓ Camera released")
    elif hasattr(camera, 'stop'):
        camera.stop()
        print("✓ RealSense stopped")

    if stop_process_log:
        try:
            stop_process_log()
            print("✓ Process log stopped")
        except:
            pass

    if elm_reader:
        try:
            elm_reader.close()
            print("✓ ELM327 closed")
        except:
            pass

    # Statistics
    if speed_history:
        avg_speed = np.mean(speed_history)
        max_speed = np.max(speed_history)
        min_speed = np.min(speed_history)
        print()
        print("[STATISTICS]")
        print(f"  Frames processed: {frame_count}")
        print(f"  Speed readings: {len(speed_history)}")
        print(f"  Average speed: {avg_speed:.1f} km/h")
        print(f"  Max speed: {max_speed:.1f} km/h")
        print(f"  Min speed: {min_speed:.1f} km/h")

    print()
    print("[DONE] VisionPilot XR headless mode finished")

