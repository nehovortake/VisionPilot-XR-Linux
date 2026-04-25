#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import platform
import traceback
import tkinter as tk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk

# =========================
# BUZZER (Jetson GPIO - INLINE)
# =========================
BUZZER_AVAILABLE = False

try:
    import Jetson.GPIO as GPIO

    BUZZER_PIN = 33
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

    BUZZER_AVAILABLE = True
    print("[INIT] BUZZER (GPIO): OK")

except Exception as e:
    print(f"[INIT] BUZZER FAILED: {e}")
    BUZZER_AVAILABLE = False


class State:
    def __init__(self):
        self.vehicle_speed = 0
        self.detected_sign = None
        self.overspeed_active = False
        self.buzzer_enabled = True


state = State()


def set_buzzer(active: bool):
    if not state.buzzer_enabled or not BUZZER_AVAILABLE:
        return

    try:
        if active:
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
        else:
            GPIO.output(BUZZER_PIN, GPIO.LOW)
    except Exception as e:
        print(f"[BUZZER] GPIO error: {e}")


def update_overspeed():
    if state.detected_sign is None:
        set_buzzer(False)
        return

    if state.vehicle_speed > state.detected_sign:
        state.overspeed_active = True
        set_buzzer(True)
    else:
        state.overspeed_active = False
        set_buzzer(False)


def simulate():
    print("Simulácia rýchlosti... Ctrl+C na ukončenie")

    try:
        while True:
            for speed in range(0, 131, 5):
                state.vehicle_speed = speed

                # simulovaná značka
                if speed > 60:
                    state.detected_sign = 50
                else:
                    state.detected_sign = None

                update_overspeed()

                print(f"\rSpeed: {speed} | Sign: {state.detected_sign} | Alarm: {state.overspeed_active}", end="")
                time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        try:
            GPIO.cleanup()
        except:
            pass


if __name__ == "__main__":
    simulate()
