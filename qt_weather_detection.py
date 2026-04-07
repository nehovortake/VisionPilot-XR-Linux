# weather_detection.py
import cv2
import numpy as np
from typing import Tuple

# === WEATHER SAMPLING CONFIG ===
WEATHER_EVERY_N_FRAMES = 10   # ako často robiť ťažšie výpočty (štandardne každých 10 frame)

# ===== Runtime state =====
_frame_counter = 0
_last_weather = 'normal'

# EMA (exponential moving average) pre stabilnejšie rozhodovanie
_ema_b = None   # brightness
_ema_s = None   # saturation
_ema_std = None # brightness std

# Hysteréza: zmeň stav až keď nový kandidát vydrží N vzoriek
_cand_weather = None
_cand_votes = 0
_VOTES_TO_SWITCH = 3


def reset_weather_state():
    """Volaj keď reštartuješ stream (nie je povinné)."""
    global _frame_counter, _last_weather, _ema_b, _ema_s, _ema_std, _cand_weather, _cand_votes
    _frame_counter = 0
    _last_weather = 'normal'
    _ema_b = None
    _ema_s = None
    _ema_std = None
    _cand_weather = None
    _cand_votes = 0


def _quick_stats(bgr):
    # type: (np.ndarray) -> Tuple[float, float, float]
    """Rýchle štatistiky z obrazu (downscale + horná časť)."""
    h, w = bgr.shape[:2]

    # Downscale kvôli výkonu a stabilite (detekcia zmeny svetla)
    if w > 220:
        scale = 160.0 / float(w)
        nh = max(24, int(h * scale))
        small = cv2.resize(bgr, (160, nh), interpolation=cv2.INTER_AREA)
    else:
        small = bgr

    # Zober horných ~45% (väčšinou obloha / svetlo) – reaguje lepšie ako celý frame
    hh = small.shape[0]
    y2 = max(8, int(hh * 0.45))
    roi = small[:y2, :, :]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    b_mean = float(np.mean(gray))
    b_std = float(np.std(gray))

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    s_mean = float(np.mean(hsv[:, :, 1]))
    return b_mean, b_std, s_mean


def detect_conditions(bgr: np.ndarray) -> str:
    """Detekcia "počasie / svetlo" z kamery (heuristika pre GUI)."""
    global _ema_b, _ema_s, _ema_std

    b, std, s = _quick_stats(bgr)

    # EMA – tlmí šum a zabráni "blikanie" medzi stavmi
    alpha = 0.20  # 0.1-0.3 je OK
    if _ema_b is None:
        _ema_b, _ema_std, _ema_s = b, std, s
    else:
        _ema_b = (1 - alpha) * _ema_b + alpha * b
        _ema_std = (1 - alpha) * _ema_std + alpha * std
        _ema_s = (1 - alpha) * _ema_s + alpha * s

    b = _ema_b
    std = _ema_std
    s = _ema_s

    # ===== Tuning prahov (RealSense D415 v aute/interiéri) =====
    if b < 55:
        return 'night'
    if s < 45 and std < 18:
        return 'fog'
    if b > 170 and s > 60 and std > 30:
        return 'sunny'
    if std < 22:
        return 'overcast'
    return 'normal'


def get_weather(bgr, mode='auto'):
    """
    Weather detection with frame throttling.
    """
    global _frame_counter, _last_weather, _cand_weather, _cand_votes

    if mode != 'auto':
        return mode

    if _frame_counter % WEATHER_EVERY_N_FRAMES == 0:
        cand = detect_conditions(bgr)

        # hysteréza: switchni až keď sa nový stav zopakuje párkrát
        if cand == _last_weather:
            _cand_weather = None
            _cand_votes = 0
        else:
            if _cand_weather != cand:
                _cand_weather = cand
                _cand_votes = 1
            else:
                _cand_votes += 1

            if _cand_votes >= _VOTES_TO_SWITCH:
                _last_weather = cand
                _cand_weather = None
                _cand_votes = 0

    _frame_counter += 1
    return _last_weather