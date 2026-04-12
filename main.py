#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Main Script
OpenCV GUI (No PyQt5) + MLP Speed Reading
"""

import os
import sys
import platform
import time
import cv2
import numpy as np
from pathlib import Path

# NOTE: LD_PRELOAD cannot be set from inside Python on Jetson/aarch64.
# Use run_visionpilot.sh launcher instead which sets it before Python starts.
# The original LD_PRELOAD block here was ineffective and has been removed.

print(f"[INIT] LD_PRELOAD={os.environ.get('LD_PRELOAD', 'Not set')}")

try:
    import psutil
except ImportError:
    psutil = None

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# IMPORTS
try:
    from realsense import RealSenseCamera
except Exception as e:
    print(f"[INIT] RealSense import: {e}")
    RealSenseCamera = None

try:
    from image_processing import ImageProcessor
except Exception as e:
    print(f"[INIT] ImageProcessor import: {e}")
    ImageProcessor = None

try:
    from read_speed import PerceptronSpeedReader
    # quick smoke-test: instantiate to verify model loads
    _test = PerceptronSpeedReader()
    del _test
    print("[INIT] PerceptronSpeedReader: OK")
except Exception as e:
    # Show the FULL traceback so you can see the real root cause
    import traceback
    print(f"[INIT] PerceptronSpeedReader FAILED:")
    traceback.print_exc()
    print(
        "\n[INIT] FIX: run via ./run_visionpilot.sh instead of python3 main.py directly.\n"
        "[INIT] This sets LD_PRELOAD before Python loads torch, which fixes the\n"
        "[INIT] 'cannot allocate memory in static TLS block' error on Jetson/aarch64.\n"
    )
    PerceptronSpeedReader = None

try:
    from elm327_can_speed import ELM327SpeedReader
except Exception as e:
    print(f"[INIT] ELM327SpeedReader import: {e}")
    ELM327SpeedReader = None

# PLATFORM INFO
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")

# STATE
class State:
    def __init__(self):
        self.running = False
        self.camera = None
        self.processor = None
        self.speed_reader = None
        self.elm327_reader = None
        self.vehicle_speed = 0
        self.detected_sign = None
        self.sign_detected_status = False
        self.sign_center = None
        self.frame_count = 0
        self.start_time = None
        self.current_frame = None
        self.cpu_samples = []
        self.timestamps = []
        self.last_display_time = 0

state = State()

# HELPERS
def get_cpu_usage():
    if psutil:
        try:
            return psutil.cpu_percent(interval=0.001)
        except:
            pass
    return 0

# INIT COMPONENTS
def init_all():
    print("\n[MAIN] ============================================")
    print("[MAIN] Initializing Components")
    print("[MAIN] ============================================\n")

    # Camera
    print("[MAIN] [1/4] Camera...")
    if RealSenseCamera:
        try:
            state.camera = RealSenseCamera(width=1920, height=1080, fps=30)
            state.camera.start()
            print("[MAIN] [OK] Camera initialized")
        except Exception as e:
            print(f"[MAIN] [NO] Camera failed: {e}")
            return False
    else:
        print("[MAIN] [NO] RealSense not available")
        return False

    # Processor
    print("[MAIN] [2/4] Image Processor...")
    if ImageProcessor:
        try:
            state.processor = ImageProcessor()
            print("[MAIN] [OK] Processor initialized")
        except Exception as e:
            print(f"[MAIN] [NO] Processor failed: {e}")
            return False
    else:
        print("[MAIN] [NO] ImageProcessor not available")
        return False

    # MLP Reader
    print("[MAIN] [3/4] MLP Speed Reader...")
    if PerceptronSpeedReader:
        try:
            state.speed_reader = PerceptronSpeedReader()
            state.processor.speed_reader = state.speed_reader
            state.processor.read_sign_enabled = True
            print("[MAIN] [OK] MLP Reader initialized")
        except Exception as e:
            print(f"[MAIN] [WARN] MLP Reader failed: {e}")
    else:
        print("[MAIN] [WARN] MLP Reader not available — speed reading disabled")

    # ELM327
    print("[MAIN] [4/4] ELM327 CAN Reader...")
    if ELM327SpeedReader:
        try:
            state.elm327_reader = ELM327SpeedReader()
            state.elm327_reader.start()
            print("[MAIN] [OK] ELM327 reader started")
        except Exception as e:
            print(f"[MAIN] [WARN] ELM327 failed: {e}")
    else:
        print("[MAIN] [WARN] ELM327 not available (pyserial missing?)")

    print("\n[MAIN] [OK] All components ready!")
    print("[MAIN] Press ESC in window or Ctrl+C to stop\n")
    return True

# PROCESS FRAME
def process_frame():
    if not state.camera or not state.processor:
        return False

    try:
        ok, frame = state.camera.read()
        if not ok or frame is None:
            return False

        state.current_frame = frame.copy()

        # Process
        state.processor.enable_red = True
        state.processor.enable_canny = True
        state.processor.enable_ellipse = True
        state.processor.read_sign_enabled = True

        # reset frame-local output before processing
        state.processor.last_sign_center = None

        result = state.processor.process(frame)

        # Get results directly from processor output
        detected_speed = getattr(state.processor, 'last_speed', None)

        if detected_speed is not None:
            state.sign_detected_status = True
            state.detected_sign = detected_speed
        else:
            state.sign_detected_status = False
            state.detected_sign = None

        state.sign_center = getattr(state.processor, 'last_sign_center', None)

        # CPU tracking
        cpu = get_cpu_usage()
        if cpu >= 0:
            state.cpu_samples.append(cpu)
            state.timestamps.append(time.time() - state.start_time)

        state.frame_count += 1
        return True
    except Exception as e:
        print(f"[ERROR] Frame processing: {e}")
        return False

# DISPLAY
def display_status():
    now = time.time()
    if now - state.last_display_time < 0.1:
        return

    state.last_display_time = now

    detected_text = "Yes" if state.sign_detected_status else "No"
    read_sign_text = f"{state.detected_sign}" if state.detected_sign is not None else "--"

    status = f"Vehicle speed: {state.vehicle_speed} km/h | Detected sign: {detected_text} | Read sign: {read_sign_text} km/h"
    sys.stdout.write(f"\r{status:<100}")
    sys.stdout.flush()

def display_frame():
    if state.current_frame is None:
        return

    try:
        frame = state.current_frame.copy()

        detected_text = "Yes" if state.sign_detected_status else "No"
        read_sign_text = f"{state.detected_sign}" if state.detected_sign is not None else "--"

        cv2.putText(frame, f"Speed: {state.vehicle_speed} km/h", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
        cv2.putText(frame, f"Detected: {detected_text}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0) if state.sign_detected_status else (0,0,255), 2)
        cv2.putText(frame, f"Read: {read_sign_text} km/h", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        if state.sign_center and len(state.sign_center) >= 2:
            x, y = int(state.sign_center[0]), int(state.sign_center[1])
            if len(state.sign_center) >= 4:
                a, b = int(state.sign_center[2]), int(state.sign_center[3])
                cv2.ellipse(frame, (x, y), (a, b), 0, 0, 360, (0,255,0), 3)
            else:
                cv2.circle(frame, (x, y), 10, (0,255,0), -1)

        cv2.imshow("VisionPilot XR", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            state.running = False
    except Exception as e:
        pass

# MAIN LOOP
def run():
    print("[MAIN] Starting main loop...\n")

    state.running = True
    state.start_time = time.time()

    try:
        while state.running:
            ok = process_frame()
            display_status()
            display_frame()
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        state.running = False
        cv2.destroyAllWindows()

# SHUTDOWN
def shutdown():
    print("\n\n")

    if state.camera:
        try:
            state.camera.stop()
        except:
            pass

    if state.elm327_reader:
        try:
            state.elm327_reader.running = False
        except:
            pass

    if plt and len(state.cpu_samples) > 0:
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(state.timestamps, state.cpu_samples, 'b-', linewidth=2)
            plt.xlabel('Time (s)')
            plt.ylabel('CPU Usage (%)')
            plt.title('CPU Usage During VisionPilot XR')
            plt.grid(True, alpha=0.3)
            plt.ylim(0, 100)

            avg = np.mean(state.cpu_samples)
            plt.text(0.5, 0.95, f'Avg: {avg:.1f}%', transform=plt.gca().transAxes, ha='center')

            log_dir = Path("log_files")
            log_dir.mkdir(exist_ok=True)
            graph_file = log_dir / f"cpu_graph_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
            plt.savefig(str(graph_file), dpi=100)
            print(f"[MAIN] Graph saved: {graph_file}\n")
            plt.show()
        except Exception as e:
            print(f"[MAIN] Graph error: {e}\n")

    print("[MAIN] ============================================")
    print(f"[MAIN] Frames: {state.frame_count}")
    print(f"[MAIN] Time: {time.time() - state.start_time:.2f}s")
    print("[MAIN] ============================================\n")

# MAIN
def main():
    print("\n[MAIN] ============================================")
    print("[MAIN] VisionPilot XR - OpenCV GUI Mode")
    print(f"[MAIN] Platform: {platform.system()}")
    if IS_JETSON:
        print("[MAIN] Device: NVIDIA Jetson")
    print("[MAIN] ============================================")

    if not init_all():
        print("[MAIN] Initialization failed")
        sys.exit(1)

    try:
        run()
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        shutdown()

if __name__ == "__main__":
    main()
