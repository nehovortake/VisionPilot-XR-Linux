#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
song.py - FIXED (Despacito melody + proper GPIO init)

- Uses BOARD pin 33
- Fixes GPIO setup error
- Plays a recognizable Despacito-style melody (simplified)
"""

import time

try:
    import Jetson.GPIO as GPIO
except Exception as e:
    print(f"[SONG] Jetson.GPIO import failed: {e}")
    raise


BUZZER_PIN = 33


# Frequencies (Hz)
NOTES = {
    "REST": 0,
    "C4": 261,
    "D4": 294,
    "E4": 330,
    "F4": 349,
    "G4": 392,
    "A4": 440,
    "B4": 494,
    "C5": 523,
    "D5": 587,
    "E5": 659,
}


def gpio_init():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)


def play_tone(pwm, freq, duration):
    if freq == 0:
        pwm.ChangeDutyCycle(0)
        time.sleep(duration)
        return

    pwm.ChangeFrequency(freq)
    pwm.ChangeDutyCycle(50)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)
    time.sleep(0.03)


def play_despacito():
    # Simplified Despacito melody
    melody = [
        ("B4", 0.2), ("A4", 0.2), ("G4", 0.2), ("A4", 0.2),
        ("B4", 0.2), ("B4", 0.2), ("B4", 0.4),

        ("A4", 0.2), ("A4", 0.2), ("A4", 0.4),

        ("B4", 0.2), ("D5", 0.2), ("D5", 0.4),

        ("B4", 0.2), ("A4", 0.2), ("G4", 0.2), ("A4", 0.2),
        ("B4", 0.2), ("B4", 0.2), ("B4", 0.4),

        ("A4", 0.2), ("A4", 0.2), ("B4", 0.2), ("A4", 0.2),
        ("G4", 0.6),

        ("REST", 0.3),
    ]

    pwm = GPIO.PWM(BUZZER_PIN, 440)
    pwm.start(0)

    try:
        for note, dur in melody:
            freq = NOTES[note]
            play_tone(pwm, freq, dur)
    finally:
        pwm.stop()


def main():
    print("[SONG] Despacito test 🎵")
    print("[SONG] Using BOARD pin 33")

    gpio_init()

    try:
        play_despacito()
    except KeyboardInterrupt:
        print("\n[SONG] Stopped")
    finally:
        try:
            GPIO.output(BUZZER_PIN, GPIO.LOW)
        except:
            pass
        GPIO.cleanup()
        print("[SONG] Done")


if __name__ == "__main__":
    main()
