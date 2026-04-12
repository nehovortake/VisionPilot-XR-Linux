#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple visual test of GUI"""

import os
import sys
import time
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("[VISUAL TEST] Starting simple GUI visual test...")

# Create test frame
frame = np.zeros((720, 1280, 3), dtype=np.uint8)
frame[:] = (50, 50, 50)  # Dark background

# Import GUI drawing function
from gui import CameraWindow, state

# Simulate state values
state.vehicle_speed = 50
state.sign_detected_this_frame = False
state.detected_sign = None
state.last_sign_center = None

# Create window
window = CameraWindow(width=1280, height=720)

# Draw on frame
frame_with_text = window.draw_detected_sign(frame.copy())

# Save to file for inspection
cv2.imwrite("test_output.png", frame_with_text)
print("[VISUAL TEST] ✓ Frame saved to test_output.png")

# Now test with detected sign
state.sign_detected_this_frame = True
state.detected_sign = 50
state.last_sign_center = (960, 540)

frame2 = np.zeros((720, 1280, 3), dtype=np.uint8)
frame2[:] = (50, 50, 50)
frame_with_text2 = window.draw_detected_sign(frame2.copy())
cv2.imwrite("test_output_detected.png", frame_with_text2)
print("[VISUAL TEST] ✓ Frame with detected sign saved to test_output_detected.png")

window.close()
print("[VISUAL TEST] Done! Check the PNG files to see the output.")

