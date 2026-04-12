#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Simple GUI with Live Camera Feed
Displays camera feed with detected speed signs highlighted
"""

import os
import sys
import platform
import time
import cv2
import numpy as np
import threading

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")

# =====================================================
# IMPORTS
# =====================================================

try:
    from realsense import RealSenseCamera
except Exception:
    RealSenseCamera = None

try:
    from image_processing import ImageProcessor, set_vehicle_speed
except Exception:
    ImageProcessor = None

try:
    from elm327_can_speed import ELM327SpeedReader
except Exception:
    ELM327SpeedReader = None


# =====================================================
# GLOBAL STATE
# =====================================================

class GUIState:
    def __init__(self):
        self.running = False
        self.camera = None
        self.processor = None
        self.elm327_reader = None

        self.current_frame = None
        self.vehicle_speed = 0
        self.detected_sign = None
        self.detected_ellipse = None
        self.sign_detected_this_frame = False  # Flag for current frame detection
        self.last_sign_center = None

        self.lock = threading.Lock()

state = GUIState()


# =====================================================
# CALLBACKS
# =====================================================

def on_vehicle_speed_received(speed_kmh):
    """Called when ELM327 reads a speed."""
    with state.lock:
        state.vehicle_speed = speed_kmh
    try:
        set_vehicle_speed(speed_kmh)
    except Exception:
        pass


# =====================================================
# CAMERA THREAD
# =====================================================

def camera_thread():
    """Background thread for camera capture and processing."""
    if state.camera is None or state.processor is None:
        return

    while state.running:
        try:
            ok, frame = state.camera.read()
            if not ok or frame is None:
                continue

            # Enable all processing features
            state.processor.enable_red = True
            state.processor.enable_canny = True
            state.processor.enable_ellipse = True
            state.processor.read_sign_enabled = True

            # Reset detection flag BEFORE processing this frame
            state.processor.sign_detected_this_frame = False

            # Process frame (this will set sign_detected_this_frame to True if ellipse found)
            result_img = state.processor.process(frame)

            if result_img is not None:
                with state.lock:
                    state.current_frame = frame.copy()
                    # Check if sign was detected in this frame
                    sign_detected = getattr(state.processor, 'sign_detected_this_frame', False)
                    state.sign_detected_this_frame = sign_detected

                    # Only update detected_sign if sign was found in this frame
                    if sign_detected and hasattr(state.processor, 'last_speed'):
                        state.detected_sign = state.processor.last_speed
                    else:
                        state.detected_sign = None

                    # Get sign center
                    if hasattr(state.processor, 'last_sign_center'):
                        state.last_sign_center = state.processor.last_sign_center

            time.sleep(0.001)
        except Exception as e:
            print(f"[GUI] Camera thread error: {e}")
            time.sleep(0.1)


# =====================================================
# GUI WINDOW
# =====================================================

class CameraWindow:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.window_name = "VisionPilot XR - Live Feed"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, width, height)

        print("[GUI] Camera window created")

    def draw_detected_sign(self, frame):
        """Draw detected sign information on the frame."""
        if frame is None:
            return frame

        frame_h, frame_w = frame.shape[:2]

        # Draw vehicle speed at top-left
        with state.lock:
            speed = state.vehicle_speed
            detected = state.sign_detected_this_frame
            sign_value = state.detected_sign
            sign_center = state.last_sign_center

        speed_text = f"Vehicle Speed: {speed} km/h"
        cv2.putText(frame, speed_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                   1.0, (0, 255, 0), 2)

        # Draw detection status
        detected_text = f"Detected: {'YES' if detected else 'NO'}"
        detected_color = (0, 255, 0) if detected else (0, 0, 255)
        cv2.putText(frame, detected_text, (20, 90), cv2.FONT_HERSHEY_SIMPLEX,
                   1.0, detected_color, 2)

        # Draw sign value (always show, even if not detected)
        read_sign_value = f"{sign_value} km/h" if (detected and sign_value is not None) else "-- km/h"
        read_sign_color = (0, 255, 255) if (detected and sign_value is not None) else (100, 100, 100)
        sign_text = f"Read Sign: {read_sign_value}"
        cv2.putText(frame, sign_text, (20, 140), cv2.FONT_HERSHEY_SIMPLEX,
                   1.0, read_sign_color, 2)

        # Draw ellipse/circle at detected position
        if detected and sign_center is not None:
            try:
                # Original frame is 1920x1080, displayed frame is 1280x720
                # Scale coordinates accordingly
                orig_w, orig_h = 1920, 1080
                cx_orig, cy_orig = sign_center

                # Scale to display frame size
                cx_display = int(cx_orig * (frame_w / orig_w))
                cy_display = int(cy_orig * (frame_h / orig_h))

                # Draw green circle at detected center
                radius = 80
                cv2.circle(frame, (cx_display, cy_display), radius, (0, 255, 0), 3)
                cv2.circle(frame, (cx_display, cy_display), 5, (0, 255, 0), -1)  # Center dot
            except Exception as e:
                pass

        return frame

    def update(self):
        """Update the GUI with current frame."""
        with state.lock:
            frame = state.current_frame.copy() if state.current_frame is not None else None

        if frame is None:
            # Show black frame while waiting
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for camera feed...", (50, self.height // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        else:
            # Resize to window size
            frame = cv2.resize(frame, (self.width, self.height))
            # Draw detection info
            frame = self.draw_detected_sign(frame)

        cv2.imshow(self.window_name, frame)

        # Check for ESC key to exit
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            return False

        return True

    def close(self):
        """Close the window."""
        cv2.destroyAllWindows()
        print("[GUI] Camera window closed")


# =====================================================
# INITIALIZATION
# =====================================================

def init_camera():
    """Initialize RealSense camera."""
    if RealSenseCamera is None:
        print("[GUI] [NO] RealSense not available")
        return False

    try:
        state.camera = RealSenseCamera(width=1920, height=1080, fps=30, auto_exposure=True)
        state.camera.start()
        print("[GUI] [OK] Camera initialized")
        return True
    except Exception as e:
        print(f"[GUI] [NO] Failed to initialize camera: {e}")
        state.camera = None
        return False


def init_processor():
    """Initialize image processor."""
    if ImageProcessor is None:
        print("[GUI] [NO] ImageProcessor not available")
        return False

    try:
        state.processor = ImageProcessor()
        print("[GUI] [OK] Image processor initialized")
        return True
    except Exception as e:
        print(f"[GUI] [NO] Failed to initialize processor: {e}")
        state.processor = None
        return False


def init_elm327():
    """Initialize ELM327."""
    if ELM327SpeedReader is None:
        print("[GUI] [NO] ELM327 not available")
        return False

    try:
        port = "COM12" if IS_WINDOWS else "/dev/ttyUSB0"
        state.elm327_reader = ELM327SpeedReader(
            port=port,
            baudrate=9600,
            callback=on_vehicle_speed_received
        )
        state.elm327_reader.start()
        print(f"[GUI] [OK] ELM327 reader started on {port}")
        return True
    except Exception as e:
        print(f"[GUI] [NO] Failed to initialize ELM327: {e}")
        state.elm327_reader = None
        return False


# =====================================================
# MAIN
# =====================================================

def main():
    """Main GUI entry point."""

    print("[GUI] ============================================")
    print("[GUI] VisionPilot XR - Simple GUI")
    print("[GUI] ============================================\n")

    # Initialize components
    print("[GUI] Initializing components...")

    if not init_camera():
        print("[GUI] [NO] Camera initialization failed")
        return

    if not init_processor():
        print("[GUI] [NO] Processor initialization failed")
        return

    init_elm327()  # Optional

    print("[GUI] [OK] All components ready\n")

    # Create window
    window = CameraWindow(width=1280, height=720)

    # Start camera thread
    state.running = True
    camera_proc = threading.Thread(target=camera_thread, daemon=True)
    camera_proc.start()

    print("[GUI] Camera thread started")
    print("[GUI] Press ESC to exit\n")

    # Main GUI loop
    try:
        while state.running:
            if not window.update():
                break
    except KeyboardInterrupt:
        print("\n[GUI] Shutdown requested")
    finally:
        state.running = False
        if state.camera is not None:
            state.camera.stop()
        if state.elm327_reader is not None:
            state.elm327_reader.running = False
        window.close()
        print("[GUI] Shutdown complete")


if __name__ == "__main__":
    main()

