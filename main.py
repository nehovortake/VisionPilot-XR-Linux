#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisionPilot XR - Headless Main Script
Runs all image processing pipelines without GUI
Jetson Orin Nano Compatible (Python 3.8+)
"""

import os
import sys
import platform
import time
import threading
import subprocess
import cv2
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

try:
    import psutil
except ImportError:
    psutil = None

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")

# Jetson model detection
JETSON_MODEL = "Unknown"
if IS_JETSON:
    try:
        with open("/sys/devices/virtual/dmi/id/board_name", "r") as f:
            JETSON_MODEL = f.read().strip()
    except Exception:
        pass

# Python version
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"

# CPU monitoring function - Jetson compatible
def get_cpu_usage():
    """Get CPU usage on Jetson or regular Linux using tegrastats or psutil."""
    if IS_JETSON:
        try:
            # Jetson: Use tegrastats (Python 3.8 compatible)
            result = subprocess.run(
                ["tegrastats", "--interval", "100", "--count", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=2
            )
            for line in result.stdout.split('\n'):
                if 'CPU' in line:
                    import re
                    match = re.search(r'CPU \[([^\]]+)\]', line)
                    if match:
                        cpu_str = match.group(1)
                        cpus = [float(x.strip().rstrip('%')) for x in cpu_str.split(',')]
                        return np.mean(cpus)
            return 0
        except Exception:
            pass

    # Fallback to psutil on other platforms or if tegrastats fails
    if psutil is not None:
        try:
            return psutil.cpu_percent(interval=0.01)
        except Exception:
            return 0

    return 0

# =====================================================
# IMPORTS
# =====================================================

try:
    from realsense import RealSenseCamera
except Exception as e:
    RealSenseCamera = None

try:
    from image_processing import ImageProcessor, start_process_log, stop_process_log, set_vehicle_speed
except Exception as e:
    ImageProcessor = None

try:
    from read_speed import PerceptronSpeedReader
except Exception as e:
    print(f"[MAIN] Import warning: PerceptronSpeedReader - {e}")
    PerceptronSpeedReader = None

try:
    from elm327_can_speed import ELM327SpeedReader
except Exception as e:
    print(f"[MAIN] Import warning: ELM327SpeedReader - {e}")
    ELM327SpeedReader = None


# =====================================================
# GLOBAL STATE
# =====================================================

class PipelineState:
    def __init__(self):
        self.running = False
        self.camera = None
        self.processor = None
        self.speed_reader = None
        self.elm327_reader = None

        self.vehicle_speed = 0
        self.detected_sign = None
        self.sign_center = None
        self.last_vehicle_speed_print = 0
        self.last_sign_print = None
        self.last_detected_value = None

        self.frame_count = 0
        self.start_time = None
        self.current_frame = None

        # CPU monitoring
        self.cpu_samples = []
        self.timestamps = []

state = PipelineState()

# =====================================================
# ELM327 CALLBACK
# =====================================================

def on_vehicle_speed_received(speed_kmh):
    """Called when ELM327 reads a speed."""
    state.vehicle_speed = speed_kmh
    set_vehicle_speed(speed_kmh)


# =====================================================
# DISPLAY STATUS
# =====================================================

def display_status():
    """Display vehicle speed, detected sign status, and read sign value on one line."""
    detected_bool = state.detected_sign is not None
    detected_text = "Yes" if detected_bool else "No"
    read_sign_text = f"{state.detected_sign}" if state.detected_sign is not None else "--"

    status_line = f"Vehicle speed: {state.vehicle_speed} km/h | Detected sign: {detected_text} | Read sign: {read_sign_text} km/h"
    print(f"\r{status_line:<120}", end="", flush=True)

# =====================================================
# INITIALIZE CAMERA
# =====================================================

def init_camera():
    """Initialize RealSense camera."""
    if RealSenseCamera is None:
        print("[MAIN] RealSense not available, cannot initialize camera")
        return False

    try:
        state.camera = RealSenseCamera(width=1920, height=1080, fps=30, auto_exposure=True)
        state.camera.start()
        print("[MAIN] [OK] Camera initialized (1920x1080 @ 30 FPS)")
        return True
    except Exception as e:
        print(f"[MAIN] [NO] Failed to initialize camera: {e}")
        state.camera = None
        return False

# =====================================================
# INITIALIZE IMAGE PROCESSOR
# =====================================================

def init_processor():
    """Initialize image processing pipeline."""
    if ImageProcessor is None:
        print("[MAIN] ImageProcessor not available")
        return False

    try:
        state.processor = ImageProcessor()
        print("[MAIN] [OK] Image processor initialized")
        print("[MAIN]   - Red Nulling: ENABLED")
        print("[MAIN]   - Canny Edge: ENABLED")
        print("[MAIN]   - Ellipse Detection: ENABLED")
        print("[MAIN]   - Speed Reader: ENABLED")
        return True
    except Exception as e:
        print(f"[MAIN] [NO] Failed to initialize processor: {e}")
        state.processor = None
        return False

# =====================================================
# INITIALIZE SPEED READER
# =====================================================

def init_speed_reader():
    """Initialize MLP speed reader."""
    if PerceptronSpeedReader is None:
        print("[MAIN] ⚠ MLP Speed Reader not available (optional)")
        return False

    try:
        state.speed_reader = PerceptronSpeedReader()
        print("[MAIN] [OK] MLP Speed Reader initialized")
        return True
    except Exception as e:
        print(f"[MAIN] ⚠ MLP Speed Reader initialization failed: {e} (optional)")
        state.speed_reader = None
        return False

# =====================================================
# INITIALIZE ELM327
# =====================================================

def init_elm327():
    """Initialize ELM327 CAN speed reader."""
    if ELM327SpeedReader is None:
        print("[MAIN] ⚠ ELM327SpeedReader not available (optional)")
        return False

    try:
        # Auto-detect port - ELM327SpeedReader will find it
        state.elm327_reader = ELM327SpeedReader(
            port=None,  # Auto-detect
            baudrate=9600,
            callback=on_vehicle_speed_received
        )
        state.elm327_reader.start()
        print(f"[MAIN] [OK] ELM327 reader started on {state.elm327_reader.port}")
        return True
    except Exception as e:
        print(f"[MAIN] ⚠ Failed to initialize ELM327: {e} (optional)")
        state.elm327_reader = None
        return False

# =====================================================
# GUI WINDOW
# =====================================================

class VisionPilotWindow(QMainWindow):
    """GUI window for visualization."""

    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VisionPilot XR - Visual Control")
        self.setGeometry(100, 100, 1000, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Video label
        self.video_label = QLabel()
        self.video_label.setMinimumSize(960, 540)
        self.video_label.setStyleSheet("border: 1px solid black; background: black;")
        layout.addWidget(self.video_label)

        # Info label
        info_layout = QHBoxLayout()
        self.vehicle_speed_label = QLabel("Vehicle speed: -- km/h")
        self.vehicle_speed_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.vehicle_speed_label.setStyleSheet("color: blue;")

        self.detected_label = QLabel("Detected sign: No")
        self.detected_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.detected_label.setStyleSheet("color: red;")

        self.read_sign_label = QLabel("Read sign: -- km/h")
        self.read_sign_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.read_sign_label.setStyleSheet("color: green;")

        info_layout.addWidget(self.vehicle_speed_label)
        info_layout.addWidget(self.detected_label)
        info_layout.addWidget(self.read_sign_label)
        layout.addLayout(info_layout)

        # Setup timer for GUI updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(30)  # ~30 FPS

        self.last_frame = None

    def update_display(self):
        """Update GUI with latest data."""
        # Update video from state
        if hasattr(state, 'current_frame') and state.current_frame is not None:
            self.display_frame(state.current_frame)

        # Update labels
        self.vehicle_speed_label.setText(f"Vehicle speed: {state.vehicle_speed} km/h")

        detected_text = "Yes" if state.detected_sign is not None else "No"
        self.detected_label.setText(f"Detected sign: {detected_text}")
        if state.detected_sign is not None:
            self.detected_label.setStyleSheet("color: green;")
        else:
            self.detected_label.setStyleSheet("color: red;")

        read_sign_text = f"{state.detected_sign}" if state.detected_sign is not None else "--"
        self.read_sign_label.setText(f"Read sign: {read_sign_text} km/h")

    def display_frame(self, frame):
        """Display frame in label."""
        try:
            # Resize frame to fit label
            h, w = frame.shape[:2]
            scale = min(960 / w, 540 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            resized = cv2.resize(frame, (new_w, new_h))

            # Draw ellipse if detected
            if state.sign_center is not None and len(state.sign_center) >= 2:
                x, y = int(state.sign_center[0] * scale), int(state.sign_center[1] * scale)
                if len(state.sign_center) >= 4:
                    # state.sign_center = (cx, cy, half_w, half_h)
                    a, b = int(state.sign_center[2] * scale), int(state.sign_center[3] * scale)
                    cv2.ellipse(resized, (x, y), (a, b), 0, 0, 360, (0, 255, 0), 3)
                else:
                    cv2.circle(resized, (x, y), 10, (0, 255, 0), -1)

            # Convert to RGB
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = 3 * w
            qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qt_image)
            self.video_label.setPixmap(pixmap)
        except Exception as e:
            print(f"[GUI] Display error: {e}")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == 16777216:  # ESC key
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle window close."""
        state.running = False
        self.timer.stop()
        event.accept()

        # Quit the QApplication
        QApplication.instance().quit()

