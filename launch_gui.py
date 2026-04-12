#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple GUI launcher with logging
"""

import subprocess
import sys
import time

print("Starting GUI.py...")
print("=" * 60)

# Run gui.py and keep it running
proc = subprocess.Popen(
    [sys.executable, "gui.py"],
    cwd="C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

print("GUI Process started with PID:", proc.pid)
print("Showing output for 20 seconds...")
print("-" * 60)

start = time.time()
try:
    while time.time() - start < 20:
        try:
            line = proc.stdout.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.1)
        except:
            break
except KeyboardInterrupt:
    print("\nInterrupted by user")

print("-" * 60)
print("Terminating GUI...")
proc.terminate()

try:
    proc.wait(timeout=2)
except:
    proc.kill()

print("GUI closed")

