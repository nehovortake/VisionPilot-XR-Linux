import os
import sys
import platform
import math
import time
import cv2
import numpy as np
import io
import wave
import struct

# Optional Windows warning sound (overspeed)
try:
    import winsound as _winsound  # type: ignore
except Exception:
    _winsound = None

import threading

# ==========================================================
# Embedded UI sounds (from button_tones.py)
# - kept inline as requested (no external import)
# ==========================================================
SOUND_ENABLED = True


def _run_in_thread(fn):
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t


def beep():
    """Generic button beep."""
    if not SOUND_ENABLED or _winsound is None:
        return
    _run_in_thread(lambda: _winsound.Beep(1000, 70))


def start_sound():
    """Rising tones for Start Cam."""
    if not SOUND_ENABLED or _winsound is None:
        return

    def sound():
        freqs = [400, 600, 800, 1000]
        for f in freqs:
            _winsound.Beep(f, 100)
            time.sleep(0.05)

    _run_in_thread(sound)


def stop_sound():
    """Deep sudden punch for Stop Cam."""
    if not SOUND_ENABLED or _winsound is None:
        return
    _run_in_thread(lambda: _winsound.Beep(400, 150))


def shutdown_sound_and_close(callback=None):
    """Descending shutdown tones for Close GUI."""
    if not SOUND_ENABLED or _winsound is None:
        if callback:
            try:
                callback()
            except Exception:
                pass
        return

    def sound_and_exit():
        freqs = [800, 600, 400, 250, 150]
        for f in freqs:
            _winsound.Beep(f, 120)
            time.sleep(0.06)
        if callback:
            callback()

    _run_in_thread(sound_and_exit)


def zed_sound():
    """Creative futuristic sound for ZED M button."""
    if not SOUND_ENABLED or _winsound is None:
        return

    def sound():
        sequence = [(500, 80), (700, 80), (900, 80), (700, 80)]
        for freq, dur in sequence:
            _winsound.Beep(freq, dur)
            time.sleep(0.05)

    _run_in_thread(sound)


def tsd_sound():
    """Creative Intel-like sound for TSD button."""
    if not SOUND_ENABLED or _winsound is None:
        return

    def sound():
        sequence = [(1200, 50), (1400, 50), (1300, 70), (1500, 50)]
        for freq, dur in sequence:
            _winsound.Beep(freq, dur)
            time.sleep(0.07)

    _run_in_thread(sound)


# Blocking version used for continuous overspeed loop (NO extra threads).
def _tsd_sound_blocking(stop_flag_fn):
    if not SOUND_ENABLED or _winsound is None:
        return
    sequence = [(1200, 50), (1400, 50), (1300, 70), (1500, 50)]
    for freq, dur in sequence:
        if stop_flag_fn():
            return
        _winsound.Beep(freq, dur)
        # micro-gap (keeps "pip-pip" feel), but continuous overall
        time.sleep(0.01)


# Blocking warning alarm (continuous) used for overspeed (NO extra threads).
# Alternating high/low tones for an aggressive automotive alert.
def _overspeed_alarm_blocking(stop_flag_fn):
    if not SOUND_ENABLED or _winsound is None:
        return
    # "Danger" two-tone alarm (no pauses between beeps)
    sequence = [
        (1800, 120),
        (1200, 120),
        (1800, 120),
        (1200, 120),
    ]
    for freq, dur in sequence:
        if stop_flag_fn():
            return
        _winsound.Beep(freq, dur)


from PyQt5.QtGui import QImage

from realsense import RealSenseCamera
from elm327_can_speed import ELM327SpeedReader

# ==========================================================
# Processing pipeline (same modules as qt_gui.py, but keyboard-driven)
# ==========================================================
try:
    from image_processing import ImageProcessor, start_process_log, stop_process_log, set_vehicle_speed
except Exception:
    ImageProcessor = None
    start_process_log = None
    stop_process_log = None
    set_vehicle_speed = None

try:
    from qt_saving import EllipseSaver
except Exception:
    EllipseSaver = None

try:
    from read_speed import PerceptronSpeedReader
except Exception:
    PerceptronSpeedReader = None

# Optional system metrics (used by PerformancePanel)
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

try:
    import pynvml  # type: ignore

    _nvml_ok = True
    try:
        pynvml.nvmlInit()
    except Exception:
        _nvml_ok = False
except Exception:
    pynvml = None
    _nvml_ok = False

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget,
    QVBoxLayout, QHBoxLayout, QMessageBox,
    QFrame, QComboBox, QCheckBox, QPushButton,
    QShortcut, QSlider, QSizePolicy, QLineEdit
)
from PyQt5.QtGui import QPixmap, QFont, QKeySequence, QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QGraphicsDropShadowEffect

# ==========================================================
# CAMERA PREVIEW WINDOW (EDIT THESE)
# - This rectangle defines where the live camera preview is drawn.
# - Values are RELATIVE to the current window size (0..1).
# - You can fine-tune with CAM_RECT_OFFSETS (pixels).
# ==========================================================
CAM_RECT_REL = (0.2, 0.3, 0.89, 0.73)  # (x_rel, y_rel, w_rel, h_rel(0.41))
CAM_RECT_OFFSETS = (0, 0, 0, 0)  # (x_px, y_px, w_px, h_px)
CROP_KEEP_RATIO = 3 / 5
VIDEO_SCALE = 0.68  # 1.0 = pôvodná veľkosť

from PyQt5.QtGui import QPainter, QFontMetrics, QColor, QPen, QBrush, QRadialGradient
from PyQt5.QtCore import QPointF
from PyQt5.QtCore import Qt, QPropertyAnimation, QAbstractAnimation, QTimer, QPoint, QEasingCurve


