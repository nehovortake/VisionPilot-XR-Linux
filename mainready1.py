#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Simple Tkinter GUI + one-line terminal status
ELM327 vehicle speed + buzzer support
"""

import os
import sys
import time
import platform
import traceback
import tkinter as tk
from pathlib import Path
from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageTk

print(f"[INIT] LD_PRELOAD={os.environ.get('LD_PRELOAD', 'Not set')}")

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    from realsense import RealSenseCamera
    print("[INIT] RealSenseCamera: OK")
except Exception as e:
    print(f"[INIT] RealSense import FAILED: {e}")
    RealSenseCamera = None

try:
    import image_processing as image_processing_module
    from image_processing import ImageProcessor, start_process_log, stop_process_log
    print("[INIT] ImageProcessor: OK")
except Exception as e:
    print(f"[INIT] ImageProcessor import FAILED: {e}")
    image_processing_module = None
    ImageProcessor = None
    start_process_log = None
    stop_process_log = None

try:
    from read_speed import PerceptronSpeedReader
    print("[INIT] read_speed imported")
    _test = PerceptronSpeedReader()
    print("[INIT] PerceptronSpeedReader test instance created")
    del _test
    print("[INIT] PerceptronSpeedReader: OK")
except Exception as e:
    print("[INIT] PerceptronSpeedReader FAILED:")
    print(f"[INIT] Exact error: {type(e).__name__}: {e}")
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

# =========================
# BUZZER (Jetson GPIO - BC537 base drive)
# =========================
BUZZER_AVAILABLE = False
GPIO = None
BUZZER_PIN = 33  # BOARD pin; this pin drives BC537 base through resistor

try:
    import Jetson.GPIO as GPIO
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    BUZZER_AVAILABLE = True
    print(f"[INIT] BUZZER GPIO: OK (BOARD pin {BUZZER_PIN})")
except Exception as e:
    print(f"[INIT] BUZZER GPIO unavailable: {e}")
    BUZZER_AVAILABLE = False
    GPIO = None


IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")


class JetsonCPUMonitor:
    def __init__(self):
        self.prev_total = None
        self.prev_idle = None

    def read(self):
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline().strip()

            parts = line.split()
            if not parts or parts[0] != "cpu":
                return 0.0

            values = list(map(int, parts[1:]))

            user = values[0]
            nice = values[1]
            system = values[2]
            idle = values[3]
            iowait = values[4] if len(values) > 4 else 0
            irq = values[5] if len(values) > 5 else 0
            softirq = values[6] if len(values) > 6 else 0
            steal = values[7] if len(values) > 7 else 0

            idle_all = idle + iowait
            non_idle = user + nice + system + irq + softirq + steal
            total = idle_all + non_idle

            if self.prev_total is None or self.prev_idle is None:
                self.prev_total = total
                self.prev_idle = idle_all
                return 0.0

            total_diff = total - self.prev_total
            idle_diff = idle_all - self.prev_idle

            self.prev_total = total
            self.prev_idle = idle_all

            if total_diff <= 0:
                return 0.0

            cpu_percent = 100.0 * (1.0 - (idle_diff / total_diff))
            return max(0.0, min(cpu_percent, 100.0))
        except Exception:
            return 0.0


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

        self.buzzer_enabled = True
        self.overspeed_active = False

        self.frame_count = 0
        self.start_time = None
        self.current_frame = None
        self.preview_frame = None

        self.cpu_samples = []
        self.timestamps = []
        self.last_display_time = 0.0
        self.last_status_len = 0

        self.last_cpu = 0.0
        self.last_proc_ms = 0.0
        self.last_capture_ms = 0.0
        self.last_overlay_ms = 0.0
        self.last_frame_ms = 0.0
        self.last_fps = 0.0
        self.prev_frame_end = None
        self.cpu_monitor = JetsonCPUMonitor()

        self.tk_root = None
        self.tk_label = None
        self.tk_status = None
        self.tk_img = None
        self.process_crop_ratio = 0.60  # match original gui.py style: top 3/5 of frame

        # Graph logging
        self.output_fps_samples = []
        self.camera_fps_samples = []
        self.proc_ms_samples = []
        self.total_ms_samples = []
        self.capture_ms_samples = []
        self.red_ms_samples = []
        self.canny_ms_samples = []
        self.ellipse_ms_samples = []
        self.read_sign_ms_samples = []
        self.graph_timestamps = []
        self.detection_events = []
        self.last_camera_frame_end = None
        self.process_log_last_len = 0


state = State()


def get_cpu_usage():
    return state.cpu_monitor.read()


def set_buzzer(active: bool):
    if not state.buzzer_enabled or not BUZZER_AVAILABLE or GPIO is None:
        return
    try:
        GPIO.output(BUZZER_PIN, GPIO.HIGH if active else GPIO.LOW)
    except Exception as e:
        print(f"\n[BUZZER] GPIO error: {e}")


def update_overspeed_alert():
    detected = state.detected_sign
    overspeed = False
    try:
        if detected is not None:
            overspeed = int(state.vehicle_speed) > int(float(detected))
    except Exception:
        overspeed = False

    if overspeed != state.overspeed_active:
        state.overspeed_active = overspeed
        set_buzzer(overspeed)


def on_vehicle_speed(speed):
    try:
        state.vehicle_speed = int(speed)
    except Exception:
        return

    try:
        if image_processing_module is not None and hasattr(image_processing_module, "set_vehicle_speed"):
            image_processing_module.set_vehicle_speed(state.vehicle_speed)
    except Exception:
        pass

    update_overspeed_alert()


def init_all():
    print("\n[MAIN] ============================================")
    print("[MAIN] Initializing Components")
    print("[MAIN] ============================================\n")

    print("[MAIN] [1/4] Camera...")
    if RealSenseCamera is None:
        print("[MAIN] [NO] RealSenseCamera not available")
        return False
    try:
        state.camera = RealSenseCamera(width=1280, height=720, fps=30)
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
        if start_process_log is not None:
            try:
                start_process_log()
                state.process_log_last_len = 0
                print("[MAIN] [OK] Processor initialized + process logging enabled")
            except Exception as log_e:
                print(f"[MAIN] [WARN] Process log start failed: {log_e}")
                print("[MAIN] [OK] Processor initialized")
        else:
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

            try:
                dummy = np.zeros((64, 64, 3), dtype=np.uint8)
                state.speed_reader.predict_from_crop(dummy)
                print("[MAIN] [OK] MLP Reader initialized (warmed up)")
            except Exception:
                print("[MAIN] [OK] MLP Reader initialized")
        except Exception as e:
            print(f"[MAIN] [WARN] MLP Reader failed: {e}")
            state.speed_reader = None

    print("[MAIN] [4/4] ELM327 CAN Reader...")
    if ELM327SpeedReader is None:
        print("[MAIN] [WARN] ELM327 not available (optional)")
    else:
        try:
            elm_port = os.environ.get("ELM327_PORT") or None
            elm_baud = os.environ.get("ELM327_BAUD")
            elm_baud = int(elm_baud) if elm_baud else None
            print(f"[MAIN] [INFO] ELM config | port={elm_port or 'AUTO'} | baud={elm_baud or 'AUTO'}")
            state.elm327_reader = ELM327SpeedReader(
                port=elm_port,
                baudrate=elm_baud,
                callback=on_vehicle_speed,
                debug=True,
            )
            state.elm327_reader.start()
            print("[MAIN] [OK] ELM327 reader started")
        except Exception as e:
            print(f"[MAIN] [WARN] ELM327 failed: {e}")
            state.elm327_reader = None

    print("\n[MAIN] [OK] All components ready!")
    print("[MAIN] Close the Tk window or press Ctrl+C to stop.\n")
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

    cv2.putText(frame, f"Alarm: {'ON' if state.overspeed_active else 'OFF'}", (20, 175),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (0, 0, 255) if state.overspeed_active else (180, 180, 180), 2)
    cv2.putText(frame, f"Proc: {state.last_proc_ms:6.2f} ms", (20, 210),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Cap: {state.last_capture_ms:6.2f} ms", (20, 245),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Total: {state.last_frame_ms:6.2f} ms", (20, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"FPS: {state.last_fps:5.1f}", (20, 315),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"CPU: {state.last_cpu:5.1f}%", (20, 350),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

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



def _safe_ms(value):
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _record_pipeline_metrics(now_rel_s: float):
    if image_processing_module is None:
        return

    try:
        proc_log = getattr(image_processing_module, "_process_log", None)
        if proc_log is None:
            return

        proc_log_len = len(proc_log)
        if proc_log_len <= state.process_log_last_len:
            return

        last_entry = proc_log[-1]
        state.process_log_last_len = proc_log_len

        state.red_ms_samples.append(_safe_ms(last_entry.get("red_ms")))
        state.canny_ms_samples.append(_safe_ms(last_entry.get("canny_ms")))
        state.ellipse_ms_samples.append(_safe_ms(last_entry.get("ellipse_ms")))
        state.read_sign_ms_samples.append(_safe_ms(last_entry.get("read_sign_ms")))

        detected_speed = last_entry.get("detected_speed")
        read_count = int(last_entry.get("read_sign_count") or 0)
        if detected_speed is None:
            if read_count > 0:
                state.detection_events.append("No read")
            else:
                state.detection_events.append("No detection")
        else:
            state.detection_events.append(str(int(detected_speed)))
    except Exception:
        state.red_ms_samples.append(0.0)
        state.canny_ms_samples.append(0.0)
        state.ellipse_ms_samples.append(0.0)
        state.read_sign_ms_samples.append(0.0)
        state.detection_events.append("No detection")


def process_frame():
    if state.camera is None or state.processor is None:
        return False

    frame_start = time.perf_counter()

    try:
        t_cap = time.perf_counter()
        ok, frame = state.camera.read()
        cap_end = time.perf_counter()
        state.last_capture_ms = (cap_end - t_cap) * 1000.0
        if not ok or frame is None:
            return False

        if state.last_camera_frame_end is not None:
            cam_dt = cap_end - state.last_camera_frame_end
            if cam_dt > 0:
                state.camera_fps_samples.append(1.0 / cam_dt)
            else:
                state.camera_fps_samples.append(0.0)
        else:
            state.camera_fps_samples.append(0.0)
        state.last_camera_frame_end = cap_end

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

        # Keep vehicle speed in processing log, too.
        try:
            if image_processing_module is not None and hasattr(image_processing_module, "set_vehicle_speed"):
                image_processing_module.set_vehicle_speed(state.vehicle_speed)
        except Exception:
            pass

        # Match original gui.py behavior: process only the top 3/5 of the frame.
        frame_h, frame_w = frame.shape[:2]
        crop_h = max(1, int(frame_h * state.process_crop_ratio))
        proc_frame = frame[:crop_h, :]

        t_proc = time.perf_counter()
        processed = state.processor.process(proc_frame)
        state.last_proc_ms = (time.perf_counter() - t_proc) * 1000.0

        raw_sign_center = getattr(state.processor, "last_sign_center", None)
        if raw_sign_center is not None:
            state.sign_center = raw_sign_center
        else:
            state.sign_center = None

        state.detected_sign = getattr(state.processor, "last_speed", None)
        state.sign_detected_status = state.sign_center is not None
        update_overspeed_alert()

        # Build a full-size preview frame while only showing processed result in the top crop area.
        base = frame.copy()
        if isinstance(processed, np.ndarray) and processed.size > 0:
            if len(processed.shape) == 2:
                processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            try:
                if processed.shape[:2] == proc_frame.shape[:2]:
                    base[:crop_h, :] = processed
                else:
                    resized_processed = cv2.resize(processed, (frame_w, crop_h), interpolation=cv2.INTER_AREA)
                    base[:crop_h, :] = resized_processed
            except Exception:
                pass

        t_ov = time.perf_counter()
        state.preview_frame = build_overlay_frame(base)
        state.last_overlay_ms = (time.perf_counter() - t_ov) * 1000.0

        frame_end = time.perf_counter()
        state.last_frame_ms = (frame_end - frame_start) * 1000.0

        instant_output_fps = 0.0
        if state.prev_frame_end is not None:
            dt = frame_end - state.prev_frame_end
            if dt > 0:
                instant_output_fps = 1.0 / dt
                if state.last_fps <= 0:
                    state.last_fps = instant_output_fps
                else:
                    state.last_fps = 0.85 * state.last_fps + 0.15 * instant_output_fps
        state.prev_frame_end = frame_end

        cpu = get_cpu_usage()
        state.last_cpu = cpu

        now_rel_s = time.time() - state.start_time
        if cpu >= 0:
            state.cpu_samples.append(cpu)
            state.timestamps.append(now_rel_s)

        state.graph_timestamps.append(now_rel_s)
        state.output_fps_samples.append(instant_output_fps if instant_output_fps > 0 else state.last_fps)
        state.proc_ms_samples.append(float(state.last_proc_ms))
        state.total_ms_samples.append(float(state.last_frame_ms))
        state.capture_ms_samples.append(float(state.last_capture_ms))
        _record_pipeline_metrics(now_rel_s)

        state.frame_count += 1
        return True

    except Exception as e:
        print(f"\n[ERROR] Frame processing: {e}")
        return False


def display_status():
    now = time.time()
    if now - state.last_display_time < 0.15:
        return

    state.last_display_time = now

    detected_text = "Yes" if state.sign_detected_status else "No"
    read_sign_text = str(state.detected_sign) if state.detected_sign is not None else "--"

    status = (
        f"V:{state.vehicle_speed:>3} "
        f"D:{detected_text[0]} "
        f"S:{read_sign_text:>3} "
        f"A:{'1' if state.overspeed_active else '0'} "
        f"P:{state.last_proc_ms:4.0f} "
        f"C:{state.last_capture_ms:4.0f} "
        f"T:{state.last_frame_ms:4.0f} "
        f"F:{state.last_fps:4.1f} "
        f"CPU:{state.last_cpu:4.0f}"
    )

    if state.tk_status is not None:
        try:
            gui_status = (
                f"Vehicle speed: {state.vehicle_speed} km/h | "
                f"Detection: {detected_text} | "
                f"Read sign: {read_sign_text} km/h | "
                f"Alarm: {'ON' if state.overspeed_active else 'OFF'} | "
                f"Proc: {state.last_proc_ms:6.2f} ms | "
                f"Cap: {state.last_capture_ms:6.2f} ms | "
                f"Total: {state.last_frame_ms:6.2f} ms | "
                f"FPS: {state.last_fps:5.1f} | "
                f"CPU: {state.last_cpu:5.1f}% | "
                f"Crop: top {int(state.process_crop_ratio*100)}%"
            )
            state.tk_status.configure(text=gui_status)
        except Exception:
            pass

    sys.stdout.write("\r\033[K" + status)
    sys.stdout.flush()
    state.last_status_len = len(status)


def on_tk_close():
    state.running = False


def init_tk():
    root = tk.Tk()
    root.title("VisionPilot XR - Simple Preview")
    root.geometry("980x620")
    root.minsize(820, 540)
    root.configure(bg="#101010")
    root.protocol("WM_DELETE_WINDOW", on_tk_close)

    title = tk.Label(
        root,
        text="VisionPilot XR (HD 1280x720)",
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
        bg="#101010",
        wraplength=940,
        justify="left"
    )
    status.pack(pady=(0, 8))

    label = tk.Label(root, bg="black")
    label.pack(fill="both", expand=True, padx=10, pady=10)

    state.tk_root = root
    state.tk_label = label
    state.tk_status = status


def update_gui_frame():
    if state.tk_root is None or state.tk_label is None:
        return

    frame = state.preview_frame
    if frame is None:
        return

    try:
        h, w = frame.shape[:2]
        max_w = max(640, state.tk_label.winfo_width())
        max_h = max(360, state.tk_label.winfo_height())

        scale = min(max_w / float(w), max_h / float(h))
        if scale <= 0:
            scale = 1.0

        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        pil_img = Image.fromarray(rgb)
        tk_img = ImageTk.PhotoImage(image=pil_img)

        state.tk_img = tk_img
        state.tk_label.configure(image=tk_img)
    except Exception:
        pass


def run():
    print("[MAIN] Starting main loop...\n")

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
        pass
    finally:
        state.running = False
        try:
            if state.tk_root is not None:
                state.tk_root.destroy()
        except Exception:
            pass


def shutdown():
    print("\n")

    try:
        set_buzzer(False)
    except Exception:
        pass

    if state.camera is not None:
        try:
            state.camera.stop()
        except Exception:
            pass

    if state.elm327_reader is not None:
        try:
            if hasattr(state.elm327_reader, "stop"):
                state.elm327_reader.stop()
            else:
                state.elm327_reader.running = False
        except Exception:
            pass

    if stop_process_log is not None:
        try:
            stop_process_log()
        except Exception as e:
            print(f"[MAIN] Process log stop warning: {e}")

    if BUZZER_AVAILABLE and GPIO is not None:
        try:
            GPIO.cleanup()
        except Exception as e:
            print(f"[MAIN] GPIO cleanup warning: {e}")

    if plt is not None:
        log_dir = Path("log_files")
        log_dir.mkdir(exist_ok=True)
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')

        def _save_current_plot(out_path: Path):
            plt.tight_layout()
            plt.savefig(str(out_path), dpi=100)
            plt.close()
            print(f"[MAIN] Graph saved: {out_path}")

        try:
            if len(state.cpu_samples) > 0:
                plt.figure(figsize=(12, 6))
                plt.plot(state.timestamps, state.cpu_samples, linewidth=2)
                plt.xlabel("Čas (s)")
                plt.ylabel("Využitie CPU (%)")
                plt.title("Využitie CPU počas behu VisionPilot XR")
                plt.grid(True, alpha=0.3)
                plt.ylim(0, 100)
                avg = float(np.mean(state.cpu_samples))
                plt.text(0.5, 0.95, f"Priemer: {avg:.1f}%", transform=plt.gca().transAxes, ha="center")
                _save_current_plot(log_dir / f"cpu_graph_{timestamp}.png")

            if len(state.graph_timestamps) > 0 and len(state.output_fps_samples) > 0:
                x = state.graph_timestamps
                cam = state.camera_fps_samples[:len(x)]
                out = state.output_fps_samples[:len(x)]
                if len(cam) < len(x):
                    cam = cam + [0.0] * (len(x) - len(cam))
                if len(out) < len(x):
                    out = out + [0.0] * (len(x) - len(out))

                plt.figure(figsize=(12, 6))
                avg_cam = float(np.mean(cam)) if len(cam) > 0 else 0.0
                avg_out = float(np.mean(out)) if len(out) > 0 else 0.0
                plt.plot(x, cam, linewidth=2, label=f"FPS kamery (priemer {avg_cam:.1f})")
                plt.plot(x, out, linewidth=2, label=f"FPS po spracovaní (priemer {avg_out:.1f})")
                plt.xlabel("Čas (s)")
                plt.ylabel("FPS")
                plt.title("Porovnanie FPS kamery a výstupných FPS")
                plt.grid(True, alpha=0.3)
                plt.legend()
                _save_current_plot(log_dir / f"fps_compare_{timestamp}.png")

            if len(state.graph_timestamps) > 0 and len(state.proc_ms_samples) > 0 and len(state.total_ms_samples) > 0:
                x = state.graph_timestamps
                proc = state.proc_ms_samples[:len(x)]
                total = state.total_ms_samples[:len(x)]

                plt.figure(figsize=(12, 6))
                avg_total = float(np.mean(total)) if len(total) > 0 else 0.0
                avg_proc = float(np.mean(proc)) if len(proc) > 0 else 0.0
                plt.plot(x, total, linewidth=2, label=f"Celkový čas (priemer {avg_total:.1f} ms)")
                plt.plot(x, proc, linewidth=2, label=f"Čas spracovania (priemer {avg_proc:.1f} ms)")
                plt.xlabel("Čas (s)")
                plt.ylabel("Čas spracovania (ms)")
                plt.title("Porovnanie celkového času a času spracovania")
                plt.grid(True, alpha=0.3)
                plt.legend()
                _save_current_plot(log_dir / f"total_vs_proc_{timestamp}.png")

            if len(state.graph_timestamps) > 0:
                x = state.graph_timestamps
                series = [
                    ("Získanie frame", state.capture_ms_samples),
                    ("Red", state.red_ms_samples),
                    ("Canny", state.canny_ms_samples),
                    ("Ellipse", state.ellipse_ms_samples),
                    ("Read sign", state.read_sign_ms_samples),
                ]

                plt.figure(figsize=(12, 6))
                anything = False
                for label, arr in series:
                    arr2 = arr[:len(x)]
                    if len(arr2) < len(x):
                        arr2 = arr2 + [0.0] * (len(x) - len(arr2))
                    if len(arr2) > 0:
                        avg_stage = float(np.mean(arr2)) if len(arr2) > 0 else 0.0
                        plt.plot(x, arr2, linewidth=2, label=f"{label} (priemer {avg_stage:.1f} ms)")
                        anything = True
                if anything:
                    plt.xlabel("Čas (s)")
                    plt.ylabel("Čas (ms)")
                    plt.title("Porovnanie časov jednotlivých častí pipeline")
                    plt.grid(True, alpha=0.3)
                    plt.legend()
                    _save_current_plot(log_dir / f"pipeline_times_{timestamp}.png")
                else:
                    plt.close()

            if len(state.detection_events) > 0:
                counts = Counter(state.detection_events)
                label_map = {"No detection": "Bez detekcie", "No read": "Detekované, ale neprečítané"}
                labels = [label_map.get(lbl, lbl) for lbl in counts.keys()]
                values = list(counts.values())

                plt.figure(figsize=(9, 9))
                plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
                plt.title("Rozdelenie detekcií")
                _save_current_plot(log_dir / f"detection_pie_{timestamp}.png")

        except Exception as e:
            print(f"[MAIN] Graph error: {e}")

    print("[MAIN] ============================================")
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
    print(f"[MAIN] Vehicle speed source: ELM327")
    print(f"[MAIN] Buzzer GPIO pin: BOARD {BUZZER_PIN} | GPIO available: {'YES' if BUZZER_AVAILABLE else 'NO'}")

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
