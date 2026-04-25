#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
song.py

ACTIVE buzzer version for Jetson Orin Nano.
Uses the same BOARD pin 33 as the main code.

IMPORTANT:
- This version is for the same buzzer behavior as your main code (ON/OFF).
- An active buzzer cannot play real musical notes with PWM melody the same way a passive buzzer can.
- So this script plays a "Despacito-style" rhythm / beep pattern using the same transistor + buzzer wiring.
"""

import time

try:
    import Jetson.GPIO as GPIO
except Exception as e:
    print(f"[SONG] Jetson.GPIO import failed: {e}")
    raise


BUZZER_PIN = 33  # same BOARD pin as in main code


def gpio_init():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)


def buzzer_on():
    GPIO.output(BUZZER_PIN, GPIO.HIGH)


def buzzer_off():
    GPIO.output(BUZZER_PIN, GPIO.LOW)


def beep(on_s: float, off_s: float = 0.05):
    buzzer_on()
    time.sleep(on_s)
    buzzer_off()
    time.sleep(off_s)


def play_despacito_rhythm():
    """
    Despacito-inspired rhythm for ACTIVE buzzer.
    This is not a true melody, because active buzzer only supports ON/OFF beeps well.
    """
    pattern = [
        (0.10, 0.05), (0.10, 0.05), (0.18, 0.08),
        (0.10, 0.05), (0.10, 0.05), (0.22, 0.10),

        (0.10, 0.05), (0.10, 0.05), (0.18, 0.08),
        (0.10, 0.05), (0.10, 0.05), (0.28, 0.12),

        (0.08, 0.04), (0.08, 0.04), (0.08, 0.04), (0.18, 0.08),
        (0.08, 0.04), (0.08, 0.04), (0.28, 0.12),

        (0.12, 0.05), (0.12, 0.05), (0.12, 0.05),
        (0.20, 0.10), (0.30, 0.18),

        (0.10, 0.05), (0.10, 0.05), (0.18, 0.08),
        (0.10, 0.05), (0.10, 0.05), (0.22, 0.10),

        (0.10, 0.05), (0.10, 0.05), (0.18, 0.08),
        (0.10, 0.05), (0.10, 0.05), (0.35, 0.20),
    ]

    for on_s, off_s in pattern:
        beep(on_s, off_s)


def main():
    print("[SONG] Active buzzer test - Despacito rhythm")
    print(f"[SONG] Using BOARD pin {BUZZER_PIN}")
    print("[SONG] This version is for the same ON/OFF buzzer behavior as your main code.")

    gpio_init()

    try:
        play_despacito_rhythm()
    except KeyboardInterrupt:
        print("\n[SONG] Stopped by user")
    finally:
        try:
            buzzer_off()
        except Exception:
            pass
        GPIO.cleanup()
        print("[SONG] Done")


if __name__ == "__main__":
    main()
