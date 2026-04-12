#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Jetson-safe main script
- terminal/headless output only
- no cv2.imshow / no Qt window backend
- fixes read-sign state handling
"""

import os
import sys
import platform
import time
from pathlib import Path

import cv2
import numpy as np

print(f"[INIT] LD_PRELOAD={os.environ.get('LD_PRELOAD', 'Not set')}")

try:
    import psutil
except ImportError:
    psutil = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None

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
    from read_speed_fixed import PerceptronSpeedReader
    print("[INIT] PerceptronSpeedReader module import: OK")
except Exception as e:
    print(f"[INIT] PerceptronSpeedReader module import FAILED: {e}")
    PerceptronSpeedReader = None

try:
    from elm327_can_speed import ELM327SpeedReader
except Exception as e:
    print(f"[INIT] ELM327SpeedReader import: {e}")
    ELM327SpeedReader = None

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")


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


def get_cpu_usage():
    if psutil:
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            pass
    return 0.0


def init_all():
    print("
[MAIN] ============================================")
    print("[MAIN] VisionPilot XR - Headless Mode")
    print(f"[MAIN] Platform: {platform.system()}")
    if IS_JETSON:
        print("[MAIN] Device: NVIDIA Jetson")
    print(f"[MAIN] Python: {platform.python_version()}")
    print("[MAIN] ============================================
")

    print("[MAIN] ============================================")
    print("[MAIN] Initializing all components...")
    print("[MAIN] ============================================
")

    print("[MAIN] [1/4] Initializing Camera...")
    if RealSenseCamera is None:
        print("[MAIN] [NO] RealSense not available")
        return False
    try:
        state.camera = RealSenseCamera(width=1920, height=1080, fps=30)
        state.camera.start()
        print("[MAIN] [OK] Camera initialized (1920x1080 @ 30 FPS)")
    except Exception as e:
        print(f"[MAIN] [NO] Camera failed: {e}")
        return False

    print("[MAIN] [2/4] Initializing Image Processor...")
    if ImageProcessor is None:
        print("[MAIN] [NO] ImageProcessor not available")
        return False
    try:
        state.processor = ImageProcessor()
        state.processor.enable_red = True
        state.processor.enable_canny = True
        state.processor.enable_ellipse = True
        state.processor.read_sign_enabled = False
        print("[MAIN] [OK] Image processor initialized")
        print("[MAIN]   - Red Nulling: ENABLED")
        print("[MAIN]   - Canny Edge: ENABLED")
        print("[MAIN]   - Ellipse Detection: ENABLED")
        print("[MAIN]   - Speed Reader: ENABLED")
    except Exception as e:
        print(f"[MAIN] [NO] ImageProcessor failed: {e}")
        return False

    print("[MAIN] [3/4] Initializing Speed Reader (MLP)...")
    if PerceptronSpeedReader is None:
        print("[MAIN] ⚠ MLP Speed Reader module not available")
        print("[MAIN] ⚠ continuing without speed classification")
    else:
        try:
            state.speed_reader = PerceptronSpeedReader()
            state.processor.speed_reader = state.speed_reader
            state.processor.read_sign_enabled = True
            print("[MAIN] [OK] MLP Speed Reader initialized")
        except Exception as e:
            print(f"[MAIN] ⚠ MLP Speed Reader not available ({e})")
            print("[MAIN] ⚠ continuing without speed classification")

    print("[MAIN] [4/4] Initializing ELM327 CAN Reader...")
    if ELM327SpeedReader is None:
        print("[MAIN] ⚠ ELM327SpeedReader not available (optional)")
        print("[MAIN] ⚠ ELM327 optional, continuing without vehicle speed")
    else:
        try:
            state.elm327_reader = ELM327SpeedReader()
            state.elm327_reader.start()
            print("[MAIN] [OK] ELM327 reader started")
        except Exception as e:
            print(f"[MAIN] ⚠ ELM327 failed: {e}")
            print("[MAIN] ⚠ ELM327 optional, continuing without vehicle speed")

    print("
[MAIN] ============================================")
    print("[MAIN] [OK] All components ready!")
    print("[MAIN] ============================================")
    print("[MAIN] Press Ctrl+C to stop
")
    return True


def process_frame():
    if not state.camera or not state.processor:
        return False

    try:
        ok, frame = state.camera.read()
        if not ok or frame is None:
            return False

        state.current_frame = frame.copy()

        # Reset frame-local outputs.
        state.processor.last_sign_center = None
        state.processor.last_speed = None

        state.processor.process(frame)

        # Detection = ellipse exists, not MLP classification.
        state.sign_center = getattr(state.processor, 'last_sign_center', None)
        state.sign_detected_status = state.sign_center is not None

        # Read sign = actual MLP output.
        detected_speed = getattr(state.processor, 'last_speed', None)
        state.detected_sign = detected_speed

        cpu = get_cpu_usage()
        if cpu >= 0:
            state.cpu_samples.append(cpu)
            state.timestamps.append(time.time() - state.start_time)

        state.frame_count += 1
        return True
    except Exception as e:
        print(f"
[ERROR] Frame processing: {e}")
        return False


def display_status():
    now = time.time()
    if now - state.last_display_time < 0.10:
        return

    state.last_display_time = now

    detected_text = "Yes" if state.sign_detected_status else "No"
    read_sign_text = f"{state.detected_sign}" if state.detected_sign is not None else "--"
    status = (
        f"Vehicle speed: {state.vehicle_speed} km/h | "
        f"Detected sign: {detected_text} | "
        f"Read sign: {read_sign_text} km/h"
    )
    sys.stdout.write("" + status.ljust(110))
    sys.stdout.flush()


def run():
    print("[MAIN] Starting main loop...
")
    state.running = True
    state.start_time = time.time()

    try:
        while state.running:
            process_frame()
            display_status()
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        state.running = False
        print()


def shutdown():
    print("

[MAIN] ============================================")
    print("[MAIN] Generating CPU usage graph...")
    print("[MAIN] ============================================
")

    if state.camera:
        try:
            state.camera.stop()
        except Exception:
            pass

    if state.elm327_reader:
        try:
            state.elm327_reader.running = False
        except Exception:
            pass

    if plt and len(state.cpu_samples) > 0:
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(state.timestamps, state.cpu_samples, linewidth=2)
            plt.xlabel('Time (s)')
            plt.ylabel('CPU Usage (%)')
            plt.title('CPU Usage During VisionPilot XR')
            plt.grid(True, alpha=0.3)
            plt.ylim(0, 100)

            log_dir = Path("log_files")
            log_dir.mkdir(exist_ok=True)
            graph_file = log_dir / f"cpu_graph_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
            plt.savefig(str(graph_file), dpi=100)
            plt.close()
            print(f"[MAIN] Graph saved to: {graph_file}
")

            avg = float(np.mean(state.cpu_samples)) if state.cpu_samples else 0.0
            mx = float(np.max(state.cpu_samples)) if state.cpu_samples else 0.0
            mn = float(np.min(state.cpu_samples)) if state.cpu_samples else 0.0
            print("[MAIN] CPU Statistics:")
            print(f"[MAIN]   - Average CPU: {avg:.2f}%")
            print(f"[MAIN]   - Max CPU: {mx:.2f}%")
            print(f"[MAIN]   - Min CPU: {mn:.2f}%")
            print(f"[MAIN]   - Total samples: {len(state.cpu_samples)}")
            runtime = (time.time() - state.start_time) if state.start_time else 0.0
            print(f"[MAIN]   - Runtime: {runtime:.2f}s")
            print("[MAIN] ============================================
")
        except Exception as e:
            print(f"[MAIN] Graph error: {e}
")

    print("[MAIN] ============================================")
    print("[MAIN] VisionPilot XR Completed")
    print(f"[MAIN] Total frames processed: {state.frame_count}")
    total_time = (time.time() - state.start_time) if state.start_time else 0.0
    print(f"[MAIN] Total time: {total_time:.2f}s")
    print("[MAIN] ============================================")


def main():
    if not init_all():
        print("[MAIN] Initialization failed")
        sys.exit(1)

    try:
        run()
    finally:
        shutdown()


if __name__ == "__main__":
    main()