# =====================================================
# MAIN PROCESSING LOOP
# =====================================================

def process_frame():
    """Process a single frame through the pipeline."""
    if state.camera is None or state.processor is None:
        return False

    try:
        ok, frame = state.camera.read()
        if not ok or frame is None:
            return False

        # Store current frame for GUI
        state.current_frame = frame.copy()

        # Enable all processing features
        state.processor.enable_red = True
        state.processor.enable_canny = True
        state.processor.enable_ellipse = True
        state.processor.read_sign_enabled = True

        # Reset detection flag BEFORE processing this frame
        state.processor.sign_detected_this_frame = False

        # Run processor
        result_img = state.processor.process(frame)

        if result_img is None:
            return False

        # Get detected sign only if it was detected in THIS frame
        sign_detected_this_frame = getattr(state.processor, 'sign_detected_this_frame', False)
        if sign_detected_this_frame and hasattr(state.processor, 'last_speed'):
            detected_sign = state.processor.last_speed
        else:
            detected_sign = None

        state.detected_sign = detected_sign

        # Also store ellipse center for visualization
        if hasattr(state.processor, 'last_sign_center'):
            state.sign_center = state.processor.last_sign_center
        else:
            state.sign_center = None

        # Check if any value changed
        speed_changed = state.vehicle_speed != state.last_vehicle_speed_print
        detected_changed = detected_sign != state.last_sign_print
        read_sign_changed = detected_sign != state.last_detected_value

        # Display if anything changed
        if speed_changed or detected_changed or read_sign_changed:
            display_status()
            state.last_vehicle_speed_print = state.vehicle_speed
            state.last_sign_print = detected_sign
            state.last_detected_value = detected_sign

        # Record CPU usage (Jetson or standard)
        cpu_percent = get_cpu_usage()
        if cpu_percent > 0:
            state.cpu_samples.append(cpu_percent)
            state.timestamps.append(time.time() - state.start_time)

        state.frame_count += 1
        return True
    except Exception as e:
        print(f"[ERROR] Frame processing failed: {e}")
        return False

