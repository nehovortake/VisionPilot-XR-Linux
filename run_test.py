#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test main.py by running it with output redirect"""

import subprocess
import sys
import time

# Run main.py and capture output
print("Starting main.py test...")
print("=" * 60)

try:
    # Run main.py for 10 seconds
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd="C:\\Users\\Minko\\Desktop\\DP\\VisionPilot-XR Linux"
    )

    # Read output for 10 seconds
    start = time.time()
    output_lines = []

    while time.time() - start < 10:
        try:
            line = proc.stdout.readline()
            if line:
                output_lines.append(line.strip())
                print(line.strip())
        except:
            break

    # Stop process
    proc.terminate()
    proc.wait(timeout=2)

    print("\n" + "=" * 60)
    print(f"Captured {len(output_lines)} lines of output")

    # Save to file
    with open("test_main_output.txt", "w") as f:
        f.write("\n".join(output_lines))

    print("Output saved to test_main_output.txt")

except Exception as e:
    print(f"Error: {e}")

