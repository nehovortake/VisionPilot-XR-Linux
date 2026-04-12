#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test GUI with live feed for 20 seconds"""

import os
import sys
import time
import cv2
import threading

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import state, init_camera, init_processor, init_elm327, camera_thread, CameraWindow

print("[LIVE TEST] Starting live feed test...")
print("[LIVE TEST] Duration: 20 seconds\n")

# Initialize
print("[LIVE TEST] Initializing camera...")
if not init_camera():
    print("[LIVE TEST] Camera init failed")
    sys.exit(1)

print("[LIVE TEST] Initializing processor...")
if not init_processor():
    print("[LIVE TEST] Processor init failed")
    sys.exit(1)

print("[LIVE TEST] Initializing ELM327...")
init_elm327()

print("[LIVE TEST] Starting camera thread...")
state.running = True
cam_thread = threading.Thread(target=camera_thread, daemon=True)
cam_thread.start()

# Create window
window = CameraWindow(width=1280, height=720)

print("[LIVE TEST] Running for 20 seconds...")
start_time = time.time()

try:
    while time.time() - start_time < 20:
        if not window.update():
            break
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\n[LIVE TEST] Interrupted")
finally:
    state.running = False
    if state.camera:
        state.camera.stop()
    if state.elm327_reader:
        state.elm327_reader.running = False
    window.close()

elapsed = time.time() - start_time
print(f"\n[LIVE TEST] Test complete ({elapsed:.1f}s)")
print("[LIVE TEST] Check if 'Detected' shows YES when sign is visible")
print("[LIVE TEST] Check if 'Read Sign' shows speed value when detected")

