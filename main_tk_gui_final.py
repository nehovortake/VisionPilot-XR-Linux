#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Simple Tkinter GUI + one-line terminal status

Features:
- Small Tkinter preview window for visual control
- Terminal shows only ONE updating line during runtime:
  Vehicle speed | Detection | Read sign
- ESC closes the app
- CPU graph is saved to PNG on shutdown, but never shown in a popup
- No cv2.imshow()
- No PIL/ImageTk dependency
"""

import os
import sys
import time
import platform
import traceback
import tkinter as tk
from pathlib import Path

import cv2
import numpy as np

print(f"[INIT] LD_PRELOAD={os.environ.get('LD_PRELOAD', 'Not set')}")

try:
    import psutil
except ImportError:
    psutil = None

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# ---------------------------------------------------------
# Imports
# ---------------------------------------------------------
try:
    from realsense import RealSenseCamera
    print("[INIT] RealSenseCamera: OK")
except Exception as e:
    print(f"[INIT] RealSense import FAILED: {e}")
    RealSenseCamera = None

try:
    from image_processing import ImageProcessor
    print("[INIT] ImageProcessor: OK")
except Exception as e:
    print(f"[INIT] ImageProcessor import FAILED: {e}")
    ImageProcessor = None

try:
    from read_speed import PerceptronSpeedReader
    _test = PerceptronSpeedReader()
    del _test
    print("[INIT] PerceptronSpeedReader: OK")
except Exception:
    print("[INIT] PerceptronSpeedReader FAILED:")
    traceback.print_exc()
    print(
        "\n[INIT] NOTE: On Jetson, run via ./run_visionpilot.sh if torch needs LD_PRELOAD.\n"
        "[INIT] If MLP is unavailable, Detection can still be Yes, but Read sign stays --.\n"
    )
    PerceptronSpeedReader = None

try:
    from elm327_can_speed import ELM327SpeedReader
    print("[INIT] ELM327SpeedReader: OK")
except Exception as e:
    print(f"[INIT] ELM327SpeedReader import FAILED: {e}")
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
        self.preview_frame = None

        self.cpu_samples = []
        self.timestamps = []
        self.last_display_time = 0.0

        self.tk_root = None
        self.tk_canvas = None
        self.tk_status = None
        self.tk_img = None
        self.canvas_img_id = None

        self.last_error_text = None


state = State()


def get_cpu_usage():
    if psutil is not None:
        try:
            return psutil.cpu_percent(interval=0.001)
        except Exception:
            pass
    return 0.0


def init_all():
    print("\n[MAIN] ============================================")
    print("[MAIN] Initializing Components")
    print("[MAIN] ============================================\n")

    print("[MAIN] [1/4] Camera...")
    if RealSenseCamera is None:
        print("[MAIN] [NO] RealSenseCamera not available")
        return False
    try:
        state.camera = RealSenseCamera(width=1920, height=1080, fps=30)
        state.camera.start()
        print("[MAIN] [OK] Camera initialized")
    except Exception as e:
        print(f"[MAIN] [NO] Camera failed: {e}")
        return False

    print("[MAIN] [2/4] Image Processor...")
    if ImageProcessor is None:
        print("[MAIN] [NO] ImageProcessor not available")
        return False
    try:
        state.processor = ImageProcessor()
        state.processor.enable_red = True
        state.processor.enable_canny = True
        state.processor.enable_ellipse = True
        state.processor.read_sign_enabled = True
        print("[MAIN] [OK] Processor initialized")
    except Exception as e:
        print(f"[MAIN] [NO] Processor failed: {e}")
        return False

    print("[MAIN] [3/4] MLP Speed Reader...")
    if PerceptronSpeedReader is None:
        print("[MAIN] [WARN] MLP Reader not available — read sign disabled")
    else:
        try:
            state.speed_reader = PerceptronSpeedReader()
            state.processor.speed_reader = state.speed_reader
            state.processor.read_sign_enabled = True
            print("[MAIN] [OK] MLP Reader initialized")
        except Exception as e:
            print(f"[MAIN] [WARN] MLP Reader failed: {e}")
            state.speed_reader = None

    print("[MAIN] [4/4] ELM327 CAN Reader...")
    if ELM327SpeedReader is None:
        print("[MAIN] [WARN] ELM327 not available (optional)")
    else:
        try:
            state.elm327_reader = ELM327SpeedReader()
            state.elm327_reader.start()
            print("[MAIN] [OK] ELM327 reader started")
        except Exception as e:
            print(f"[MAIN] [WARN] ELM327 failed: {e}")
            state.elm327_reader = None

    print("\n[MAIN] [OK] All components ready!")
    print("[MAIN] Close window, press ESC, or Ctrl+C to stop.\n")
    return True


def build_overlay_frame(frame_bgr: np.ndarray) -> np.ndarray:
    frame = frame_bgr.copy()

    detected_text = "Yes" if state.sign_detected_status else "No"
    read_sign_text = str(state.detected_sign) if state.detected_sign is not None else "--"

    cv2.putText(frame, f"Vehicle: {state.vehicle_speed} km/h", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
    cv2.putText(frame, f"Detection: {detected_text}", (20, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (0, 255, 0) if state.sign_detected_status else (0, 0, 255), 2)
    cv2.putText(frame, f"Read sign: {read_sign_text} km/h", (20, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    sc = state.sign_center
    if sc is not None:
        try:
            if len(sc) >= 4:
                x, y, a, b = map(int, sc[:4])
                cv2.ellipse(frame, (x, y), (max(1, a), max(1, b)), 0, 0, 360, (0, 255, 0), 3)
            elif len(sc) >= 2:
                x, y = map(int, sc[:2])
                cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)
        except Exception:
            pass

    return frame


def process_frame():
    if state.camera is None or state.processor is None:
        return False

    try:
        ok, frame = state.camera.read()
        if not ok or frame is None:
            return False

        state.current_frame = frame.copy()

        state.processor.enable_red = True
        state.processor.enable_canny = True
        state.processor.enable_ellipse = True
        state.processor.read_sign_enabled = (state.speed_reader is not None)

        try:
            state.processor.last_sign_center = None
        except Exception:
            pass
        try:
            state.processor.last_speed = None
        except Exception:
            pass

        processed = state.processor.process(frame)

        state.sign_center = getattr(state.processor, "last_sign_center", None)
        state.detected_sign = getattr(state.processor, "last_speed", None)

        # Detection = localization found, Read sign = MLP value
        state.sign_detected_status = state.sign_center is not None

        if isinstance(processed, np.ndarray) and processed.size > 0:
            if len(processed.shape) == 2:
                processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            base = processed
        else:
            base = frame

        state.preview_frame = build_overlay_frame(base)

        cpu = get_cpu_usage()
        if cpu >= 0:
            state.cpu_samples.append(cpu)
            state.timestamps.append(time.time() - state.start_time)

        state.frame_count += 1
        return True

    except Exception as e:
        # no spam during runtime; keep last error only
        state.last_error_text = str(e)
        return False


def display_status():
    now = time.time()
    if now - state.last_display_time < 0.1:
        return

    state.last_display_time = now

    detected_text = "Yes" if state.sign_detected_status else "No"
    read_sign_text = str(state.detected_sign) if state.detected_sign is not None else "--"

    status = (
        f"Vehicle speed: {state.vehicle_speed} km/h | "
        f"Detection: {detected_text} | "
        f"Read sign: {read_sign_text} km/h"
    )

    # exactly one updating terminal line
    sys.stdout.write("\r" + status.ljust(120))
    sys.stdout.flush()

    if state.tk_status is not None:
        try:
            state.tk_status.config(text=status)
        except Exception:
            pass


def on_tk_close():
    state.running = False


def init_tk():
    root = tk.Tk()
    root.title("VisionPilot XR - Simple Preview")
    root.geometry("980x620")
    root.minsize(820, 540)
    root.configure(bg="#101010")
    root.protocol("WM_DELETE_WINDOW", on_tk_close)
    root.bind("<Escape>", lambda event: on_tk_close())

    title = tk.Label(
        root,
        text="VisionPilot XR",
        font=("Arial", 16, "bold"),
        fg="white",
        bg="#101010"
    )
    title.pack(pady=(10, 4))

    status = tk.Label(
        root,
        text="Waiting for frames...",
        font=("Consolas", 11),
        fg="#7CFC90",
        bg="#101010"
    )
    status.pack(pady=(0, 8))

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=10, pady=10)

    state.tk_root = root
    state.tk_canvas = canvas
    state.tk_status = status
    state.canvas_img_id = None


def update_gui_frame():
    if state.tk_root is None or state.tk_canvas is None:
        return

    frame = state.preview_frame
    if frame is None:
        return

    try:
        canvas_w = max(640, state.tk_canvas.winfo_width())
        canvas_h = max(360, state.tk_canvas.winfo_height())

        h, w = frame.shape[:2]
        scale = min(canvas_w / float(w), canvas_h / float(h))
        if scale <= 0:
            scale = 1.0

        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # No PIL needed: encode to PPM and load via Tk PhotoImage
        ok, buf = cv2.imencode(".ppm", rgb)
        if not ok:
            return

        img = tk.PhotoImage(data=buf.tobytes())
        state.tk_img = img

        state.tk_canvas.delete("all")
        x = canvas_w // 2
        y = canvas_h // 2
        state.tk_canvas.create_image(x, y, image=img, anchor="center")

    except Exception:
        pass


def run():
    print("[MAIN] Starting main loop...")

    state.running = True
    state.start_time = time.time()
    init_tk()

    try:
        while state.running:
            if state.tk_root is not None:
                try:
                    state.tk_root.update_idletasks()
                    state.tk_root.update()
                except tk.TclError:
                    state.running = False
                    break

            process_frame()
            display_status()
            update_gui_frame()
            time.sleep(0.001)

    except KeyboardInterrupt:
        state.running = False
    finally:
        try:
            if state.tk_root is not None:
                state.tk_root.destroy()
        except Exception:
            pass


def shutdown():
    # clear the one-line runtime status cleanly
    sys.stdout.write("\r" + " " * 140 + "\r")
    sys.stdout.flush()
    print()

    if state.camera is not None:
        try:
            state.camera.stop()
        except Exception:
            pass

    if state.elm327_reader is not None:
        try:
            state.elm327_reader.running = False
        except Exception:
            pass

    if plt is not None and len(state.cpu_samples) > 0:
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(state.timestamps, state.cpu_samples, linewidth=2)
            plt.xlabel("Time (s)")
            plt.ylabel("CPU Usage (%)")
            plt.title("CPU Usage During VisionPilot XR")
            plt.grid(True, alpha=0.3)
            plt.ylim(0, 100)

            avg = float(np.mean(state.cpu_samples))
            plt.text(0.5, 0.95, f"Avg: {avg:.1f}%", transform=plt.gca().transAxes, ha="center")

            log_dir = Path("log_files")
            log_dir.mkdir(exist_ok=True)
            graph_file = log_dir / f"cpu_graph_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
            plt.savefig(str(graph_file), dpi=100)
            plt.close()
            print(f"[MAIN] Graph saved: {graph_file}")
        except Exception as e:
            print(f"[MAIN] Graph error: {e}")

    print("[MAIN] ============================================")
    print(f"[MAIN] Frames: {state.frame_count}")
    if state.start_time is not None:
        print(f"[MAIN] Time: {time.time() - state.start_time:.2f}s")
    print("[MAIN] ============================================")


def main():
    print("\n[MAIN] ============================================")
    print("[MAIN] VisionPilot XR - Tkinter GUI Mode")
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
        print(f"\n[ERROR] {e}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