class InfoPanel(QFrame):
    """
    Embedded (child) settings panel - animates only inside a defined area.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._animating = False

        # Embedded widget (NOT a dialog/window)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        # Outer transparent layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Card frame (semi-transparent, not fully)
        self.card = QFrame(self)
        self.card.setObjectName("infoCard")
        self.card.setStyleSheet("""
            QFrame#infoCard {
                background: rgba(20, 20, 20, 165);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 14px;
            }
            QLabel {
                color: rgba(255,255,255,220);
                background: transparent;
            }
            QComboBox {
                background: rgba(0,0,0,120);
                color: rgba(255,255,255,230);
                border: 1px solid rgba(255,255,255,40);
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 28px;
            }
            QComboBox::drop-down {
                border: 0px;
                width: 28px;
            }
            QCheckBox {
                color: rgba(255,255,255,215);
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,55);
                background: rgba(0,0,0,120);
            }
            QCheckBox::indicator:checked {
                background: rgba(120,255,150,200);
                border: 1px solid rgba(120,255,150,220);
            }
            QPushButton {
                background: rgba(0,0,0,120);
                color: rgba(255,255,255,230);
                border: 1px solid rgba(255,255,255,40);
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 700;
                min-height: 30px;
            }
            QPushButton:hover {
                border: 1px solid rgba(255,255,255,70);
                background: rgba(0,0,0,150);
            }
        """)
        outer.addWidget(self.card)

        # Inner layout
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # top hint
        self.lbl_hint = QLabel("Press [i] to exit", self.card)
        f = QFont("Bahnschrift", 12)
        f.setBold(True)
        self.lbl_hint.setFont(f)
        self.lbl_hint.setStyleSheet("color: rgba(255,255,255,170); letter-spacing: 1px;")
        lay.addWidget(self.lbl_hint)

        # resolution
        self.cmb_res = QComboBox(self.card)
        self.cmb_res.addItems([
            "1920x1080 @ 30",
            "1280x720 @ 30",
            "848x480 @ 60",
            "640x480 @ 60"
        ])
        lay.addWidget(self.cmb_res)

        # checkboxes
        self.chk_autoexp = QCheckBox("Auto Exposure", self.card)
        self.chk_autoexp.setChecked(True)
        self.chk_save = QCheckBox("Save detections", self.card)
        self.chk_log = QCheckBox("Log data", self.card)
        lay.addWidget(self.chk_autoexp)
        lay.addWidget(self.chk_save)
        lay.addWidget(self.chk_log)

        # analyse data (button)
        self.btn_analyse = QPushButton("Analyse data", self.card)
        lay.addWidget(self.btn_analyse)

        # Slide animations (local coords only!)
        self._slide_in = QPropertyAnimation(self, b"pos", self)
        self._slide_in.setDuration(650)
        self._slide_in.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_in.finished.connect(self._finish_anim)

        self._slide_out = QPropertyAnimation(self, b"pos", self)
        self._slide_out.setDuration(650)
        self._slide_out.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_out.finished.connect(self._hide_done)

    def slide_in(self, start_pos: QPoint, end_pos: QPoint):
        self._animating = True
        self._slide_out.stop()
        self._slide_in.stop()

        self.move(start_pos)
        self.show()
        self.raise_()

        self._slide_in.setStartValue(start_pos)
        self._slide_in.setEndValue(end_pos)
        self._slide_in.start()

    def slide_out(self, end_pos: QPoint):
        self._animating = True
        self._slide_in.stop()
        self._slide_out.stop()

        self._slide_out.setStartValue(self.pos())
        self._slide_out.setEndValue(end_pos)
        self._slide_out.start()

    def _finish_anim(self):
        self._animating = False

    def _hide_done(self):
        self._animating = False
        self.hide()


class SpeedWeatherPanel(QFrame):
    """
    SPEED panel (same slot as Info panel).

    Requested update:
    - Under the speed value add a divider line (not touching left/right edges).
    - Under the divider show an icon/image of the detected speed sign (e.g., 20 -> 20e.png).

    NOTE:
    - Weather was moved to a separate panel (WeatherPanel).
    """

    def __init__(self, parent=None, sign_icon_dir: str | None = None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        # where sign icons live
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_dir = os.path.join(base_dir, "gui_assets", "signstocluster")
        # user requested absolute path (keep as fallback)
        abs_fallback = r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\gui_assets\signstocluster"
        self._sign_icon_dir = sign_icon_dir or (default_dir if os.path.isdir(default_dir) else abs_fallback)

        # cache pixmaps so we don't hit disk every frame
        self._sign_cache: dict[int, QPixmap] = {}
        self._last_sign_val: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("swCard")
        self.card.setStyleSheet("""
            QFrame#swCard {
                background: rgba(20, 20, 20, 165);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 14px;
            }
            QLabel {
                color: rgba(255,255,255,230);
                background: transparent;
            }
        """)
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # ---- SPEED ----
        speed_row = QHBoxLayout()
        speed_row.setContentsMargins(0, 0, 0, 0)
        speed_row.setSpacing(14)
        speed_row.setAlignment(Qt.AlignCenter)

        self.lbl_speed = QLabel("0", self.card)
        f_speed = QFont("Bahnschrift", 80)
        f_speed.setBold(True)
        self.lbl_speed.setFont(f_speed)
        self.lbl_speed.setStyleSheet("color: rgba(255,255,255,240);")
        # --- Audi-style red glow (used for overspeed pulse) ---
        self._speed_shadow = QGraphicsDropShadowEffect(self.lbl_speed)
        self._speed_shadow.setOffset(0, 0)
        self._speed_shadow.setBlurRadius(0)
        self._speed_shadow.setColor(QColor(255, 60, 60, 0))
        self.lbl_speed.setGraphicsEffect(self._speed_shadow)

        speed_row.addWidget(self.lbl_speed)
        lay.addLayout(speed_row, stretch=1)

        # ---- DIVIDER (does not touch edges) ----
        div_wrap = QWidget(self.card)
        div_lay = QHBoxLayout(div_wrap)
        div_lay.setContentsMargins(18, 0, 18, 0)  # ✅ keep away from edges
        div_lay.setSpacing(0)

        self.div_line = QFrame(div_wrap)
        self.div_line.setFrameShape(QFrame.HLine)
        self.div_line.setFrameShadow(QFrame.Plain)
        self.div_line.setFixedHeight(1)
        self.div_line.setStyleSheet("background: rgba(255,255,255,70); border: none;")
        div_lay.addWidget(self.div_line)

        lay.addWidget(div_wrap, stretch=0)

        # ---- SIGN ICON (detected) ----
        self.lbl_sign = QLabel(self.card)
        self.lbl_sign.setAlignment(Qt.AlignCenter)
        self.lbl_sign.setMinimumHeight(96)
        self.lbl_sign.setStyleSheet("background: transparent;")
        self.lbl_sign.setText("")  # no placeholder text
        lay.addWidget(self.lbl_sign, stretch=0)

    def set_speed(self, kmh):
        try:
            self.lbl_speed.setText(str(int(round(float(kmh)))))
        except Exception:
            self.lbl_speed.setText("--")

    def _find_sign_path(self, v: int) -> str | None:
        """
        Finds file by exact expected name '{v}e.png' (preferred).
        If missing, tries '{v}e.*' (png/jpg/webp/etc).
        """
        if v is None:
            return None
        try:
            v = int(v)
        except Exception:
            return None

        p1 = os.path.join(self._sign_icon_dir, f"{v}e.png")
        if os.path.exists(p1):
            return p1

        # fallback: any extension
        try:
            import glob as _glob
            pattern = os.path.join(self._sign_icon_dir, f"{v}e.*")
            hits = sorted(_glob.glob(pattern))
            if hits:
                return hits[0]
        except Exception:
            pass

        return None

    def set_sign(self, kmh: float | int | None):
        """
        Update sign icon based on detected speed (e.g. 20 -> 20e.png).
        Call this each frame if you want; internally it updates only on change.
        """
        if kmh is None:
            self._last_sign_val = None
            self.lbl_sign.clear()
            return

        try:
            v = int(round(float(kmh)))
        except Exception:
            self._last_sign_val = None
            self.lbl_sign.clear()
            return

        if self._last_sign_val == v:
            return  # no change

        self._last_sign_val = v

        # cached?
        pm = self._sign_cache.get(v, None)
        if pm is None or pm.isNull():
            path = self._find_sign_path(v)
            if not path:
                self.lbl_sign.clear()
                return
            pm = QPixmap(path)
            if pm.isNull():
                self.lbl_sign.clear()
                return
            self._sign_cache[v] = pm

        try:
            scaled = pm.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_sign.setPixmap(scaled)
        except Exception:
            self.lbl_sign.clear()

    # ======================================================
    # Audi Virtual Cockpit overspeed pulse (external drive)
    # intensity: 0.0 .. 1.0
    # ======================================================
    def apply_overspeed_pulse(self, intensity: float):
        try:
            x = float(intensity)
        except Exception:
            x = 0.0
        if x < 0.0:
            x = 0.0
        if x > 1.0:
            x = 1.0

        # Color mix: white -> red
        r = int(255)
        g = int(255 - (255 - 80) * x)  # 255 -> ~80
        b = int(255 - (255 - 80) * x)  # 255 -> ~80

        # Glow grows with intensity
        blur = int(6 + 28 * x)
        alpha = int(40 + 170 * x)

        self.lbl_speed.setStyleSheet(f"color: rgba({r},{g},{b},240);")
        try:
            self._speed_shadow.setBlurRadius(blur)
            self._speed_shadow.setColor(QColor(255, 60, 60, alpha))
        except Exception:
            pass

    def reset_overspeed_style(self):
        self.lbl_speed.setStyleSheet("color: rgba(255,255,255,240);")
        try:
            self._speed_shadow.setBlurRadius(0)
            self._speed_shadow.setColor(QColor(255, 60, 60, 0))
        except Exception:
            pass


class WeatherPanel(QFrame):
    """
    Separate Weather panel (shown only after START/Space).
    - Displays: 'WEATHER:' label + icon (emoji by default).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("weatherCard")
        self.card.setStyleSheet("""
            QFrame#weatherCard {
                background: rgba(20, 20, 20, 165);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 14px;
            }
            QLabel {
                color: rgba(255,255,255,230);
                background: transparent;
            }
        """)
        outer.addWidget(self.card)

        lay = QHBoxLayout(self.card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignVCenter)

        self.lbl_title = QLabel("WEATHER:", self.card)
        f_t = QFont("Bahnschrift", 14)
        f_t.setBold(True)
        self.lbl_title.setFont(f_t)
        self.lbl_title.setStyleSheet("color: rgba(255,255,255,200);")
        lay.addWidget(self.lbl_title, stretch=0)

        self.lbl_icon = QLabel("☀", self.card)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        f_i = QFont("Segoe UI Emoji", 28)
        self.lbl_icon.setFont(f_i)
        lay.addWidget(self.lbl_icon, stretch=1)

    def set_weather(self, key: str):
        k = (key or "").strip().lower()
        if k in ("sunny", "clear"):
            self.lbl_icon.setText("☀")
        elif k in ("normal", "day"):
            # default daytime / neutral conditions
            self.lbl_icon.setText("⛅")
        elif k in ("cloudy", "overcast"):
            self.lbl_icon.setText("☁")
        elif k in ("rain", "rainy"):
            self.lbl_icon.setText("🌩")
        elif k in ("snow", "snowy"):
            self.lbl_icon.setText("❄")
        elif k in ("fog", "mist"):
            self.lbl_icon.setText("🌫")
        elif k in ("night", "dark"):
            self.lbl_icon.setText("🌙")
        else:
            self.lbl_icon.setText("☀")

    def set_icon_pixmap(self, pm: QPixmap):
        """Optional: allow replacing emoji by a real icon."""
        try:
            if pm is None or pm.isNull():
                return
            scaled = pm.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_icon.setPixmap(scaled)
        except Exception:
            pass