# =====================================================
# MAIN LOOP
# =====================================================

def run():
    """Main processing loop."""
    print("[MAIN] Starting main loop...\n")

    state.running = True
    state.start_time = time.time()

    frame_times = []

    try:
        while state.running:
            frame_start = time.time()

            # Process one frame
            ok = process_frame()

            frame_time = (time.time() - frame_start) * 1000  # ms
            frame_times.append(frame_time)

            # Keep only last 100 frame times
            if len(frame_times) > 100:
                frame_times.pop(0)

            # Sleep a bit to prevent 100% CPU
            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
    finally:
        state.running = False

# =====================================================
# SHUTDOWN
# =====================================================

def shutdown():
    """Clean shutdown of all components."""
    state.running = False

    # Stop ELM327
    if state.elm327_reader is not None:
        try:
            state.elm327_reader.running = False
        except Exception:
            pass

    # Stop camera
    if state.camera is not None:
        try:
            state.camera.stop()
        except Exception:
            pass

    # Clear the terminal line before showing final stats
    print("\n\n")

    # Display CPU graph
    print("[MAIN] ============================================")
    print("[MAIN] Generating CPU usage graph...")
    print("[MAIN] ============================================\n")

    if plt is not None and len(state.cpu_samples) > 0:
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(state.timestamps, state.cpu_samples, 'b-', linewidth=2, label='CPU Usage')
            plt.xlabel('Time (seconds)', fontsize=12)
            plt.ylabel('CPU Usage (%)', fontsize=12)
            plt.title('CPU Usage During VisionPilot XR Execution', fontsize=14, fontweight='bold')
            plt.grid(True, alpha=0.3)
            plt.legend(fontsize=11)

            # Add statistics
            avg_cpu = np.mean(state.cpu_samples)
            max_cpu = np.max(state.cpu_samples)
            min_cpu = np.min(state.cpu_samples)

            stats_text = f'Avg: {avg_cpu:.1f}% | Max: {max_cpu:.1f}% | Min: {min_cpu:.1f}%'
            plt.text(0.5, 0.95, stats_text, transform=plt.gca().transAxes,
                    ha='center', va='top', fontsize=11, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            # Save graph
            log_dir = os.path.join(os.path.dirname(__file__), "log_files")
            os.makedirs(log_dir, exist_ok=True)
            graph_file = os.path.join(log_dir, f"cpu_graph_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png")
            plt.savefig(graph_file, dpi=100)
            print(f"[MAIN] Graph saved to: {graph_file}\n")

            # Try to show graph
            try:
                plt.show()
            except Exception:
                pass

            print(f"[MAIN] CPU Statistics:")
            print(f"[MAIN]   - Average CPU: {avg_cpu:.2f}%")
            print(f"[MAIN]   - Max CPU: {max_cpu:.2f}%")
            print(f"[MAIN]   - Min CPU: {min_cpu:.2f}%")
            print(f"[MAIN]   - Total samples: {len(state.cpu_samples)}")
            print(f"[MAIN]   - Runtime: {state.timestamps[-1]:.2f}s")
            print("[MAIN] ============================================\n")
        except Exception as e:
            print(f"[MAIN] Error displaying CPU graph: {e}\n")
    elif plt is None:
        print("[MAIN] ⚠ matplotlib not installed, cannot display graph\n")
    else:
        print("[MAIN] ⚠ No CPU data collected\n")


# =====================================================
# MAIN ENTRY
# =====================================================

def main():
    """Main entry point."""

    print("[MAIN] ============================================")
    print("[MAIN] VisionPilot XR - Headless Mode")
    print(f"[MAIN] Platform: {platform.system()}")
    if IS_JETSON:
        print(f"[MAIN] Device: NVIDIA Jetson ({JETSON_MODEL})")
    print(f"[MAIN] Python: {PYTHON_VERSION}")
    print("[MAIN] ============================================\n")

    print("[MAIN] ============================================")
    print("[MAIN] Initializing all components...")
    print("[MAIN] ============================================\n")

    success = True

    print("[MAIN] [1/4] Initializing Camera...")
    if not init_camera():
        success = False

    print("[MAIN] [2/4] Initializing Image Processor...")
    if not init_processor():
        success = False

    print("[MAIN] [3/4] Initializing Speed Reader (MLP)...")
    if not init_speed_reader():
        print("[MAIN] ⚠ MLP Speed Reader optional, continuing without speed classification")

    print("[MAIN] [4/4] Initializing ELM327 CAN Reader...")
    if not init_elm327():
        print("[MAIN] ⚠ ELM327 optional, continuing without vehicle speed")

    # Connect speed_reader to processor
    if state.speed_reader is not None and state.processor is not None:
        try:
            state.processor.speed_reader = state.speed_reader
            state.processor.read_sign_enabled = True
            print("[MAIN] [OK] Speed reader connected to processor")
        except Exception as e:
            print(f"[MAIN] [NO] Failed to connect speed reader: {e}")

    if not success:
        print("\n[MAIN] ✗ Critical component failed to initialize")
        sys.exit(1)

    print("\n[MAIN] ============================================")
    print("[MAIN] [OK] All components ready!")
    print("[MAIN] ============================================")
    print("[MAIN] Press Ctrl+C or ESC to stop\n")

    # Try to create GUI if display is available
    gui_available = False
    processing_thread = None
    try:
        app = QApplication(sys.argv)
        window = VisionPilotWindow()
        window.show()
        gui_available = True

        # Start processing thread
        processing_thread = threading.Thread(target=run, daemon=False)
        processing_thread.start()

        # Run Qt event loop
        app.exec_()

        # After GUI closes, wait for processing thread to finish
        state.running = False
        if processing_thread is not None:
            processing_thread.join(timeout=5)

        # Call shutdown to display graph
        shutdown()

    except Exception as e:
        if gui_available:
            state.running = False
            if processing_thread is not None:
                processing_thread.join(timeout=5)
            shutdown()
            raise
        print(f"[MAIN] GUI not available, running headless mode only\n")
        # Run main loop directly
        run()
        shutdown()

if __name__ == "__main__":
    main()