class PerformancePanel(QFrame):
    """
    Narrow performance panel (slides from the RIGHT, like Info but opposite).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._animating = False

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._slide_in = QPropertyAnimation(self, b"pos", self)
        self._slide_in.setDuration(650)
        self._slide_in.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_in.finished.connect(self._finish_anim)

        self._slide_out = QPropertyAnimation(self, b"pos", self)
        self._slide_out.setDuration(650)
        self._slide_out.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_out.finished.connect(self._hide_done)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("perfCard")
        self.card.setStyleSheet("""
            QFrame#perfCard {
                background: rgba(20, 20, 20, 165);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 14px;
            }
            QLabel {
                color: rgba(255,255,255,220);
                background: transparent;
            }
        """)
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self.lbl_proc = QLabel("Processes", self.card)
        f_hdr = QFont("Bahnschrift", 12)
        f_hdr.setBold(True)
        self.lbl_proc.setFont(f_hdr)
        self.lbl_proc.setStyleSheet("color: rgba(255,255,255,170);")
        lay.addWidget(self.lbl_proc)

        self.val_proc_ms = QLabel("0.9 ms", self.card)
        f_big = QFont("Bahnschrift", 26)
        f_big.setBold(True)
        self.val_proc_ms.setFont(f_big)
        self.val_proc_ms.setStyleSheet("color: rgba(255,255,255,235);")
        lay.addWidget(self.val_proc_ms)

        def make_row(lbl_txt: str, default_val: str = "--"):
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(8)

            lbl = QLabel(lbl_txt, self.card)
            lbl.setFont(f_hdr)
            lbl.setStyleSheet("color: rgba(255,255,255,170);")

            val = QLabel(default_val, self.card)
            fv = QFont("Bahnschrift", 12)
            fv.setBold(True)
            val.setFont(fv)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("color: rgba(255,255,255,230);")
            val.setMinimumWidth(20)

            r.addWidget(lbl, 1)
            r.addWidget(val, 0)
            lay.addLayout(r)
            return val

        self.val_cpu = make_row("CPU:", "-- %")
        self.val_gpu = make_row("GPU/", "--")
        self.val_vram = make_row("VRAM:", "-- MB")
        lay.addStretch(1)

        self._cpu_percent = None
        self._gpu_percent = None
        self._vram_mb = None
        self._proc_ms = None

    def slide_in(self, start_pos: QPoint, end_pos: QPoint):
        self._animating = True
        self._slide_out.stop()
        self._slide_in.stop()

        self.move(start_pos)
        self.show()
        self.raise_()

        self._slide_in.setStartValue(start_pos)
        self._slide_in.setEndValue(end_pos)
        self._slide_in.start()

    def slide_out(self, end_pos: QPoint):
        self._animating = True
        self._slide_in.stop()
        self._slide_out.stop()

        self._slide_out.setStartValue(self.pos())
        self._slide_out.setEndValue(end_pos)
        self._slide_out.start()

    def _finish_anim(self):
        self._animating = False

    def _hide_done(self):
        self._animating = False
        self.hide()

    def set_process_ms(self, ms: float | None):
        self._proc_ms = ms
        if ms is None:
            self.val_proc_ms.setText("-- ms")
        else:
            try:
                self.val_proc_ms.setText(f"{float(ms):.1f} ms")
            except Exception:
                self.val_proc_ms.setText("-- ms")

    def set_cpu_percent(self, pct: float | None):
        self._cpu_percent = pct
        if pct is None:
            self.val_cpu.setText("-- %")
        else:
            try:
                self.val_cpu.setText(f"{float(pct):.0f} %")
            except Exception:
                self.val_cpu.setText("-- %")

    def set_gpu_percent(self, pct: float | None):
        self._gpu_percent = pct
        if pct is None:
            self.val_gpu.setText("--")
        else:
            try:
                self.val_gpu.setText(f"{float(pct):.0f}")
            except Exception:
                self.val_gpu.setText("--")

    def set_vram_mb(self, mb: float | None):
        self._vram_mb = mb
        if mb is None:
            self.val_vram.setText("-- MB")
        else:
            try:
                self.val_vram.setText(f"{float(mb):.0f} MB")
            except Exception:
                self.val_vram.setText("-- MB")


class RedNullingPanel(QFrame):
    """Red Nulling settings panel (lives in perf_area; slides in/out like InfoPanel)."""

    def __init__(self, parent=None, get_processor=None):
        super().__init__(parent)
        self._animating = False
        self._get_processor = get_processor

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._slide_in = QPropertyAnimation(self, b"pos", self)
        self._slide_in.setDuration(650)
        self._slide_in.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_in.finished.connect(self._finish_anim)

        self._slide_out = QPropertyAnimation(self, b"pos", self)
        self._slide_out.setDuration(650)
        self._slide_out.setEasingCurve(QEasingCurve.InOutCubic)
        self._slide_out.finished.connect(self._hide_done)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("rnCard")
        self.card.setStyleSheet("""
            QFrame#rnCard {
                background: rgba(20, 20, 20, 165);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 14px;
            }
            QLabel { color: rgba(255,255,255,220); background: transparent; }
            QCheckBox { color: rgba(235,235,235,220); font-family: Bahnschrift; font-size: 12px; font-weight: 700; }
            QLineEdit {
                background: rgba(0,0,0,140);
                border: 1px solid rgba(255,255,255,35);
                border-radius: 8px;
                padding: 6px 8px;
                color: rgba(255,255,255,230);
                font-family: Bahnschrift;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit:focus { border: 1px solid rgba(255,255,255,80); }
        """)
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hdr = QLabel("Red Nulling", self.card)
        f_hdr = QFont("Bahnschrift", 12);
        f_hdr.setBold(True)
        hdr.setFont(f_hdr)
        hdr.setStyleSheet("color: rgba(255,255,255,170);")
        lay.addWidget(hdr)

        self.chk_override = QCheckBox("Override weather", self.card)
        self.chk_override.setChecked(False)
        lay.addWidget(self.chk_override)

        # --- editable value rows (type value -> applies immediately) ---
        def mk_edit(title: str, default_text: str, validator, hint: str = ""):
            row = QHBoxLayout();
            row.setContentsMargins(0, 0, 0, 0);
            row.setSpacing(10)

            lbl = QLabel(title, self.card)
            f = QFont("Bahnschrift", 11);
            f.setBold(True)
            lbl.setFont(f);
            lbl.setStyleSheet("color: rgba(255,255,255,170);")
            lbl.setMinimumWidth(88)

            edit = QLineEdit(self.card)
            edit.setText(default_text)
            edit.setValidator(validator)
            edit.setFixedWidth(86)
            if hint:
                edit.setPlaceholderText(hint)

            row.addWidget(lbl, 0)
            row.addStretch(1)
            row.addWidget(edit, 0)
            lay.addLayout(row)

            # apply on any change (instant)
            edit.textChanged.connect(lambda _=None: self._apply())
            edit.editingFinished.connect(self._apply)
            return edit

        # Defaults match your earlier sliders:
        # rd=1.5, minB=10, brightness=0.0, contrast=1.0, blur=3
        self.e_rd = mk_edit("rd", "1.5", QDoubleValidator(0.0, 9.9, 2, self.card), "float")
        self.e_minb = mk_edit("minB", "10", QIntValidator(0, 255, self.card), "int")
        self.e_bri = mk_edit("bright", "0.0", QDoubleValidator(-9.9, 9.9, 2, self.card), "float")
        self.e_con = mk_edit("contr", "1.0", QDoubleValidator(0.0, 9.9, 2, self.card), "float")
        self.e_blur = mk_edit("blur", "3", QIntValidator(1, 99, self.card), "odd int")

        lay.addStretch(1)
        self.chk_override.stateChanged.connect(lambda _=None: self._apply())

    def slide_in(self, start_pos: QPoint, end_pos: QPoint):
        self._animating = True
        self._slide_out.stop();
        self._slide_in.stop()
        self.move(start_pos);
        self.show();
        self.raise_()
        self._slide_in.setStartValue(start_pos);
        self._slide_in.setEndValue(end_pos)
        self._slide_in.start()

    def slide_out(self, end_pos: QPoint):
        self._animating = True
        self._slide_in.stop();
        self._slide_out.stop()
        self._slide_out.setStartValue(self.pos());
        self._slide_out.setEndValue(end_pos)
        self._slide_out.start()

    def _finish_anim(self):
        self._animating = False

    def _hide_done(self):
        self._animating = False; self.hide()

    def _apply(self):
        # Applies overrides into processor.rn_params immediately
        try:
            proc = self._get_processor() if callable(self._get_processor) else None
        except Exception:
            proc = None
        if proc is None:
            return

        try:
            if not self.chk_override.isChecked():
                if hasattr(proc, "rn_params"):
                    proc.rn_params = None
                return

            # Safe parsing (ignore until valid)
            def _f(edit: QLineEdit, default: float) -> float:
                s = (edit.text() or "").strip()
                try:
                    return float(s)
                except Exception:
                    return default

            def _i(edit: QLineEdit, default: int) -> int:
                s = (edit.text() or "").strip()
                try:
                    return int(float(s))
                except Exception:
                    return default

            rd = _f(self.e_rd, 1.5)
            minb = _i(self.e_minb, 10)
            bri = _f(self.e_bri, 0.0)
            con = _f(self.e_con, 1.0)

            k = _i(self.e_blur, 3)
            if k < 1:
                k = 1
            # enforce odd kernel size
            if k % 2 == 0:
                k += 1

            params = {
                "rd": float(rd),
                "min_brightness": int(minb),
                "brightness": float(bri),
                "contrast": float(con),
                "pre_blur_ksize": int(k),
            }
            if hasattr(proc, "rn_params"):
                proc.rn_params = params
        except Exception:
            pass


class LegendRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

        self.items = ["CAM", "RED", "CANNY", "ELLIPSE", "DETECT"]
        self.enabled = [False, False, False, False, False]
        self.text_color = QColor(230, 230, 230, 210)

        self.font_name = "Bahnschrift"
        self.font_size = 26
        self.font_bold = True

        self.dot_text_gap = 10
        self.base_item_gap = 40
        self.max_item_gap = 50

        self.baseline_shift = 0
        self.dot_vertical_offset = 8

        self.pulse_enabled = True
        self.pulse_period_ms = 3000
        self.pulse_alpha_min = 90
        self.pulse_alpha_max = 200
        self._pulse_t = 0.0

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(33)

        self.led_radius = 15
        self.led_glow_radius = 22
        self.led_glow_strength = 170
        self.led_core_strength = 255
        self.led_ring_alpha = 140
        self.led_pulse_size = 1.15

    def _tick_pulse(self):
        if not self.pulse_enabled:
            return
        self._pulse_t += 33.0
        self.update()

    def set_state(self, index: int, enabled: bool):
        if 0 <= index < len(self.enabled):
            self.enabled[index] = bool(enabled)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        f = QFont(self.font_name, self.font_size)
        f.setBold(self.font_bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
        p.setFont(f)
        fm = QFontMetrics(f)

        text_w = [fm.horizontalAdvance(t) for t in self.items]
        led_block_w = int(self.led_glow_radius * 2)
        item_w = [led_block_w + self.dot_text_gap + text_w[i] for i in range(len(self.items))]
        total_items = sum(item_w)

        n_gaps = max(1, len(self.items) - 1)
        available = self.width() - total_items

        gap = self.base_item_gap
        stretched = available / n_gaps if n_gaps > 0 else gap
        gap = max(self.base_item_gap, min(self.max_item_gap, stretched))

        total_row = total_items + gap * n_gaps
        x = (self.width() - total_row) / 2 if total_row < self.width() else 0

        y_center = self.height() / 2 + self.baseline_shift
        text_vertical_offset = 6

        if self.pulse_enabled:
            phase = (self._pulse_t % self.pulse_period_ms) / float(self.pulse_period_ms)
            s = 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)
            alpha = int(self.pulse_alpha_min + (self.pulse_alpha_max - self.pulse_alpha_min) * s)
            glow_scale = 1.0 + (self.led_pulse_size - 1.0) * s
        else:
            alpha = 180
            glow_scale = 1.0

        for i, label in enumerate(self.items):
            base = QColor(120, 255, 150) if self.enabled[i] else QColor(255, 70, 70)

            cx = x + self.led_glow_radius
            cy = y_center + self.dot_vertical_offset

            gr = QRadialGradient(QPointF(cx, cy), self.led_glow_radius * glow_scale)
            outer = QColor(base)
            outer.setAlpha(0)

            mid = QColor(base)
            mid.setAlpha(int(self.led_glow_strength * (alpha / 255.0)))

            inner = QColor(base)
            inner.setAlpha(int(min(255, (self.led_glow_strength + 60) * (alpha / 255.0))))

            gr.setColorAt(0.0, inner)
            gr.setColorAt(0.35, mid)
            gr.setColorAt(1.0, outer)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(gr))
            p.drawEllipse(QPointF(cx, cy),
                          self.led_glow_radius * glow_scale,
                          self.led_glow_radius * glow_scale)

            core = QColor(base)
            core.setAlpha(int(self.led_core_strength * (alpha / 255.0)))
            p.setBrush(QBrush(core))
            p.drawEllipse(QPointF(cx, cy), self.led_radius, self.led_radius)

            hi = QColor(255, 255, 255)
            hi.setAlpha(int(120 * (alpha / 255.0)))
            p.setBrush(QBrush(hi))
            p.drawEllipse(QPointF(cx - self.led_radius * 0.25, cy - self.led_radius * 0.25),
                          self.led_radius * 0.45,
                          self.led_radius * 0.45)

            ring = QColor(255, 255, 255)
            ring.setAlpha(int(self.led_ring_alpha * (alpha / 255.0)))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(ring, 1))
            p.drawEllipse(QPointF(cx, cy), self.led_radius + 1, self.led_radius + 1)

            p.setFont(f)
            p.setPen(QPen(self.text_color))
            tx = x + led_block_w + self.dot_text_gap
            text_y = y_center + (fm.ascent() - fm.height() / 2) + text_vertical_offset
            p.drawText(int(tx), int(text_y), label)

            x += item_w[i] + gap


class BackgroundWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("VisionPilot XR - Background")
        self.setStyleSheet("background-color: black;")

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.path_bg = os.path.join(self.base_dir, "gui_assets", "background.png")
        self.path_screen = os.path.join(self.base_dir, "gui_assets", "screen.png")
        self.path_logo = os.path.join(self.base_dir, "gui_assets", "logo.png")

        self.root = QWidget(self)
        self.setCentralWidget(self.root)

        self.bg_label = QLabel(self.root)
        self.bg_label.setAlignment(Qt.AlignCenter)

        self.video_panel = QLabel(self.root)
        self.video_panel.setAlignment(Qt.AlignCenter)
        self.video_panel.setStyleSheet("""
            background-color: rgba(0,0,0,160);
            border-radius: 18px;
        """)
        self.video_panel.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.video_panel.hide()

        self.cam = None
        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(Qt.PreciseTimer)
        self._frame_timer.timeout.connect(self._on_frame)

        self._pix = QPixmap(self.path_bg)
        if self._pix.isNull():
            self.bg_label.setText(f"Image not found:\n{self.path_bg}")
            self.bg_label.setStyleSheet("color: white; font-size: 16px;")
            self.resize(1000, 600)
        else:
            w = min(self._pix.width(), 1536)
            h = min(self._pix.height(), 1020)
            self.setFixedSize(w, h)
            self.resize(w, h)

        self.overlay = QWidget(self.root)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.overlay.setStyleSheet("background: transparent;")

        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(8)
        overlay_layout.setAlignment(Qt.AlignCenter)

        self.lbl_start = QLabel("Press [SPACE] to Start.", self.overlay)
        self.lbl_info = QLabel("Press [i] for System info.", self.overlay)

        font_start = QFont("Segoe UI", 32)
        font_start.setBold(True)
        self.lbl_start.setFont(font_start)
        self.lbl_start.setStyleSheet("color: white; background: transparent;")

        font_info = QFont("Segoe UI", 20)
        font_info.setBold(True)
        self.lbl_info.setFont(font_info)
        self.lbl_info.setStyleSheet("color: rgba(255,255,255,200); background: transparent;")

        self.lbl_start.setAlignment(Qt.AlignCenter)
        self.lbl_info.setAlignment(Qt.AlignCenter)

        overlay_layout.addWidget(self.lbl_start)
        overlay_layout.addWidget(self.lbl_info)

        self._opacity = QGraphicsOpacityEffect(self.overlay)
        self._opacity.setOpacity(1.0)
        self.overlay.setGraphicsEffect(self._opacity)

        self._blink = QPropertyAnimation(self._opacity, b"opacity", self)
        self._blink.setDuration(1800)
        self._blink.setStartValue(1.0)
        self._blink.setKeyValueAt(0.5, 0.15)
        self._blink.setEndValue(1.0)
        self._blink.setLoopCount(-1)
        self._blink.start()

        self.hud = QWidget(self.root)
        self.hud.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hud.setStyleSheet("background: transparent;")
        self.hud.hide()

        self.top_logo = QLabel(self.hud)
        self.top_logo.setAlignment(Qt.AlignCenter)
        self.top_logo.setStyleSheet("background: transparent;")

        pm_logo = QPixmap(self.path_logo)
        if not pm_logo.isNull():
            self.LOGO_H = 250
            self.LOGO_Y = 60
            self.top_logo.setPixmap(pm_logo.scaledToHeight(self.LOGO_H, Qt.SmoothTransformation))
            self.top_logo.adjustSize()
        else:
            self.LOGO_Y = 60
            self.top_logo.setPixmap(QPixmap())
            self.top_logo.setFixedSize(1, 1)

        self._logo_opacity = QGraphicsOpacityEffect(self.top_logo)
        self._logo_opacity.setOpacity(0.0)
        self.top_logo.setGraphicsEffect(self._logo_opacity)

        self._logo_fade = QPropertyAnimation(self._logo_opacity, b"opacity", self)
        self._logo_fade.setDuration(1300)
        self._logo_fade.setStartValue(0.0)
        self._logo_fade.setEndValue(1.0)

        self.legend = LegendRow(self.hud)
        self.legend.show()

        self.res_label = QLabel(self.hud)
        self.res_label.setObjectName("hudResolution")
        self.res_label.setText("")
        self.res_label.setStyleSheet("""
            QLabel#hudResolution {
                color: rgba(235,235,235,220);
                background: rgba(0,0,0,120);
                border: 1px solid rgba(255,255,255,35);
                border-radius: 10px;
                padding: 6px 10px;
                font-family: Bahnschrift;
                font-size: 16px;
                font-weight: 700;
            }
        """)
        self.res_label.setAlignment(Qt.AlignCenter)
        self.res_label.hide()

        self.fps_label = QLabel(self.hud)
        self.fps_label.setObjectName("hudFps")
        self.fps_label.setText("TAR.: 30 FPS / REAL: -- FPS")
        self.fps_label.setStyleSheet("""
            QLabel#hudFps {
                color: rgba(235,235,235,220);
                background: rgba(0,0,0,120);
                border: 1px solid rgba(255,255,255,35);
                border-radius: 10px;
                padding: 6px 10px;
                font-family: Bahnschrift;
                font-size: 16px;
                font-weight: 800;
            }
        """)
        self.fps_label.setAlignment(Qt.AlignCenter)
        self.fps_label.hide()

        self._fps_target = 30
        self._fps_real_text = "--"

        self.INFO_AREA_X = 85
        self.INFO_AREA_Y = 340
        self.INFO_AREA_W = 300
        self.INFO_AREA_H = 310

        self.INFO_W = 200
        self.INFO_H = 250

        self.PERF_W = 200
        self.PERF_H = self.INFO_H
        self.PERF_RIGHT_PAD = 85

        self.info_area = QWidget(self.root)
        self.info_area.setStyleSheet("background: transparent;")
        self.info_area.setAttribute(Qt.WA_StyledBackground, True)

        self.perf_area = QWidget(self.root)
        self.perf_area.setStyleSheet("background: transparent;")
        self.perf_area.setAttribute(Qt.WA_StyledBackground, True)

        self.info_panel = InfoPanel(self.info_area)
        self.info_panel.setFixedSize(self.INFO_W, self.INFO_H)
        self.info_panel.move(self._info_out_pos())
        self.info_panel.hide()

        self._pending_sw_return = False
        try:
            self.info_panel._slide_out.finished.connect(self._on_info_slide_out_finished)
        except Exception:
            pass

        self.sw_panel = SpeedWeatherPanel(self.root)
        self.sw_panel.setFixedSize(self.INFO_W, self.INFO_H)
        self.sw_panel.move(self._sw_in_pos())
        self.sw_panel.hide()
        self._sw_enabled = False

        # ======================================================
        # Vehicle speed (from ELM327 CAN bus) + overspeed pulse
        # - speed comes from ELM327SpeedReader via OBD-II PID 010D
        # - sign_limit comes from processor.last_speed (detected sign)
        # ======================================================
        self._vehicle_speed = 0
        self._sign_speed_limit = None
        self.elm327 = None

        self._overspeed_active = False
        self._overspeed_phase = 0.0  # radians
        self._overspeed_timer = QTimer(self)
        self._overspeed_timer.setTimerType(Qt.PreciseTimer)
        self._overspeed_timer.timeout.connect(self._tick_overspeed_pulse)
        self._overspeed_timer.start(33)  # ~30 Hz pulse update

        # --- Overspeed warning sound (CONTINUOUS pip without interruption) ---
        # Plays a looping beep-sequence while vehicle_speed > sign_limit.
        self._overspeed_sound_active = False
        self._overspeed_sound_thread = None

        # --- Separate Weather panel (shown only after START/Space) ---
        self.weather_panel = WeatherPanel(self.root)
        # --- WEATHER absolute position (independent) ---
        self.WEATHER_X = 200  # <- sem si daj X
        self.WEATHER_Y = 230  # <- sem si daj Y
        self.weather_panel.setFixedSize(self.INFO_W, 72)
        self.weather_panel.move(self.WEATHER_X, self.WEATHER_Y)
        self.weather_panel.hide()
        self._weather_enabled = False
        # cache last shown weather key so we don't spam setText() every frame
        self._weather_ui_key = None

        self._sw_anim = QPropertyAnimation(self.sw_panel, b"pos", self)
        self._sw_anim.setDuration(650)
        self._sw_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.perf_panel = PerformancePanel(self.root)
        self.perf_panel.setFixedSize(self.PERF_W, self.PERF_H)
        self.perf_panel.move(self._perf_in_global_pos())
        self.perf_panel.hide()

        # PERF swap animation (like sw_panel): PERF stays visible, only moves.
        self._perf_swap_anim = QPropertyAnimation(self.perf_panel, b"pos", self)
        self._perf_swap_anim.setDuration(650)
        self._perf_swap_anim.setEasingCurve(QEasingCurve.InOutCubic)

        # RN panel lives inside perf_area and slides in/out (it hides when out).
        self.rn_panel = RedNullingPanel(self.perf_area, get_processor=lambda: self.processor)
        self.rn_panel.setFixedSize(self.PERF_W, self.PERF_H)
        self.rn_panel.move(self._rn_out_pos())
        self.rn_panel.hide()
        self._rn_visible = False

        self.info_panel.cmb_res.currentTextChanged.connect(self._on_resolution_changed)
        self._on_resolution_changed(self.info_panel.cmb_res.currentText())
        # === InfoPanel actions ===
        self.info_panel.chk_autoexp.stateChanged.connect(self._on_autoexp_changed)
        self.info_panel.chk_save.stateChanged.connect(self._on_save_changed)
        self.info_panel.chk_log.stateChanged.connect(self._on_log_changed)
        self.info_panel.btn_analyse.clicked.connect(self._on_analyse_clicked)

        # Feature states
        self._feat = {"red": False, "canny": False, "ellipse": False, "detect": False}
        self.set_feature_state("red", False)
        self.set_feature_state("canny", False)
        self.set_feature_state("ellipse", False)
        self.set_feature_state("detect", False)

        # ======================================================
        # PROCESSOR (qt_image_process pipeline) + helpers
        # ======================================================
        self.processor = None
        self.ellipse_saver = None
        self.speed_reader = None

        if ImageProcessor is not None:
            try:
                self.processor = ImageProcessor()
            except Exception as e:
                print("[GUI] ImageProcessor init failed:", e)
                self.processor = None

        if EllipseSaver is not None:
            try:
                save_root = os.path.join(self.base_dir, "detections")
                os.makedirs(save_root, exist_ok=True)
                self.ellipse_saver = EllipseSaver(save_root)
            except Exception as e:
                print("[GUI] EllipseSaver init failed:", e)
                self.ellipse_saver = None

        if PerceptronSpeedReader is not None:
            try:
                self.speed_reader = PerceptronSpeedReader()
            except Exception as e:
                print("[GUI] SpeedReader init failed:", e)
                self.speed_reader = None

        if self.processor is not None:
            self.processor.ellipse_saver = self.ellipse_saver
            self.processor.speed_reader = self.speed_reader
            self.processor.read_sign_enabled = False

        try:
            self.info_panel.chk_save.stateChanged.connect(self._on_save_changed)
        except Exception:
            pass
        try:
            self.info_panel.chk_log.stateChanged.connect(self._on_log_changed)
        except Exception:
            pass

        self._on_save_changed()
        self._on_log_changed()

        self._last_frame_ts = None
        self._fps_counter = 0
        self._fps_last_report_ts = None

        self._setup_shortcuts()

        self._relayout()
        self._update_pixmap()

        self.bg_label.lower()
        self.info_area.raise_()
        self.sw_panel.raise_()
        self.perf_area.raise_()
        self.perf_panel.raise_()

    def _setup_shortcuts(self):
        def mk(key: str, fn):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(fn)
            return sc

        # --- CORE CONTROLS ---
        self._sc_esc = mk("Esc", self._act_quit)  # QUIT program
        self._sc_space = mk("Space", self._act_start)  # START program
        self._sc_l = mk("L", self._toggle_logging)  # LOG ON/OFF
        self._sc_s = mk("S", self._toggle_save)  # SAVE detections ON/OFF


        # --- PANELS ---
        self._sc_i = mk("I", self._act_toggle_info)
        self._sc_p = mk("P", self._act_toggle_perf)

        # --- PROCESSING FEATURES ---
        self._sc_r = mk("R", lambda: self._toggle_feat("red"))
        self._sc_c = mk("C", lambda: self._toggle_feat("canny"))
        self._sc_e = mk("E", lambda: self._toggle_feat("ellipse"))
        self._sc_d = mk("D", lambda: self._toggle_feat("detect"))

    def _info_in_pos(self) -> QPoint:
        return QPoint(0, 0)

    def _info_out_pos(self) -> QPoint:
        return QPoint(-self.INFO_AREA_W, 0)

    def _perf_in_pos(self) -> QPoint:
        return QPoint(0, 0)

    def _perf_out_pos(self) -> QPoint:
        return QPoint(self.PERF_W + 20, 0)

    # --- PERF/RN swap positions (mirror of Speed/Info but on RIGHT) ---
    def _perf_in_global_pos(self) -> QPoint:
        # PERF default slot (right side) in ROOT coords
        perf_x = self.width() - self.PERF_RIGHT_PAD - self.PERF_W
        perf_y = self.INFO_AREA_Y
        return QPoint(int(perf_x), int(perf_y))

    def _perf_out_left_global_pos(self) -> QPoint:
        # slide PERF to the LEFT (still visible) like sw_panel does to the right
        p = self._perf_in_global_pos()
        return QPoint(p.x() - (self.PERF_W + 18), p.y())

    def _rn_in_pos(self) -> QPoint:
        return QPoint(0, 0)

    def _rn_out_pos(self) -> QPoint:
        # RN hidden to the RIGHT inside perf_area
        return QPoint(self.PERF_W + 20, 0)

    def _sw_in_pos(self) -> QPoint:
        return QPoint(self.INFO_AREA_X, self.INFO_AREA_Y)

    def _sw_out_right_pos(self) -> QPoint:
        return QPoint(self.INFO_AREA_X + self.INFO_W + 18, self.INFO_AREA_Y)

    def _sw_slide_to(self, end_pos: QPoint, duration_ms: int = None, easing: QEasingCurve = None):
        if not getattr(self, "_sw_enabled", False):
            return
        if not hasattr(self, "sw_panel") or self.sw_panel is None:
            return
        self._sw_anim.stop()
        if duration_ms is not None:
            self._sw_anim.setDuration(int(duration_ms))
        if easing is not None:
            self._sw_anim.setEasingCurve(easing)
        if not self.sw_panel.isVisible():
            self.sw_panel.show()
        self.sw_panel.raise_()
        self._sw_anim.setStartValue(self.sw_panel.pos())
        self._sw_anim.setEndValue(end_pos)
        self._sw_anim.start()

    def _on_info_slide_out_finished(self):
        # No-op: kept for legacy hook but we now start SW moves simultaneously
        # from _act_toggle_info, so deferred logic is not used.
        return

    def _update_fps_label(self):
        self.fps_label.setText(f"TAR.: {self._fps_target} FPS / REAL: {self._fps_real_text} FPS")

    def _on_resolution_changed(self, text: str):
        t = (text or "").strip()
        if not t:
            self.res_label.setText("")
            return

        if "@" in t:
            left, right = [x.strip() for x in t.split("@", 1)]
            fps_txt = right.replace("fps", "").strip()
            shown = f"{left}  {fps_txt} FPS"
            self.res_label.setText(shown)

            try:
                self._fps_target = int("".join(ch for ch in fps_txt if ch.isdigit()))
            except Exception:
                self._fps_target = 30
        else:
            self.res_label.setText(t)

        self._update_fps_label()

    def _on_autoexp_changed(self, state: int):
        enabled = (state == Qt.Checked)

        # ak kamera beží, zmeň AE hneď
        if self.cam is not None:
            try:
                self.cam.set_auto_exposure(enabled)
            except Exception:
                pass

    def _on_analyse_clicked(self):
        # rovnaký štýl ako v qt_gui.py -> vyberieš log a vygeneruje grafy
        from PyQt5.QtWidgets import QFileDialog

        log_dir = os.path.join(os.path.dirname(__file__), "log_files")
        os.makedirs(log_dir, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File to Analyze",
            log_dir,
            "Log Files (*.txt);All Files (*)"
        )
        if not file_path:
            return

        try:
            from qt_analyse import parse_log_file, generate_graphs, open_analysis_graph

            data = parse_log_file(file_path)
            if not data.get("frames"):
                return

            result = generate_graphs(data)

            # qt_analyse môže vracať 1 alebo 2 grafy (analysis + speed pie)
            if isinstance(result, tuple) and len(result) == 2:
                analysis_path, speed_pie_path = result
                open_analysis_graph(analysis_path)
                try:
                    open_analysis_graph(speed_pie_path)
                except Exception:
                    pass
            else:
                open_analysis_graph(result)

        except Exception as e:
            print("[Analyse Error]", e)

    def _act_quit(self):
        try:
            self._stop_camera()
        except Exception:
            pass
        QApplication.quit()

    def _act_start(self):
        self._set_image(self.path_screen)  # ✅ prepne background.png -> screen.png
        self._start_camera()

        # gate for panels (Perf toggle uses this)
        self._started = True

        # Sync processor flags with current LED states (start = all OFF)
        if self.processor is not None:
            try:
                self.processor.enable_red = bool(self._feat.get('red', False))
                self.processor.enable_canny = bool(self._feat.get('canny', False))
                self.processor.enable_ellipse = bool(self._feat.get('ellipse', False))
                self.processor.read_sign_enabled = bool(self._feat.get('detect', False))
            except Exception:
                pass

        if getattr(self, "_blink", None) is not None:
            self._blink.stop()
        if hasattr(self, "overlay") and self.overlay is not None:
            self.overlay.hide()

        if hasattr(self, "hud") and self.hud is not None:
            self.hud.show()
            self.hud.raise_()

        # Fade-in the top logo when START (Space) is pressed.
        try:
            if hasattr(self, "_logo_opacity") and self._logo_opacity is not None:
                # ensure logo starts hidden and will animate in
                self._logo_opacity.setOpacity(0.0)
            if hasattr(self, "_logo_fade") and self._logo_fade is not None:
                try:
                    self._logo_fade.stop()
                except Exception:
                    pass
                try:
                    self._logo_fade.setStartValue(0.0)
                    self._logo_fade.setEndValue(1.0)
                    self._logo_fade.start()
                except Exception:
                    pass
        except Exception:
            pass

        if hasattr(self, "res_label") and self.res_label is not None:
            self.res_label.show()
            self.res_label.raise_()
            # show FPS box (target + real)
            if hasattr(self, "fps_label") and self.fps_label is not None:
                self._update_fps_label()
                self.fps_label.show()
                self.fps_label.raise_()

        if hasattr(self, "sw_panel") and self.sw_panel is not None:
            self._sw_enabled = True
            self.sw_panel.move(self._sw_in_pos())
            self.sw_panel.show()
            self.sw_panel.raise_()

        if hasattr(self, "weather_panel") and self.weather_panel is not None:
            self._weather_enabled = True
            self.weather_panel.move(self.WEATHER_X, self.WEATHER_Y)
            # default (until real weather module updates it)
            try:
                self.weather_panel.set_weather("sunny")
            except Exception:
                pass
            self.weather_panel.show()
            self.weather_panel.raise_()

        if hasattr(self, "perf_panel") and self.perf_panel is not None:
            try:
                self.perf_panel.move(self._perf_in_global_pos())
            except Exception:
                pass
            self.perf_panel.show()
            try:
                self.perf_area.show()
            except Exception:
                pass
            try:
                self.perf_area.raise_()
            except Exception:
                pass
            try:
                self.perf_panel.raise_()
            except Exception:
                pass

        try:
            self.info_area.raise_()
        except Exception:
            pass
        try:
            self.perf_area.raise_()
        except Exception:
            pass

        # propagate initial vehicle speed to image_processing module
        try:
            if set_vehicle_speed is not None:
                set_vehicle_speed(self._vehicle_speed)
        except Exception:
            pass

        # --- Start ELM327 CAN bus speed reader ---
        try:
            if self.elm327 is None:
                self.elm327 = ELM327SpeedReader(
                    port="COM12",
                    baudrate=9600,
                    callback=self.update_vehicle_speed_from_can
                )
                self.elm327.start()
        except Exception as e:
            print("ELM327 error:", e)
            self.elm327 = None

    # ======================================================
    # KEYBOARD TOGGLES (L = log, S = save)
    # ======================================================

    def _toggle_logging(self):
        try:
            current = self.info_panel.chk_log.isChecked()
            self.info_panel.chk_log.setChecked(not current)
        except Exception:
            pass

    def _toggle_save(self):
        try:
            current = self.info_panel.chk_save.isChecked()
            self.info_panel.chk_save.setChecked(not current)
        except Exception:
            pass

    # ======================================================
    # VEHICLE SPEED (from ELM327 CAN bus) + OVERSPEED PULSE
    # ======================================================
    def update_vehicle_speed_from_can(self, speed_kmh):
        """Called by ELM327 thread when new speed is received."""
        try:
            self._vehicle_speed = int(speed_kmh)
        except Exception:
            return
        try:
            if set_vehicle_speed is not None:
                set_vehicle_speed(self._vehicle_speed)
        except Exception:
            pass

    def _set_overspeed(self, active: bool):
        active = bool(active)
        if self._overspeed_active == active:
            return
        self._overspeed_active = active

        # Start/stop continuous warning sound together with visual pulse
        if active:
            self._start_overspeed_sound()
        else:
            self._stop_overspeed_sound()
        if not active:
            self._overspeed_phase = 0.0
            try:
                if self.sw_panel is not None:
                    self.sw_panel.reset_overspeed_style()
            except Exception:
                pass

    def _start_overspeed_sound(self):
        """Start continuous warning sound (no gaps) until stopped."""
        if getattr(self, "_overspeed_sound_active", False):
            return
        self._overspeed_sound_active = True

        def loop():
            # Continuous loop: keeps repeating the TSD sequence without spawning new threads.
            while self._overspeed_sound_active:
                _overspeed_alarm_blocking(lambda: not self._overspeed_sound_active)

        self._overspeed_sound_thread = threading.Thread(target=loop, daemon=True)
        self._overspeed_sound_thread.start()

    def _stop_overspeed_sound(self):
        """Stop continuous warning sound."""
        self._overspeed_sound_active = False
        # no join needed (daemon); it will exit after current Beep finishes
        self._overspeed_sound_thread = None

    def _tick_overspeed_pulse(self):
        # called continuously; apply only when overspeed is active and panel visible
        if not getattr(self, "_sw_enabled", False):
            return
        if not self._overspeed_active:
            return
        if not hasattr(self, "sw_panel") or self.sw_panel is None or not self.sw_panel.isVisible():
            return

        # smooth pulse (Audi VC vibe)
        # intensity in [0..1]
        self._overspeed_phase += 0.18  # speed of pulse
        import math as _math
        intensity = 0.5 - 0.5 * _math.cos(self._overspeed_phase)  # 0..1

        try:
            self.sw_panel.apply_overspeed_pulse(float(intensity))
        except Exception:
            pass

    def _tick_overspeed_beep(self):
        """Periodic audible warning while overspeed is active.

        Non-blocking: called from a Qt timer. Uses Windows system beep when
        available; otherwise falls back to QApplication.beep().
        """
        if not getattr(self, "_overspeed_active", False):
            return
        if _winsound is not None:
            try:
                _winsound.MessageBeep(getattr(_winsound, "MB_ICONHAND", -1))
            except Exception:
                try:
                    QApplication.beep()
                except Exception:
                    pass
        else:
            try:
                QApplication.beep()
            except Exception:
                pass

    def _act_toggle_info(self):
        in_pos = self._info_in_pos()
        out_pos = self._info_out_pos()

        # Toggle Info panel. Start SW move at the same time as Info (both show
        # and hide) so they animate concurrently using Info's animation
        # duration/easing.
        if self.info_panel.isVisible():
            # Hide Info -> Slide SW back IN at the same time
            if getattr(self, "_sw_enabled", False):
                try:
                    dur = int(self.info_panel._slide_out.duration())
                    easing = self.info_panel._slide_out.easingCurve()
                except Exception:
                    dur = None
                    easing = None
                self._sw_slide_to(self._sw_in_pos(), duration_ms=dur, easing=easing)

            self.info_panel.slide_out(out_pos)
        else:
            # Show Info -> Slide SW OUT at the same time
            if getattr(self, "_sw_enabled", False):
                try:
                    dur = int(self.info_panel._slide_in.duration())
                    easing = self.info_panel._slide_in.easingCurve()
                except Exception:
                    dur = None
                    easing = None
                self._sw_slide_to(self._sw_out_right_pos(), duration_ms=dur, easing=easing)

            self.info_panel.slide_in(out_pos, in_pos)

    def _act_toggle_perf(self):
        if not getattr(self, "_started", False):
            return

        # Mirror of Speed/Info but on the RIGHT side:
        # - PERF stays visible and slides LEFT
        # - RN slides in/out in the PERF slot (inside perf_area)
        p_in = self._perf_in_global_pos()
        p_out = self._perf_out_left_global_pos()
        rn_in = self._rn_in_pos()
        rn_out = self._rn_out_pos()

        try:
            self._perf_swap_anim.stop()
        except Exception:
            pass

        if getattr(self, "_rn_visible", False):
            # RN -> OUT (right), PERF -> back IN
            try:
                self.rn_panel.slide_out(rn_out)
            except Exception:
                try:
                    self.rn_panel.hide()
                except Exception:
                    pass
            self._rn_visible = False

            try:
                self._perf_swap_anim.setStartValue(self.perf_panel.pos())
                self._perf_swap_anim.setEndValue(p_in)
                self._perf_swap_anim.start()
            except Exception:
                try:
                    self.perf_panel.move(p_in)
                except Exception:
                    pass
        else:
            # RN -> IN (from right), PERF -> slide LEFT
            try:
                self.rn_panel.slide_in(rn_out, rn_in)
            except Exception:
                try:
                    self.rn_panel.move(rn_in)
                    self.rn_panel.show()
                except Exception:
                    pass
            self._rn_visible = True

            try:
                self._perf_swap_anim.setStartValue(self.perf_panel.pos())
                self._perf_swap_anim.setEndValue(p_out)
                self._perf_swap_anim.start()
            except Exception:
                try:
                    self.perf_panel.move(p_out)
                except Exception:
                    pass

    def _toggle_feat(self, name: str):
        if name not in self._feat:
            return

        if not getattr(self, "_started", False):
            return

        new_state = not self._feat[name]
        self._feat[name] = new_state

        if name == "ellipse" and new_state:
            if not self._feat.get("canny", False):
                self._feat["canny"] = True
        if name == "detect" and new_state:
            if not self._feat.get("canny", False):
                self._feat["canny"] = True
            if not self._feat.get("ellipse", False):
                self._feat["ellipse"] = True

        for k, v in self._feat.items():
            self.set_feature_state(k, v)

        if self.processor is not None:
            try:
                self.processor.enable_red = bool(self._feat.get("red", False))
                self.processor.enable_canny = bool(self._feat.get("canny", False))
                self.processor.enable_ellipse = bool(self._feat.get("ellipse", False))
                self.processor.read_sign_enabled = bool(self._feat.get("detect", False))
            except Exception as e:
                print("[GUI] Processor toggle failed:", e)

        if name == "ellipse" and not new_state:
            if self._feat.get("detect", False):
                self._feat["detect"] = False
                self.set_feature_state("detect", False)
                if self.processor is not None:
                    try:
                        self.processor.read_sign_enabled = False
                        self.processor.last_speed = None
                    except Exception:
                        pass

    # ======================================================
    # INFO PANEL -> runtime toggles
    # ======================================================
    def _on_save_changed(self, *_args):
        try:
            enabled = bool(self.info_panel.chk_save.isChecked())
        except Exception:
            enabled = False

        if self.ellipse_saver is not None:
            try:
                self.ellipse_saver.set_enabled(enabled)
            except Exception as e:
                print("[GUI] EllipseSaver toggle failed:", e)

    def _on_log_changed(self, *_args):
        try:
            enabled = bool(self.info_panel.chk_log.isChecked())
        except Exception:
            enabled = False

        if start_process_log is None or stop_process_log is None:
            return

        try:
            if enabled:
                start_process_log()
            else:
                stop_process_log()
        except Exception as e:
            print("[GUI] Process log toggle failed:", e)

    # ======================================================
    # LAYOUT
    # ======================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()
        self._update_pixmap()

    def _relayout(self):
        self.bg_label.setGeometry(0, 0, self.root.width(), self.root.height())
        self.overlay.setGeometry(0, 0, self.root.width(), self.root.height())
        self.hud.setGeometry(0, 0, self.root.width(), self.root.height())

        rx, ry, rw, rh = CAM_RECT_REL
        ox, oy, ow, oh = CAM_RECT_OFFSETS
        W = self.root.width()
        H = self.root.height()

        x = int(W * rx) + int(ox)
        y = int(H * ry) + int(oy)
        w = int((W * rw) * VIDEO_SCALE) + int(ow)

        # --- FIX: keep panel aspect ratio equal to CROPPED image ---
        # camera aspect ~ 16:9 (or whatever RealSense is set to)
        # after crop (keep top 3/5): new_aspect = cam_aspect / (3/5) = cam_aspect * 5/3
        cam_aspect = 16 / 9  # if you always run 1920x1080 / 1280x720 etc.
        cropped_aspect = cam_aspect / CROP_KEEP_RATIO  # = cam_aspect * (5/3)

        h = int(w / cropped_aspect) + int(oh)

        self.video_panel.setGeometry(x, y, w, h)

        self.info_area.setGeometry(self.INFO_AREA_X, self.INFO_AREA_Y, self.INFO_AREA_W, self.INFO_AREA_H)

        perf_x = self.width() - self.PERF_RIGHT_PAD - self.PERF_W
        perf_y = self.INFO_AREA_Y
        self.perf_area.setGeometry(perf_x, perf_y, self.PERF_W, self.PERF_H)

        # PERF panel is a ROOT-child (so it can slide left and stay visible).
        try:
            perf_running = (
                        hasattr(self, "_perf_swap_anim") and self._perf_swap_anim.state() == QAbstractAnimation.Running)
        except Exception:
            perf_running = False
        if hasattr(self,
                   "perf_panel") and self.perf_panel is not None and self.perf_panel.isVisible() and not perf_running:
            try:
                if getattr(self, "_rn_visible", False):
                    self.perf_panel.move(self._perf_out_left_global_pos())
                else:
                    self.perf_panel.move(self._perf_in_global_pos())
            except Exception:
                pass
        self.top_logo.adjustSize()
        x = (self.width() - self.top_logo.width()) // 2
        self.top_logo.move(x, int(self.LOGO_Y))

        LEGEND_H = 50
        LEGEND_Y = self.height() - 360
        LEGEND_XPAD = 110
        self.legend.setGeometry(
            LEGEND_XPAD,
            LEGEND_Y,
            max(10, self.width() - 2 * LEGEND_XPAD),
            LEGEND_H
        )

        res_x = 170
        res_y = self.height() - 395
        res_w = 220
        self.res_label.setGeometry(res_x, res_y, res_w, 36)

        # FPS box: same vertical level as resolution box, anchored left of PERF panel
        fps_w = 290
        fps_x = int(perf_x + 120 - fps_w)  # 20px gap from PERF area (matches red-box position)
        fps_y = res_y
        self.fps_label.setGeometry(fps_x, fps_y, fps_w, 36)

        try:
            info_running = (self.info_panel._slide_in.state() == QAbstractAnimation.Running) or (
                    self.info_panel._slide_out.state() == QAbstractAnimation.Running
            )
        except Exception:
            info_running = False

        if hasattr(self, "info_panel") and self.info_panel is not None:
            if self.info_panel.isVisible() and not info_running:
                self.info_panel.move(self._info_in_pos())
            elif not self.info_panel.isVisible() and not info_running:
                self.info_panel.move(self._info_out_pos())

        if hasattr(self, "sw_panel") and self.sw_panel is not None:
            # keep it anchored to the INFO slot
            self.sw_panel.move(self._sw_in_pos())
            if getattr(self, "_sw_enabled", False):
                if not self.sw_panel.isVisible():
                    self.sw_panel.show()
            else:
                if self.sw_panel.isVisible():
                    self.sw_panel.hide()

        if hasattr(self, "weather_panel") and self.weather_panel is not None:
            # place under SPEED panel
            if hasattr(self, "weather_panel") and self.weather_panel is not None:
                # absolute weather position (independent)
                self.weather_panel.move(self.WEATHER_X, self.WEATHER_Y)
            else:
                if self.weather_panel.isVisible():
                    self.weather_panel.hide()

    # ======================================================
    # CAMERA (RealSense) - starts only after pressing [S]
    # ======================================================
    def _parse_mode(self, text: str):
        t = (text or "").strip()
        if not t:
            return None
        try:
            left, right = [x.strip() for x in t.split("@", 1)]
            w_s, h_s = [x.strip() for x in left.lower().split("x", 1)]
            fps_s = "".join(ch for ch in right if ch.isdigit())
            return int(w_s), int(h_s), int(fps_s) if fps_s else 30
        except Exception:
            return None

    def _start_camera(self):
        if self.cam is not None:
            return

        mode_txt = None
        autoexp = True
        try:
            mode_txt = self.info_panel.cmb_res.currentText()
            autoexp = self.info_panel.chk_autoexp.isChecked()
        except Exception:
            pass

        mode = self._parse_mode(mode_txt) if mode_txt else None
        if mode is None:
            mode = (1920, 1080, 30)
        w, h, fps = mode

        try:
            self.cam = RealSenseCamera(width=w, height=h, fps=fps, auto_exposure=autoexp)
            self.cam.start()
            self.video_panel.show()
            self.video_panel.raise_()

            self.set_feature_state("cam", True)

            try:
                self.info_area.raise_()
            except Exception:
                pass
            try:
                self.perf_area.raise_()
            except Exception:
                pass
            try:
                self.hud.raise_()
            except Exception:
                pass
            try:
                self.perf_panel.raise_()
            except Exception:
                pass
            try:
                self.sw_panel.raise_()
            except Exception:
                pass

            self._frame_timer.start(0)
        except Exception as e:
            self.cam = None
            try:
                self.set_feature_state("cam", False)
            except Exception:
                pass
            self.video_panel.hide()
            QMessageBox.critical(self, "Camera error", f"RealSense start failed:\n{e}")

    def _stop_camera(self):
        try:
            if self._frame_timer.isActive():
                self._frame_timer.stop()
        except Exception:
            pass
        try:
            if self.cam is not None:
                self.cam.stop()
        except Exception:
            pass
        self.cam = None
        try:
            self.set_feature_state("cam", False)
        except Exception:
            pass
        try:
            self.video_panel.hide()
        except Exception:
            pass
        try:
            if hasattr(self, "fps_label") and self.fps_label is not None:
                self.fps_label.hide()
        except Exception:
            pass

        # --- Stop ELM327 CAN bus speed reader ---
        if self.elm327:
            self.elm327.stop()
            self.elm327 = None

    def _on_frame(self):
        if self.cam is None:
            return

        ok, frame_bgr = False, None
        try:
            ok, frame_bgr = self.cam.read()
            # --- CROP bottom 2/5 ---
            h, w = frame_bgr.shape[:2]
            crop_h = int(h * 3 / 5)  # keep top 3/5
            frame_bgr = frame_bgr[:crop_h, :]

        except Exception:
            ok, frame_bgr = False, None

        if not ok or frame_bgr is None:
            return

        t0 = time.perf_counter()
        out_bgr = frame_bgr

        if self.processor is not None:
            try:
                out_bgr = self.processor.process(frame_bgr)
            except Exception as e:
                print("[GUI] process() failed:", e)
                out_bgr = frame_bgr

        proc_ms = (time.perf_counter() - t0) * 1000.0

        try:
            self.perf_panel.set_process_ms(proc_ms)
        except Exception:
            pass

        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                self.perf_panel.set_cpu_percent(cpu)
            except Exception:
                pass

        if pynvml is not None and _nvml_ok:
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                self.perf_panel.set_vram_mb(mem.used / (1024.0 * 1024.0))
            except Exception:
                pass

        if getattr(self, "_sw_enabled", False) and hasattr(self, "sw_panel") and self.sw_panel is not None:
            try:
                sp = getattr(self.processor, "last_speed", None) if self.processor is not None else None

                # --- SIGN ICON must come from folder (e.g. 20 -> 20e.png) ---
                if sp is not None:
                    try:
                        self._sign_speed_limit = int(round(float(sp)))
                    except Exception:
                        self._sign_speed_limit = None
                    try:
                        self.sw_panel.set_sign(self._sign_speed_limit)
                    except Exception:
                        pass
                else:
                    self._sign_speed_limit = None
                    try:
                        self.sw_panel.set_sign(None)
                    except Exception:
                        pass

                # --- MAIN SPEED value = vehicle speed (from ELM327 CAN bus) ---
                self.sw_panel.set_speed(self._vehicle_speed)

                # --- Overspeed pulse when vehicle_speed > detected sign limit ---
                if self._sign_speed_limit is not None and self._vehicle_speed > self._sign_speed_limit:
                    self._set_overspeed(True)
                else:
                    self._set_overspeed(False)

                # (kept for compatibility; WeatherPanel is separate)
                wkey = getattr(self.processor, "last_weather", None) if self.processor is not None else None
                if wkey is not None:
                    try:
                        self.sw_panel.set_weather(str(wkey))
                    except Exception:
                        pass
            except Exception:
                pass

        # ==============================
        # WEATHER PANEL UPDATE (FIX)
        # - WeatherPanel was shown on START, but its icon was never updated per-frame.
        # - ImageProcessor updates: self.last_weather (see image_processing.py)
        # ==============================
        if getattr(self, "_weather_enabled", False) and hasattr(self, "weather_panel") and self.weather_panel is not None:
            try:
                wkey = getattr(self.processor, "last_weather", None) if self.processor is not None else None
                if wkey is not None:
                    wkey_s = str(wkey)
                    if wkey_s != getattr(self, "_weather_ui_key", None):
                        self._weather_ui_key = wkey_s
                        self.weather_panel.set_weather(wkey_s)
            except Exception:
                pass

        now = time.perf_counter()
        if self._last_frame_ts is None:
            self._last_frame_ts = now
            self._fps_last_report_ts = now
            self._fps_counter = 0
        else:
            self._fps_counter += 1
            if self._fps_last_report_ts is not None and (now - self._fps_last_report_ts) >= 0.5:
                dt = now - self._fps_last_report_ts
                real_fps = self._fps_counter / dt if dt > 1e-6 else 0.0
                self._fps_real_text = f"{real_fps:.1f}"
                self._fps_counter = 0
                self._fps_last_report_ts = now
                self._update_fps_label()

        # --- Display without distortion (KEEP aspect ratio) ---
        try:
            rgb = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
            pm = QPixmap.fromImage(qimg)

            pm_scaled = pm.scaled(
                self.video_panel.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.video_panel.setPixmap(pm_scaled)

        except Exception:
            return

    def _set_image(self, img_path: str):
        pm = QPixmap(img_path)
        if pm.isNull():
            QMessageBox.warning(self, "Image error", f"Image not found:\n{img_path}")
            return
        self._pix = pm
        self._update_pixmap()

    def _update_pixmap(self):
        if self._pix.isNull():
            return
        scaled = self._pix.scaled(
            self.bg_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.bg_label.setPixmap(scaled)

    def set_feature_state(self, name: str, enabled: bool):
        name = (name or "").strip().lower()
        idx = {"cam": 0, "red": 1, "canny": 2, "ellipse": 3, "detect": 4}.get(name, None)
        if idx is None:
            return
        self.legend.set_state(idx, enabled)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self._stop_camera()
        except Exception:
            pass
        # make sure ELM327 is stopped
        try:
            if self.elm327:
                self.elm327.stop()
                self.elm327 = None
        except Exception:
            pass
        # make sure continuous warning sound is stopped
        try:
            self._stop_overspeed_sound()
        except Exception:
            pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = BackgroundWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
